#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.services.evidence_grounding_benchmark import (
    build_evidence_grounding_threshold_adoption_review_report,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Review whether calibrated evidence-grounding thresholds are ready for production-policy adoption. "
            "This writes a non-canonical review artifact and does not mutate runtime threshold policy."
        )
    )
    parser.add_argument("--calibration-report", required=True)
    parser.add_argument(
        "--comparison-suite",
        help="Path to comparison_suite.json. Used to resolve comparison and run-readiness reports when explicit paths are omitted.",
    )
    parser.add_argument("--comparison-report")
    parser.add_argument("--run-readiness-report")
    parser.add_argument("--out", required=True)
    parser.add_argument("--adoption-id", default="evidence-grounding-threshold-adoption-review")
    parser.add_argument(
        "--required-metric",
        action="append",
        default=None,
        help="Required calibrated threshold metric name. May be repeated.",
    )
    parser.add_argument("--reviewer-approval-reference")
    parser.add_argument(
        "--allow-production-threshold-ready",
        action="store_true",
        help="Allow the review to mark production_threshold_ready=true when every check passes.",
    )
    args = parser.parse_args()
    if not args.comparison_suite and (not args.comparison_report or not args.run_readiness_report):
        parser.error("--comparison-suite or both --comparison-report and --run-readiness-report are required")

    report = build_evidence_grounding_threshold_adoption_review_report(
        calibration_report_path=Path(args.calibration_report),
        comparison_suite_path=Path(args.comparison_suite) if args.comparison_suite else None,
        comparison_report_path=Path(args.comparison_report) if args.comparison_report else None,
        run_readiness_report_path=Path(args.run_readiness_report) if args.run_readiness_report else None,
        adoption_id=args.adoption_id,
        required_metric_names=args.required_metric,
        reviewer_approval_reference=args.reviewer_approval_reference,
        allow_production_threshold_ready=args.allow_production_threshold_ready,
        out=Path(args.out).expanduser().resolve(),
    )
    print(f"[evidence_grounding_threshold_adoption_review] adoption_id={report.adoption_id}")
    print(f"[evidence_grounding_threshold_adoption_review] fail_count={report.fail_count}")
    print(
        "[evidence_grounding_threshold_adoption_review] "
        f"production_threshold_ready={report.production_threshold_ready}"
    )
    print(f"[evidence_grounding_threshold_adoption_review] out={Path(args.out).expanduser().resolve()}")
    return 0 if report.production_threshold_ready else 1


if __name__ == "__main__":
    raise SystemExit(main())
