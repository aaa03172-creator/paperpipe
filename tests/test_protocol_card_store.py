from __future__ import annotations

from datetime import datetime, timezone

import pytest

import src.protocol_cards.store as protocol_card_store
from src.protocol_cards.store import (
    list_protocol_card_ids,
    load_protocol_card,
    load_protocol_card_markdown,
    load_protocol_version,
    load_protocol_versions,
    protocol_card_json_path,
    protocol_card_markdown_path,
    protocol_card_version_json_path,
    save_protocol_card_bundle,
)
from src.schemas.protocol_card import ProtocolCard, ProtocolVersion, build_protocol_version_summary


def _sample_protocol_version(
    *,
    version_id: str = "protver_alpha_v1",
    version_number: int = 1,
    status: str = "active",
) -> ProtocolVersion:
    return ProtocolVersion(
        version_id=version_id,
        protocol_id="protocol_alpha",
        version_number=version_number,
        key_steps_summary=["Seed cells", "Add treatment"],
        materials=["DMEM", "FBS"],
        equipment=["incubator"],
        critical_conditions=["37 C", "5% CO2"],
        readouts=["Cell viability"],
        cautions=["Do not overconfluence"],
        content_snapshot=f"Protocol snapshot {version_number}",
        change_reason="Initial draft" if version_number == 1 else "Update",
        status=status,
        created_by="operator",
        created_at=datetime(2026, 3, 23, 1, version_number, tzinfo=timezone.utc),
        source_refs=[{"paper_slug": "paper-alpha", "claim_id": f"claim-{version_number:03d}"}],
    )


def _sample_protocol_card(*versions: ProtocolVersion, title: str = "Alpha assay protocol") -> ProtocolCard:
    return ProtocolCard(
        protocol_id="protocol_alpha",
        title=title,
        purpose="Evaluate treatment response",
        context="In vitro assay",
        source_kind="paper_derived",
        linked_paper_ids=["paper-001", "paper-002"],
        linked_note_slugs=["alpha-note"],
        current_version_id=versions[-1].version_id if versions else None,
        validation_status="reviewed",
        created_at=datetime(2026, 3, 23, 1, 0, tzinfo=timezone.utc),
        updated_at=datetime(2026, 3, 23, 2, 0, tzinfo=timezone.utc),
        version_summaries=[build_protocol_version_summary(version) for version in versions],
    )


def test_protocol_card_store_roundtrip_creates_expected_layout(tmp_path) -> None:
    root = tmp_path / "protocol_cards"
    version_1 = _sample_protocol_version()
    version_2 = _sample_protocol_version(version_id="protver_alpha_v2", version_number=2)
    card = _sample_protocol_card(version_1, version_2)
    markdown = "# Protocol Card\n"

    result = save_protocol_card_bundle(card, markdown, versions=[version_1, version_2], root=root)
    loaded_card = load_protocol_card(card.protocol_id, root)
    loaded_markdown = load_protocol_card_markdown(card.protocol_id, root)
    loaded_version = load_protocol_version(card.protocol_id, "protver_alpha_v2", root)
    loaded_versions = load_protocol_versions(card.protocol_id, root)

    assert result["json"] == protocol_card_json_path(card.protocol_id, root)
    assert result["markdown"] == protocol_card_markdown_path(card.protocol_id, root)
    assert result["version:protver_alpha_v1"] == protocol_card_version_json_path(card.protocol_id, "protver_alpha_v1", root)
    assert loaded_card.current_version_id == "protver_alpha_v2"
    assert loaded_markdown == markdown
    assert loaded_version.version_number == 2
    assert [version.version_id for version in loaded_versions] == ["protver_alpha_v1", "protver_alpha_v2"]
    assert list_protocol_card_ids(root) == [card.protocol_id]


def test_protocol_card_store_rejects_path_like_ids(tmp_path) -> None:
    root = tmp_path / "protocol_cards"

    with pytest.raises(ValueError, match="protocol_id"):
        protocol_card_json_path("../escape", root)

    with pytest.raises(ValueError, match="version_id"):
        protocol_card_version_json_path("protocol_alpha", "../escape", root)


def test_protocol_card_store_rejects_missing_version_payloads(tmp_path) -> None:
    root = tmp_path / "protocol_cards"
    version_1 = _sample_protocol_version()
    version_2 = _sample_protocol_version(version_id="protver_alpha_v2", version_number=2)
    card = _sample_protocol_card(version_1, version_2)

    with pytest.raises(ValueError, match="Missing version payload"):
        save_protocol_card_bundle(card, "# Protocol Card\n", versions=[version_1], root=root)


def test_protocol_card_store_removes_stale_version_files_on_overwrite(tmp_path) -> None:
    root = tmp_path / "protocol_cards"
    version_1 = _sample_protocol_version()
    version_2 = _sample_protocol_version(version_id="protver_alpha_v2", version_number=2)
    card = _sample_protocol_card(version_1, version_2)
    save_protocol_card_bundle(card, "# First\n", versions=[version_1, version_2], root=root)

    updated_card = _sample_protocol_card(version_1, title="Alpha assay protocol updated")
    save_protocol_card_bundle(updated_card, "# Updated\n", versions=[version_1], root=root)

    loaded_card = load_protocol_card(updated_card.protocol_id, root)
    assert loaded_card.title == "Alpha assay protocol updated"
    assert loaded_card.current_version_id == "protver_alpha_v1"
    assert not protocol_card_version_json_path(updated_card.protocol_id, "protver_alpha_v2", root).exists()


def test_protocol_card_store_rolls_back_if_version_write_fails(tmp_path, monkeypatch) -> None:
    root = tmp_path / "protocol_cards"
    original_version = _sample_protocol_version()
    original_card = _sample_protocol_card(original_version, title="Original title")
    save_protocol_card_bundle(original_card, "# Original\n", versions=[original_version], root=root)
    notes_path = protocol_card_json_path(original_card.protocol_id, root).parent / "operator_notes.txt"
    notes_path.write_text("keep operator note\n", encoding="utf-8")
    versions_note_path = protocol_card_version_json_path(original_card.protocol_id, original_version.version_id, root).parent / "README.txt"
    versions_note_path.write_text("keep version note\n", encoding="utf-8")

    updated_version = _sample_protocol_version(version_id="protver_alpha_v2", version_number=2)
    updated_card = _sample_protocol_card(original_version, updated_version, title="Updated title")
    original_atomic_write_text = protocol_card_store._atomic_write_text
    call_count = {"value": 0}

    def fail_on_fourth_write(path, content):
        call_count["value"] += 1
        if call_count["value"] == 4:
            raise IOError("boom")
        return original_atomic_write_text(path, content)

    monkeypatch.setattr(protocol_card_store, "_atomic_write_text", fail_on_fourth_write)

    with pytest.raises(OSError):
        save_protocol_card_bundle(
            updated_card,
            "# Updated\n",
            versions=[original_version, updated_version],
            root=root,
        )

    loaded_card = load_protocol_card(original_card.protocol_id, root)
    loaded_markdown = load_protocol_card_markdown(original_card.protocol_id, root)
    loaded_versions = load_protocol_versions(original_card.protocol_id, root)
    assert loaded_card.title == "Original title"
    assert loaded_markdown == "# Original\n"
    assert [version.version_id for version in loaded_versions] == ["protver_alpha_v1"]
    assert notes_path.read_text(encoding="utf-8") == "keep operator note\n"
    assert versions_note_path.read_text(encoding="utf-8") == "keep version note\n"
    assert not protocol_card_version_json_path(original_card.protocol_id, "protver_alpha_v2", root).exists()
