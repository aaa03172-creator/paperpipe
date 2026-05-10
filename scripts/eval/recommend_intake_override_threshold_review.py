#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import sys

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.services.intake_override_audit import (  # noqa: E402
    INTAKE_OVERRIDE_AUDIT_CALIBRATION_TARGET_RUNS,
    build_intake_override_audit_calibration_snapshot,
    default_intake_override_audits_root,
    normalize_threshold_review_provenance_kind,
    render_intake_override_threshold_review_markdown,
)
from src.services.runtime_readiness import (  # noqa: E402
    LATEST_INTAKE_OVERRIDE_AUDIT_MIN_AUDITED_DOCS,
    LATEST_INTAKE_OVERRIDE_AUDIT_WARN_RATE,
)


ROOT = REPO_ROOT
_ADJUDICATION_SIGNALS: tuple[str, ...] = ("slot_adjudication", "tagging_adjudication")
_TUNING_TARGET_BY_SIGNAL: dict[str, str] = {
    "slot_adjudication": "slot_classification",
    "tagging_adjudication": "tagging_first_pass",
}
_SIGNALS_BY_TUNING_TARGET: dict[str, tuple[str, ...]] = {
    target: tuple(
        signal for signal, mapped_target in _TUNING_TARGET_BY_SIGNAL.items() if mapped_target == target
    )
    for target in set(_TUNING_TARGET_BY_SIGNAL.values())
}
_TUNING_ACTIONS_BY_TARGET: dict[str, dict[str, str]] = {
    "slot_classification": {
        "action": "audit_slot_ambiguity_thresholds",
        "summary": "Inspect ambiguity thresholds and evidence-bundle cues before policy changes.",
    },
    "tagging_first_pass": {
        "action": "audit_tagging_first_pass_quality",
        "summary": "Inspect first-pass tagging robustness, soft-tag formatting, and evidence-span quality before policy changes.",
    },
}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _compact_intake_override_threshold_review_text(summary: dict[str, Any]) -> str:
    decision = summary.get("decision") if isinstance(summary.get("decision"), dict) else {}
    provenance = summary.get("provenance") if isinstance(summary.get("provenance"), dict) else {}
    snapshot = summary.get("snapshot") if isinstance(summary.get("snapshot"), dict) else {}
    inputs = summary.get("inputs") if isinstance(summary.get("inputs"), dict) else {}

    parts = [f"review_ready={bool(decision.get('review_ready'))}"]

    recommended_action = str(decision.get("recommended_action") or "").strip()
    if recommended_action:
        parts.append(f"action={recommended_action}")

    latest_run_status = str(decision.get("latest_run_status") or "").strip()
    if latest_run_status:
        parts.append(f"latest_run_status={latest_run_status}")

    eligible_runs = snapshot.get("eligible_runs")
    calibration_target_runs = inputs.get("calibration_target_runs")
    if eligible_runs is not None and calibration_target_runs is not None:
        parts.append(f"eligible_runs={int(eligible_runs)}/{int(calibration_target_runs)}")

    provenance_kind = str(provenance.get("kind") or "").strip()
    if provenance_kind:
        parts.append(f"provenance={provenance_kind}")

    if "latest_eligible" in provenance:
        parts.append(f"latest_eligible={bool(provenance.get('latest_eligible'))}")

    latest_run_id = str(decision.get("latest_run_id") or "").strip()
    if latest_run_id:
        parts.append(f"latest_run={latest_run_id}")

    return " ".join(parts)


def _rank_threshold_review_signals(raw_signal_summary: object) -> list[dict[str, Any]]:
    if not isinstance(raw_signal_summary, list):
        return []
    return sorted(
        (
            entry
            for entry in raw_signal_summary
            if isinstance(entry, dict) and int(entry.get("warn_run_count") or 0) > 0
        ),
        key=lambda entry: (
            int(entry.get("warn_run_count") or 0),
            float(entry.get("max_rate") or 0.0),
            str(entry.get("signal") or ""),
        ),
        reverse=True,
    )


def _build_threshold_review_focus_signals(ranked_signals: list[dict[str, Any]], *, max_items: int = 4) -> list[str]:
    focus_signals: list[str] = []
    for entry in ranked_signals[:3]:
        signal = str(entry.get("signal") or "").strip()
        if signal and signal not in focus_signals:
            focus_signals.append(signal)
    for entry in ranked_signals:
        signal = str(entry.get("signal") or "").strip()
        if signal in _ADJUDICATION_SIGNALS and signal not in focus_signals:
            focus_signals.append(signal)
        if len(focus_signals) >= max_items:
            break
    return focus_signals[:max_items]


