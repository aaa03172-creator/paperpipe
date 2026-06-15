#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from src.services.evidence_grounding_benchmark import (
    compare_evidence_grounding_scorecard_reports,
    threshold_metric_values_from_calibration_report,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compare evidence grounding scorecards or benchmark reports and fail on regressions."
    )
    parser.add_argument("--baseline", required=True, help="Baseline scorecard or benchmark JSON path")
    parser.add_argument("--candidate", required=True, help="Candidate scorecard or benchmark JSON path")
    parser.add_argument("--out", required=True, help="Output comparison report JSON path")
    parser.add_argument(
        "--tolerance",
        type=float,
        default=0.0,
        help="Allowed regression tolerance for each compared metric",
    )
    parser.add_argument(
        "--gate-metric",
        action="append",
        default=None,
        help=(
            "Optional metric name to include in the hard regression gate. "
            "May be repeated. When omitted, all comparable metrics keep the legacy gate behavior."
        ),
    )
    parser.add_argument(
        "--gate-preset",
        choices=("all-comparable", "p0-gold"),
        default="all-comparable",
        help=(
            "Named metric gate preset. Use p0-gold to gate only P0 gold-scored metrics while still "
            "reporting all comparable metrics. Ignored when --gate-metric is provided."
        ),
    )
    parser.add_argument(
        "--threshold-preset",
        choices=("none", "p0-gold-minimum"),
        default="none",
        help=(
            "Optional absolute candidate-quality threshold policy. "
            "Use p0-gold-minimum to require the fixed P0 gold metrics to meet minimum promotion thresholds."
        ),
    )
    parser.add_argument(
        "--threshold-metric",
        action="append",
        default=None,
        metavar="NAME=VALUE",
        help=(
            "Optional absolute candidate threshold. Direction comes from the metric definition: "
            "higher-is-better metrics use VALUE as a minimum, lower-is-better metrics use VALUE as a maximum. "
            "Metric names may be plain, group-qualified, or stage.group-qualified."
        ),
    )
    parser.add_argument(
        "--threshold-calibration-report",
        default=None,
        help=(
            "Optional evidence_grounding_threshold_calibration.v1 report. Available recommendations are "
            "applied as explicit threshold metrics. Repeated --threshold-metric values override matching recommendations."
        ),
    )
    args = parser.parse_args()
    threshold_metric_values = _load_threshold_metric_values(
        calibration_report=args.threshold_calibration_report,
        explicit_values=args.threshold_metric,
    )

    report = compare_evidence_grounding_scorecard_reports(
        baseline=Path(args.baseline).expanduser().resolve(),
        candidate=Path(args.candidate).expanduser().resolve(),
        tolerance=args.tolerance,
        gate_metric_names=args.gate_metric,
        gate_preset=args.gate_preset.replace("-", "_"),
        threshold_preset=args.threshold_preset.replace("-", "_"),
        threshold_metric_values=threshold_metric_values,
        out=Path(args.out).expanduser().resolve(),
    )
    print(f"[evidence_grounding_compare] passed={report.decision.passed}")
    print(f"[evidence_grounding_compare] compared_metric_count={report.decision.compared_metric_count}")
    print(f"[evidence_grounding_compare] regressions={','.join(report.decision.regressions) or '-'}")
    print(f"[evidence_grounding_compare] out={Path(args.out).expanduser().resolve()}")
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
