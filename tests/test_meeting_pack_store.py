from __future__ import annotations

from datetime import datetime, timezone
import json
import pytest

import src.meeting_packs.store as meeting_pack_store
from src.meeting_packs.store import (
    list_meeting_pack_ids,
    load_meeting_pack,
    load_meeting_pack_markdown,
    meeting_pack_json_path,
    meeting_pack_markdown_path,
    save_meeting_pack_bundle,
)
from src.schemas.meeting_pack import (
    MeetingPack,
    MeetingPackEvidenceRef,
    MeetingPackGenerateRequest,
    MeetingPackOnePageSummary,
    MeetingPackSourceItem,
    MeetingPackSourceSelector,
)


def _sample_pack(title: str = "Meeting draft") -> MeetingPack:
    return MeetingPack(
        id="meetingpack_20260313T090000Z_journal_club_a1b2c3d4",
        mode="journal_club",
        title=title,
        created_at=datetime(2026, 3, 13, 9, 0, tzinfo=timezone.utc),
        generation_request=MeetingPackGenerateRequest(
            mode="journal_club",
            title=title,
            source_items=[
                MeetingPackSourceSelector(
                    type="paper_slug",
                    ref="wenzelShortchainFattyAcids2020",
                )
            ],
            max_slides=6,
        ),
        source_items=[
            MeetingPackSourceItem(
                id="src_01",
                type="paper_slug",
                ref="wenzelShortchainFattyAcids2020",
                title="wenzelShortchainFattyAcids2020",
                priority=1,
                included=True,
            )
        ],
        one_page_summary=MeetingPackOnePageSummary(overview="Summary"),
        evidence_refs=[
            MeetingPackEvidenceRef(
                id="evref_01",
                paper_slug="wenzelShortchainFattyAcids2020",
                support_type="direct",
            )
        ],
    )


def test_meeting_pack_store_roundtrip_creates_expected_layout(tmp_path):
    root = tmp_path / "meeting_packs"
    pack = _sample_pack()
    markdown = "# Draft\n\n- item"

    json_path, md_path = save_meeting_pack_bundle(pack, markdown, root)
    loaded = load_meeting_pack(pack.id, root)
    loaded_markdown = load_meeting_pack_markdown(pack.id, root)

    assert json_path == meeting_pack_json_path(pack.id, root)
    assert md_path == meeting_pack_markdown_path(pack.id, root)
    assert loaded.id == pack.id
    assert loaded.title == pack.title
    assert loaded.output_mode_family == "lab_meeting"
    assert loaded.generation_request is not None
    assert loaded.generation_request.max_slides == 6
    assert loaded_markdown == markdown
    assert list_meeting_pack_ids(root) == [pack.id]


def test_meeting_pack_store_overwrites_same_pack_id_without_duplicate_dump(tmp_path):
    root = tmp_path / "meeting_packs"
    pack = _sample_pack(title="First title")
    save_meeting_pack_bundle(pack, "# First", root)

    updated = _sample_pack(title="Updated title")
    save_meeting_pack_bundle(updated, "# Updated", root)

    loaded = load_meeting_pack(updated.id, root)
    loaded_markdown = load_meeting_pack_markdown(updated.id, root)

    assert loaded.title == "Updated title"
    assert loaded_markdown == "# Updated"
    assert len(list((root / updated.id).iterdir())) == 2


def test_meeting_pack_store_rolls_back_bundle_if_markdown_write_fails(tmp_path, monkeypatch):
    root = tmp_path / "meeting_packs"
    original = _sample_pack(title="First title")
    save_meeting_pack_bundle(original, "# First", root)

    updated = _sample_pack(title="Updated title")
    original_atomic_write_text = meeting_pack_store._atomic_write_text
    call_count = {"value": 0}

    def fail_on_second_write(path, content):
        call_count["value"] += 1
        if call_count["value"] == 2:
            raise IOError("boom")
        return original_atomic_write_text(path, content)

    monkeypatch.setattr(meeting_pack_store, "_atomic_write_text", fail_on_second_write)

    with pytest.raises(OSError):
        save_meeting_pack_bundle(updated, "# Updated", root)

    loaded = load_meeting_pack(updated.id, root)
    loaded_markdown = load_meeting_pack_markdown(updated.id, root)
    assert loaded.title == "First title"
    assert loaded_markdown == "# First"
    assert len(list((root / updated.id).iterdir())) == 2


def test_meeting_pack_store_does_not_leave_partial_new_bundle_if_markdown_write_fails(tmp_path, monkeypatch):
    root = tmp_path / "meeting_packs"
    pack = _sample_pack(title="First title")
    original_atomic_write_text = meeting_pack_store._atomic_write_text
    call_count = {"value": 0}

    def fail_on_second_write(path, content):
        call_count["value"] += 1
        if call_count["value"] == 2:
            raise IOError("boom")
        return original_atomic_write_text(path, content)

    monkeypatch.setattr(meeting_pack_store, "_atomic_write_text", fail_on_second_write)

    with pytest.raises(OSError):
        save_meeting_pack_bundle(pack, "# First", root)

    assert list_meeting_pack_ids(root) == []


def test_meeting_pack_store_backfills_output_mode_family_for_legacy_json(tmp_path):
    root = tmp_path / "meeting_packs"
    pack = _sample_pack()
    json_path = meeting_pack_json_path(pack.id, root)
    md_path = meeting_pack_markdown_path(pack.id, root)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    payload = pack.model_dump(mode="json")
    payload.pop("output_mode_family", None)
    json_path.write_text(json.dumps(payload), encoding="utf-8")
    md_path.write_text("# Draft", encoding="utf-8")

    loaded = load_meeting_pack(pack.id, root)

    assert loaded.output_mode_family == "lab_meeting"
