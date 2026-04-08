import json

from src.services.deepread_handoff_artifacts import (
    build_deepread_acceptance_contract,
    build_deepread_context_manifest,
    build_deepread_quality_gate,
    write_deepread_handoff_artifacts,
)


def test_build_deepread_handoff_artifacts_for_review_ready_bundle():
    run_meta = {
        "status": "succeeded",
        "parser_backend": "fitz_pdfplumber",
    }
    bootstrap_meta = {
        "run_verify": True,
        "clean_reindex_requested": False,
        "persona_id": "default",
        "reasoning_persona": "researcher",
        "profile_id": None,
        "artifact_claimset_resolved_written": True,
        "artifact_reader_eval_written": True,
        "claimset_ready": True,
        "claimset_readiness": "ready",
        "verifier_status": "completed",
    }

    contract = build_deepread_acceptance_contract(
        paper_id="paper-1",
        run_id="run-1",
        run_meta=run_meta,
        bootstrap_meta=bootstrap_meta,
    )
    quality_gate = build_deepread_quality_gate(
        paper_id="paper-1",
        run_id="run-1",
        run_meta=run_meta,
        bootstrap_meta=bootstrap_meta,
    )
    context_manifest = build_deepread_context_manifest(
        paper_id="paper-1",
        run_id="run-1",
        run_meta=run_meta,
        bootstrap_meta={
            **bootstrap_meta,
            "reader_analysis": {
                "configured_attempt_order": "focused_first",
                "effective_attempt_order": ["focused", "primary"],
                "attempt_count": 2,
                "return_mode": "success",
                "selected_attempt": 1,
                "selected_attempt_label": "focused",
                "final_claim_count": 3,
                "used_heuristic_fallback": False,
                "attempts": [
                    {
                        "attempt_idx": 1,
                        "label": "focused",
                        "status": "parsed",
                        "context_mode": "chunk_context",
                        "context_chars": 12000,
                        "prompt_chars": 14000,
                        "estimated_prompt_tokens": 3800,
                        "estimated_response_tokens": 1000,
                        "included_chunk_count": 11,
                        "unique_section_count": 2,
                        "unique_page_hint_count": 6,
                        "sentence_focus_count": 0,
                        "truncated_chunk_count": 1,
                    },
                    {
                        "attempt_idx": 2,
                        "label": "primary",
                        "status": "skipped",
                    },
                ],
            },
        },
    )

    assert contract.workflow == "deep_read"
    assert "claimset.resolved.json" in contract.expected_outputs
    assert "stats_report.json" in contract.expected_outputs
    assert quality_gate.overall_status == "pass"
    assert quality_gate.current_promotion_candidate is True
    assert quality_gate.review_ready is True
    assert quality_gate.reason_codes == []
    assert context_manifest is not None
    assert context_manifest.selected_attempt_label == "focused"
    assert context_manifest.selected_attempt_summary is not None
    assert context_manifest.selected_attempt_summary.included_chunk_count == 11
    assert context_manifest.attempt_count == 2


def test_build_deepread_handoff_artifacts_warn_for_not_ready_claimset():
    run_meta = {
        "status": "succeeded",
        "parser_backend": "fitz_pdfplumber",
    }
    bootstrap_meta = {
        "run_verify": False,
        "artifact_claimset_resolved_written": True,
        "artifact_reader_eval_written": False,
        "claimset_ready": False,
        "claimset_readiness": "not_ready",
        "verifier_status": "not_run",
    }

    quality_gate = build_deepread_quality_gate(
        paper_id="paper-2",
        run_id="run-2",
        run_meta=run_meta,
        bootstrap_meta=bootstrap_meta,
    )

    assert quality_gate.overall_status == "warn"
    assert quality_gate.current_promotion_candidate is True
    assert quality_gate.review_ready is False
    assert "CLAIMSET_NOT_READY" in quality_gate.reason_codes
    check_map = {check.name: check for check in quality_gate.checks}
    assert check_map["claimset_ready"].status == "warn"
    assert check_map["verification_completed"].status == "not_run"


def test_deepread_handoff_models_are_json_serializable():
    run_meta = {"status": "failed"}
    bootstrap_meta = {
        "run_verify": True,
        "artifact_claimset_resolved_written": False,
        "claimset_ready": None,
        "claimset_readiness": "unknown",
        "verifier_status": "failed",
    }
    contract = build_deepread_acceptance_contract(
        paper_id="paper-3",
        run_id="run-3",
        run_meta=run_meta,
        bootstrap_meta=bootstrap_meta,
    )
    quality_gate = build_deepread_quality_gate(
        paper_id="paper-3",
        run_id="run-3",
        run_meta=run_meta,
        bootstrap_meta=bootstrap_meta,
    )
    context_manifest = build_deepread_context_manifest(
        paper_id="paper-3",
        run_id="run-3",
        run_meta=run_meta,
        bootstrap_meta=bootstrap_meta,
    )

    json.loads(contract.model_dump_json())
    json.loads(quality_gate.model_dump_json())
    assert context_manifest is None


def test_write_deepread_handoff_artifacts_writes_context_manifest_when_reader_analysis_present(tmp_path):
    artifact_dir = tmp_path / "artifacts"
    artifact_dir.mkdir()
    paths = write_deepread_handoff_artifacts(
        artifact_dir,
        paper_id="paper-ctx",
        run_id="run-ctx",
        run_meta={
            "status": "succeeded",
            "reader_analysis": {
                "configured_attempt_order": "focused_first",
                "effective_attempt_order": ["focused", "primary"],
                "selected_attempt": 2,
                "selected_attempt_label": "primary",
                "attempts": [
                    {"attempt_idx": 1, "label": "focused", "status": "failed"},
                    {"attempt_idx": 2, "label": "primary", "status": "parsed", "included_chunk_count": 7},
                ],
            },
        },
        bootstrap_meta={
            "artifact_claimset_resolved_written": True,
            "artifact_reader_eval_written": True,
            "claimset_ready": True,
            "claimset_readiness": "ready",
            "run_verify": False,
            "verifier_status": "not_run",
        },
    )

    assert "context_manifest_path" in paths
    manifest = json.loads((artifact_dir / "context_manifest.json").read_text(encoding="utf-8"))
    assert manifest["selected_attempt_label"] == "primary"
    assert manifest["selected_attempt_summary"]["included_chunk_count"] == 7
