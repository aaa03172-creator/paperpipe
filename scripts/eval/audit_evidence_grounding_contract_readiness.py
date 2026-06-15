#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.services.evidence_grounding_benchmark import build_evidence_grounding_contract_readiness_report


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Audit whether evidence-grounding review artifacts have enough migration, backfill, "
            "public contract, and approval evidence to be considered for stable external contract use."
        )
    )
    parser.add_argument("--compatibility-report", required=True, help="Compatibility report JSON path")
    parser.add_argument("--out", required=True, help="Output readiness report JSON path")
    parser.add_argument("--readiness-id", default="evidence-grounding-contract-readiness")
    parser.add_argument("--migration-plan", help="Migration review document path")
    parser.add_argument("--backfill-plan", help="Backfill review document path")
    parser.add_argument("--public-contract-doc", help="Public/stable contract review document path")
    parser.add_argument("--reviewer-approval-reference", help="Explicit human approval reference")
    parser.add_argument(
        "--allow-external-contract-ready",
        action="store_true",
        help="Allow the audit to mark external_contract_ready=true when all checks pass",
    )
    args = parser.parse_args()

    report = build_evidence_grounding_contract_readiness_report(
        compatibility_report_path=Path(args.compatibility_report),
        readiness_id=args.readiness_id,
        migration_plan_path=Path(args.migration_plan) if args.migration_plan else None,
        backfill_plan_path=Path(args.backfill_plan) if args.backfill_plan else None,
        public_contract_doc_path=Path(args.public_contract_doc) if args.public_contract_doc else None,
        reviewer_approval_reference=args.reviewer_approval_reference,
        allow_external_contract_ready=args.allow_external_contract_ready,
        out=Path(args.out).expanduser().resolve(),
    )
    print(f"[evidence_grounding_contract_readiness] readiness_id={report.readiness_id}")
    print(f"[evidence_grounding_contract_readiness] artifact_count={report.artifact_count}")
    print(f"[evidence_grounding_contract_readiness] fail_count={report.fail_count}")
    print(f"[evidence_grounding_contract_readiness] external_contract_ready={report.external_contract_ready}")
    print(f"[evidence_grounding_contract_readiness] out={Path(args.out).expanduser().resolve()}")
    return 0 if report.external_contract_ready else 1


if __name__ == "__main__":
    raise SystemExit(main())