def _build_threshold_review_tuning_recommendations(
    *,
    focus_signals: list[str],
    latest_warn_signals: list[str],
) -> list[str]:
    active_signals = {signal for signal in [*focus_signals, *latest_warn_signals] if signal}
    recommendations: list[str] = []
    if "slot_adjudication" in active_signals:
        recommendations.append(
            "Audit slot-classification ambiguity thresholds and evidence-bundle cues before widening the warning-threshold review policy."
        )
    if "tagging_adjudication" in active_signals:
        recommendations.append(
            "Audit first-pass tagging robustness, soft-tag formatting, and evidence-span quality before changing warning-threshold heuristics."
        )
    return recommendations


def _build_threshold_review_tuning_targets(
    *,
    focus_signals: list[str],
    latest_warn_signals: list[str],
) -> list[str]:
    active_signals = [signal for signal in [*focus_signals, *latest_warn_signals] if signal]
    targets: list[str] = []
    for signal in active_signals:
        target = _TUNING_TARGET_BY_SIGNAL.get(signal)
        if target and target not in targets:
            targets.append(target)
    return targets


def _build_threshold_review_tuning_actions(tuning_targets: list[str]) -> list[dict[str, str]]:
    actions: list[dict[str, str]] = []
    for target in tuning_targets:
        action_config = _TUNING_ACTIONS_BY_TARGET.get(target)
        if not action_config:
            continue
        actions.append(
            {
                "target": target,
                "action": action_config["action"],
                "summary": action_config["summary"],
            }
        )
    return actions


def _active_threshold_review_signals(
    *,
    focus_signals: list[str],
    latest_warn_signals: list[str],
) -> list[str]:
    active_signals: list[str] = []
    for signal in [*focus_signals, *latest_warn_signals]:
        if signal and signal not in active_signals:
            active_signals.append(signal)
    return active_signals


def _signals_for_tuning_target(
    target: str,
    *,
    active_signals: list[str],
) -> list[str]:
    target_signals = _SIGNALS_BY_TUNING_TARGET.get(target, ())
    return [signal for signal in target_signals if signal in active_signals]


def _action_plan_evidence(
    *,
    target_met: bool,
    eligible_runs: int,
    calibration_target_runs: int,
) -> str:
    if calibration_target_runs <= 0:
        return "No calibration run floor is configured, so manual threshold review can proceed immediately."
    if not target_met:
        return (
            f"{eligible_runs}/{calibration_target_runs} sufficiently-audited runs currently meet the review floor, "
            "so threshold changes should stay blocked until more audit evidence accumulates."
        )
    return (
        f"{eligible_runs}/{calibration_target_runs} sufficiently-audited runs meet the review floor, "
        "so manual threshold review can proceed if operators agree with the evidence."
    )


def _target_action_evidence(
    *,
    target: str,
    signals: list[str],
) -> str:
    if not signals:
        return "No persistent adjudication signals are currently mapped to this tuning target."
    if target == "slot_classification":
        return (
            "Triggered because slot adjudication remains present in the threshold-review focus/latest-warn signals, "
            "which points to slot-classification ambiguity rather than a pure threshold-only issue."
        )
    if target == "tagging_first_pass":
        return (
            "Triggered because tagging adjudication remains present in the threshold-review focus/latest-warn signals, "
            "which points to first-pass tagging robustness rather than a pure threshold-only issue."
        )
    return (
        "Triggered because persistent adjudication pressure is still mapped to this tuning target in the "
        "threshold-review focus/latest-warn signals."
    )


def _build_threshold_review_action_plan(
    *,
    target_met: bool,
    next_step: str,
    tuning_actions: list[dict[str, str]],
    focus_signals: list[str],
    latest_warn_signals: list[str],
    eligible_runs: int,
    calibration_target_runs: int,
) -> list[dict[str, object]]:
    active_signals = _active_threshold_review_signals(
        focus_signals=focus_signals,
        latest_warn_signals=latest_warn_signals,
    )
    action_plan: list[dict[str, object]] = [
        {
            "order": 1,
            "action": next_step,
            "target": None,
            "blocking": True,
            "signals": [],
            "summary": (
                "Gather more sufficiently-audited runs before promoting this threshold review into manual threshold changes."
                if not target_met
                else "Review the current warning threshold and sample floor manually before applying threshold changes."
            ),
            "evidence": _action_plan_evidence(
                target_met=target_met,
                eligible_runs=eligible_runs,
                calibration_target_runs=calibration_target_runs,
            ),
        }
    ]
    for index, item in enumerate(tuning_actions, start=2):
        target = item["target"]
        signals = _signals_for_tuning_target(target, active_signals=active_signals)
        action_plan.append(
            {
                "order": index,
                "action": item["action"],
                "target": target,
                "blocking": False,
                "signals": signals,
                "summary": item["summary"],
                "evidence": _target_action_evidence(target=target, signals=signals),
            }
        )
    return action_plan


