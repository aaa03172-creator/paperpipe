#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.services.evidence_grounding_benchmark import (  # noqa: E402
    run_evidence_grounding_fixed_goldset_comparison_suite_package_from_benchmark_run_packages,
    threshold_metric_values_from_calibration_report,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Compare baseline/candidate evidence-grounding benchmark run packages "
            "and write one fixed-goldset comparison suite per split."
        )
    )
    parser.add_argument("--baseline-run-package", required=True)
    parser.add_argument("--candidate-run-package", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--package-id", default="evidence-grounding-fixed-goldset-comparison-suite-package")
    parser.add_argument("--suite-id-prefix", default="evidence-grounding-fixed-goldset-comparison")
    parser.add_argument("--tolerance", type=float, default=0.0)
    parser.add_argument(
        "--gate-metric",
        action="append",
        default=None,
        help="Optional metric name to include in the hard regression gate. May be repeated.",
    )
    parser.add_argument(
        "--gate-preset",
        choices=("all-comparable", "p0-gold"),
        default="all-comparable",
    )
    parser.add_argument(
        "--threshold-preset",
        choices=("none", "p0-gold-minimum"),
        default="none",
    )
    parser.add_argument(
        "--threshold-metric",
        action="append",
        default=None,
        metavar="NAME=VALUE",
        help="Optional absolute candidate threshold. May be repeated.",
    )
    parser.add_argument(
        "--threshold-calibration-report",
        default=None,
        help="Optional evidence_grounding_threshold_calibration.v1 report.",
    )
    parser.add_argument("--out", help="Optional output path for the comparison-suite package JSON")
    args = parser.parse_args()

    package = run_evidence_grounding_fixed_goldset_comparison_suite_package_from_benchmark_run_packages(
        baseline_run_package_path=Path(args.baseline_run_package),
        candidate_run_package_path=Path(args.candidate_run_package),
        out_dir=Path(args.out_dir),
        package_id=args.package_id,
        suite_id_prefix=args.suite_id_prefix,
        tolerance=args.tolerance,
        gate_metric_names=args.gate_metric,
        gate_preset=args.gate_preset.replace("-", "_"),
        threshold_preset=args.threshold_preset.replace("-", "_"),
        threshold_metric_values=_load_threshold_metric_values(
            calibration_report=args.threshold_calibration_report,
            explicit_values=args.threshold_metric,
        ),
        out=Path(args.out).expanduser().resolve() if args.out else None,
    )
    print(f"[evidence_grounding_fixed_goldset_comparison_suite_package] package_id={package.package_id}")
    print(f"[evidence_grounding_fixed_goldset_comparison_suite_package] suite_count={package.suite_count}")
    print(
        "[evidence_grounding_fixed_goldset_comparison_suite_package] "
        f"comparison_pass_count={package.comparison_pass_count}"
    )
    print(
        "[evidence_grounding_fixed_goldset_comparison_suite_package] "
        f"comparison_fail_count={package.comparison_fail_count}"
    )
    print(
        "[evidence_grounding_fixed_goldset_comparison_suite_package] "
        "baseline_scorecard_readiness="
        f"pass={package.baseline_scorecard_readiness_pass_count} "
        f"warn={package.baseline_scorecard_readiness_warn_count} "
        f"fail={package.baseline_scorecard_readiness_fail_count}"
    )
    print(
        "[evidence_grounding_fixed_goldset_comparison_suite_package] "
        "candidate_scorecard_readiness="
        f"pass={package.candidate_scorecard_readiness_pass_count} "
        f"warn={package.candidate_scorecard_readiness_warn_count} "
        f"fail={package.candidate_scorecard_readiness_fail_count}"
    )
    print(f"[evidence_grounding_fixed_goldset_comparison_suite_package] out_dir={package.out_dir}")
    if args.out:
        print(
            "[evidence_grounding_fixed_goldset_comparison_suite_package] "
            f"package={Path(args.out).expanduser().resolve()}"
        )
    return 0 if package.suite_count > 0 else 1


def _load_threshold_metric_values(
    *,
    calibration_report: str | None,
    explicit_values: list[str] | None,
) -> dict[str, float] | None:
    values: dict[str, float] = {}
    if calibration_report:
        values.update(threshold_metric_values_from_calibration_report(Path(calibration_report)))
    if explicit_values:
        for raw_value in explicit_values:
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
