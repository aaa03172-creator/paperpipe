from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.schemas.slot_classification_paired_compare import (
    SlotClassificationPairedCompareCheck,
    SlotClassificationPairedCompareDecision,
    SlotClassificationPairedCompareInputs,
    SlotClassificationPairedCompareSummary,
    SlotClassificationPairedCompareSurface,
    SlotClassificationPairedCompareThresholds,
)
from src.skills.storage import atomic_write_text


def load_slot_classification_audit_summary(path_or_dir: Path) -> tuple[Path, dict[str, Any]]:
    summary_path = path_or_dir.expanduser().resolve()
    if summary_path.is_dir():
        summary_path = summary_path / "summary.json"
    payload = json.loads(summary_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"slot_classification_summary_dict_expected={summary_path}")
    schema_version = str(payload.get("schema_version") or "")
    if not schema_version.startswith("slot_classification_goldset_audit_summary.v"):
        raise ValueError(f"unsupported_slot_classification_summary_schema={summary_path}")
    return summary_path, payload


def build_slot_classification_paired_compare(
    *,
    baseline_default_summary: dict[str, Any],
    baseline_default_summary_path: Path,
    baseline_boundary_summary: dict[str, Any],
    baseline_boundary_summary_path: Path,
    candidate_default_summary: dict[str, Any],
    candidate_default_summary_path: Path,
    candidate_boundary_summary: dict[str, Any],
    candidate_boundary_summary_path: Path,
    run_id: str,
    thresholds: SlotClassificationPairedCompareThresholds | None = None,
) -> SlotClassificationPairedCompareSummary:
    thresholds = thresholds or SlotClassificationPairedCompareThresholds()
    baseline = SlotClassificationPairedCompareInputs(
        default_template=_build_surface(
            summary=baseline_default_summary,
            summary_path=baseline_default_summary_path,
        ),
        boundary_companion=_build_surface(
            summary=baseline_boundary_summary,
            summary_path=baseline_boundary_summary_path,
        ),
    )
    candidate = SlotClassificationPairedCompareInputs(
        default_template=_build_surface(
            summary=candidate_default_summary,
            summary_path=candidate_default_summary_path,
        ),
        boundary_companion=_build_surface(
            summary=candidate_boundary_summary,
            summary_path=candidate_boundary_summary_path,
        ),
    )

    checks = _build_checks(baseline=baseline, candidate=candidate, thresholds=thresholds)
    failed_checks = [check.name for check in checks if not check.passed]
    regressions = _build_regressions(baseline=baseline, candidate=candidate)

    default_resolved, default_new = _mismatch_delta(
        baseline.default_template.documents_with_mismatch,
        candidate.default_template.documents_with_mismatch,
    )
    boundary_resolved, boundary_new = _mismatch_delta(
        baseline.boundary_companion.documents_with_mismatch,
        candidate.boundary_companion.documents_with_mismatch,
    )
    surfaces_with_mismatch_migration = []
    if default_resolved and default_new:
        surfaces_with_mismatch_migration.append("default_template")
    if boundary_resolved and boundary_new:
        surfaces_with_mismatch_migration.append("boundary_companion")

    error_migration_detected = bool(surfaces_with_mismatch_migration)
    tradeoff_review_required = error_migration_detected

    decision_reason = "paired slot-classification benchmarks stayed at or above the requested baseline"
    if tradeoff_review_required:
        decision_reason = (
            "paired slot-classification benchmarks require review because the mismatch identities moved across one or more surfaces"
        )
    if failed_checks or regressions:
        decision_reason = (
            "candidate paired slot-classification benchmarks regressed one or more baseline metrics or mismatch counts"
        )

    decision = SlotClassificationPairedCompareDecision(
        passed=not failed_checks and not regressions and not tradeoff_review_required,
        failed_checks=failed_checks,
        regressions=regressions,
        error_migration_detected=error_migration_detected,
        tradeoff_review_required=tradeoff_review_required,
        surfaces_with_mismatch_migration=surfaces_with_mismatch_migration,
        checks=checks,
        default_template_resolved_mismatches=default_resolved,
        default_template_new_mismatches=default_new,
        boundary_companion_resolved_mismatches=boundary_resolved,
        boundary_companion_new_mismatches=boundary_new,
        decision_reason=decision_reason,
    )

    return SlotClassificationPairedCompareSummary(
        generated_at=datetime.now(timezone.utc),
        run_id=run_id,
        baseline=baseline,
        candidate=candidate,
        thresholds=thresholds,
        decision=decision,
    )