def _build_threshold_review_blocking_action(
    action_plan: list[dict[str, object]],
) -> dict[str, object] | None:
    if not action_plan:
        return None
    for item in action_plan:
        if bool(item.get("blocking")):
            return dict(item)
    return dict(action_plan[0])


def _build_threshold_review_blocking_summary(
    blocking_action: dict[str, object] | None,
) -> str | None:
    if not isinstance(blocking_action, dict):
        return None
    action = str(blocking_action.get("action") or "").strip()
    if not action:
        return None
    order = int(blocking_action.get("order") or 0)
    target = str(blocking_action.get("target") or "").strip()
    evidence = str(blocking_action.get("evidence") or "").strip()
    action_text = f"{order}.{action}" if order > 0 else action
    if target:
        action_text = f"{action_text}->{target}"
    if evidence:
        return f"{action_text}: {evidence}"
    return action_text


def build_intake_override_threshold_review_summary(
    *,
    audit_root: Path,
    run_id: str,
    warn_threshold: float,
    min_audited_docs: int,
    calibration_target_runs: int,
    provenance_kind: str = "operator",
    latest_eligible: bool | None = None,
) -> dict[str, Any]:
    normalized_provenance_kind = normalize_threshold_review_provenance_kind(provenance_kind)
    effective_latest_eligible = (
        normalized_provenance_kind == "operator" if latest_eligible is None else bool(latest_eligible)
    )
    snapshot = build_intake_override_audit_calibration_snapshot(
        root=audit_root,
        warn_threshold=warn_threshold,
        min_audited_docs=min_audited_docs,
        calibration_target_runs=calibration_target_runs,
    )

    eligible_runs = int(snapshot.get("eligible_runs") or 0)
    total_runs = int(snapshot.get("total_runs") or 0)
    target_met = eligible_runs >= calibration_target_runs if calibration_target_runs > 0 else True
    recommended_action = "manual_threshold_review" if target_met else "hold_current_threshold"
    latest_run = None
    raw_runs = snapshot.get("runs")
    if isinstance(raw_runs, list) and raw_runs:
        latest_run = raw_runs[0]

    ranked_signals = _rank_threshold_review_signals(snapshot.get("signal_summary"))
    focus_signals = _build_threshold_review_focus_signals(ranked_signals)
    persistent_adjudication_signals = [
        str(entry.get("signal") or "")
        for entry in ranked_signals
        if str(entry.get("signal") or "") in _ADJUDICATION_SIGNALS
    ]
    latest_warn_signals = (
        [str(item).strip() for item in latest_run.get("warn_signals", []) if str(item).strip()]
        if isinstance(latest_run, dict)
        else []
    )
    tuning_recommendations = _build_threshold_review_tuning_recommendations(
        focus_signals=focus_signals,
        latest_warn_signals=latest_warn_signals,
    )
    tuning_targets = _build_threshold_review_tuning_targets(
        focus_signals=focus_signals,
        latest_warn_signals=latest_warn_signals,
    )
    tuning_actions = _build_threshold_review_tuning_actions(tuning_targets)

    if total_runs == 0:
        decision_reason = "no intake override audit runs exist yet, so threshold review should stay on hold"
    elif not target_met:
        decision_reason = (
            f"only {eligible_runs} sufficiently-audited run(s) exist, below the "
            f"{calibration_target_runs}-run review floor"
        )
    else:
        decision_reason = (
            f"{eligible_runs} sufficiently-audited run(s) meet the "
            f"{calibration_target_runs}-run review floor for manual threshold review"
        )
    if persistent_adjudication_signals:
        decision_reason = (
            f"{decision_reason}; persistent adjudication signals: "
            + ", ".join(persistent_adjudication_signals)
        )

    next_step = (
        "collect_more_audit_runs"
        if not target_met
        else "review_warn_threshold_and_sample_floor_manually"
    )
    action_plan = _build_threshold_review_action_plan(
        target_met=target_met,
        next_step=next_step,
        tuning_actions=tuning_actions,
        focus_signals=focus_signals,
        latest_warn_signals=latest_warn_signals,
        eligible_runs=eligible_runs,
        calibration_target_runs=calibration_target_runs,
    )
    blocking_action = _build_threshold_review_blocking_action(action_plan)
    blocking_summary = _build_threshold_review_blocking_summary(blocking_action)

    return {
        "schema_version": "intake_override_threshold_review.v1",
        "generated_at": _utc_now_iso(),
        "run_id": run_id,
        "provenance": {
            "kind": normalized_provenance_kind,
            "latest_eligible": effective_latest_eligible,
            "producer": "recommend_intake_override_threshold_review",
        },
        "inputs": {
            "audit_root": str(audit_root),
            "warn_threshold": float(warn_threshold),
            "min_audited_docs": int(max(min_audited_docs, 0)),
            "calibration_target_runs": int(max(calibration_target_runs, 0)),
        },
        "decision": {
            "recommended_action": recommended_action,
            "review_ready": bool(target_met),
            "decision_reason": decision_reason,
            "next_step": next_step,
            "focus_signals": focus_signals,
            "latest_run_id": str(latest_run.get("run_id") or "") if isinstance(latest_run, dict) else None,
            "latest_run_status": str(latest_run.get("status") or "") if isinstance(latest_run, dict) else None,
            "blocking_action": blocking_action,
            "blocking_summary": blocking_summary,
            "latest_warn_signals": latest_warn_signals,
            "tuning_targets": tuning_targets,
            "tuning_actions": tuning_actions,
            "tuning_recommendations": tuning_recommendations,
            "action_plan": action_plan,
        },
        "snapshot": snapshot,
    }


