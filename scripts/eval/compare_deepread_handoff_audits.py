#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _utc_now_tag() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


def _safe_name(value: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9._-]", "_", value)
    normalized = re.sub(r"_+", "_", normalized).strip("_")
    return normalized or "snapshot"


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"invalid_json_object={path}")
    return payload


def _resolve_summary_path(path_or_dir: Path) -> Path:
    if path_or_dir.is_dir():
        candidate = path_or_dir / "summary.json"
        if not candidate.exists():
            raise FileNotFoundError(f"summary_missing={candidate}")
        return candidate
    return path_or_dir


def _load_summary(path_or_dir: Path) -> tuple[Path, dict[str, Any]]:
    summary_path = _resolve_summary_path(path_or_dir)
    if not summary_path.exists():
        raise FileNotFoundError(f"summary_missing={summary_path}")
    payload = _load_json(summary_path)
    if str(payload.get("schema_version") or "") != "deepread_handoff_audit.v1":
        raise RuntimeError(f"unsupported_schema_version={summary_path}")
    return summary_path, payload


def _as_int(payload: dict[str, Any], key: str) -> int:
    try:
        return int(payload.get(key) or 0)
    except Exception:
        return 0


def _status_count(payload: dict[str, Any], field: str, status: str) -> int:
    counts = payload.get(field)
    if not isinstance(counts, dict):
        return 0
    try:
        return int(counts.get(status) or 0)
    except Exception:
        return 0


def _warn_or_fail_count(payload: dict[str, Any], field: str) -> int:
    return _status_count(payload, field, "warn") + _status_count(payload, field, "fail")


