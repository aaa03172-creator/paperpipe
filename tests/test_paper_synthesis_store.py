from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

import src.paper_syntheses.store as paper_synthesis_store
from src.paper_syntheses.store import (
    list_paper_synthesis_ids,
    load_paper_synthesis,
    load_paper_synthesis_markdown,
    paper_synthesis_json_path,
    paper_synthesis_markdown_path,
    save_paper_synthesis_bundle,
)
from src.schemas.chat import ChatEvidenceRef
from src.schemas.paper_synthesis import PaperSynthesis, PaperSynthesisSourceRef


def _sample_synthesis(title: str = "SCFA paper synthesis") -> PaperSynthesis:
    return PaperSynthesis(
        synthesis_id="papersynth_20260407T120000Z_scfa_demo",
        paper_slug="wenzelShortchainFattyAcids2020",
        title=title,
        created_at=datetime(2026, 4, 7, 12, 0, tzinfo=timezone.utc),
        updated_at=datetime(2026, 4, 7, 12, 5, tzinfo=timezone.utc),
        readiness="mixed",
        freshness="current",
        summary="Condenses current paper-scoped evidence into a reviewable note.",
        source_refs=[
            PaperSynthesisSourceRef(
                kind="structured_state",
                paper_slug="wenzelShortchainFattyAcids2020",
                note="Primary canonical owner.",
            ),
            PaperSynthesisSourceRef(
                kind="claimset_resolved",
                paper_slug="wenzelShortchainFattyAcids2020",
                run_id="20260407T110000Z",
                path="storage/artifacts/wenzelShortchainFattyAcids2020/20260407T110000Z/claimset.resolved.json",
            ),
            PaperSynthesisSourceRef(
                kind="run_meta",
                paper_slug="wenzelShortchainFattyAcids2020",
                run_id="20260407T110000Z",
                path="storage/artifacts/wenzelShortchainFattyAcids2020/20260407T110000Z/run_meta.json",
            ),
        ],
        evidence_refs=[
            ChatEvidenceRef(
                paper_slug="wenzelShortchainFattyAcids2020",
                run_id="20260407T110000Z",
            )
        ],
        warnings=["Compiled view only"],
        uncertainty_notes=["Needs upstream jump for promoted biomedical answers"],
    )


def test_paper_synthesis_store_roundtrip_creates_expected_layout(tmp_path):
    root = tmp_path / "paper_syntheses"
    synthesis = _sample_synthesis()
    markdown = "# Paper synthesis\n"

    json_path, md_path = save_paper_synthesis_bundle(synthesis, markdown, root)
    loaded = load_paper_synthesis(synthesis.synthesis_id, root)
    loaded_markdown = load_paper_synthesis_markdown(synthesis.synthesis_id, root)

    assert json_path == paper_synthesis_json_path(synthesis.synthesis_id, root)
    assert md_path == paper_synthesis_markdown_path(synthesis.synthesis_id, root)
    assert loaded.synthesis_id == synthesis.synthesis_id
    assert loaded.title == synthesis.title
    assert loaded.artifact_family == "paper_synthesis"
    assert loaded.template_kind == "paper"
    assert loaded.layer == "compiled_knowledge"
    assert loaded.canonical_status == "non_canonical"
    assert loaded.readiness == "mixed"
    assert loaded_markdown == markdown
    assert list_paper_synthesis_ids(root) == [synthesis.synthesis_id]


def test_paper_synthesis_store_overwrites_same_id_without_duplicate_dump(tmp_path):
    root = tmp_path / "paper_syntheses"
    synthesis = _sample_synthesis(title="First title")
    save_paper_synthesis_bundle(synthesis, "# First", root)

    updated = _sample_synthesis(title="Updated title")
    save_paper_synthesis_bundle(updated, "# Updated", root)

    loaded = load_paper_synthesis(updated.synthesis_id, root)
    loaded_markdown = load_paper_synthesis_markdown(updated.synthesis_id, root)

    assert loaded.title == "Updated title"
    assert loaded_markdown == "# Updated"
    assert len(list((root / updated.synthesis_id).iterdir())) == 2


def test_paper_synthesis_store_rolls_back_bundle_if_markdown_write_fails(tmp_path, monkeypatch):
    root = tmp_path / "paper_syntheses"
    original = _sample_synthesis(title="First title")
    save_paper_synthesis_bundle(original, "# First", root)

    updated = _sample_synthesis(title="Updated title")
    original_atomic_write_text = paper_synthesis_store._atomic_write_text
    call_count = {"value": 0}

    def fail_on_second_write(path, content):
        call_count["value"] += 1
        if call_count["value"] == 2:
            raise IOError("boom")
        return original_atomic_write_text(path, content)

    monkeypatch.setattr(paper_synthesis_store, "_atomic_write_text", fail_on_second_write)

    with pytest.raises(OSError):
        save_paper_synthesis_bundle(updated, "# Updated", root)

    loaded = load_paper_synthesis(updated.synthesis_id, root)
    loaded_markdown = load_paper_synthesis_markdown(updated.synthesis_id, root)
    assert loaded.title == "First title"
    assert loaded_markdown == "# First"
    assert len(list((root / updated.synthesis_id).iterdir())) == 2


def test_paper_synthesis_store_does_not_leave_partial_new_bundle_if_markdown_write_fails(tmp_path, monkeypatch):
    root = tmp_path / "paper_syntheses"
    synthesis = _sample_synthesis()
    original_atomic_write_text = paper_synthesis_store._atomic_write_text
    call_count = {"value": 0}

    def fail_on_second_write(path, content):
        call_count["value"] += 1
        if call_count["value"] == 2:
            raise IOError("boom")
        return original_atomic_write_text(path, content)

    monkeypatch.setattr(paper_synthesis_store, "_atomic_write_text", fail_on_second_write)

    with pytest.raises(OSError):
        save_paper_synthesis_bundle(synthesis, "# First", root)

    assert list_paper_synthesis_ids(root) == []


def test_paper_synthesis_schema_rejects_evidence_backed_without_evidence_refs():
    with pytest.raises(ValidationError, match="evidence_backed requires at least one evidence_ref"):
        PaperSynthesis(
            synthesis_id="papersynth_demo_run_1234567890",
            paper_slug="demo-paper",
            title="Paper synthesis: demo-paper",
            created_at=datetime(2026, 4, 7, 12, 0, tzinfo=timezone.utc),
            updated_at=datetime(2026, 4, 7, 12, 5, tzinfo=timezone.utc),
            readiness="evidence_backed",
            source_refs=[
                PaperSynthesisSourceRef(
                    kind="structured_state",
                    paper_slug="demo-paper",
                    path="vault/.pp/demo-paper/state.json",
                ),
                PaperSynthesisSourceRef(
                    kind="claimset_resolved",
                    paper_slug="demo-paper",
                    run_id="run-1",
                    path="storage/artifacts/demo-paper/run-1/claimset.resolved.json",
                ),
                PaperSynthesisSourceRef(
                    kind="run_meta",
                    paper_slug="demo-paper",
                    run_id="run-1",
                    path="storage/artifacts/demo-paper/run-1/run_meta.json",
                ),
            ],
        )
