from __future__ import annotations

from pathlib import Path
from typing import Any

from src.schemas.deepread_handoff import (
    DeepReadAcceptanceCheck,
    DeepReadAcceptanceContract,
    DeepReadQualityGate,
    DeepReadQualityGateCheck,
)


def build_deepread_acceptance_contract(
    *,
    paper_id: str,
    run_id: str,
    run_meta: dict[str, Any],
    bootstrap_meta: dict[str, Any],
) -> DeepReadAcceptanceContract:
    run_verify = bool(bootstrap_meta.get("run_verify"))
    expected_outputs = [
        "document_artifact.json",
        "index_artifact.json",
        "claimset.json",
        "claimset.resolved.json",
        "run_meta.json",
        "bootstrap_meta.json",
    ]
    if run_verify:
        expected_outputs.append("stats_report.json")

    checks = [
        DeepReadAcceptanceCheck(
            name="run_succeeded",
            source="run_meta.status",
            description="Deep-read run reached succeeded state.",
        ),
        DeepReadAcceptanceCheck(
            name="claimset_resolved_written",
            source="bootstrap_meta.artifact_claimset_resolved_written",
            description="Resolved claimset artifact exists for downstream promotion.",
        ),
        DeepReadAcceptanceCheck(
            name="claimset_ready",
            source="bootstrap_meta.claimset_ready",
            description="Claimset is non-empty and marked review-ready.",
        ),
        DeepReadAcceptanceCheck(
            name="reader_eval_written",
            required=False,
            source="bootstrap_meta.artifact_reader_eval_written",
            description="Reader eval sidecar exists for bounded post-read review.",
        ),
        DeepReadAcceptanceCheck(
            name="verification_completed",
            required=run_verify,
            source="bootstrap_meta.verifier_status",
            description="Stats verification completed when run_verify was requested.",
        ),
    ]
    return DeepReadAcceptanceContract(
        paper_id=paper_id,
        run_id=run_id,
        requested_scope={
            "run_verify": run_verify,
            "clean_reindex_requested": bool(bootstrap_meta.get("clean_reindex_requested")),
            "persona_id": bootstrap_meta.get("persona_id"),
            "parser_backend": run_meta.get("parser_backend") or bootstrap_meta.get("parser_backend"),
        },
        expected_outputs=expected_outputs,
        acceptance_checks=checks,
        promotion_contract={
            "current_note_state_promotion_rule": "run succeeded and claimset.resolved.json exists",
            "review_ready_rule": "promotion candidate plus claimset_ready and verifier completed when requested",
            "owner": "current deep-read runtime; additive pilot metadata only",
        },
    )


def build_deepread_quality_gate(
    *,
    paper_id: str,
    run_id: str,
    run_meta: dict[str, Any],
    bootstrap_meta: dict[str, Any],
) -> DeepReadQualityGate:
    run_status = str(run_meta.get("status") or "").strip().lower()
    run_verify = bool(bootstrap_meta.get("run_verify"))
    verifier_status = str(bootstrap_meta.get("verifier_status") or "not_run").strip().lower()
    claimset_ready = bootstrap_meta.get("claimset_ready") is True
    claimset_resolved_written = bool(bootstrap_meta.get("artifact_claimset_resolved_written"))
    reader_eval_written = bool(bootstrap_meta.get("artifact_reader_eval_written"))
    current_promotion_candidate = run_status == "succeeded" and claimset_resolved_written
    verification_completed = (not run_verify) or verifier_status == "completed"
    review_ready = current_promotion_candidate and claimset_ready and verification_completed

    checks: list[DeepReadQualityGateCheck] = [
        DeepReadQualityGateCheck(
            name="run_succeeded",
            status="pass" if run_status == "succeeded" else "fail",
            detail=run_status or "unknown",
        ),
        DeepReadQualityGateCheck(
            name="claimset_resolved_written",
            status="pass" if claimset_resolved_written else "fail",
            detail=str(bool(claimset_resolved_written)).lower(),
        ),
        DeepReadQualityGateCheck(
            name="claimset_ready",
            status="pass" if claimset_ready else "warn",
            detail=str(bootstrap_meta.get("claimset_readiness") or "unknown"),
        ),
        DeepReadQualityGateCheck(
            name="reader_eval_written",
            status="pass" if reader_eval_written else "warn",
            detail=str(bool(reader_eval_written)).lower(),
        ),
    ]
    if run_verify:
        checks.append(
            DeepReadQualityGateCheck(
                name="verification_completed",
                status="pass" if verifier_status == "completed" else "warn",
                detail=verifier_status or "not_run",
            )
        )
    else:
        checks.append(
            DeepReadQualityGateCheck(
                name="verification_completed",
                status="not_run",
                detail="run_verify=false",
            )
        )

    reason_codes: list[str] = []
    if not claimset_resolved_written:
        reason_codes.append("MISSING_CLAIMSET_RESOLVED")
    if not claimset_ready:
        reason_codes.append("CLAIMSET_NOT_READY")
    if run_verify and verifier_status == "failed":
        reason_codes.append("VERIFIER_FAILED")

    if not current_promotion_candidate:
        overall_status: str = "fail"
    elif review_ready:
        overall_status = "pass"
    else:
        overall_status = "warn"

    return DeepReadQualityGate(
        paper_id=paper_id,
        run_id=run_id,
        overall_status=overall_status,  # type: ignore[arg-type]
        current_promotion_candidate=current_promotion_candidate,
        review_ready=review_ready,
        reason_codes=reason_codes,
        checks=checks,
    )


def write_deepread_handoff_artifacts(
    artifact_dir: Path,
    *,
    paper_id: str,
    run_id: str,
    run_meta: dict[str, Any],
    bootstrap_meta: dict[str, Any],
) -> dict[str, str]:
    contract = build_deepread_acceptance_contract(
        paper_id=paper_id,
        run_id=run_id,
        run_meta=run_meta,
        bootstrap_meta=bootstrap_meta,
    )
    quality_gate = build_deepread_quality_gate(
        paper_id=paper_id,
        run_id=run_id,
        run_meta=run_meta,
        bootstrap_meta=bootstrap_meta,
    )

    contract_path = artifact_dir / "acceptance_contract.json"
    quality_gate_path = artifact_dir / "quality_gate.json"
    contract_path.write_text(contract.model_dump_json(indent=2), encoding="utf-8")
    quality_gate_path.write_text(quality_gate.model_dump_json(indent=2), encoding="utf-8")
    return {
        "acceptance_contract_path": str(contract_path),
        "quality_gate_path": str(quality_gate_path),
    }
