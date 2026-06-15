#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.services.evidence_grounding_benchmark import (
    build_evidence_grounding_contract_compatibility_report_from_comparison_suite,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Check evidence-grounding fixed-goldset suite artifacts for supported schema versions and "
            "non-canonical review-gate posture."
        )
    )
    parser.add_argument("--comparison-suite", required=True, help="Path to comparison_suite.json")
    parser.add_argument("--out", required=True, help="Output compatibility report JSON path")
    parser.add_argument("--compatibility-id", default="evidence-grounding-contract-compatibility")
    parser.add_argument("--threshold-calibration-report")
    parser.add_argument("--threshold-adoption-review")
    parser.add_argument(
        "--skip-embedded-scorecards",
        action="store_true",
        help="Do not inspect scorecards embedded in the suite's benchmark reports.",
    )
    args = parser.parse_args()

    report = build_evidence_grounding_contract_compatibility_report_from_comparison_suite(
        comparison_suite_path=Path(args.comparison_suite),
        threshold_calibration_report_path=(
            Path(args.threshold_calibration_report) if args.threshold_calibration_report else None
        ),
        threshold_adoption_review_path=Path(args.threshold_adoption_review) if args.threshold_adoption_review else None,
        compatibility_id=args.compatibility_id,
        include_embedded_scorecards=not args.skip_embedded_scorecards,
        out=Path(args.out).expanduser().resolve(),
    )
    print(f"[evidence_grounding_contract_compatibility] compatibility_id={report.compatibility_id}")
    print(f"[evidence_grounding_contract_compatibility] artifact_count={report.artifact_count}")
    print(f"[evidence_grounding_contract_compatibility] fail_count={report.fail_count}")
    print(f"[evidence_grounding_contract_compatibility] out={Path(args.out).expanduser().resolve()}")
    return 0 if report.fail_count == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
