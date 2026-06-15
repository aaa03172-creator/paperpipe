#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.services.evidence_grounding_benchmark import (
    build_evidence_grounding_threshold_adoption_review_report_from_comparison_suite,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Build calibration, a threshold-checked comparison, and a threshold adoption review "
            "from a fixed-goldset comparison suite. The review remains non-canonical and requires "
            "explicit human approval plus opt-in before it can be production-threshold ready."
        )
    )
    parser.add_argument("--comparison-suite", required=True)
    parser.add_argument("--calibration-out", required=True)
    parser.add_argument("--threshold-checked-comparison-out", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--calibration-id", default="evidence-grounding-threshold-calibration")
    parser.add_argument("--adoption-id", default="evidence-grounding-threshold-adoption-review")
    parser.add_argument("--calibration-metric", action="append", default=None)
    parser.add_argument("--calibration-metric-preset", choices=("p0-gold", "explicit"), default="p0-gold")
    parser.add_argument("--include-baseline-report", action="store_true")
    parser.add_argument("--exclude-candidate-report", action="store_true")
    parser.add_argument("--tolerance", type=float, default=0.0)
    parser.add_argument("--gate-metric", action="append", default=None)
    parser.add_argument("--gate-preset", choices=("all-comparable", "p0-gold"), default="p0-gold")
    parser.add_argument("--threshold-metric", action="append", default=None, metavar="NAME=VALUE")
    parser.add_argument("--required-metric", action="append", default=None)
    parser.add_argument("--reviewer-approval-reference")
    parser.add_argument("--allow-production-threshold-ready", action="store_true")
    args = parser.parse_args()
    include_candidate_report = not args.exclude_candidate_report
    if not args.include_baseline_report and not include_candidate_report:
        parser.error("at least one suite benchmark report must be selected for calibration")

    report = build_evidence_grounding_threshold_adoption_review_report_from_comparison_suite(
        comparison_suite_path=Path(args.comparison_suite),
        calibration_report_out=Path(args.calibration_out),
        threshold_checked_comparison_report_out=Path(args.threshold_checked_comparison_out),
        out=Path(args.out).expanduser().resolve(),
        calibration_id=args.calibration_id,
        calibration_metric_names=args.calibration_metric,
        calibration_metric_preset=args.calibration_metric_preset.replace("-", "_"),
        include_baseline_report=args.include_baseline_report,
        include_candidate_report=include_candidate_report,
        tolerance=args.tolerance,
        gate_metric_names=args.gate_metric,
        gate_preset=args.gate_preset.replace("-", "_"),
        threshold_metric_values=_parse_threshold_metrics(args.threshold_metric),
        adoption_id=args.adoption_id,
        required_metric_names=args.required_metric,
        reviewer_approval_reference=args.reviewer_approval_reference,
        allow_production_threshold_ready=args.allow_production_threshold_ready,
    )
    print(f"[evidence_grounding_threshold_adoption_review] adoption_id={report.adoption_id}")
    print(f"[evidence_grounding_threshold_adoption_review] fail_count={report.fail_count}")
    print(
        "[evidence_grounding_threshold_adoption_review] "
        f"production_threshold_ready={report.production_threshold_ready}"
    )
    print(f"[evidence_grounding_threshold_adoption_review] calibration_out={Path(args.calibration_out).resolve()}")
    print(
        "[evidence_grounding_threshold_adoption_review] "
        f"threshold_checked_comparison_out={Path(args.threshold_checked_comparison_out).resolve()}"
    )
    print(f"[evidence_grounding_threshold_adoption_review] out={Path(args.out).expanduser().resolve()}")
    return 0 if report.production_threshold_ready else 1


def _parse_threshold_metrics(raw_values: list[str] | None) -> dict[str, float] | None:
    if not raw_values:
        return None
    parsed: dict[str, float] = {}
    for raw_value in raw_values:
        if "=" not in raw_value:
            raise ValueError(f"--threshold-metric must use NAME=VALUE: {raw_value!r}")
        name, value = raw_value.split("=", 1)
        name = name.strip()
        if not name:
            raise ValueError(f"--threshold-metric requires a metric name: {raw_value!r}")
        parsed[name] = float(value.strip())
    return parsed


if __name__ == "__main__":
    raise SystemExit(main())
