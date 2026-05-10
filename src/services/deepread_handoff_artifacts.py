from __future__ import annotations

from pathlib import Path
from typing import Any

from src.skills.storage import atomic_write_text
from src.schemas.deepread_handoff import (
    DeepReadAcceptanceCheck,
    DeepReadAcceptanceContract,
    DeepReadContextManifest,
    DeepReadContextManifestAttempt,
    DeepReadGoalDriftSummary,
    DeepReadHardFailCondition,
    DeepReadQualityGate,
    DeepReadQualityGateCheck,
    DeepReadRecoverySummary,
    DeepReadStepStabilitySummary,
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
    if bool(bootstrap_meta.get("artifact_claimset_coverage_written")):
        expected_outputs.append("claimset_coverage.json")

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
            name="claimset_coverage_written",
            required=False,
            source="bootstrap_meta.artifact_claimset_coverage_written",
            description="Coverage sidecar exists for advisory post-read coverage review.",
        ),
        DeepReadAcceptanceCheck(
            name="verification_completed",
            required=run_verify,
            source="bootstrap_meta.verifier_status",
            description="Stats verification completed when run_verify was requested.",
        ),
    ]
    hard_fail_conditions = [
        DeepReadHardFailCondition(
            code="RUN_NOT_SUCCEEDED",
            source="run_meta.status",
            description="The deep-read run did not reach succeeded state.",
        ),
        DeepReadHardFailCondition(
            code="MISSING_CLAIMSET_RESOLVED",
            source="bootstrap_meta.artifact_claimset_resolved_written",
            description="Resolved claimset artifact is missing, so promotion cannot proceed.",
        ),
    ]
    return DeepReadAcceptanceContract(
        paper_id=paper_id,
        run_id=run_id,
        requested_scope={
            "run_verify": run_verify,
            "clean_reindex_requested": bool(bootstrap_meta.get("clean_reindex_requested")),
            "persona_id": bootstrap_meta.get("persona_id"),
            "reasoning_persona": bootstrap_meta.get("reasoning_persona"),
            "profile_id": bootstrap_meta.get("profile_id"),
            "parser_backend": run_meta.get("parser_backend") or bootstrap_meta.get("parser_backend"),
        },
        expected_outputs=expected_outputs,
        acceptance_checks=checks,
        hard_fail_conditions=hard_fail_conditions,
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
    raw_analysis = bootstrap_meta.get("reader_analysis")
    if not isinstance(raw_analysis, dict) or not raw_analysis:
        raw_analysis = run_meta.get("reader_analysis")
    if not isinstance(raw_analysis, dict):
        raw_analysis = {}
    claimset_ready = bootstrap_meta.get("claimset_ready") is True
    claimset_resolved_written = bool(bootstrap_meta.get("artifact_claimset_resolved_written"))
    reader_eval_written = bool(bootstrap_meta.get("artifact_reader_eval_written"))
    reader_eval_bbox_span_count = int(bootstrap_meta.get("reader_eval_bbox_span_count") or 0)
    reader_eval_text_match_span_count = int(bootstrap_meta.get("reader_eval_text_match_span_count") or 0)
    reader_eval_approx_span_count = int(bootstrap_meta.get("reader_eval_approx_span_count") or 0)
    reader_eval_unresolved_span_count = int(bootstrap_meta.get("reader_eval_unresolved_span_count") or 0)
    reader_eval_ambiguous_span_count = int(bootstrap_meta.get("reader_eval_ambiguous_span_count") or 0)
    claimset_section_count = int(
        bootstrap_meta.get("claimset_section_count")
        or run_meta.get("section_count")
        or 0
    )
    has_section_navigation_signal = bool(claimset_section_count > 0 or run_meta.get("section_summary"))
    used_heuristic_fallback = bool(raw_analysis.get("used_heuristic_fallback"))
    return_mode = str(raw_analysis.get("return_mode") or "").strip().lower() or None
    reader_timeout_triggered = bool(
        bootstrap_meta.get("reader_timeout_triggered") or run_meta.get("reader_timeout_triggered")
    )
    finished_at = str(run_meta.get("finished_at") or "").strip() or None
    run_error = str(run_meta.get("error") or "").strip() or None
    run_error_type = str(run_meta.get("error_type") or "").strip() or None
    claimset_ops_action = str(bootstrap_meta.get("claimset_ops_action") or "").strip().lower() or None
    current_promotion_candidate = run_status == "succeeded" and claimset_resolved_written
    verification_completed = (not run_verify) or verifier_status == "completed"
    review_ready = current_promotion_candidate and claimset_ready and verification_completed
    step_stability_reason_codes: list[str] = []
    if run_status != "succeeded":
        step_stability_reason_codes.append("RUN_NOT_SUCCEEDED")
    if reader_timeout_triggered:
        step_stability_reason_codes.append("READER_TIMEOUT_TRIGGERED")
    if used_heuristic_fallback:
        step_stability_reason_codes.append("HEURISTIC_FALLBACK_USED")
    if run_verify and verifier_status == "failed":
        step_stability_reason_codes.append("VERIFIER_FAILED")
    elif run_verify and verifier_status not in {"completed", "failed"}:
        step_stability_reason_codes.append("VERIFIER_INCOMPLETE")
    if run_status != "succeeded":
        step_stability_status = "fail"
    elif step_stability_reason_codes:
        step_stability_status = "warn"
    else:
        step_stability_status = "pass"
    step_stability_detail = (
        f"run_status={run_status or 'unknown'}, "
        f"reader_timeout_triggered={str(reader_timeout_triggered).lower()}, "
        f"return_mode={return_mode or 'unknown'}, "
        f"heuristic_fallback={str(used_heuristic_fallback).lower()}, "
        f"verifier_status={verifier_status or 'not_run'}"
    )
    step_stability_summary = DeepReadStepStabilitySummary(
        status=step_stability_status,
        reason_codes=step_stability_reason_codes,
        detail=step_stability_detail,
    )
    failure_recovery_reason_codes: list[str] = []
    if run_status in {"failed", "cancelled"}:
        if finished_at is None:
            failure_recovery_reason_codes.append("MISSING_FINISHED_AT")
        if run_error is None and run_error_type is None:
            failure_recovery_reason_codes.append("MISSING_ERROR_DETAIL")
        if claimset_ops_action not in {"retry_suggested", "manual_review_queued", "manual_review_already_open"}:
            failure_recovery_reason_codes.append("MISSING_RECOVERY_GUIDANCE")
    if run_status in {"failed", "cancelled"} and any(
        code in {"MISSING_FINISHED_AT", "MISSING_ERROR_DETAIL"} for code in failure_recovery_reason_codes
    ):
        failure_recovery_status = "fail"
    elif failure_recovery_reason_codes:
        failure_recovery_status = "warn"
    else:
        failure_recovery_status = "pass"
    failure_recovery_detail = (
        f"run_status={run_status or 'unknown'}, "
        f"finished_at={'present' if finished_at else 'missing'}, "
        f"error_detail={'present' if (run_error or run_error_type) else 'missing'}, "
        f"ops_action={claimset_ops_action or 'none'}"
    )
    failure_recovery_summary = DeepReadRecoverySummary(
        status=failure_recovery_status,
        reason_codes=failure_recovery_reason_codes,
        detail=failure_recovery_detail,
    )

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
        DeepReadQualityGateCheck(
            name="evidence_locator_quality",
            status=(
                "warn"
                if (
                    (not reader_eval_written)
                    or reader_eval_approx_span_count > 0
                    or reader_eval_unresolved_span_count > 0
                    or reader_eval_ambiguous_span_count > 0
                )
                else "pass"
            ),
            detail=(
                "reader_eval_missing"
                if not reader_eval_written
                else (
                    f"bbox={reader_eval_bbox_span_count}, "
                    f"text_match={reader_eval_text_match_span_count}, "
                    f"approx={reader_eval_approx_span_count}, "
                    f"unresolved={reader_eval_unresolved_span_count}, "
                    f"ambiguous={reader_eval_ambiguous_span_count}"
                )
            ),
        ),
        DeepReadQualityGateCheck(
            name="section_navigation_signal",
            status="pass" if has_section_navigation_signal else "warn",
            detail=(
                f"claimset_section_count={claimset_section_count}, "
                f"summary_present={str(bool(run_meta.get('section_summary'))).lower()}"
            ),
        ),
        DeepReadQualityGateCheck(
            name="step_stability",
            status=step_stability_status,
            detail=step_stability_detail,
        ),
        DeepReadQualityGateCheck(
            name="failure_recovery",
            status=failure_recovery_status,
            detail=failure_recovery_detail,
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
    hard_fail_codes: list[str] = []
    if run_status != "succeeded":
        reason_codes.append("RUN_NOT_SUCCEEDED")
        hard_fail_codes.append("RUN_NOT_SUCCEEDED")
    if not claimset_resolved_written:
        reason_codes.append("MISSING_CLAIMSET_RESOLVED")
        hard_fail_codes.append("MISSING_CLAIMSET_RESOLVED")
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
        hard_fail_codes=hard_fail_codes,
        checks=checks,
        step_stability_summary=step_stability_summary,
        failure_recovery_summary=failure_recovery_summary,
    )


def build_deepread_context_manifest(
    *,
    paper_id: str,
    run_id: str,
    run_meta: dict[str, Any],
    bootstrap_meta: dict[str, Any],
) -> DeepReadContextManifest | None:
    raw_analysis = bootstrap_meta.get("reader_analysis")
    if not isinstance(raw_analysis, dict) or not raw_analysis:
        raw_analysis = run_meta.get("reader_analysis")
    if not isinstance(raw_analysis, dict) or not raw_analysis:
        return None

    attempts_payload = raw_analysis.get("attempts")
    raw_attempts = attempts_payload if isinstance(attempts_payload, list) else []
    attempts: list[DeepReadContextManifestAttempt] = []
    for idx, raw_attempt in enumerate(raw_attempts, start=1):
        if not isinstance(raw_attempt, dict):
            continue
        attempt = DeepReadContextManifestAttempt(
            attempt_idx=int(raw_attempt.get("attempt_idx") or idx),
            label=str(raw_attempt.get("label") or f"attempt_{idx}"),
            status=str(raw_attempt.get("status") or "unknown"),
            context_mode=str(raw_attempt.get("context_mode") or "").strip() or None,
            context_chars=_safe_int(raw_attempt.get("context_chars")),
            prompt_chars=_safe_int(raw_attempt.get("prompt_chars")),
            estimated_prompt_tokens=_safe_int(raw_attempt.get("estimated_prompt_tokens")),
            estimated_response_tokens=_safe_int(raw_attempt.get("estimated_response_tokens")),
            included_chunk_count=_safe_int(raw_attempt.get("included_chunk_count")),
            unique_section_count=_safe_int(raw_attempt.get("unique_section_count")),
            unique_page_hint_count=_safe_int(raw_attempt.get("unique_page_hint_count")),
            sentence_focus_count=_safe_int(raw_attempt.get("sentence_focus_count")),
            truncated_chunk_count=_safe_int(raw_attempt.get("truncated_chunk_count")),
        )
        attempts.append(attempt)

    selected_attempt_idx = _safe_int(raw_analysis.get("selected_attempt"))
    selected_attempt_label = str(raw_analysis.get("selected_attempt_label") or "").strip() or None
    selected_attempt_summary = _select_context_attempt(
        attempts=attempts,
        selected_attempt_idx=selected_attempt_idx,
        selected_attempt_label=selected_attempt_label,
    )

    effective_attempt_order_payload = raw_analysis.get("effective_attempt_order")
    effective_attempt_order = [
        str(label).strip()
        for label in (effective_attempt_order_payload if isinstance(effective_attempt_order_payload, list) else [])
        if str(label).strip()
    ]
    goal_drift_reason_codes: list[str] = []
    return_mode = str(raw_analysis.get("return_mode") or "").strip() or None
    used_heuristic_fallback = bool(raw_analysis.get("used_heuristic_fallback"))
    final_claim_count = _safe_int(raw_analysis.get("final_claim_count"))
    if not attempts:
        goal_drift_reason_codes.append("NO_RECORDED_ATTEMPTS")
    if selected_attempt_summary is None and attempts:
        goal_drift_reason_codes.append("NO_SELECTED_ATTEMPT_RECORDED")
    if selected_attempt_label and effective_attempt_order and selected_attempt_label not in effective_attempt_order:
        goal_drift_reason_codes.append("SELECTED_ATTEMPT_OUTSIDE_EFFECTIVE_ORDER")
    if used_heuristic_fallback:
        goal_drift_reason_codes.append("HEURISTIC_FALLBACK_USED")
    if return_mode and return_mode.lower() in {"empty", "best_empty"}:
        goal_drift_reason_codes.append("NO_CLAIMS_RETURNED")
    elif final_claim_count is not None and final_claim_count <= 0:
        goal_drift_reason_codes.append("FINAL_CLAIM_COUNT_ZERO")
    goal_drift_summary = DeepReadGoalDriftSummary(
        status="warn" if goal_drift_reason_codes else "pass",
        reason_codes=goal_drift_reason_codes,
        detail=(
            f"return_mode={return_mode or 'unknown'}, "
            f"selected_attempt={selected_attempt_label or 'unknown'}, "
            f"final_claim_count={final_claim_count if final_claim_count is not None else 'unknown'}, "
            f"heuristic_fallback={str(used_heuristic_fallback).lower()}"
        ),
    )

    return DeepReadContextManifest(
        paper_id=paper_id,
        run_id=run_id,
        configured_attempt_order=str(raw_analysis.get("configured_attempt_order") or "").strip() or None,
        effective_attempt_order=effective_attempt_order,
        attempt_count=_safe_int(raw_analysis.get("attempt_count")) or len(attempts),
        return_mode=return_mode,
        selected_attempt=selected_attempt_idx,
        selected_attempt_label=selected_attempt_label,
        final_claim_count=final_claim_count,
        used_heuristic_fallback=used_heuristic_fallback,
        attempts=attempts,
        selected_attempt_summary=selected_attempt_summary,
        goal_drift_summary=goal_drift_summary,
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
    context_manifest = build_deepread_context_manifest(
        paper_id=paper_id,
        run_id=run_id,
        run_meta=run_meta,
        bootstrap_meta=bootstrap_meta,
    )

    contract_path = artifact_dir / "acceptance_contract.json"
    quality_gate_path = artifact_dir / "quality_gate.json"
    atomic_write_text(contract_path, contract.model_dump_json(indent=2))
    atomic_write_text(quality_gate_path, quality_gate.model_dump_json(indent=2))
    written_paths = {
        "acceptance_contract_path": str(contract_path),
        "quality_gate_path": str(quality_gate_path),
    }
    if context_manifest is not None:
        context_manifest_path = artifact_dir / "context_manifest.json"
        atomic_write_text(context_manifest_path, context_manifest.model_dump_json(indent=2))
        written_paths["context_manifest_path"] = str(context_manifest_path)
    return written_paths


def _safe_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except Exception:
        return None


def _select_context_attempt(
    *,
    attempts: list[DeepReadContextManifestAttempt],
    selected_attempt_idx: int | None,
    selected_attempt_label: str | None,
) -> DeepReadContextManifestAttempt | None:
    if selected_attempt_idx is not None:
        for attempt in attempts:
            if attempt.attempt_idx == selected_attempt_idx:
                return attempt
    if selected_attempt_label:
        for attempt in attempts:
            if attempt.label == selected_attempt_label:
                return attempt
    return attempts[-1] if attempts else None
