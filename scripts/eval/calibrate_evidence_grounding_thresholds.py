#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.services.evidence_grounding_benchmark import build_evidence_grounding_threshold_calibration_report


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build an additive threshold calibration report from saved evidence-grounding reports."
    )
    parser.add_argument("--report", action="append", required=True, help="Scorecard or benchmark report JSON path")
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
    args = parser.parse_args()

    report = build_evidence_grounding_threshold_calibration_report(
        report_paths=[Path(path) for path in args.report],
        calibration_id=args.calibration_id,
        metric_names=args.metric,
        metric_preset=args.metric_preset.replace("-", "_"),
        out=Path(args.out).expanduser().resolve(),
    )
    print(f"[evidence_grounding_threshold_calibration] calibration_id={report.calibration_id}")
    print(f"[evidence_grounding_threshold_calibration] report_count={report.report_count}")
    print(
        "[evidence_grounding_threshold_calibration] available_metric_count="
        f"{sum(1 for recommendation in report.recommendations if recommendation.status == 'available')}"
    )
    print(f"[evidence_grounding_threshold_calibration] out={Path(args.out).expanduser().resolve()}")
    return 0 if any(recommendation.status == "available" for recommendation in report.recommendations) else 1


if __name__ == "__main__":
    raise SystemExit(main())
