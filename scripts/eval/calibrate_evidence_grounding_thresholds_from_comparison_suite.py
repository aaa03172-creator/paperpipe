#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.services.evidence_grounding_benchmark import (
    build_evidence_grounding_threshold_calibration_report_from_comparison_suite,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Build an additive threshold calibration report from the benchmark reports linked by "
            "an evidence-grounding fixed-goldset comparison suite."
        )
    )
    parser.add_argument("--comparison-suite", required=True, help="Path to comparison_suite.json")
    parser.add_argument("--out", required=True, help="Output threshold calibration report JSON path")
    parser.add_argument("--calibration-id", default="evidence-grounding-threshold-calibration")
    parser.add_argument(
        "--metric-preset",
        choices=("p0-gold", "explicit"),
        default="p0-gold",
        help="Metric preset to calibrate. Ignored when --metric is provided.",
    )
    parser.add_argument(
        "--metric",
        action="append",
        default=None,
        help="Metric to calibrate. May be plain or group-qualified, for example claim_precision.",
    )
    parser.add_argument(
        "--include-baseline-report",
        action="store_true",
        help="Also use the suite's baseline benchmark report as calibration evidence.",
    )
    parser.add_argument(
        "--exclude-candidate-report",
        action="store_true",
        help="Do not use the suite's candidate benchmark report as calibration evidence.",
    )
    args = parser.parse_args()
    include_candidate_report = not args.exclude_candidate_report
    if not args.include_baseline_report and not include_candidate_report:
        parser.error("at least one suite benchmark report must be selected")

    report = build_evidence_grounding_threshold_calibration_report_from_comparison_suite(
        comparison_suite_path=Path(args.comparison_suite),
        calibration_id=args.calibration_id,
        metric_names=args.metric,
        metric_preset=args.metric_preset.replace("-", "_"),
        include_baseline_report=args.include_baseline_report,
        include_candidate_report=include_candidate_report,
        out=Path(args.out).expanduser().resolve(),
    )
    print(f"[evidence_grounding_threshold_calibration] calibration_id={report.calibration_id}")
    print(f"[evidence_grounding_threshold_calibration] report_count={report.report_count}")
    print(
        "[evidence_grounding_threshold_calibration] available_metric_count="
        f"{sum(1 for recommendation in report.recommendations if recommendation.status == 'available')}"
    )
    print(
        "[evidence_grounding_threshold_calibration] "
        f"comparison_suite={Path(args.comparison_suite).expanduser().resolve()}"
    )
    print(f"[evidence_grounding_threshold_calibration] out={Path(args.out).expanduser().resolve()}")
    return 0 if any(recommendation.status == "available" for recommendation in report.recommendations) else 1


if __name__ == "__main__":
    raise SystemExit(main())