def run_intake_override_threshold_review(
    *,
    audit_root: Path,
    out_dir: Path,
    run_id: str,
    warn_threshold: float,
    min_audited_docs: int,
    calibration_target_runs: int,
    provenance_kind: str = "operator",
    latest_eligible: bool | None = None,
) -> Path:
    summary = build_intake_override_threshold_review_summary(
        audit_root=audit_root.expanduser().resolve(),
        run_id=run_id,
        warn_threshold=warn_threshold,
        min_audited_docs=min_audited_docs,
        calibration_target_runs=calibration_target_runs,
        provenance_kind=provenance_kind,
        latest_eligible=latest_eligible,
    )
    run_root = out_dir / run_id
    _write_json(run_root / "summary.json", summary)
    _write_text(
        run_root / "audit.md",
        render_intake_override_threshold_review_markdown(summary, run_root=run_root),
    )
    return run_root


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Recommend whether intake override warning thresholds should stay on hold or move into "
            "manual review, based on bounded audit calibration evidence."
        ),
        epilog=(
            "Use the default operator provenance for a real review candidate. "
            "Synthetic or exploratory runs should usually use `--provenance-kind synthetic` or "
            "`--not-latest-eligible` so they stay out of operator-facing latest selection."
        ),
    )
    parser.add_argument(
        "--audit-root",
        default=str(default_intake_override_audits_root()),
        help="Path to the intake override audit run root.",
    )
    parser.add_argument(
        "--out-dir",
        default=str(ROOT / "snapshots" / "intake_override_threshold_review"),
        help="Directory to write the review summary into.",
    )
    parser.add_argument("--run-id", required=True, help="Output run identifier.")
    parser.add_argument(
        "--warn-threshold",
        type=float,
        default=LATEST_INTAKE_OVERRIDE_AUDIT_WARN_RATE,
        help="Current warning heuristic threshold to review.",
    )
    parser.add_argument(
        "--min-audited-docs",
        type=int,
        default=LATEST_INTAKE_OVERRIDE_AUDIT_MIN_AUDITED_DOCS,
        help="Minimum audited document count required for a run to count as calibration evidence.",
    )
    parser.add_argument(
        "--calibration-target-runs",
        type=int,
        default=INTAKE_OVERRIDE_AUDIT_CALIBRATION_TARGET_RUNS,
        help="Minimum count of sufficiently-audited runs before manual threshold review is considered ready.",
    )
    parser.add_argument(
        "--provenance-kind",
        choices=tuple(normalize_threshold_review_provenance_kind(kind) for kind in ("operator", "synthetic")),
        default="operator",
        help="Mark this threshold review artifact as operator-visible or synthetic.",
    )
    parser.add_argument(
        "--latest-eligible",
        dest="latest_eligible",
        action="store_true",
        default=None,
        help="Force this threshold review artifact to be eligible for operator-facing latest selection.",
    )
    parser.add_argument(
        "--not-latest-eligible",
        dest="latest_eligible",
        action="store_false",
        help="Force this threshold review artifact to stay out of operator-facing latest selection.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_arg_parser()
    args = parser.parse_args(argv)
    run_root = run_intake_override_threshold_review(
        audit_root=Path(args.audit_root),
        out_dir=Path(args.out_dir).expanduser().resolve(),
        run_id=str(args.run_id),
        warn_threshold=max(float(args.warn_threshold), 0.0),
        min_audited_docs=max(int(args.min_audited_docs), 0),
        calibration_target_runs=max(int(args.calibration_target_runs), 0),
        provenance_kind=str(args.provenance_kind),
        latest_eligible=args.latest_eligible,
    )
    summary_payload = json.loads((run_root / "summary.json").read_text(encoding="utf-8"))
    print(
        "[recommend_intake_override_threshold_review] "
        + _compact_intake_override_threshold_review_text(summary_payload),
        file=sys.stderr,
    )
    print(run_root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
