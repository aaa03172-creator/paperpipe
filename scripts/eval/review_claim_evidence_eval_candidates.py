#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.schemas.claim_evidence_correction import ClaimEvidenceEvalReviewResolution
from src.services.claim_evidence_corrections import (
    list_claim_evidence_eval_review_queue,
    resolve_claim_evidence_eval_review_record,
)
from src.services.runtime_paths import goldset_root as default_goldset_root


def _default_records_dir(goldset_root: Path) -> Path:
    return goldset_root / "reviews" / "claim_evidence_eval_candidates"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="List or resolve claim/evidence eval-candidate review intake records."
    )
    parser.add_argument(
        "--goldset-root",
        default=str(default_goldset_root()),
        help="Goldset root. Defaults to PAPERPIPE_GOLDSET_DIR or ./goldset.",
    )
    parser.add_argument(
        "--records-dir",
        default="",
        help="Optional review intake directory. Defaults to <goldset>/reviews/claim_evidence_eval_candidates.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    list_parser = subparsers.add_parser("list", help="List pending eval-candidate intake records.")
    list_parser.add_argument("--all", action="store_true", help="Include records that already have a decision.")

    resolve_parser = subparsers.add_parser("resolve", help="Resolve one eval-candidate intake record.")
    resolve_parser.add_argument("--intake-id", required=True)
    resolve_parser.add_argument(
        "--resolution",
        required=True,
        choices=["APPROVE_FOR_EVAL", "REJECT", "NEEDS_MORE_EVIDENCE"],
    )
    resolve_parser.add_argument("--reviewer", default="human")
    resolve_parser.add_argument("--notes", default="")

    args = parser.parse_args()
    goldset_root = Path(args.goldset_root).expanduser().resolve()
    records_dir = Path(args.records_dir).expanduser().resolve() if args.records_dir else _default_records_dir(goldset_root)

    if args.command == "list":
        rows = list_claim_evidence_eval_review_queue(records_dir, include_resolved=bool(args.all))
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return 0

    resolution: ClaimEvidenceEvalReviewResolution = args.resolution
    decision = resolve_claim_evidence_eval_review_record(
        records_dir=records_dir,
        intake_id=args.intake_id,
        resolution=resolution,
        reviewer_id=args.reviewer,
        notes=args.notes,
    )
    print(decision.model_dump_json(indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
