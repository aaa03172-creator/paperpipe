#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.services.evidence_grounding_benchmark import (  # noqa: E402
    build_evidence_grounding_threshold_adoption_review_package_from_comparison_suite_package,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Build threshold calibration and per-split threshold-adoption reviews "
            "from an evidence-grounding comparison-suite package."
        )
    )
    parser.add_argument("--comparison-suite-package", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--package-id", default="evidence-grounding-threshold-adoption-review-package")
    parser.add_argument("--calibration-report-out")
    parser.add_argument("--calibration-id", default="evidence-grounding-threshold-calibration")
    parser.add_argument("--calibration-metric", action="append", default=None)
    parser.add_argument("--calibration-metric-preset", choices=("p0-gold", "explicit"), default="p0-gold")
    parser.add_argument("--include-baseline-report", action="store_true")
    parser.add_argument("--skip-candidate-report", action="store_true")
    parser.add_argument("--tolerance", type=float, default=0.0)
    parser.add_argument("--gate-metric", action="append", default=None)
    parser.add_argument("--gate-preset", choices=("all-comparable", "p0-gold"), default="p0-gold")
    parser.add_argument("--threshold-metric", action="append", default=None, metavar="NAME=VALUE")
    parser.add_argument("--adoption-id-prefix", default="evidence-grounding-threshold-adoption-review")
    parser.add_argument("--required-metric", action="append", default=None)
    parser.add_argument("--reviewer-approval-reference")
    parser.add_argument("--allow-production-threshold-ready", action="store_true")
    parser.add_argument("--out", help="Optional output path for the threshold-adoption package JSON")
    args = parser.parse_args()

    package = build_evidence_grounding_threshold_adoption_review_package_from_comparison_suite_package(
        comparison_suite_package_path=Path(args.comparison_suite_package),
        out_dir=Path(args.out_dir),
        package_id=args.package_id,
        calibration_report_out=Path(args.calibration_report_out) if args.calibration_report_out else None,
        calibration_id=args.calibration_id,
        calibration_metric_names=args.calibration_metric,
        calibration_metric_preset=args.calibration_metric_preset.replace("-", "_"),
        include_baseline_report=args.include_baseline_report,
        include_candidate_report=not args.skip_candidate_report,
        tolerance=args.tolerance,
        gate_metric_names=args.gate_metric,
        gate_preset=args.gate_preset.replace("-", "_"),
        threshold_metric_values=_parse_threshold_metrics(args.threshold_metric),
        adoption_id_prefix=args.adoption_id_prefix,
        required_metric_names=args.required_metric,
        reviewer_approval_reference=args.reviewer_approval_reference,
        allow_production_threshold_ready=args.allow_production_threshold_ready,
        out=Path(args.out).expanduser().resolve() if args.out else None,
    )
    print(f"[evidence_grounding_threshold_adoption_review_package] package_id={package.package_id}")
    print(
        "[evidence_grounding_threshold_adoption_review_package] "
        f"comparison_suite_count={package.comparison_suite_count}"
    )
    print(
        "[evidence_grounding_threshold_adoption_review_package] "
        f"production_threshold_ready_count={package.production_threshold_ready_count}"
    )
    print(
        "[evidence_grounding_threshold_adoption_review_package] "
        f"production_threshold_blocked_count={package.production_threshold_blocked_count}"
    )
    print(
        "[evidence_grounding_threshold_adoption_review_package] "
        "baseline_scorecard_readiness="
        f"pass={package.baseline_scorecard_readiness_pass_count} "
        f"warn={package.baseline_scorecard_readiness_warn_count} "
        f"fail={package.baseline_scorecard_readiness_fail_count}"
    )
    print(
        "[evidence_grounding_threshold_adoption_review_package] "
        "candidate_scorecard_readiness="
        f"pass={package.candidate_scorecard_readiness_pass_count} "
        f"warn={package.candidate_scorecard_readiness_warn_count} "
        f"fail={package.candidate_scorecard_readiness_fail_count}"
    )
    if args.out:
        print(
            "[evidence_grounding_threshold_adoption_review_package] "
            f"package={Path(args.out).expanduser().resolve()}"
        )
    return 0 if package.comparison_suite_count > 0 else 1


def _parse_threshold_metrics(raw_values: list[str] | None) -> dict[str, float] | None:
    values: dict[str, float] = {}
    if not raw_values:
        return None
    for raw_value in raw_values:
        if "=" not in raw_value:
            raise SystemExit(f"--threshold-metric must be NAME=VALUE, got: {raw_value}")
        name, value = raw_value.split("=", 1)
        name = name.strip()
        if not name:
            raise SystemExit(f"--threshold-metric name is required: {raw_value}")
        values[name] = float(value)
    return values or None


if __name__ == "__main__":
    raise SystemExit(main())
