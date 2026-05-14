from __future__ import annotations

from datetime import datetime, timezone
import json

import pytest

import src.talk_packs.store as talk_pack_store
from src.schemas.talk_pack import (
    TalkPack,
    TalkPackGenerateRequest,
    TalkPackOutputMember,
    TalkPackReviewArtifact,
    TalkPackUpstreamOwnerRef,
)
from src.talk_packs.store import (
    list_talk_pack_ids,
    load_talk_pack,
    load_talk_pack_artifact_bytes,
    load_talk_pack_artifact_json,
    load_talk_pack_artifact_text,
    save_talk_pack_artifact_json,
    save_talk_pack_artifact_bytes,
    save_talk_pack_artifact_text,
    save_talk_pack_bundle,
    talk_pack_artifact_path,
    talk_pack_json_path,
)


def _sample_pack(
    title: str = "SCFA journal club talk",
    *,
    output_statuses: dict[str, str] | None = None,
    review_artifacts: list[TalkPackReviewArtifact] | None = None,
) -> TalkPack:
    output_statuses = dict(output_statuses or {})
    request = TalkPackGenerateRequest(
        paper_slug="wenzelShortchainFattyAcids2020",
        title=title,
        talk_mode="journal_club",
        audience_profile="mixed_research_group",
        duration_minutes=12,
        selected_exports=["deck_pptx", "speaker_script"],
        auto_include_dependencies=True,
    )
    return TalkPack(
        talk_pack_id="talkpack_20260421T010203Z_journal_club_a1b2c3d4",
        paper_slug="wenzelShortchainFattyAcids2020",
        title=title,
        created_at=datetime(2026, 4, 21, 1, 2, 3, tzinfo=timezone.utc),
        updated_at=datetime(2026, 4, 21, 1, 2, 3, tzinfo=timezone.utc),
        talk_mode="journal_club",
        audience_profile="mixed_research_group",
        duration_minutes=12,
        generation_request=request,
        upstream_owners=[
            TalkPackUpstreamOwnerRef(
                owner_kind="paper_state",
                ref="vault/.pp/wenzelShortchainFattyAcids2020/state.json",
                role="canonical",
            )
        ],
        selected_outputs=["deck_pptx", "speaker_script"],
        required_outputs=["slide_manifest", "key_numbers", "deck_pptx", "speaker_script"],
        output_members=[
            TalkPackOutputMember(
                kind="slide_manifest",
                path="slide_manifest.json",
                required=True,
                status=output_statuses.get("slide_manifest", "generated"),
            ),
            TalkPackOutputMember(
                kind="key_numbers",
                path="key_numbers.md",
                required=True,
                status=output_statuses.get("key_numbers", "generated"),
            ),
            TalkPackOutputMember(
                kind="deck_pptx",
                path="exports/deck.pptx",
                required=True,
                status=output_statuses.get("deck_pptx", "generated"),
            ),
            TalkPackOutputMember(
                kind="speaker_script",
                path="exports/speaker_script.md",
                required=True,
                status=output_statuses.get("speaker_script", "generated"),
            ),
        ],
        review_artifacts=review_artifacts or [
            TalkPackReviewArtifact(kind="presentation_review", path="review/presentation_review.json"),
            TalkPackReviewArtifact(kind="style_lint", path="review/style_lint.json"),
        ],
    )


def _sample_bundle_payloads() -> tuple[dict[str, str], dict[str, dict[str, object]], dict[str, bytes]]:
    return (
        {
            "slide_manifest.json": '{"slides":[]}\n',
            "key_numbers.md": "# Key Numbers\n",
            "exports/speaker_script.md": "# Script\n",
        },
        {
            "review/presentation_review.json": {"overall_status": "pass"},
            "review/style_lint.json": {"overall_status": "warn"},
        },
        {
            "exports/deck.pptx": b"PPTX placeholder bytes",
        },
    )


