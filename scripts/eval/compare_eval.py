#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REQUIRED_METRICS = (
    "schema_valid_rate",
    "evidence_location_rate",
    "summary_artifact_rate",
    "manual_correction_rate",
)


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


def _resolve_metrics_path(path_or_dir: Path) -> Path:
    if path_or_dir.is_dir():
        candidate = path_or_dir / "metrics.json"
        if not candidate.exists():
            raise FileNotFoundError(f"metrics_missing={candidate}")
        return candidate
    return path_or_dir


def _load_metrics(path_or_dir: Path) -> tuple[Path, dict[str, Any]]:
    metrics_path = _resolve_metrics_path(path_or_dir)
    if not metrics_path.exists():
        raise FileNotFoundError(f"metrics_missing={metrics_path}")
    payload = _load_json(metrics_path)
    missing = [key for key in REQUIRED_METRICS if key not in payload]
    if missing:
        raise RuntimeError(f"metrics_missing_keys={','.join(missing)} path={metrics_path}")
    return metrics_path, payload


def _as_float(payload: dict[str, Any], key: str) -> float:
    try:
        return float(payload.get(key, 0.0))
    except Exception:
        return 0.0


def compare_metrics(
    baseline_metrics: dict[str, Any],
    new_metrics: dict[str, Any],
    *,
    delta_schema: float = 0.0,
    delta_evidence: float = 0.0,
    delta_summary: float = 0.0,
    allow_manual_increase: float = 0.0,
) -> dict[str, Any]:
    b_schema = _as_float(baseline_metrics, "schema_valid_rate")
    b_evidence = _as_float(baseline_metrics, "evidence_location_rate")
    b_summary = _as_float(baseline_metrics, "summary_artifact_rate")
    b_manual = _as_float(baseline_metrics, "manual_correction_rate")

    n_schema = _as_float(new_metrics, "schema_valid_rate")
    n_evidence = _as_float(new_metrics, "evidence_location_rate")
    n_summary = _as_float(new_metrics, "summary_artifact_rate")
    n_manual = _as_float(new_metrics, "manual_correction_rate")

    checks = [
        {
            "name": "schema_valid_rate",
            "baseline": b_schema,
            "new": n_schema,
            "required": b_schema + delta_schema,
            "passed": n_schema >= (b_schema + delta_schema),
            "direction": "higher_is_better",
        },
        {
            "name": "evidence_location_rate",
            "baseline": b_evidence,
            "new": n_evidence,
            "required": b_evidence + delta_evidence,
            "passed": n_evidence >= (b_evidence + delta_evidence),
            "direction": "higher_is_better",
        },
        {
            "name": "summary_artifact_rate",
            "baseline": b_summary,
            "new": n_summary,
            "required": b_summary + delta_summary,
            "passed": n_summary >= (b_summary + delta_summary),
            "direction": "higher_is_better",
        },
        {
            "name": "manual_correction_rate",
            "baseline": b_manual,
            "new": n_manual,
            "required": b_manual + allow_manual_increase,
            "passed": n_manual <= (b_manual + allow_manual_increase),
            "direction": "lower_is_better",
        },
    ]

    regressions = []
    if n_schema < b_schema:
        regressions.append("schema_valid_rate")
    if n_evidence < b_evidence:
        regressions.append("evidence_location_rate")
    if n_summary < b_summary:
        regressions.append("summary_artifact_rate")
    if n_manual > b_manual:
        regressions.append("manual_correction_rate")

    failed_checks = [check["name"] for check in checks if not check["passed"]]
    passed = len(failed_checks) == 0 and len(regressions) == 0

    return {
        "passed": passed,
        "checks": checks,
        "failed_checks": failed_checks,
        "regressions": regressions,
        "deltas": {
            "schema_valid_rate": n_schema - b_schema,
            "evidence_location_rate": n_evidence - b_evidence,
            "summary_artifact_rate": n_summary - b_summary,
            "manual_correction_rate": n_manual - b_manual,
        },
    }


