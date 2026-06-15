#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.services.evidence_grounding_benchmark import (  # noqa: E402
    build_evidence_grounding_p0_overstatement_review_summary,
    write_evidence_grounding_p0_overstatement_review_summary_open_issue_csv,
    write_evidence_grounding_p0_overstatement_review_summary,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Validate reviewer decisions from a P0 overstatement packet and summarize "
            "overstatement_rate as non-canonical review-gate evidence."
        )
    )
    parser.add_argument("--packet", required=True, help="P0 overstatement review packet JSON path.")
    parser.add_argument(
        "--reviewed-csv",
        default=None,
        help="Optional reviewed CSV exported from the packet with reviewer_decision/rationale filled.",
    )
    parser.add_argument("--out", required=True, help="Output summary JSON path.")
    parser.add_argument(
        "--open-issue-csv-out",
        default=None,
        help=(
            "Optional diagnostic CSV containing only rows with missing, invalid, uncertain, "
            "or rationale-missing review issues. This is a worklist, not an approval source."
        ),
    )
    args = parser.parse_args()

    summary = build_evidence_grounding_p0_overstatement_review_summary(
        packet_path=Path(args.packet),
        reviewed_csv_path=Path(args.reviewed_csv) if args.reviewed_csv else None,
    )
    open_issue_csv_out = (
        write_evidence_grounding_p0_overstatement_review_summary_open_issue_csv(
            summary,
            Path(args.open_issue_csv_out),
        )
        if args.open_issue_csv_out
        else None
    )
    out = write_evidence_grounding_p0_overstatement_review_summary(summary, Path(args.out))
    print(f"[p0_overstatement_review_summary] ready_for_p0_metric={summary.ready_for_p0_metric}")
    print(f"[p0_overstatement_review_summary] claim_review_row_count={summary.claim_review_row_count}")
    print(f"[p0_overstatement_review_summary] included_claim_count={summary.included_claim_count}")
    print(f"[p0_overstatement_review_summary] overstated_claim_count={summary.overstated_claim_count}")
    print(f"[p0_overstatement_review_summary] missing_decision_count={summary.missing_decision_count}")
    print(f"[p0_overstatement_review_summary] invalid_decision_count={summary.invalid_decision_count}")
    print(f"[p0_overstatement_review_summary] missing_rationale_count={summary.missing_rationale_count}")
    print(f"[p0_overstatement_review_summary] out={out}")
    if open_issue_csv_out:
        print(f"[p0_overstatement_review_summary] open_issue_csv_out={open_issue_csv_out}")
    return 0 if summary.ready_for_p0_metric else 1


if __name__ == "__main__":
    raise SystemExit(main())