def write_slot_classification_paired_compare(
    *,
    summary: SlotClassificationPairedCompareSummary,
    out_dir: Path,
) -> Path:
    run_root = out_dir / summary.run_id
    atomic_write_text(run_root / "summary.json", summary.model_dump_json(indent=2))
    atomic_write_text(
        run_root / "compare.md",
        render_slot_classification_paired_compare_markdown(summary=summary),
    )
    return run_root


def render_slot_classification_paired_compare_markdown(
    *,
    summary: SlotClassificationPairedCompareSummary,
) -> str:
    lines = [
        f"# Slot Classification Paired Compare: {summary.run_id}",
        "",
        f"- Generated At: {summary.generated_at.isoformat()}",
        f"- Passed: {summary.decision.passed}",
        f"- Decision Reason: {summary.decision.decision_reason}",
        "",
        "## Baseline",
        _surface_line("default_template", summary.baseline.default_template),
        _surface_line("boundary_companion", summary.baseline.boundary_companion),
        "",
        "## Candidate",
        _surface_line("default_template", summary.candidate.default_template),
        _surface_line("boundary_companion", summary.candidate.boundary_companion),
        "",
        "## Checks",
    ]
    if not summary.decision.checks:
        lines.append("- No checks recorded.")
    for check in summary.decision.checks:
        lines.append(
            f"- {check.name}: baseline={check.baseline}, new={check.new}, required={check.required}, passed={check.passed}"
        )
    lines.extend(
        [
            "",
            "## Mismatch Deltas",
            (
                "- default_template: "
                f"resolved={summary.decision.default_template_resolved_mismatches or ['-']}, "
                f"new={summary.decision.default_template_new_mismatches or ['-']}"
            ),
            (
                "- boundary_companion: "
                f"resolved={summary.decision.boundary_companion_resolved_mismatches or ['-']}, "
                f"new={summary.decision.boundary_companion_new_mismatches or ['-']}"
            ),
            "",
            "## Decision",
            f"- Failed Checks: {summary.decision.failed_checks or ['-']}",
            f"- Regressions: {summary.decision.regressions or ['-']}",
            f"- Surfaces With Mismatch Migration: {summary.decision.surfaces_with_mismatch_migration or ['-']}",
            f"- Error Migration Detected: {summary.decision.error_migration_detected}",
        ]
    )
    return "\n".join(lines) + "\n"


def _surface_line(name: str, surface: SlotClassificationPairedCompareSurface) -> str:
    return (
        f"- {name}: run_id={surface.run_id}, accuracy={surface.accuracy:.4f}, "
        f"coverage={surface.prediction_coverage_rate:.4f}, mismatch_count={surface.mismatch_count}, "
        f"mismatches={surface.documents_with_mismatch}"
    )


def _build_surface(*, summary: dict[str, Any], summary_path: Path) -> SlotClassificationPairedCompareSurface:
    metrics = summary.get("metrics")
    if not isinstance(metrics, dict):
        raise ValueError(f"slot_classification_metrics_missing={summary_path}")
    return SlotClassificationPairedCompareSurface(
        summary_path=str(summary_path),
        run_id=_clean_optional_text(summary.get("run_id")),
        generated_at=_coerce_optional_datetime(summary.get("generated_at")),
        document_count=_as_int(metrics.get("document_count")),
        evaluated_count=_as_int(metrics.get("evaluated_count")),
        mismatch_count=_as_int(metrics.get("mismatch_count")),
        accuracy=_as_float(metrics.get("accuracy")),
        prediction_coverage_rate=_as_float(metrics.get("prediction_coverage_rate")),
        documents_with_mismatch=_clean_string_list(summary.get("documents_with_mismatch")),
    )


