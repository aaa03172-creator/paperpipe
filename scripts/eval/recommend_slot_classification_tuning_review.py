#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.services.slot_classification_tuning_review import run_slot_classification_tuning_review


def _compact_tuning_review_text(summary: dict[str, object]) -> str:
    decision = summary.get("decision") if isinstance(summary.get("decision"), dict) else {}
    parts = [
        f"review_ready={bool(decision.get('review_ready'))}",
    ]

    recommended_action = str(decision.get("recommended_action") or "").strip()
    if recommended_action:
        parts.append(f"action={recommended_action}")

    paired_compare_status = str(decision.get("paired_compare_status") or "").strip()
    if paired_compare_status:
        parts.append(f"paired_compare={paired_compare_status}")

    default_rerun_status = str(decision.get("default_rerun_status") or "").strip()
    if default_rerun_status:
        parts.append(f"default_rerun={default_rerun_status}")

    boundary_rerun_status = str(decision.get("boundary_rerun_status") or "").strip()
    if boundary_rerun_status:
        parts.append(f"boundary_rerun={boundary_rerun_status}")

    latest_compare_run_id = str(decision.get("latest_compare_run_id") or "").strip()
    if latest_compare_run_id:
        parts.append(f"compare_run={latest_compare_run_id}")

    return " ".join(parts)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build an advisory review summary for slot-classification prompt or policy tuning using paired compare and rerun-drift artifacts."
    )
    parser.add_argument("--paired-compare-summary", default=None, help="Paired compare summary.json path or run directory.")
    parser.add_argument("--default-rerun-drift-summary", default=None, help="Default benchmark rerun-drift summary.json path or run directory.")
    parser.add_argument("--boundary-rerun-drift-summary", default=None, help="Boundary benchmark rerun-drift summary.json path or run directory.")
    parser.add_argument(
        "--out-dir",
        default=str(ROOT / "snapshots" / "slot_classification_tuning_review"),
        help="Output directory for slot-classification tuning review artifacts.",
    )
    parser.add_argument("--run-id", required=True, help="Tuning review run identifier.")
    parser.add_argument("--max-default-rerun-drift-rate", type=float, default=0.0)
    parser.add_argument("--max-boundary-rerun-drift-rate", type=float, default=0.0)
    args = parser.parse_args()

    run_root = run_slot_classification_tuning_review(
        paired_compare_summary_path=Path(args.paired_compare_summary).expanduser() if args.paired_compare_summary else None,
        default_rerun_drift_summary_path=Path(args.default_rerun_drift_summary).expanduser() if args.default_rerun_drift_summary else None,
        boundary_rerun_drift_summary_path=Path(args.boundary_rerun_drift_summary).expanduser() if args.boundary_rerun_drift_summary else None,
        out_dir=Path(args.out_dir).expanduser(),
        run_id=args.run_id,
        max_default_rerun_drift_rate=max(float(args.max_default_rerun_drift_rate), 0.0),
        max_boundary_rerun_drift_rate=max(float(args.max_boundary_rerun_drift_rate), 0.0),
    )
    payload = {
        "run_root": str(run_root),
        "summary_path": str(run_root / "summary.json"),
        "markdown_path": str(run_root / "audit.md"),
    }
    summary_payload = json.loads((run_root / "summary.json").read_text(encoding="utf-8"))
    print(
        "[recommend_slot_classification_tuning_review] "
        + _compact_tuning_review_text(summary_payload),
        file=sys.stderr,
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
