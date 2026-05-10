#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.schemas.slot_classification_paired_compare import SlotClassificationPairedCompareThresholds
from src.services.slot_classification_paired_compare import (
    build_slot_classification_paired_compare,
    load_slot_classification_audit_summary,
    write_slot_classification_paired_compare,
)


def run_compare(
    *,
    baseline_default_summary_path: Path,
    baseline_boundary_summary_path: Path,
    candidate_default_summary_path: Path,
    candidate_boundary_summary_path: Path,
    out_dir: Path,
    run_id: str,
    thresholds: SlotClassificationPairedCompareThresholds | None = None,
) -> Path:
    resolved_baseline_default_path, baseline_default_summary = load_slot_classification_audit_summary(
        baseline_default_summary_path
    )
    resolved_baseline_boundary_path, baseline_boundary_summary = load_slot_classification_audit_summary(
        baseline_boundary_summary_path
    )
    resolved_candidate_default_path, candidate_default_summary = load_slot_classification_audit_summary(
        candidate_default_summary_path
    )
    resolved_candidate_boundary_path, candidate_boundary_summary = load_slot_classification_audit_summary(
        candidate_boundary_summary_path
    )

    summary = build_slot_classification_paired_compare(
        baseline_default_summary=baseline_default_summary,
        baseline_default_summary_path=resolved_baseline_default_path,
        baseline_boundary_summary=baseline_boundary_summary,
        baseline_boundary_summary_path=resolved_baseline_boundary_path,
        candidate_default_summary=candidate_default_summary,
        candidate_default_summary_path=resolved_candidate_default_path,
        candidate_boundary_summary=candidate_boundary_summary,
        candidate_boundary_summary_path=resolved_candidate_boundary_path,
        run_id=run_id,
        thresholds=thresholds,
    )
    return write_slot_classification_paired_compare(summary=summary, out_dir=out_dir)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compare two paired slot-classification benchmark snapshots and flag regressions or mismatch migration."
    )
    parser.add_argument("--baseline-default", required=True, help="Baseline default-template summary.json path or run dir.")
    parser.add_argument("--baseline-boundary", required=True, help="Baseline boundary-companion summary.json path or run dir.")
    parser.add_argument("--candidate-default", required=True, help="Candidate default-template summary.json path or run dir.")
    parser.add_argument("--candidate-boundary", required=True, help="Candidate boundary-companion summary.json path or run dir.")
    parser.add_argument(
        "--out-dir",
        default=str(ROOT / "snapshots" / "slot_classification_paired_compares"),
        help="Output directory for paired-compare artifacts.",
    )
    parser.add_argument("--run-id", required=True, help="Paired compare run identifier.")
    parser.add_argument("--allow-default-accuracy-drop", type=float, default=0.0)
    parser.add_argument("--allow-boundary-accuracy-drop", type=float, default=0.0)
    parser.add_argument("--allow-default-coverage-drop", type=float, default=0.0)
    parser.add_argument("--allow-boundary-coverage-drop", type=float, default=0.0)
    parser.add_argument("--allow-default-mismatch-increase", type=int, default=0)
    parser.add_argument("--allow-boundary-mismatch-increase", type=int, default=0)
    args = parser.parse_args()

    run_root = run_compare(
        baseline_default_summary_path=Path(args.baseline_default).expanduser(),
        baseline_boundary_summary_path=Path(args.baseline_boundary).expanduser(),
        candidate_default_summary_path=Path(args.candidate_default).expanduser(),
        candidate_boundary_summary_path=Path(args.candidate_boundary).expanduser(),
        out_dir=Path(args.out_dir).expanduser(),
        run_id=args.run_id,
        thresholds=SlotClassificationPairedCompareThresholds(
            allow_default_accuracy_drop=max(float(args.allow_default_accuracy_drop), 0.0),
            allow_boundary_accuracy_drop=max(float(args.allow_boundary_accuracy_drop), 0.0),
            allow_default_coverage_drop=max(float(args.allow_default_coverage_drop), 0.0),
            allow_boundary_coverage_drop=max(float(args.allow_boundary_coverage_drop), 0.0),
            allow_default_mismatch_increase=max(int(args.allow_default_mismatch_increase), 0),
            allow_boundary_mismatch_increase=max(int(args.allow_boundary_mismatch_increase), 0),
        ),
    )
    payload = {
        "run_root": str(run_root),
        "summary_path": str(run_root / "summary.json"),
        "markdown_path": str(run_root / "compare.md"),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