def _promote_snapshot(*, new_metrics_path: Path, promote_dir: Path, report: dict[str, Any]) -> Path:
    run_id = str(report.get("new", {}).get("run_id") or "")
    tag = _safe_name(run_id) if run_id else _utc_now_tag()
    target = promote_dir / tag
    target.mkdir(parents=True, exist_ok=True)

    shutil.copy2(new_metrics_path, target / "metrics.json")
    (target / "promotion_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return target


def compare_eval(
    *,
    baseline: Path,
    new: Path,
    out: Path,
    delta_schema: float = 0.0,
    delta_evidence: float = 0.0,
    delta_summary: float = 0.0,
    allow_manual_increase: float = 0.0,
    promote_dir: Path | None = None,
) -> dict[str, Any]:
    baseline_path, baseline_metrics = _load_metrics(baseline)
    new_path, new_metrics = _load_metrics(new)

    decision = compare_metrics(
        baseline_metrics,
        new_metrics,
        delta_schema=delta_schema,
        delta_evidence=delta_evidence,
        delta_summary=delta_summary,
        allow_manual_increase=allow_manual_increase,
    )

    report = {
        "schema_version": "eval_compare.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "baseline": {
            "path": str(baseline_path),
            "run_id": baseline_metrics.get("run_id"),
            "metrics": {key: baseline_metrics.get(key) for key in REQUIRED_METRICS},
        },
        "new": {
            "path": str(new_path),
            "run_id": new_metrics.get("run_id"),
            "metrics": {key: new_metrics.get(key) for key in REQUIRED_METRICS},
        },
        "thresholds": {
            "delta_schema": delta_schema,
            "delta_evidence": delta_evidence,
            "delta_summary": delta_summary,
            "allow_manual_increase": allow_manual_increase,
        },
        "decision": decision,
    }

    if promote_dir and decision["passed"]:
        promoted_to = _promote_snapshot(new_metrics_path=new_path, promote_dir=promote_dir, report=report)
        report["promotion"] = {"promoted": True, "path": str(promoted_to)}
    else:
        report["promotion"] = {"promoted": False, "path": None}

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    out_txt = out.with_suffix(".txt")
    lines = [
        f"baseline={baseline_path}",
        f"new={new_path}",
        f"passed={decision['passed']}",
        f"failed_checks={','.join(decision['failed_checks']) if decision['failed_checks'] else '-'}",
        f"regressions={','.join(decision['regressions']) if decision['regressions'] else '-'}",
        f"promotion={report['promotion']['path'] or '-'}",
    ]
    out_txt.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare eval metrics snapshots and decide promotion.")
    parser.add_argument("--baseline", required=True, help="Baseline metrics.json path or snapshot dir")
    parser.add_argument("--new", required=True, help="New metrics.json path or snapshot dir")
    parser.add_argument("--out", required=True, help="Output compare report JSON path")
    parser.add_argument("--delta-schema", type=float, default=0.0, help="Required improvement delta for schema_valid_rate")
    parser.add_argument(
        "--delta-evidence",
        type=float,
        default=0.0,
        help="Required improvement delta for evidence_location_rate",
    )
    parser.add_argument(
        "--delta-summary",
        type=float,
        default=0.0,
        help="Required improvement delta for summary_artifact_rate",
    )
    parser.add_argument(
        "--allow-manual-increase",
        type=float,
        default=0.0,
        help="Allowed increase for manual_correction_rate (0 means no increase)",
    )
    parser.add_argument(
        "--promote-dir",
        default="",
        help="Optional baselines directory. If set and decision passes, new metrics are promoted.",
    )
    args = parser.parse_args()

    report = compare_eval(
        baseline=Path(args.baseline).expanduser().resolve(),
        new=Path(args.new).expanduser().resolve(),
        out=Path(args.out).expanduser().resolve(),
        delta_schema=args.delta_schema,
        delta_evidence=args.delta_evidence,
        delta_summary=args.delta_summary,
        allow_manual_increase=args.allow_manual_increase,
        promote_dir=Path(args.promote_dir).expanduser().resolve() if args.promote_dir else None,
    )
    print(f"[compare_eval] passed={report['decision']['passed']}")
    print(f"[compare_eval] out={Path(args.out).expanduser().resolve()}")
    print(f"[compare_eval] promotion={report['promotion']['path']}")
    return 0 if report["decision"]["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
