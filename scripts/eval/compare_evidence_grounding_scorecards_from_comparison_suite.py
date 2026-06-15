#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.services.evidence_grounding_benchmark import (
    compare_evidence_grounding_scorecard_reports_from_comparison_suite,
    threshold_metric_values_from_calibration_report,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Recompare the baseline and candidate benchmark reports linked by a fixed-goldset "
            "comparison suite, optionally applying calibrated threshold checks."
        )
    )
    parser.add_argument("--comparison-suite", required=True, help="Path to comparison_suite.json")
    parser.add_argument("--out", required=True, help="Output comparison report JSON path")
    parser.add_argument("--tolerance", type=float, default=0.0)
    parser.add_argument("--gate-metric", action="append", default=None)
    parser.add_argument("--gate-preset", choices=("all-comparable", "p0-gold"), default="all-comparable")
    parser.add_argument("--threshold-preset", choices=("none", "p0-gold-minimum"), default="none")
    parser.add_argument("--threshold-metric", action="append", default=None, metavar="NAME=VALUE")
    parser.add_argument(
        "--threshold-calibration-report",
        default=None,
        help=(
            "Optional evidence_grounding_threshold_calibration.v1 report. Available recommendations are "
            "applied as explicit threshold metrics. Repeated --threshold-metric values override matching recommendations."
        ),
    )
    args = parser.parse_args()

    report = compare_evidence_grounding_scorecard_reports_from_comparison_suite(
        comparison_suite_path=Path(args.comparison_suite),
        tolerance=args.tolerance,
        gate_metric_names=args.gate_metric,
        gate_preset=args.gate_preset.replace("-", "_"),
        threshold_preset=args.threshold_preset.replace("-", "_"),
        threshold_metric_values=_load_threshold_metric_values(
            calibration_report=args.threshold_calibration_report,
            explicit_values=args.threshold_metric,
        ),
        threshold_calibration_report_path=None,
        out=Path(args.out).expanduser().resolve(),
    )
    print(f"[evidence_grounding_compare_from_suite] passed={report.decision.passed}")
    print(
        "[evidence_grounding_compare_from_suite] "
        f"threshold_check_count={len(report.threshold_checks)}"
    )
    print(f"[evidence_grounding_compare_from_suite] failed_checks={','.join(report.decision.failed_checks) or '-'}")
    print(f"[evidence_grounding_compare_from_suite] out={Path(args.out).expanduser().resolve()}")
    return 0 if report.decision.passed else 1


def _load_threshold_metric_values(
    *,
    calibration_report: str | None,
    explicit_values: list[str] | None,
) -> dict[str, float] | None:
    values: dict[str, float] = {}
    if calibration_report:
        values.update(threshold_metric_values_from_calibration_report(Path(calibration_report).expanduser().resolve()))
    values.update(_parse_threshold_metrics(explicit_values) or {})
    return values or None


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