def test_talk_pack_store_roundtrip_creates_expected_layout(tmp_path) -> None:
    root = tmp_path / "talk_packs"
    pack = _sample_pack()
    text_artifacts, json_artifacts, binary_artifacts = _sample_bundle_payloads()

    result = save_talk_pack_bundle(
        pack,
        text_artifacts=text_artifacts,
        json_artifacts=json_artifacts,
        binary_artifacts=binary_artifacts,
        root=root,
    )

    loaded = load_talk_pack(pack.talk_pack_id, root)
    loaded_slide_manifest = load_talk_pack_artifact_text(pack.talk_pack_id, "slide_manifest.json", root)
    loaded_review = load_talk_pack_artifact_json(pack.talk_pack_id, "review/presentation_review.json", root)
    loaded_deck = load_talk_pack_artifact_bytes(pack.talk_pack_id, "exports/deck.pptx", root)

    assert result["json"] == talk_pack_json_path(pack.talk_pack_id, root)
    assert result["text:slide_manifest.json"] == talk_pack_artifact_path(
        pack.talk_pack_id,
        "slide_manifest.json",
        root,
    )
    assert result["json:review/presentation_review.json"] == talk_pack_artifact_path(
        pack.talk_pack_id,
        "review/presentation_review.json",
        root,
    )
    assert loaded.talk_pack_id == pack.talk_pack_id
    assert loaded.title == pack.title
    assert loaded_slide_manifest == '{"slides":[]}\n'
    assert loaded_review == {"overall_status": "pass"}
    assert loaded_deck == b"PPTX placeholder bytes"
    assert list_talk_pack_ids(root) == [pack.talk_pack_id]


def test_talk_pack_store_rejects_path_like_ids(tmp_path) -> None:
    root = tmp_path / "talk_packs"

    with pytest.raises(ValueError, match="talk_pack_id"):
        talk_pack_json_path("../escape", root)

    with pytest.raises(ValueError, match="talk_pack_id"):
        talk_pack_artifact_path("talkpack_nested/escape", "slide_manifest.json", root)


def test_talk_pack_store_overwrites_same_id_without_duplicate_dump(tmp_path) -> None:
    root = tmp_path / "talk_packs"
    original = _sample_pack(title="First title")
    original_text, original_json, original_binary = _sample_bundle_payloads()
    save_talk_pack_bundle(
        original,
        text_artifacts={**original_text, "key_numbers.md": "# First\n"},
        json_artifacts=original_json,
        binary_artifacts=original_binary,
        root=root,
    )

    updated = _sample_pack(title="Updated title")
    updated_text, updated_json, updated_binary = _sample_bundle_payloads()
    save_talk_pack_bundle(
        updated,
        text_artifacts={**updated_text, "key_numbers.md": "# Updated\n"},
        json_artifacts=updated_json,
        binary_artifacts=updated_binary,
        root=root,
    )

    loaded = load_talk_pack(updated.talk_pack_id, root)
    loaded_key_numbers = load_talk_pack_artifact_text(updated.talk_pack_id, "key_numbers.md", root)

    assert loaded.title == "Updated title"
    assert loaded_key_numbers == "# Updated\n"


