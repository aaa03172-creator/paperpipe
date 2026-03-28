import json

from src.services.deepread_handoff_artifacts import (
    build_deepread_acceptance_contract,
    build_deepread_quality_gate,
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

    assert contract.workflow == "deep_read"
    assert "claimset.resolved.json" in contract.expected_outputs
    assert "stats_report.json" in contract.expected_outputs
    assert quality_gate.overall_status == "pass"
    assert quality_gate.current_promotion_candidate is True
    assert quality_gate.review_ready is True
    assert quality_gate.reason_codes == []


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

    json.loads(contract.model_dump_json())
    json.loads(quality_gate.model_dump_json())
