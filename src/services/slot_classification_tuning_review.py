from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.schemas.slot_classification_tuning_review import (
    SlotClassificationTuningReviewAction,
    SlotClassificationTuningReviewDecision,
    SlotClassificationTuningReviewInputs,
    SlotClassificationTuningReviewSummary,
)
from src.skills.storage import atomic_write_text

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SLOT_CLASSIFICATION_TUNING_REVIEW_ROOT = (
    REPO_ROOT / "snapshots" / "slot_classification_tuning_review"
)

_SLOT_TARGET = "slot_classification"


def load_slot_classification_tuning_summary(path_or_dir: Path, *, expected_schema_prefix: str) -> tuple[Path, dict[str, Any]]:
    summary_path = path_or_dir.expanduser().resolve()
    if summary_path.is_dir():
        summary_path = summary_path / "summary.json"
    payload = json.loads(summary_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"slot_classification_tuning_summary_expected={summary_path}")
    schema_version = str(payload.get("schema_version") or "")
    if not schema_version.startswith(expected_schema_prefix):
        raise ValueError(f"unsupported_slot_classification_tuning_schema={summary_path}")
    return summary_path, payload


def default_slot_classification_tuning_review_root(*, repo_root: Path | None = None) -> Path:
    base = (repo_root or REPO_ROOT).expanduser().resolve(strict=False)
    return (base / "snapshots" / "slot_classification_tuning_review").resolve(strict=False)


def latest_slot_classification_tuning_review_run(root: Path | None = None) -> Path | None:
    review_root = (root or DEFAULT_SLOT_CLASSIFICATION_TUNING_REVIEW_ROOT).expanduser().resolve(strict=False)
    if not review_root.exists() or not review_root.is_dir():
        return None

    candidates: list[tuple[float, float, str, Path]] = []
    for candidate in review_root.iterdir():
        if not candidate.is_dir():
            continue
        summary_path = candidate / "summary.json"
        if not summary_path.exists():
            continue
        try:
            mtime = summary_path.stat().st_mtime
        except OSError:
            continue
        generated_sort_key = 0.0
        try:
            payload = load_slot_classification_tuning_review_summary(candidate)
        except Exception:
            payload = None
        if isinstance(payload, dict):
            generated_at_text = str(payload.get("generated_at") or "").strip()
            if generated_at_text:
                try:
                    generated_sort_key = datetime.fromisoformat(
                        generated_at_text.replace("Z", "+00:00")
                    ).timestamp()
                except ValueError:
                    generated_sort_key = 0.0
        candidates.append((generated_sort_key, mtime, candidate.name, candidate))

    if not candidates:
        return None
    return max(candidates, key=lambda item: (item[0], item[1], item[2]))[3]


def load_slot_classification_tuning_review_summary(path_or_dir: Path) -> dict[str, Any]:
    _, payload = load_slot_classification_tuning_summary(
        path_or_dir,
        expected_schema_prefix="slot_classification_tuning_review.v",
    )
    return payload