def _build_checks(
    *,
    baseline: SlotClassificationPairedCompareInputs,
    candidate: SlotClassificationPairedCompareInputs,
    thresholds: SlotClassificationPairedCompareThresholds,
) -> list[SlotClassificationPairedCompareCheck]:
    return [
        SlotClassificationPairedCompareCheck(
            name="default_template_accuracy",
            baseline=baseline.default_template.accuracy,
            new=candidate.default_template.accuracy,
            required=baseline.default_template.accuracy - thresholds.allow_default_accuracy_drop,
            passed=candidate.default_template.accuracy
            >= (baseline.default_template.accuracy - thresholds.allow_default_accuracy_drop),
            direction="higher_is_better",
        ),
        SlotClassificationPairedCompareCheck(
            name="boundary_companion_accuracy",
            baseline=baseline.boundary_companion.accuracy,
            new=candidate.boundary_companion.accuracy,
            required=baseline.boundary_companion.accuracy - thresholds.allow_boundary_accuracy_drop,
            passed=candidate.boundary_companion.accuracy
            >= (baseline.boundary_companion.accuracy - thresholds.allow_boundary_accuracy_drop),
            direction="higher_is_better",
        ),
        SlotClassificationPairedCompareCheck(
            name="default_template_prediction_coverage",
            baseline=baseline.default_template.prediction_coverage_rate,
            new=candidate.default_template.prediction_coverage_rate,
            required=baseline.default_template.prediction_coverage_rate - thresholds.allow_default_coverage_drop,
            passed=candidate.default_template.prediction_coverage_rate
            >= (baseline.default_template.prediction_coverage_rate - thresholds.allow_default_coverage_drop),
            direction="higher_is_better",
        ),
        SlotClassificationPairedCompareCheck(
            name="boundary_companion_prediction_coverage",
            baseline=baseline.boundary_companion.prediction_coverage_rate,
            new=candidate.boundary_companion.prediction_coverage_rate,
            required=baseline.boundary_companion.prediction_coverage_rate - thresholds.allow_boundary_coverage_drop,
            passed=candidate.boundary_companion.prediction_coverage_rate
            >= (baseline.boundary_companion.prediction_coverage_rate - thresholds.allow_boundary_coverage_drop),
            direction="higher_is_better",
        ),
        SlotClassificationPairedCompareCheck(
            name="default_template_mismatch_count",
            baseline=float(baseline.default_template.mismatch_count),
            new=float(candidate.default_template.mismatch_count),
            required=float(baseline.default_template.mismatch_count + thresholds.allow_default_mismatch_increase),
            passed=candidate.default_template.mismatch_count
            <= (baseline.default_template.mismatch_count + thresholds.allow_default_mismatch_increase),
            direction="lower_is_better",
        ),
        SlotClassificationPairedCompareCheck(
            name="boundary_companion_mismatch_count",
            baseline=float(baseline.boundary_companion.mismatch_count),
            new=float(candidate.boundary_companion.mismatch_count),
            required=float(baseline.boundary_companion.mismatch_count + thresholds.allow_boundary_mismatch_increase),
            passed=candidate.boundary_companion.mismatch_count
            <= (baseline.boundary_companion.mismatch_count + thresholds.allow_boundary_mismatch_increase),
            direction="lower_is_better",
        ),
    ]


def _build_regressions(
    *,
    baseline: SlotClassificationPairedCompareInputs,
    candidate: SlotClassificationPairedCompareInputs,
) -> list[str]:
    regressions: list[str] = []
    if candidate.default_template.accuracy < baseline.default_template.accuracy:
        regressions.append("default_template_accuracy")
    if candidate.boundary_companion.accuracy < baseline.boundary_companion.accuracy:
        regressions.append("boundary_companion_accuracy")
    if candidate.default_template.prediction_coverage_rate < baseline.default_template.prediction_coverage_rate:
        regressions.append("default_template_prediction_coverage")
    if candidate.boundary_companion.prediction_coverage_rate < baseline.boundary_companion.prediction_coverage_rate:
        regressions.append("boundary_companion_prediction_coverage")
    if candidate.default_template.mismatch_count > baseline.default_template.mismatch_count:
        regressions.append("default_template_mismatch_count")
    if candidate.boundary_companion.mismatch_count > baseline.boundary_companion.mismatch_count:
        regressions.append("boundary_companion_mismatch_count")
    return regressions


def _mismatch_delta(baseline: list[str], candidate: list[str]) -> tuple[list[str], list[str]]:
    baseline_set = {value for value in baseline if value}
    candidate_set = {value for value in candidate if value}
    return sorted(baseline_set - candidate_set), sorted(candidate_set - baseline_set)


def _as_int(value: Any) -> int:
    try:
        return int(value or 0)
    except Exception:
        return 0


def _as_float(value: Any) -> float:
    try:
        return float(value or 0.0)
    except Exception:
        return 0.0


def _coerce_optional_datetime(value: Any) -> datetime | None:
    text = _clean_optional_text(value)
    if text is None:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except Exception:
        return None


def _clean_optional_text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _clean_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    cleaned: list[str] = []
    for item in value:
        text = _clean_optional_text(item)
        if text is not None:
            cleaned.append(text)
    return cleaned