def _rate(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return numerator / denominator


def compare_summaries(
    baseline_summary: dict[str, Any],
    new_summary: dict[str, Any],
    *,
    allow_review_ready_drop: float = 0.0,
    allow_goal_drift_increase: float = 0.0,
    allow_section_navigation_signal_increase: float = 0.0,
    allow_step_stability_increase: float = 0.0,
    allow_failure_recovery_increase: float = 0.0,
    allow_goal_drift_missing_increase: float = 0.0,
    allow_step_stability_missing_increase: float = 0.0,
    allow_failure_recovery_missing_increase: float = 0.0,
    allow_context_missing_increase: float = 0.0,
) -> dict[str, Any]:
    baseline_run_count = max(1, _as_int(baseline_summary, "run_count"))
    new_run_count = max(1, _as_int(new_summary, "run_count"))

    baseline_review_ready_rate = _rate(_as_int(baseline_summary, "review_ready_count"), baseline_run_count)
    new_review_ready_rate = _rate(_as_int(new_summary, "review_ready_count"), new_run_count)
    baseline_goal_drift_warn_rate = _rate(
        _warn_or_fail_count(baseline_summary, "goal_drift_status_counts"),
        baseline_run_count,
    )
    new_goal_drift_warn_rate = _rate(
        _warn_or_fail_count(new_summary, "goal_drift_status_counts"),
        new_run_count,
    )
    baseline_section_navigation_warn_rate = _rate(
        _warn_or_fail_count(baseline_summary, "section_navigation_signal_status_counts"),
        baseline_run_count,
    )
    new_section_navigation_warn_rate = _rate(
        _warn_or_fail_count(new_summary, "section_navigation_signal_status_counts"),
        new_run_count,
    )
    baseline_step_warn_rate = _rate(
        _warn_or_fail_count(baseline_summary, "step_stability_status_counts"),
        baseline_run_count,
    )
    new_step_warn_rate = _rate(
        _warn_or_fail_count(new_summary, "step_stability_status_counts"),
        new_run_count,
    )
    baseline_recovery_warn_rate = _rate(
        _warn_or_fail_count(baseline_summary, "failure_recovery_status_counts"),
        baseline_run_count,
    )
    new_recovery_warn_rate = _rate(
        _warn_or_fail_count(new_summary, "failure_recovery_status_counts"),
        new_run_count,
    )
    baseline_goal_missing_rate = _rate(
        _status_count(baseline_summary, "goal_drift_status_counts", "missing"),
        baseline_run_count,
    )
    new_goal_missing_rate = _rate(
        _status_count(new_summary, "goal_drift_status_counts", "missing"),
        new_run_count,
    )
    baseline_step_missing_rate = _rate(
        _status_count(baseline_summary, "step_stability_status_counts", "missing"),
        baseline_run_count,
    )
    new_step_missing_rate = _rate(
        _status_count(new_summary, "step_stability_status_counts", "missing"),
        new_run_count,
    )
    baseline_recovery_missing_rate = _rate(
        _status_count(baseline_summary, "failure_recovery_status_counts", "missing"),
        baseline_run_count,
    )
    new_recovery_missing_rate = _rate(
        _status_count(new_summary, "failure_recovery_status_counts", "missing"),
        new_run_count,
    )
    baseline_context_missing_rate = _rate(_as_int(baseline_summary, "context_manifest_missing_count"), baseline_run_count)
    new_context_missing_rate = _rate(_as_int(new_summary, "context_manifest_missing_count"), new_run_count)

    checks = [
        {
            "name": "review_ready_rate",
            "baseline": baseline_review_ready_rate,
            "new": new_review_ready_rate,
            "required": baseline_review_ready_rate - allow_review_ready_drop,
            "passed": new_review_ready_rate >= (baseline_review_ready_rate - allow_review_ready_drop),
            "direction": "higher_is_better",
        },
        {
            "name": "goal_drift_warn_or_fail_rate",
            "baseline": baseline_goal_drift_warn_rate,
            "new": new_goal_drift_warn_rate,
            "required": baseline_goal_drift_warn_rate + allow_goal_drift_increase,
            "passed": new_goal_drift_warn_rate <= (baseline_goal_drift_warn_rate + allow_goal_drift_increase),
            "direction": "lower_is_better",
        },
        {
            "name": "section_navigation_signal_warn_or_fail_rate",
            "baseline": baseline_section_navigation_warn_rate,
            "new": new_section_navigation_warn_rate,
            "required": baseline_section_navigation_warn_rate + allow_section_navigation_signal_increase,
            "passed": new_section_navigation_warn_rate <= (
                baseline_section_navigation_warn_rate + allow_section_navigation_signal_increase
            ),
            "direction": "lower_is_better",
        },
        {
            "name": "step_stability_warn_or_fail_rate",
            "baseline": baseline_step_warn_rate,
            "new": new_step_warn_rate,
            "required": baseline_step_warn_rate + allow_step_stability_increase,
            "passed": new_step_warn_rate <= (baseline_step_warn_rate + allow_step_stability_increase),
            "direction": "lower_is_better",
        },
        {
            "name": "failure_recovery_warn_or_fail_rate",
            "baseline": baseline_recovery_warn_rate,
            "new": new_recovery_warn_rate,
            "required": baseline_recovery_warn_rate + allow_failure_recovery_increase,
            "passed": new_recovery_warn_rate <= (baseline_recovery_warn_rate + allow_failure_recovery_increase),
            "direction": "lower_is_better",
        },
        {
            "name": "goal_drift_missing_rate",
            "baseline": baseline_goal_missing_rate,
            "new": new_goal_missing_rate,
            "required": baseline_goal_missing_rate + allow_goal_drift_missing_increase,
            "passed": new_goal_missing_rate <= (baseline_goal_missing_rate + allow_goal_drift_missing_increase),
            "direction": "lower_is_better",
        },
        {
            "name": "step_stability_missing_rate",
            "baseline": baseline_step_missing_rate,
            "new": new_step_missing_rate,
            "required": baseline_step_missing_rate + allow_step_stability_missing_increase,
            "passed": new_step_missing_rate <= (baseline_step_missing_rate + allow_step_stability_missing_increase),
            "direction": "lower_is_better",
        },
        {
            "name": "failure_recovery_missing_rate",
            "baseline": baseline_recovery_missing_rate,
            "new": new_recovery_missing_rate,
            "required": baseline_recovery_missing_rate + allow_failure_recovery_missing_increase,
            "passed": new_recovery_missing_rate <= (baseline_recovery_missing_rate + allow_failure_recovery_missing_increase),
            "direction": "lower_is_better",
        },
        {
            "name": "context_manifest_missing_rate",
            "baseline": baseline_context_missing_rate,
            "new": new_context_missing_rate,
            "required": baseline_context_missing_rate + allow_context_missing_increase,
            "passed": new_context_missing_rate <= (baseline_context_missing_rate + allow_context_missing_increase),
            "direction": "lower_is_better",
        },
    ]

    failed_checks = [check["name"] for check in checks if not check["passed"]]
    regressions: list[str] = []
    if new_review_ready_rate < baseline_review_ready_rate:
        regressions.append("review_ready_rate")
    if new_goal_drift_warn_rate > baseline_goal_drift_warn_rate:
        regressions.append("goal_drift_warn_or_fail_rate")
    if new_section_navigation_warn_rate > baseline_section_navigation_warn_rate:
        regressions.append("section_navigation_signal_warn_or_fail_rate")
    if new_step_warn_rate > baseline_step_warn_rate:
        regressions.append("step_stability_warn_or_fail_rate")
    if new_recovery_warn_rate > baseline_recovery_warn_rate:
        regressions.append("failure_recovery_warn_or_fail_rate")
    if new_goal_missing_rate > baseline_goal_missing_rate:
        regressions.append("goal_drift_missing_rate")
    if new_step_missing_rate > baseline_step_missing_rate:
        regressions.append("step_stability_missing_rate")
    if new_recovery_missing_rate > baseline_recovery_missing_rate:
        regressions.append("failure_recovery_missing_rate")
    if new_context_missing_rate > baseline_context_missing_rate:
        regressions.append("context_manifest_missing_rate")

    return {
        "passed": len(failed_checks) == 0 and len(regressions) == 0,
        "checks": checks,
        "failed_checks": failed_checks,
        "regressions": regressions,
        "deltas": {
            "review_ready_rate": new_review_ready_rate - baseline_review_ready_rate,
            "goal_drift_warn_or_fail_rate": new_goal_drift_warn_rate - baseline_goal_drift_warn_rate,
            "section_navigation_signal_warn_or_fail_rate": (
                new_section_navigation_warn_rate - baseline_section_navigation_warn_rate
            ),
            "step_stability_warn_or_fail_rate": new_step_warn_rate - baseline_step_warn_rate,
            "failure_recovery_warn_or_fail_rate": new_recovery_warn_rate - baseline_recovery_warn_rate,
            "goal_drift_missing_rate": new_goal_missing_rate - baseline_goal_missing_rate,
            "step_stability_missing_rate": new_step_missing_rate - baseline_step_missing_rate,
            "failure_recovery_missing_rate": new_recovery_missing_rate - baseline_recovery_missing_rate,
            "context_manifest_missing_rate": new_context_missing_rate - baseline_context_missing_rate,
        },
    }


def _promote_snapshot(*, new_summary_path: Path, promote_dir: Path, report: dict[str, Any]) -> Path:
    run_id = str(report.get("new", {}).get("run_id") or "")
    tag = _safe_name(run_id) if run_id else _utc_now_tag()
    source_dir = new_summary_path.parent
    target = promote_dir / tag
    target.mkdir(parents=True, exist_ok=True)

    shutil.copy2(source_dir / "summary.json", target / "summary.json")
    details_path = source_dir / "details.json"
    if details_path.exists():
        shutil.copy2(details_path, target / "details.json")
    (target / "promotion_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return target


def compare_deepread_handoff_audits(
    *,
    baseline: Path,
    new: Path,
    out: Path,
    allow_review_ready_drop: float = 0.0,
    allow_goal_drift_increase: float = 0.0,
    allow_section_navigation_signal_increase: float = 0.0,
    allow_step_stability_increase: float = 0.0,
    allow_failure_recovery_increase: float = 0.0,
    allow_goal_drift_missing_increase: float = 0.0,
    allow_step_stability_missing_increase: float = 0.0,
    allow_failure_recovery_missing_increase: float = 0.0,
    allow_context_missing_increase: float = 0.0,
    promote_dir: Path | None = None,
) -> dict[str, Any]:
    baseline_path, baseline_summary = _load_summary(baseline)
    new_path, new_summary = _load_summary(new)

    decision = compare_summaries(
        baseline_summary,
        new_summary,
        allow_review_ready_drop=allow_review_ready_drop,
        allow_goal_drift_increase=allow_goal_drift_increase,
        allow_section_navigation_signal_increase=allow_section_navigation_signal_increase,
        allow_step_stability_increase=allow_step_stability_increase,
        allow_failure_recovery_increase=allow_failure_recovery_increase,
        allow_goal_drift_missing_increase=allow_goal_drift_missing_increase,
        allow_step_stability_missing_increase=allow_step_stability_missing_increase,
        allow_failure_recovery_missing_increase=allow_failure_recovery_missing_increase,
        allow_context_missing_increase=allow_context_missing_increase,
    )

    report = {
        "schema_version": "deepread_handoff_compare.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "baseline": {
            "path": str(baseline_path),
            "run_id": baseline_summary.get("run_id"),
            "run_count": baseline_summary.get("run_count"),
        },
        "new": {
            "path": str(new_path),
            "run_id": new_summary.get("run_id"),
            "run_count": new_summary.get("run_count"),
        },
        "thresholds": {
            "allow_review_ready_drop": allow_review_ready_drop,
            "allow_goal_drift_increase": allow_goal_drift_increase,
            "allow_section_navigation_signal_increase": allow_section_navigation_signal_increase,
            "allow_step_stability_increase": allow_step_stability_increase,
            "allow_failure_recovery_increase": allow_failure_recovery_increase,
            "allow_goal_drift_missing_increase": allow_goal_drift_missing_increase,
            "allow_step_stability_missing_increase": allow_step_stability_missing_increase,
            "allow_failure_recovery_missing_increase": allow_failure_recovery_missing_increase,
            "allow_context_missing_increase": allow_context_missing_increase,
        },
        "decision": decision,
    }

    if promote_dir and decision["passed"]:
        promoted_to = _promote_snapshot(new_summary_path=new_path, promote_dir=promote_dir, report=report)
        report["promotion"] = {"promoted": True, "path": str(promoted_to)}
    else:
        report["promotion"] = {"promoted": False, "path": None}

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    out.with_suffix(".txt").write_text(
        "\n".join(
            [
                f"baseline={baseline_path}",
                f"new={new_path}",
                f"passed={decision['passed']}",
                f"failed_checks={','.join(decision['failed_checks']) if decision['failed_checks'] else '-'}",
                f"regressions={','.join(decision['regressions']) if decision['regressions'] else '-'}",
                f"promotion={report['promotion']['path'] or '-'}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare deep-read handoff audit summaries and decide whether the new summary regresses.")
    parser.add_argument("--baseline", required=True, help="Baseline summary.json path or audit run directory")
    parser.add_argument("--new", required=True, help="New summary.json path or audit run directory")
    parser.add_argument("--out", required=True, help="Output compare report JSON path")
    parser.add_argument("--allow-review-ready-drop", type=float, default=0.0)
    parser.add_argument("--allow-goal-drift-increase", type=float, default=0.0)
    parser.add_argument("--allow-section-navigation-signal-increase", type=float, default=0.0)
    parser.add_argument("--allow-step-stability-increase", type=float, default=0.0)
    parser.add_argument("--allow-failure-recovery-increase", type=float, default=0.0)
    parser.add_argument("--allow-goal-drift-missing-increase", type=float, default=0.0)
    parser.add_argument("--allow-step-stability-missing-increase", type=float, default=0.0)
    parser.add_argument("--allow-failure-recovery-missing-increase", type=float, default=0.0)
    parser.add_argument("--allow-context-missing-increase", type=float, default=0.0)
    parser.add_argument("--promote-dir", default="", help="Optional baseline promotion directory")
    args = parser.parse_args()

    report = compare_deepread_handoff_audits(
        baseline=Path(args.baseline).expanduser().resolve(),
        new=Path(args.new).expanduser().resolve(),
        out=Path(args.out).expanduser().resolve(),
        allow_review_ready_drop=float(args.allow_review_ready_drop),
        allow_goal_drift_increase=float(args.allow_goal_drift_increase),
        allow_section_navigation_signal_increase=float(args.allow_section_navigation_signal_increase),
        allow_step_stability_increase=float(args.allow_step_stability_increase),
        allow_failure_recovery_increase=float(args.allow_failure_recovery_increase),
        allow_goal_drift_missing_increase=float(args.allow_goal_drift_missing_increase),
        allow_step_stability_missing_increase=float(args.allow_step_stability_missing_increase),
        allow_failure_recovery_missing_increase=float(args.allow_failure_recovery_missing_increase),
        allow_context_missing_increase=float(args.allow_context_missing_increase),
        promote_dir=Path(args.promote_dir).expanduser().resolve() if args.promote_dir else None,
    )
    print(f"[compare_deepread_handoff_audits] passed={report['decision']['passed']}")
    print(f"[compare_deepread_handoff_audits] out={Path(args.out).expanduser().resolve()}")
    print(f"[compare_deepread_handoff_audits] promotion={report['promotion']['path']}")
    return 0 if report["decision"]["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
