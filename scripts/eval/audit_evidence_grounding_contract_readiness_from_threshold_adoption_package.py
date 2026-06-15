#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.services.evidence_grounding_benchmark import (  # noqa: E402
    build_evidence_grounding_contract_readiness_report_from_threshold_adoption_package,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawTextHelpFormatter,
        description=(
            "Build contract compatibility from a threshold-adoption package, then audit "
            "migration, backfill, public contract, and approval evidence."
        )
    )
    parser.add_argument("--threshold-adoption-package", required=True)
    parser.add_argument("--compatibility-out", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument(
        "--additional-artifact",
        action="append",
        default=[],
        help=(
            "Additional review/contract artifact to include in compatibility, such as:\n"
            "  evidence_grounding_scorecard.json\n"
            "  scorecard_input_backfill.json\n"
            "  evidence_grounding_benchmark.json\n"
            "  evidence_grounding_benchmark_manifest_package.json\n"
            "  evidence_grounding_benchmark_run_package.json\n"
            "  evidence_grounding_scorecard_comparison.json\n"
            "  evidence_grounding_fixed_goldset_comparison_suite.json\n"
            "  evidence_grounding_fixed_goldset_comparison_suite_package.json\n"
            "  evidence_grounding_fixed_goldset_run_readiness.json\n"
            "  evidence_grounding_threshold_calibration.json\n"
            "  evidence_grounding_threshold_adoption_review.json\n"
            "  evidence_grounding_threshold_adoption_package.json\n"
            "  claim_evidence_eval_candidates.json\n"
            "  claim_evidence_correction_repair_plan.json\n"
            "  p0_overstatement_review_packet.json\n"
            "  p0_overstatement_review_summary.json\n"
            "  active_review_readiness.json\n"
            "  active_reviewer_handoff_refresh.json\n"
            "  claim_evidence_reviewed_eval_fixtures.json\n"
            "  paper_understanding_gold_release_package.json\n"
            "  paper_understanding_gold_release_readiness.json"
        ),
    )
    parser.add_argument("--compatibility-id", default="evidence-grounding-contract-compatibility")
    parser.add_argument("--readiness-id", default="evidence-grounding-contract-readiness")
    parser.add_argument("--skip-embedded-scorecards", action="store_true")
    parser.add_argument("--migration-plan")
    parser.add_argument("--backfill-plan")
    parser.add_argument("--public-contract-doc")
    parser.add_argument("--reviewer-approval-reference")
    parser.add_argument("--allow-external-contract-ready", action="store_true")
    args = parser.parse_args()

    report = build_evidence_grounding_contract_readiness_report_from_threshold_adoption_package(
        threshold_adoption_package_path=Path(args.threshold_adoption_package),
        compatibility_report_out=Path(args.compatibility_out),
        out=Path(args.out).expanduser().resolve(),
        compatibility_id=args.compatibility_id,
        readiness_id=args.readiness_id,
        include_embedded_scorecards=not args.skip_embedded_scorecards,
        additional_artifact_paths=[Path(path) for path in args.additional_artifact],
        migration_plan_path=Path(args.migration_plan) if args.migration_plan else None,
        backfill_plan_path=Path(args.backfill_plan) if args.backfill_plan else None,
        public_contract_doc_path=Path(args.public_contract_doc) if args.public_contract_doc else None,
        reviewer_approval_reference=args.reviewer_approval_reference,
        allow_external_contract_ready=args.allow_external_contract_ready,
    )
    print(f"[evidence_grounding_contract_readiness] readiness_id={report.readiness_id}")
    print(f"[evidence_grounding_contract_readiness] artifact_count={report.artifact_count}")
    print(f"[evidence_grounding_contract_readiness] fail_count={report.fail_count}")
    print(f"[evidence_grounding_contract_readiness] external_contract_ready={report.external_contract_ready}")
    print(f"[evidence_grounding_contract_readiness] compatibility_out={Path(args.compatibility_out).resolve()}")
    print(f"[evidence_grounding_contract_readiness] out={Path(args.out).expanduser().resolve()}")
    return 0 if report.external_contract_ready else 1


if __name__ == "__main__":
    raise SystemExit(main())
