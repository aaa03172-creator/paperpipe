import json

from src.services.deepread_handoff_artifacts import (
    build_deepread_acceptance_contract,
    build_deepread_context_manifest,
    build_deepread_quality_gate,
)


def test_build_deepread_handoff_artifacts_for_review_ready_bundle():
    run_meta = {
        "status": "succeeded",
        "parser_backend": "fitz_pdfplumber",
        "section_count": 2,
        "section_summary": [
            {"key": "results", "label": "Results"},
            {"key": "discussion", "label": "Discussion"},
        ],
    }
    bootstrap_meta = {
        "run_verify": True,
        "clean_reindex_requested": False,
        "persona_id": "default",
        "reasoning_persona": "researcher",
        "profile_id": None,
        "artifact_claimset_resolved_written": True,
        "artifact_claimset_coverage_written": True,
        "artifact_claimset_coverage_focus_written": True,
        "artifact_reader_eval_written": True,
        "reader_eval_bbox_span_count": 1,
        "reader_eval_text_match_span_count": 2,
        "reader_eval_approx_span_count": 0,
        "reader_eval_unresolved_span_count": 0,
        "reader_eval_ambiguous_span_count": 0,
        "claimset_ready": True,
        "claimset_readiness": "ready",
        "verifier_status": "completed",
        "reader_analysis": {
            "configured_attempt_order": "focused_first",
            "effective_attempt_order": ["focused", "primary"],
            "attempt_count": 1,
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
                }
            ],
        },
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
        bootstrap_meta=bootstrap_meta,
    )

    assert contract.workflow == "deep_read"
    assert "claimset.resolved.json" in contract.expected_outputs
    assert "claimset_coverage.json" in contract.expected_outputs
    assert "claimset_coverage_focus.json" in contract.expected_outputs
    assert "stats_report.json" in contract.expected_outputs
    acceptance_check_map = {check.name: check for check in contract.acceptance_checks}
    assert acceptance_check_map["claimset_coverage_written"].required is False
    assert acceptance_check_map["claimset_coverage_written"].source == (
        "bootstrap_meta.artifact_claimset_coverage_written"
    )
    assert acceptance_check_map["claimset_coverage_focus_written"].required is False
    assert acceptance_check_map["claimset_coverage_focus_written"].source == (
        "bootstrap_meta.artifact_claimset_coverage_focus_written"
    )
    assert [item.code for item in contract.hard_fail_conditions] == [
        "RUN_NOT_SUCCEEDED",
        "MISSING_CLAIMSET_RESOLVED",
    ]
    assert quality_gate.overall_status == "pass"
    assert quality_gate.current_promotion_candidate is True
    assert quality_gate.review_ready is True
    assert quality_gate.reason_codes == []
    assert quality_gate.hard_fail_codes == []
    check_map = {check.name: check for check in quality_gate.checks}
    assert check_map["evidence_locator_quality"].status == "pass"
    assert "bbox=1" in check_map["evidence_locator_quality"].detail
    assert check_map["section_navigation_signal"].status == "pass"
    assert "claimset_section_count=2" in check_map["section_navigation_signal"].detail
    assert check_map["step_stability"].status == "pass"
    assert quality_gate.step_stability_summary is not None
    assert quality_gate.step_stability_summary.reason_codes == []
    assert check_map["failure_recovery"].status == "pass"
    assert quality_gate.failure_recovery_summary is not None
    assert quality_gate.failure_recovery_summary.reason_codes == []
    assert context_manifest is not None
    assert context_manifest.selected_attempt_label == "focused"
    assert context_manifest.selected_attempt_summary is not None
    assert context_manifest.selected_attempt_summary.included_chunk_count == 11
    assert context_manifest.selected_attempt_summary.truncated_chunk_count == 1
    assert context_manifest.goal_drift_summary is not None
    assert context_manifest.goal_drift_summary.status == "pass"
    assert context_manifest.goal_drift_summary.reason_codes == []


