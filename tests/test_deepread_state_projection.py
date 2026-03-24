import json
from pathlib import Path

from src.services.deepread_state_projection import (
    build_deepread_structured_state_candidate,
    promote_deepread_structured_state_for_note,
)
from src.skills.storage import load_structured_state


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_build_deepread_structured_state_candidate_from_modern_bundle(tmp_path):
    artifact_dir = tmp_path / "storage" / "artifacts" / "paper-1" / "run-123"
    _write_json(
        artifact_dir / "run_meta.json",
        {
            "run_id": "run-123",
            "status": "succeeded",
            "finished_at": "2026-03-24T10:00:00+00:00",
            "parser_backend": "docling",
            "verification_status": "completed",
        },
    )
    _write_json(
        artifact_dir / "bootstrap_meta.json",
        {
            "claimset_readiness": "ready",
            "claimset_readiness_badge": "READY",
            "claimset_ops_action": "none",
            "claimset_ops_alert": False,
            "claimset_ops_note": "ready",
            "claimset_ready": True,
            "stats_report_written": True,
            "artifact_document_written": True,
            "artifact_index_written": True,
            "artifact_claimset_written": True,
            "artifact_stats_written": True,
            "anchor_verify_summary": {"pass": 3, "warn": 0, "fail": 0, "no_api": 0},
        },
    )
    _write_json(
        artifact_dir / "claimset.resolved.json",
        {
            "doc_id": "paper-1",
            "claims": [
                {
                    "claim_id": "claim-1",
                    "type": "finding",
                    "statement": "Treatment improved the primary outcome.",
                    "confidence": 0.81,
                    "evidence_spans": [
                        {
                            "quote": "Primary outcome improved by 12%.",
                            "page": 3,
                            "section": "Results",
                            "chunk_id": "chunk-1",
                            "grounded": True,
                            "resolution": "resolved",
                            "source": "reader",
                        }
                    ],
                }
            ],
        },
    )

    state = build_deepread_structured_state_candidate(
        paper_slug="demo-note",
        artifact_dir=artifact_dir,
    )

    assert state is not None
    assert state.paper_slug == "demo-note"
    assert state.runs[0].id == "run-123"
    assert state.runs[0].action == "deep_read"
    assert state.runs[0].status == "succeeded"
    assert state.signals["state_source"] == "deep_read_promotion"
    assert state.signals["state_source_run_id"] == "run-123"
    assert state.signals["parser_backend"] == "docling"
    assert state.signals["claimset_readiness"] == "ready"
    assert state.signals["verification_status"] == "completed"
    assert len(state.claimset) == 1
    assert state.claimset[0].run_id == "run-123"
    assert state.claimset[0].evidence[0].run_id == "run-123"
    assert state.outcomes == ["finding"]
    assert not (tmp_path / ".pp" / "demo-note" / "state.json").exists()


def test_build_deepread_structured_state_candidate_rejects_legacy_or_incomplete_bundle(tmp_path):
    artifact_dir = tmp_path / "storage" / "artifacts" / "paper-2" / "run-456"
    _write_json(
        artifact_dir / "run_meta.json",
        {
            "run_id": "run-456",
            "status": "succeeded",
            "finished_at": "2026-03-24T10:00:00+00:00",
        },
    )

    state = build_deepread_structured_state_candidate(
        paper_slug="legacy-note",
        artifact_dir=artifact_dir,
    )

    assert state is None


def test_promote_deepread_structured_state_for_note_writes_canonical_state_and_frontmatter(tmp_path):
    vault_path = tmp_path / "Vault"
    note_path = vault_path / "Inbox" / "demo-note.md"
    note_path.parent.mkdir(parents=True, exist_ok=True)
    note_path.write_text("# Demo note\n\nBody\n", encoding="utf-8")
    artifact_dir = tmp_path / "storage" / "artifacts" / "paper-3" / "run-789"
    _write_json(
        artifact_dir / "run_meta.json",
        {
            "run_id": "run-789",
            "status": "succeeded",
            "finished_at": "2026-03-24T10:00:00+00:00",
            "parser_backend": "docling",
        },
    )
    _write_json(
        artifact_dir / "bootstrap_meta.json",
        {
            "claimset_readiness": "ready",
            "claimset_readiness_badge": "READY",
            "claimset_ops_action": "none",
            "claimset_ops_alert": False,
            "claimset_ops_note": "ready",
            "claimset_ready": True,
            "artifact_claimset_written": True,
        },
    )
    _write_json(
        artifact_dir / "claimset.resolved.json",
        {
            "doc_id": "paper-3",
            "claims": [
                {
                    "claim_id": "claim-1",
                    "type": "finding",
                    "statement": "Projected claim.",
                    "evidence_spans": [{"quote": "Projected evidence.", "page": 2, "section": "Results"}],
                }
            ],
        },
    )

    result = promote_deepread_structured_state_for_note(
        vault_path=vault_path,
        note_path=note_path,
        artifact_dir=artifact_dir,
    )

    assert result["status"] == "created"
    state = load_structured_state(vault_path, "demo-note", {})
    assert state is not None
    assert state.runs[0].action == "deep_read"
    assert state.signals["state_source"] == "deep_read_promotion"
    note_text = note_path.read_text(encoding="utf-8")
    assert "structured_path: .pp/demo-note/state.json" in note_text
    assert "deep_read" in note_text


def test_promote_deepread_structured_state_for_note_skips_existing_non_promotion_state(tmp_path):
    vault_path = tmp_path / "Vault"
    note_path = vault_path / "Inbox" / "demo-note.md"
    note_path.parent.mkdir(parents=True, exist_ok=True)
    note_path.write_text(
        "---\npp:\n  structured_path: .pp/demo-note/state.json\n---\n\n# Demo note\n",
        encoding="utf-8",
    )
    state_path = vault_path / ".pp" / "demo-note" / "state.json"
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(
        json.dumps(
            {
                "paper_slug": "demo-note",
                "updated_at": "2026-03-24T09:00:00+00:00",
                "runs": [
                    {
                        "id": "skill-1",
                        "action": "critical_appraisal",
                        "ts": "2026-03-24T09:00:00+00:00",
                        "status": "succeeded",
                        "summary": "Skill-owned state.",
                        "artifacts": {},
                        "data": {},
                    }
                ],
                "signals": {
                    "state_source": "skill_run",
                    "last_action": "critical_appraisal",
                },
                "claimset": [],
                "entities": [],
                "mesh": [],
                "outcomes": [],
            }
        ),
        encoding="utf-8",
    )
    original_text = state_path.read_text(encoding="utf-8")
    artifact_dir = tmp_path / "storage" / "artifacts" / "paper-4" / "run-999"
    _write_json(
        artifact_dir / "run_meta.json",
        {
            "run_id": "run-999",
            "status": "succeeded",
            "finished_at": "2026-03-24T10:00:00+00:00",
        },
    )
    _write_json(artifact_dir / "bootstrap_meta.json", {"claimset_readiness": "ready"})
    _write_json(
        artifact_dir / "claimset.resolved.json",
        {"doc_id": "paper-4", "claims": [{"statement": "Projected claim.", "type": "finding", "evidence_spans": []}]},
    )

    result = promote_deepread_structured_state_for_note(
        vault_path=vault_path,
        note_path=note_path,
        artifact_dir=artifact_dir,
    )

    assert result["status"] == "skipped"
    assert result["reason"] == "canonical_state_owned_elsewhere"
    assert state_path.read_text(encoding="utf-8") == original_text