def build_slot_classification_tuning_review_summary(
    *,
    paired_compare_summary: dict[str, Any] | None,
    paired_compare_summary_path: Path | None,
    default_rerun_drift_summary: dict[str, Any] | None,
    default_rerun_drift_summary_path: Path | None,
    boundary_rerun_drift_summary: dict[str, Any] | None,
    boundary_rerun_drift_summary_path: Path | None,
    run_id: str,
    max_default_rerun_drift_rate: float,
    max_boundary_rerun_drift_rate: float,
) -> dict[str, Any]:
    compare_status, compare_blocker, compare_recommendations = _paired_compare_status(paired_compare_summary)
    default_status, default_blocker, default_recommendations = _rerun_status(
        default_rerun_drift_summary,
        max_allowed_drift_rate=max_default_rerun_drift_rate,
        surface_name="default benchmark",
    )
    boundary_status, boundary_blocker, boundary_recommendations = _rerun_status(
        boundary_rerun_drift_summary,
        max_allowed_drift_rate=max_boundary_rerun_drift_rate,
        surface_name="boundary benchmark",
    )

    actions: list[SlotClassificationTuningReviewAction] = []
    recommendations: list[str] = []
    tuning_targets = [_SLOT_TARGET]
    tuning_actions = [
        {
            "target": _SLOT_TARGET,
            "action": "audit_slot_policy_with_paired_compare_and_rerun_drift",
            "summary": "Evaluate any slot prompt or policy candidate with both paired benchmark comparison and rerun-drift evidence before treating it as durable.",
        }
    ]

    if compare_status == "regressed":
        actions.append(
            SlotClassificationTuningReviewAction(
                order=len(actions) + 1,
                action="hold_current_prompt_policy",
                target=_SLOT_TARGET,
                blocking=True,
                summary="Do not treat the candidate slot prompt or policy as an improvement while the paired benchmark shows a regression.",
                evidence=compare_blocker,
            )
        )
        recommendations.extend(compare_recommendations)
    elif compare_status == "tradeoff":
        actions.append(
            SlotClassificationTuningReviewAction(
                order=len(actions) + 1,
                action="review_boundary_rubric_and_expand_goldset",
                target=_SLOT_TARGET,
                blocking=True,
                summary="Mismatch migration is still visible across the paired benchmark, so review the rubric and benchmark rows before treating the prompt change as ready.",
                evidence=compare_blocker,
            )
        )
        recommendations.extend(compare_recommendations)
    elif compare_status == "missing":
        actions.append(
            SlotClassificationTuningReviewAction(
                order=len(actions) + 1,
                action="generate_paired_compare_evidence",
                target=_SLOT_TARGET,
                blocking=True,
                summary="Generate a paired benchmark compare artifact before reviewing the slot prompt or policy change.",
                evidence=compare_blocker,
            )
        )
        recommendations.extend(compare_recommendations)

    if default_status == "warn":
        actions.append(
            SlotClassificationTuningReviewAction(
                order=len(actions) + 1,
                action="collect_default_rerun_stability_evidence",
                target=_SLOT_TARGET,
                blocking=True,
                summary="Same-code reruns on the default benchmark are unstable above the allowed drift rate.",
                evidence=default_blocker,
            )
        )
        recommendations.extend(default_recommendations)
    elif default_status == "missing":
        actions.append(
            SlotClassificationTuningReviewAction(
                order=len(actions) + 1,
                action="generate_default_rerun_drift_audit",
                target=_SLOT_TARGET,
                blocking=True,
                summary="Generate rerun-drift evidence for the default slot benchmark before treating the candidate as review-ready.",
                evidence=default_blocker,
            )
        )
        recommendations.extend(default_recommendations)

    if boundary_status == "warn":
        actions.append(
            SlotClassificationTuningReviewAction(
                order=len(actions) + 1,
                action="collect_boundary_rerun_stability_evidence",
                target=_SLOT_TARGET,
                blocking=True,
                summary="Same-code reruns on the boundary benchmark are unstable above the allowed drift rate.",
                evidence=boundary_blocker,
            )
        )
        recommendations.extend(boundary_recommendations)
    elif boundary_status == "missing":
        actions.append(
            SlotClassificationTuningReviewAction(
                order=len(actions) + 1,
                action="generate_boundary_rerun_drift_audit",
                target=_SLOT_TARGET,
                blocking=True,
                summary="Generate rerun-drift evidence for the boundary slot benchmark before treating the candidate as review-ready.",
                evidence=boundary_blocker,
            )
        )
        recommendations.extend(boundary_recommendations)

    if not actions:
        actions.append(
            SlotClassificationTuningReviewAction(
                order=1,
                action="manual_slot_tuning_review",
                target=_SLOT_TARGET,
                blocking=False,
                summary="Paired benchmark and rerun-drift evidence are both within the requested bounds, so the slot prompt or policy change is ready for manual review.",
                evidence="paired compare passed and rerun-drift checks stayed within the configured tolerance",
            )
        )
        recommendations.append(
            "Paired compare and rerun-drift evidence are both acceptable, so this slot prompt or policy candidate is ready for a manual rubric-based review."
        )

    review_ready = all(action.blocking is False for action in actions)
    recommended_action = actions[0].action
    decision_reason = actions[0].summary
    prompt_change_ready = review_ready
    prompt_change_status = "ready_for_manual_review" if review_ready else "blocked_advisory"
    prompt_change_blocker = actions[0].evidence or actions[0].summary
    next_step = actions[0].action

    decision = SlotClassificationTuningReviewDecision(
        recommended_action=recommended_action,
        review_ready=review_ready,
        decision_reason=decision_reason,
        next_step=next_step,
        latest_compare_run_id=_clean_optional_text((paired_compare_summary or {}).get("run_id")),
        paired_compare_status=compare_status,
        default_rerun_status=default_status,
        boundary_rerun_status=boundary_status,
        prompt_change_ready=prompt_change_ready,
        prompt_change_status=prompt_change_status,
        prompt_change_blocker=prompt_change_blocker,
        tuning_targets=tuning_targets,
        tuning_actions=tuning_actions,
        action_plan=actions,
        tuning_recommendations=_dedupe(recommendations),
    )

    summary = SlotClassificationTuningReviewSummary(
        generated_at=datetime.now(timezone.utc),
        run_id=run_id,
        inputs=SlotClassificationTuningReviewInputs(
            paired_compare_summary_path=str(paired_compare_summary_path) if paired_compare_summary_path else None,
            default_rerun_drift_summary_path=(
                str(default_rerun_drift_summary_path) if default_rerun_drift_summary_path else None
            ),
            boundary_rerun_drift_summary_path=(
                str(boundary_rerun_drift_summary_path) if boundary_rerun_drift_summary_path else None
            ),
            max_default_rerun_drift_rate=max(max_default_rerun_drift_rate, 0.0),
            max_boundary_rerun_drift_rate=max(max_boundary_rerun_drift_rate, 0.0),
        ),
        decision=decision,
        signal_summary={
            "paired_compare_failed_checks": _clean_string_list((paired_compare_summary or {}).get("decision", {}).get("failed_checks") if isinstance((paired_compare_summary or {}).get("decision"), dict) else []),
            "paired_compare_regressions": _clean_string_list((paired_compare_summary or {}).get("decision", {}).get("regressions") if isinstance((paired_compare_summary or {}).get("decision"), dict) else []),
            "paired_compare_error_migration_detected": bool(((paired_compare_summary or {}).get("decision") or {}).get("error_migration_detected")) if isinstance((paired_compare_summary or {}).get("decision"), dict) else False,
            "default_rerun_drift_rate": _safe_float(((default_rerun_drift_summary or {}).get("metrics") or {}).get("drift_rate")),
            "boundary_rerun_drift_rate": _safe_float(((boundary_rerun_drift_summary or {}).get("metrics") or {}).get("drift_rate")),
            "default_rerun_drift_count": _safe_int(((default_rerun_drift_summary or {}).get("metrics") or {}).get("drift_count")),
            "boundary_rerun_drift_count": _safe_int(((boundary_rerun_drift_summary or {}).get("metrics") or {}).get("drift_count")),
        },
    )
    return summary.model_dump(mode="json")