def test_build_deepread_handoff_artifacts_warn_for_not_ready_claimset():
    run_meta = {
        "status": "succeeded",
        "parser_backend": "fitz_pdfplumber",
    }
    bootstrap_meta = {
        "run_verify": False,
        "artifact_claimset_resolved_written": True,
        "artifact_reader_eval_written": False,
        "reader_eval_bbox_span_count": 0,
        "reader_eval_text_match_span_count": 0,
        "reader_eval_approx_span_count": 1,
        "reader_eval_unresolved_span_count": 1,
        "reader_eval_ambiguous_span_count": 0,
        "claimset_ready": False,
        "claimset_readiness": "not_ready",
        "claimset_section_count": 0,
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
    assert quality_gate.hard_fail_codes == []
    check_map = {check.name: check for check in quality_gate.checks}
    assert check_map["claimset_ready"].status == "warn"
    assert check_map["evidence_locator_quality"].status == "warn"
    assert check_map["section_navigation_signal"].status == "warn"
    assert check_map["step_stability"].status == "pass"
    assert check_map["failure_recovery"].status == "pass"
    assert check_map["verification_completed"].status == "not_run"


def test_deepread_handoff_summaries_surface_long_run_warnings():
    run_meta = {
        "status": "succeeded",
        "reader_timeout_triggered": True,
    }
    bootstrap_meta = {
        "run_verify": True,
        "artifact_claimset_resolved_written": True,
        "artifact_reader_eval_written": True,
        "reader_eval_bbox_span_count": 0,
        "reader_eval_text_match_span_count": 2,
        "reader_eval_approx_span_count": 0,
        "reader_eval_unresolved_span_count": 0,
        "reader_eval_ambiguous_span_count": 0,
        "claimset_ready": True,
        "claimset_readiness": "ready",
        "verifier_status": "failed",
        "reader_analysis": {
            "configured_attempt_order": "focused_first",
            "effective_attempt_order": ["focused", "primary"],
            "attempt_count": 1,
            "return_mode": "heuristic_fallback",
            "selected_attempt": 1,
            "selected_attempt_label": "fallback",
            "final_claim_count": 1,
            "used_heuristic_fallback": True,
            "attempts": [
                {
                    "attempt_idx": 1,
                    "label": "focused",
                    "status": "timeout",
                    "context_mode": "chunk_context",
                    "context_chars": 20000,
                    "prompt_chars": 24000,
                    "estimated_prompt_tokens": 6000,
                    "estimated_response_tokens": 0,
                    "included_chunk_count": 18,
                    "unique_section_count": 4,
                    "unique_page_hint_count": 10,
                    "sentence_focus_count": 0,
                    "truncated_chunk_count": 3,
                }
            ],
        },
    }

    quality_gate = build_deepread_quality_gate(
        paper_id="paper-4",
        run_id="run-4",
        run_meta=run_meta,
        bootstrap_meta=bootstrap_meta,
    )
    context_manifest = build_deepread_context_manifest(
        paper_id="paper-4",
        run_id="run-4",
        run_meta=run_meta,
        bootstrap_meta=bootstrap_meta,
    )

    assert quality_gate.step_stability_summary is not None
    assert quality_gate.step_stability_summary.status == "warn"
    assert quality_gate.step_stability_summary.reason_codes == [
        "READER_TIMEOUT_TRIGGERED",
        "HEURISTIC_FALLBACK_USED",
        "VERIFIER_FAILED",
    ]
    check_map = {check.name: check for check in quality_gate.checks}
    assert check_map["step_stability"].status == "warn"
    assert check_map["failure_recovery"].status == "pass"
    assert context_manifest is not None
    assert context_manifest.goal_drift_summary is not None
    assert context_manifest.goal_drift_summary.status == "warn"
    assert context_manifest.goal_drift_summary.reason_codes == [
        "SELECTED_ATTEMPT_OUTSIDE_EFFECTIVE_ORDER",
        "HEURISTIC_FALLBACK_USED",
    ]


def test_deepread_quality_gate_marks_recovery_fail_when_terminal_metadata_missing():
    quality_gate = build_deepread_quality_gate(
        paper_id="paper-5",
        run_id="run-5",
        run_meta={"status": "failed"},
        bootstrap_meta={
            "run_verify": False,
            "artifact_claimset_resolved_written": False,
            "claimset_ready": None,
            "claimset_readiness": "unknown",
            "verifier_status": "not_run",
        },
    )

    assert quality_gate.failure_recovery_summary is not None
    assert quality_gate.failure_recovery_summary.status == "fail"
    assert quality_gate.failure_recovery_summary.reason_codes == [
        "MISSING_FINISHED_AT",
        "MISSING_ERROR_DETAIL",
        "MISSING_RECOVERY_GUIDANCE",
    ]
    check_map = {check.name: check for check in quality_gate.checks}
    assert check_map["failure_recovery"].status == "fail"


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
    assert "RUN_NOT_SUCCEEDED" in quality_gate.reason_codes
    assert quality_gate.hard_fail_codes == [
        "RUN_NOT_SUCCEEDED",
        "MISSING_CLAIMSET_RESOLVED",
    ]
    assert context_manifest is None