def test_talk_pack_store_rolls_back_bundle_if_text_write_fails(tmp_path, monkeypatch) -> None:
    root = tmp_path / "talk_packs"
    original = _sample_pack(title="First title")
    original_text, original_json, original_binary = _sample_bundle_payloads()
    save_talk_pack_bundle(
        original,
        text_artifacts={**original_text, "key_numbers.md": "# First\n"},
        json_artifacts=original_json,
        binary_artifacts=original_binary,
        root=root,
    )
    pack_dir = talk_pack_json_path(original.talk_pack_id, root).parent
    note_path = pack_dir / "operator_notes.txt"
    note_path.write_text("keep operator note\n", encoding="utf-8")
    exports_note_path = talk_pack_artifact_path(original.talk_pack_id, "exports/README.txt", root)
    exports_note_path.write_text("keep exports note\n", encoding="utf-8")
    review_note_path = talk_pack_artifact_path(original.talk_pack_id, "review/README.txt", root)
    review_note_path.write_text("keep review note\n", encoding="utf-8")

    updated = _sample_pack(title="Updated title")
    updated_text, updated_json, updated_binary = _sample_bundle_payloads()
    original_atomic_write_text = talk_pack_store._atomic_write_text
    call_count = {"value": 0}

    def fail_on_second_write(path, content):
        call_count["value"] += 1
        if call_count["value"] == 2:
            raise IOError("boom")
        return original_atomic_write_text(path, content)

    monkeypatch.setattr(talk_pack_store, "_atomic_write_text", fail_on_second_write)

    with pytest.raises(OSError):
        save_talk_pack_bundle(
            updated,
            text_artifacts={**updated_text, "key_numbers.md": "# Updated\n"},
            json_artifacts=updated_json,
            binary_artifacts=updated_binary,
            root=root,
        )

    loaded = load_talk_pack(updated.talk_pack_id, root)
    loaded_key_numbers = load_talk_pack_artifact_text(updated.talk_pack_id, "key_numbers.md", root)
    assert loaded.title == "First title"
    assert loaded_key_numbers == "# First\n"
    assert load_talk_pack_artifact_bytes(updated.talk_pack_id, "exports/deck.pptx", root) == b"PPTX placeholder bytes"
    assert note_path.read_text(encoding="utf-8") == "keep operator note\n"
    assert exports_note_path.read_text(encoding="utf-8") == "keep exports note\n"
    assert review_note_path.read_text(encoding="utf-8") == "keep review note\n"


def test_talk_pack_store_does_not_leave_partial_new_bundle_if_text_write_fails(tmp_path, monkeypatch) -> None:
    root = tmp_path / "talk_packs"
    pack = _sample_pack()
    text_artifacts, json_artifacts, binary_artifacts = _sample_bundle_payloads()
    original_atomic_write_text = talk_pack_store._atomic_write_text
    call_count = {"value": 0}

    def fail_on_second_write(path, content):
        call_count["value"] += 1
        if call_count["value"] == 2:
            raise IOError("boom")
        return original_atomic_write_text(path, content)

    monkeypatch.setattr(talk_pack_store, "_atomic_write_text", fail_on_second_write)

    with pytest.raises(OSError):
        save_talk_pack_bundle(
            pack,
            text_artifacts={**text_artifacts, "key_numbers.md": "# First\n"},
            json_artifacts=json_artifacts,
            binary_artifacts=binary_artifacts,
            root=root,
        )

    assert list_talk_pack_ids(root) == []


def test_talk_pack_store_saves_additive_artifacts_individually(tmp_path) -> None:
    root = tmp_path / "talk_packs"
    pack = _sample_pack()
    text_artifacts, json_artifacts, binary_artifacts = _sample_bundle_payloads()
    save_talk_pack_bundle(
        pack,
        text_artifacts=text_artifacts,
        json_artifacts=json_artifacts,
        binary_artifacts=binary_artifacts,
        root=root,
    )

    text_path = save_talk_pack_artifact_text(
        pack.talk_pack_id,
        "exports/speaker_script.md",
        "# Script\n",
        root,
    )
    json_path = save_talk_pack_artifact_json(
        pack.talk_pack_id,
        "review/style_lint.json",
        {"overall_status": "warn"},
        root,
    )
    binary_path = save_talk_pack_artifact_bytes(
        pack.talk_pack_id,
        "exports/deck.pptx",
        b"PPTX placeholder bytes",
        root,
    )

    assert text_path == talk_pack_artifact_path(pack.talk_pack_id, "exports/speaker_script.md", root)
    assert json_path == talk_pack_artifact_path(pack.talk_pack_id, "review/style_lint.json", root)
    assert binary_path == talk_pack_artifact_path(pack.talk_pack_id, "exports/deck.pptx", root)
    assert load_talk_pack_artifact_text(pack.talk_pack_id, "exports/speaker_script.md", root) == "# Script\n"
    assert load_talk_pack_artifact_json(pack.talk_pack_id, "review/style_lint.json", root) == {
        "overall_status": "warn"
    }
    assert load_talk_pack_artifact_bytes(pack.talk_pack_id, "exports/deck.pptx", root) == (
        b"PPTX placeholder bytes"
    )


