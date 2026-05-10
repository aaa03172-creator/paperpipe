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


def _write_fixture_state(path: Path) -> None:
    _write_json(
        path,
        {
            "paper_slug": "demo-note",
            "updated_at": "2026-03-24T09:00:00+00:00",
            "runs": [],
            "signals": {
                "state_source": "skill_run",
                "last_action": "critical_appraisal",
            },
            "claimset": [
                {
                    "id": "claim_c0ffee000001",
                    "source_claim_id": "e2e-claim-1",
                    "claim": "Fixture claim",
                    "evidence_ids": ["evidence_deadbeef0001"],
                    "evidence": [
                        {
                            "id": "evidence_deadbeef0001",
                            "claim_id": "claim_c0ffee000001",
                            "text": "Fixture evidence",
                            "locator": {"chunk_id": "chunk-e2e-001", "source": "bbox"},
                        }
                    ],
                }
            ],
            "entities": [],
            "mesh": [],
            "outcomes": [],
        },
    )


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
            "artifact_acceptance_contract_written": True,
            "artifact_quality_gate_written": True,
            "artifact_clinical_extraction_written": True,
            "clinical_extraction_status": "completed",
            "clinical_extraction_note_type": "clinical",
            "anchor_verify_summary": {"pass": 3, "warn": 0, "fail": 0, "no_api": 0},
        },
    )
    _write_json(
        artifact_dir / "quality_gate.json",
        {
            "workflow": "deep_read",
            "paper_id": "paper-1",
            "run_id": "run-123",
            "overall_status": "pass",
            "current_promotion_candidate": True,
            "review_ready": True,
            "checks": [
                {
                    "name": "section_navigation_signal",
                    "status": "pass",
                    "detail": "claimset_section_count=1, summary_present=true",
                }
            ],
            "reason_codes": [],
        },
    )
    _write_json(
        artifact_dir / "context_manifest.json",
        {
            "workflow": "deep_read",
            "paper_id": "paper-1",
            "run_id": "run-123",
            "configured_attempt_order": "current",
            "effective_attempt_order": ["primary", "focused"],
            "attempt_count": 2,
            "selected_attempt": 2,
            "selected_attempt_label": "focused",
            "attempts": [],
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
    _write_json(
        artifact_dir / "clinical_extraction.json",
        {
            "paper_id": "paper-1",
            "citation": {
                "title": "Clinical bundle",
                "authors_first": "Kim",
                "year": 2026,
                "journal_or_server": "Test Journal",
                "doi": "10.1000/clinical-bundle",
                "url": "https://example.org/clinical-bundle",
            },
            "study_design": {},
            "population": {
                "condition": "Metastatic non-small cell lung cancer",
                "n_total": 52,
            },
            "intervention": {
                "category": "small_molecule",
                "name": "Targeted therapy",
            },
            "comparator": {"category": "placebo"},
            "outcomes": {"primary": [], "secondary": [], "biomarkers": [], "safety": []},
            "safety_adherence": {},
            "eligibility_flags": {
                "followup_tag": "therapeutic",
            },
            "extraction_quality": {
                "confidence": "medium",
                "missing_fields": [],
            },
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
    assert state.signals["artifact_acceptance_contract_written"] is True
    assert state.signals["artifact_quality_gate_written"] is True
    assert state.signals["artifact_clinical_extraction_written"] is True
    assert state.signals["clinical_extraction_status"] == "completed"
    assert state.signals["clinical_extraction_note_type"] == "clinical"
    assert state.signals["clinical_condition"] == "Metastatic non-small cell lung cancer"
    assert state.signals["clinical_intervention"] == "Targeted therapy, small molecule"
    assert state.signals["clinical_followup_tag"] == "therapeutic"
    assert state.signals["quality_gate_status"] == "pass"
    assert state.signals["quality_gate_review_ready"] is True
    assert state.signals["quality_gate_section_navigation_signal"] == "pass"
    assert len(state.claimset) == 1
    assert state.claimset[0].run_id == "run-123"
    assert state.claimset[0].evidence[0].run_id == "run-123"
    assert state.runs[0].data["quality_gate_status"] == "pass"
    assert state.runs[0].data["review_ready"] is True
    assert state.runs[0].data["section_navigation_signal_status"] == "pass"
    assert state.runs[0].data["section_navigation_signal_detail"] == "claimset_section_count=1, summary_present=true"
    assert state.runs[0].artifacts["clinical_extraction_path"].endswith("clinical_extraction.json")
    assert state.runs[0].artifacts["context_manifest_path"].endswith("context_manifest.json")
    assert state.runs[0].data["clinical_extraction_status"] == "completed"
    assert state.runs[0].data["clinical_condition"] == "Metastatic non-small cell lung cancer"
    assert state.runs[0].data["clinical_intervention"] == "Targeted therapy, small molecule"
    assert state.runs[0].data["clinical_followup_tag"] == "therapeutic"
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
            "artifact_clinical_extraction_written": True,
            "clinical_extraction_status": "completed",
            "clinical_extraction_note_type": "clinical",
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
    _write_json(
        artifact_dir / "clinical_extraction.json",
        {
            "paper_id": "paper-3",
            "citation": {
                "title": "Projected clinical bundle",
                "authors_first": "Park",
                "year": 2026,
                "journal_or_server": "Clinical Notes",
                "doi": "10.1000/projected-clinical",
                "url": "https://example.org/projected-clinical",
            },
            "study_design": {},
            "population": {"condition": "Ulcerative colitis", "n_total": 40},
            "intervention": {"category": "biologic", "name": "Monoclonal antibody"},
            "comparator": {"category": "placebo"},
            "outcomes": {"primary": [], "secondary": [], "biomarkers": [], "safety": []},
            "safety_adherence": {},
            "eligibility_flags": {"followup_tag": "therapeutic"},
            "extraction_quality": {"confidence": "medium", "missing_fields": []},
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
    assert state.signals["clinical_condition"] == "Ulcerative colitis"
    assert state.signals["clinical_intervention"] == "Monoclonal antibody, biologic"
    assert state.runs[0].data["clinical_extraction_status"] == "completed"
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


def test_promote_deepread_structured_state_for_note_preserves_existing_reading_assists(tmp_path):
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
                        "id": "run-prev",
                        "action": "deep_read",
                        "ts": "2026-03-24T09:00:00+00:00",
                        "status": "succeeded",
                        "summary": "Earlier promoted state.",
                        "artifacts": {},
                        "data": {},
                    }
                ],
                "signals": {
                    "state_source": "deep_read_promotion",
                    "state_source_run_id": "run-prev",
                },
                "claimset": [],
                "entities": [],
                "mesh": [],
                "outcomes": [],
                "reading_assists": [
                    {
                        "locale": "ko",
                        "canonical_locale": "en",
                        "machine_translated": True,
                        "partial": True,
                        "blocks": [
                            {
                                "kind": "abstract",
                                "text": "기존 한국어 읽기 보조를 유지해야 한다.",
                                "source_heading": "Abstract",
                                "provenance": {
                                    "source_field": "abstract",
                                    "source_locale": "en",
                                    "translator": "manual-seed",
                                },
                            }
                        ],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    artifact_dir = tmp_path / "storage" / "artifacts" / "paper-5" / "run-1000"
    _write_json(
        artifact_dir / "run_meta.json",
        {
            "run_id": "run-1000",
            "status": "succeeded",
            "finished_at": "2026-03-24T10:00:00+00:00",
        },
    )
    _write_json(artifact_dir / "bootstrap_meta.json", {"claimset_readiness": "ready"})
    _write_json(
        artifact_dir / "claimset.resolved.json",
        {
            "doc_id": "paper-5",
            "claims": [{"statement": "Projected claim.", "type": "finding", "evidence_spans": []}],
        },
    )

    result = promote_deepread_structured_state_for_note(
        vault_path=vault_path,
        note_path=note_path,
        artifact_dir=artifact_dir,
    )

    assert result["status"] == "refreshed"
    state = load_structured_state(vault_path, "demo-note", {})
    assert state is not None
    assert len(state.reading_assists) == 1
    assert state.reading_assists[0].locale == "ko"
    assert state.reading_assists[0].blocks[0].text == "기존 한국어 읽기 보조를 유지해야 한다."
    assert state.runs[0].id == "run-1000"


def test_promote_deepread_structured_state_for_note_ignores_hidden_fixture_existing_state(tmp_path):
    vault_path = tmp_path / "Vault"
    note_path = vault_path / "Inbox" / "demo-note.md"
    note_path.parent.mkdir(parents=True, exist_ok=True)
    note_path.write_text(
        "---\npp:\n  structured_path: .pp/demo-note/state.json\n---\n\n# Demo note\n",
        encoding="utf-8",
    )
    state_path = vault_path / ".pp" / "demo-note" / "state.json"
    state_path.parent.mkdir(parents=True, exist_ok=True)
    _write_fixture_state(state_path)

    artifact_dir = tmp_path / "storage" / "artifacts" / "paper-6" / "run-1001"
    _write_json(
        artifact_dir / "run_meta.json",
        {
            "run_id": "run-1001",
            "status": "succeeded",
            "finished_at": "2026-03-24T10:00:00+00:00",
        },
    )
    _write_json(artifact_dir / "bootstrap_meta.json", {"claimset_readiness": "ready"})
    _write_json(
        artifact_dir / "claimset.resolved.json",
        {
            "doc_id": "paper-6",
            "claims": [{"statement": "Projected claim.", "type": "finding", "evidence_spans": []}],
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
    assert state.runs[0].id == "run-1001"
    assert state.claimset[0].id != "claim_c0ffee000001"
