#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.services.paper_understanding_gold_drafts import write_paper_understanding_gold_candidate_drafts
from src.services.runtime_paths import goldset_root as default_goldset_root


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Draft non-canonical paper-understanding gold candidates from reviewed claim/evidence fixtures."
    )
    parser.add_argument(
        "--goldset-root",
        default=str(default_goldset_root()),
        help="Goldset root. Defaults to PAPERPIPE_GOLDSET_DIR or ./goldset.",
    )
    parser.add_argument(
        "--reviewed-dir",
        default="",
        help=(
            "Optional reviewed fixture directory. Defaults to "
            "<goldset>/reviews/claim_evidence_eval_candidates/reviewed."
        ),
    )
    parser.add_argument(
        "--out-dir",
        default="",
        help=(
            "Output directory for candidate drafts. Defaults to "
            "<goldset>/reviews/paper_understanding_gold_drafts."
        ),
    )
    parser.add_argument("--paper-id", default=None, help="Optional paper_id filter.")
    parser.add_argument("--run-id", default=None, help="Optional run_id filter.")
    parser.add_argument("--claim-id", default=None, help="Optional claim_id filter.")
    args = parser.parse_args()

    goldset_root = Path(args.goldset_root).expanduser().resolve()
    reviewed_dir = (
        Path(args.reviewed_dir).expanduser().resolve()
        if args.reviewed_dir
        else goldset_root / "reviews" / "claim_evidence_eval_candidates" / "reviewed"
    )
    out_dir = (
        Path(args.out_dir).expanduser().resolve()
        if args.out_dir
        else goldset_root / "reviews" / "paper_understanding_gold_drafts"
    )
    manifest = write_paper_understanding_gold_candidate_drafts(
        reviewed_dir=reviewed_dir,
        out_dir=out_dir,
        paper_id=args.paper_id,
        run_id=args.run_id,
        claim_id=args.claim_id,
    )
    print(f"[paper_understanding_gold_drafts] draft_count={manifest.draft_count}")
    print(f"[paper_understanding_gold_drafts] out_dir={manifest.out_dir}")
    print(f"[paper_understanding_gold_drafts] manifest={out_dir / 'manifest.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