def run_slot_classification_tuning_review(
    *,
    paired_compare_summary_path: Path | None,
    default_rerun_drift_summary_path: Path | None,
    boundary_rerun_drift_summary_path: Path | None,
    out_dir: Path,
    run_id: str,
    max_default_rerun_drift_rate: float,
    max_boundary_rerun_drift_rate: float,
) -> Path:
    paired_compare_summary = None
    resolved_paired_compare_path = None
    if paired_compare_summary_path is not None:
        resolved_paired_compare_path, paired_compare_summary = load_slot_classification_tuning_summary(
            paired_compare_summary_path,
            expected_schema_prefix="slot_classification_paired_compare.v",
        )

    default_rerun_drift_summary = None
    resolved_default_rerun_path = None
    if default_rerun_drift_summary_path is not None:
        resolved_default_rerun_path, default_rerun_drift_summary = load_slot_classification_tuning_summary(
            default_rerun_drift_summary_path,
            expected_schema_prefix="slot_classification_rerun_drift.v",
        )

    boundary_rerun_drift_summary = None
    resolved_boundary_rerun_path = None
    if boundary_rerun_drift_summary_path is not None:
        resolved_boundary_rerun_path, boundary_rerun_drift_summary = load_slot_classification_tuning_summary(
            boundary_rerun_drift_summary_path,
            expected_schema_prefix="slot_classification_rerun_drift.v",
        )

    summary = build_slot_classification_tuning_review_summary(
        paired_compare_summary=paired_compare_summary,
        paired_compare_summary_path=resolved_paired_compare_path,
        default_rerun_drift_summary=default_rerun_drift_summary,
        default_rerun_drift_summary_path=resolved_default_rerun_path,
        boundary_rerun_drift_summary=boundary_rerun_drift_summary,
        boundary_rerun_drift_summary_path=resolved_boundary_rerun_path,
        run_id=run_id,
        max_default_rerun_drift_rate=max_default_rerun_drift_rate,
        max_boundary_rerun_drift_rate=max_boundary_rerun_drift_rate,
    )
    run_root = out_dir / run_id
    atomic_write_text(run_root / "summary.json", json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
    atomic_write_text(run_root / "audit.md", render_slot_classification_tuning_review_markdown(summary))
    return run_root


def render_slot_classification_tuning_review_markdown(summary: dict[str, Any]) -> str:
    decision = summary.get("decision") if isinstance(summary.get("decision"), dict) else {}
    signal_summary = summary.get("signal_summary") if isinstance(summary.get("signal_summary"), dict) else {}
    action_plan = decision.get("action_plan") if isinstance(decision.get("action_plan"), list) else []
    lines = [
        f"# Slot Classification Tuning Review: {summary.get('run_id')}",
        "",
        f"- Generated At: {summary.get('generated_at')}",
        f"- Advisory Only: {bool(summary.get('advisory_only'))}",
        f"- Review Ready: {bool(decision.get('review_ready'))}",
        f"- Recommended Action: {decision.get('recommended_action')}",
        f"- Decision Reason: {decision.get('decision_reason')}",
        f"- Next Step: {decision.get('next_step')}",
        "",
        "## Status",
        f"- Paired Compare Status: {decision.get('paired_compare_status')}",
        f"- Default Rerun Status: {decision.get('default_rerun_status')}",
        f"- Boundary Rerun Status: {decision.get('boundary_rerun_status')}",
        f"- Prompt Change Ready: {bool(decision.get('prompt_change_ready'))}",
        f"- Prompt Change Blocker: {decision.get('prompt_change_blocker')}",
        "",
        "## Signal Summary",
        f"- Paired Compare Failed Checks: {signal_summary.get('paired_compare_failed_checks')}",
        f"- Paired Compare Regressions: {signal_summary.get('paired_compare_regressions')}",
        f"- Paired Compare Error Migration Detected: {signal_summary.get('paired_compare_error_migration_detected')}",
        f"- Default Rerun Drift Rate: {signal_summary.get('default_rerun_drift_rate')}",
        f"- Boundary Rerun Drift Rate: {signal_summary.get('boundary_rerun_drift_rate')}",
        "",
        "## Action Plan",
    ]
    if not action_plan:
        lines.append("- No actions recorded.")
    for item in action_plan:
        if not isinstance(item, dict):
            continue
        lines.append(
            f"- {item.get('order')}. {item.get('action')} ({item.get('target') or '-'}) blocking={bool(item.get('blocking'))}: {item.get('summary')}"
        )
    recommendations = decision.get("tuning_recommendations") if isinstance(decision.get("tuning_recommendations"), list) else []
    if recommendations:
        lines.extend(["", "## Recommendations"])
        for recommendation in recommendations:
            lines.append(f"- {recommendation}")
    return "\n".join(lines) + "\n"


def _paired_compare_status(summary: dict[str, Any] | None) -> tuple[str, str, list[str]]:
    if not isinstance(summary, dict):
        return "missing", "no paired compare summary was provided", [
            "Generate a paired compare artifact before treating a slot prompt or policy candidate as review-ready."
        ]
    decision = summary.get("decision")
    if not isinstance(decision, dict):
        return "missing", "paired compare summary is missing its decision block", [
            "Regenerate the paired compare artifact because its decision block is missing."
        ]
    failed_checks = _clean_string_list(decision.get("failed_checks"))
    regressions = _clean_string_list(decision.get("regressions"))
    error_migration = bool(decision.get("error_migration_detected"))
    if failed_checks or regressions:
        return (
            "regressed",
            f"paired compare shows failed_checks={failed_checks or ['-']} and regressions={regressions or ['-']}",
            [
                "Do not treat the candidate slot prompt or policy as an improvement while the paired benchmark regresses.",
            ],
        )
    if error_migration or bool(decision.get("tradeoff_review_required")):
        return (
            "tradeoff",
            "paired compare still shows mismatch migration across the benchmark surfaces",
            [
                "Mismatch migration is still visible across the paired benchmark, so expand adjudicated boundary evidence before accepting the prompt change.",
            ],
        )
    if bool(decision.get("passed")):
        return (
            "ok",
            "paired compare passed without benchmark regression or mismatch migration",
            [
                "Paired compare evidence looks acceptable, but rerun stability should still be checked before treating the result as durable.",
            ],
        )
    return "warn", "paired compare did not pass cleanly", [
        "Review the paired compare artifact because it did not pass cleanly."
    ]


def _rerun_status(
    summary: dict[str, Any] | None,
    *,
    max_allowed_drift_rate: float,
    surface_name: str,
) -> tuple[str, str, list[str]]:
    if not isinstance(summary, dict):
        return "missing", f"no rerun-drift summary was provided for the {surface_name}", [
            f"Generate rerun-drift evidence for the {surface_name} before treating a live replay delta as durable."
        ]
    metrics = summary.get("metrics")
    if not isinstance(metrics, dict):
        return "missing", f"rerun-drift summary is missing metrics for the {surface_name}", [
            f"Regenerate the {surface_name} rerun-drift artifact because its metrics block is missing."
        ]
    drift_rate = _safe_float(metrics.get("drift_rate"))
    drift_count = _safe_int(metrics.get("drift_count"))
    if drift_rate > max_allowed_drift_rate:
        return (
            "warn",
            f"{surface_name} rerun drift is {drift_count} row(s) / {drift_rate:.4f}, above the allowed {max_allowed_drift_rate:.4f}",
            [
                f"Same-code reruns on the {surface_name} are not yet stable enough for a durable prompt/policy conclusion.",
            ],
        )
    return (
        "ok",
        f"{surface_name} rerun drift is {drift_count} row(s) / {drift_rate:.4f}, within the allowed {max_allowed_drift_rate:.4f}",
        [
            f"{surface_name.capitalize()} rerun drift is within the requested bound.",
        ],
    )


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if not text or text in seen:
            continue
        ordered.append(text)
        seen.add(text)
    return ordered


def _clean_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [text for text in (_clean_optional_text(item) for item in value) if text]


def _clean_optional_text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _safe_float(value: Any) -> float | None:
    try:
        if value in (None, ""):
            return None
        return float(value)
    except Exception:
        return None


def _safe_int(value: Any) -> int | None:
    try:
        if value in (None, ""):
            return None
        return int(value)
    except Exception:
        return None