def test_talk_pack_store_rejects_non_object_json_artifact_payload_on_load(tmp_path) -> None:
    root = tmp_path / "talk_packs"
    pack = _sample_pack()
    text_artifacts, json_artifacts, binary_artifacts = _sample_bundle_payloads()
    save_talk_pack_bundle(
        pack,
        text_artifacts=text_artifacts,
        json_artifacts=json_artifacts,
        binary_artifacts=binary_artifacts,
        root=root,
    )

    artifact_path = talk_pack_artifact_path(pack.talk_pack_id, "review/style_lint.json", root)
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text(json.dumps(["bad", "payload"]), encoding="utf-8")

    with pytest.raises(ValueError, match="must deserialize to an object"):
        load_talk_pack_artifact_json(pack.talk_pack_id, "review/style_lint.json", root)


def test_talk_pack_store_rejects_artifact_path_traversal(tmp_path) -> None:
    root = tmp_path / "talk_packs"
    pack = _sample_pack()

    with pytest.raises(ValueError, match="artifact filename is invalid"):
        talk_pack_artifact_path(pack.talk_pack_id, "../escape.md", root)

    with pytest.raises(ValueError, match="artifact filename is invalid"):
        save_talk_pack_artifact_text(pack.talk_pack_id, "/tmp/escape.md", "bad", root)


def test_talk_pack_store_ignores_invalid_stale_manifest_paths_on_overwrite(tmp_path) -> None:
    root = tmp_path / "talk_packs"
    pack = _sample_pack()
    outside_path = root / "escape.md"
    outside_path.parent.mkdir(parents=True, exist_ok=True)
    outside_path.write_text("keep me\n", encoding="utf-8")
    manifest_path = talk_pack_json_path(pack.talk_pack_id, root)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(
            {
                "output_members": [
                    {
                        "kind": "speaker_script",
                        "path": "../escape.md",
                        "status": "generated",
                    }
                ],
                "review_artifacts": [
                    {
                        "kind": "presentation_review",
                        "path": "/tmp/escape-review.json",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    text_artifacts, json_artifacts, binary_artifacts = _sample_bundle_payloads()

    save_talk_pack_bundle(
        pack,
        text_artifacts=text_artifacts,
        json_artifacts=json_artifacts,
        binary_artifacts=binary_artifacts,
        root=root,
    )

    assert outside_path.read_text(encoding="utf-8") == "keep me\n"


def test_talk_pack_store_requires_payloads_for_declared_generated_members(tmp_path) -> None:
    root = tmp_path / "talk_packs"
    pack = _sample_pack()
    text_artifacts, json_artifacts, _binary_artifacts = _sample_bundle_payloads()

    with pytest.raises(ValueError, match="missing declared generated artifact payloads"):
        save_talk_pack_bundle(
            pack,
            text_artifacts=text_artifacts,
            json_artifacts=json_artifacts,
            root=root,
        )


def test_talk_pack_store_removes_stale_generated_artifacts_on_overwrite(tmp_path) -> None:
    root = tmp_path / "talk_packs"
    original = _sample_pack()
    original_text, original_json, original_binary = _sample_bundle_payloads()
    save_talk_pack_bundle(
        original,
        text_artifacts=original_text,
        json_artifacts=original_json,
        binary_artifacts=original_binary,
        root=root,
    )

    updated = _sample_pack(
        output_statuses={"speaker_script": "blocked"},
        review_artifacts=[
            TalkPackReviewArtifact(kind="presentation_review", path="review/presentation_review.json"),
        ],
    )
    updated_text = {
        "slide_manifest.json": '{"slides":[]}\n',
        "key_numbers.md": "# Key Numbers\n",
    }
    updated_json = {
        "review/presentation_review.json": {"overall_status": "pass"},
    }
    updated_binary = {
        "exports/deck.pptx": b"PPTX placeholder bytes",
    }

    save_talk_pack_bundle(
        updated,
        text_artifacts=updated_text,
        json_artifacts=updated_json,
        binary_artifacts=updated_binary,
        root=root,
    )

    assert not talk_pack_artifact_path(updated.talk_pack_id, "exports/speaker_script.md", root).exists()
    assert not talk_pack_artifact_path(updated.talk_pack_id, "review/style_lint.json", root).exists()
