from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from src.schemas.ml_quality_eval import (
    MLQualityEvalManifest,
    MLQualityEvalReport,
    MLQualityMetricResult,
    MLQualityMetricSpec,
)


def _relative_delta(
    *,
    baseline_value: float,
    candidate_value: float,
    direction: str,
) -> float | None:
    if baseline_value == 0:
        return None
    if direction == "higher_is_better":
        return (candidate_value - baseline_value) / abs(baseline_value)
    return (baseline_value - candidate_value) / abs(baseline_value)


def _absolute_delta(
    *,
    baseline_value: float,
    candidate_value: float,
    direction: str,
) -> float:
    if direction == "higher_is_better":
        return candidate_value - baseline_value
    return baseline_value - candidate_value


def evaluate_metric_gate(
    spec: MLQualityMetricSpec,
    *,
    baseline_value: float,
    candidate_value: float,
) -> MLQualityMetricResult:
    relative_delta = _relative_delta(
        baseline_value=baseline_value,
        candidate_value=candidate_value,
        direction=spec.direction,
    )
    absolute_delta = _absolute_delta(
        baseline_value=baseline_value,
        candidate_value=candidate_value,
        direction=spec.direction,
    )
    reason_codes: list[str] = []
    passed = True

    if absolute_delta < 0:
        if spec.hard_fail_on_regression:
            passed = False
            reason_codes.append("hard_regression")
        elif abs(absolute_delta) > spec.max_allowed_regression:
            passed = False
            reason_codes.append("regression_exceeds_allowance")

    if relative_delta is not None and relative_delta < spec.min_relative_improvement:
        passed = False
        reason_codes.append("insufficient_relative_improvement")

    return MLQualityMetricResult(
        metric_id=spec.metric_id,
        baseline_value=baseline_value,
        candidate_value=candidate_value,
        absolute_delta=round(absolute_delta, 6),
        relative_delta=round(relative_delta, 6) if relative_delta is not None else None,
        passed=passed,
        reason_codes=reason_codes,
    )


def build_ml_quality_eval_report(
    manifest: MLQualityEvalManifest,
    *,
    baseline_metrics: dict[str, float],
    candidate_metrics: dict[str, float],
    baseline_run_ref: str,
    candidate_run_ref: str,
    generated_at: datetime | None = None,
) -> MLQualityEvalReport:
    metric_results: list[MLQualityMetricResult] = []
    reason_codes: list[str] = []
    missing_metrics: list[str] = []

    for spec in manifest.metric_specs:
        if spec.metric_id not in baseline_metrics or spec.metric_id not in candidate_metrics:
            missing_metrics.append(spec.metric_id)
            continue
        result = evaluate_metric_gate(
            spec,
            baseline_value=float(baseline_metrics[spec.metric_id]),
            candidate_value=float(candidate_metrics[spec.metric_id]),
        )
        metric_results.append(result)
        reason_codes.extend(result.reason_codes)

    if missing_metrics:
        reason_codes.append("missing_metrics")
    if not metric_results:
        raise ValueError("at least one metric result is required")

    primary_result = next((result for result in metric_results if result.metric_id == manifest.primary_metric_id), None)
    if primary_result is None:
        raise ValueError("primary metric result is required")

    safety_failures = [
        result
        for result in metric_results
        if result.metric_id in manifest.safety_metric_ids and not result.passed
    ]
    if missing_metrics or safety_failures:
        recommendation = "reject"
    elif primary_result.passed and all(result.passed for result in metric_results):
        recommendation = "promote"
    else:
        recommendation = "hold"

    if recommendation != "promote" and not reason_codes:
        reason_codes.append("gate_not_passed")

    return MLQualityEvalReport(
        eval_id=manifest.eval_id,
        task=manifest.task,
        payload_class=manifest.payload_class,
        fixed_manifest_ref=manifest.fixed_manifest_ref,
        baseline_run_ref=baseline_run_ref,
        candidate_run_ref=candidate_run_ref,
        case_count=len(manifest.case_ids),
        metric_results=metric_results,
        primary_metric_id=manifest.primary_metric_id,
        promotion_recommendation=recommendation,
        reason_codes=reason_codes,
        generated_at=generated_at or datetime.now(timezone.utc),
    )


def write_ml_quality_eval_report(report: MLQualityEvalReport, out: Path) -> Path:
    out = Path(out).expanduser().resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    return out
