#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.services.claim_evidence_corrections import write_claim_evidence_reviewed_eval_fixtures_sidecar
from src.services.runtime_paths import goldset_root as default_goldset_root


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Package reviewed claim/evidence eval fixtures into a run-dir scorecard sidecar."
    )
    parser.add_argument("--run-dir", required=True, help="Artifact run directory to receive the sidecar.")
    parser.add_argument("--paper-id", default=None, help="Optional paper_id filter.")
    parser.add_argument("--run-id", default=None, help="Optional run_id filter.")
    parser.add_argument("--claim-id", default=None, help="Optional claim_id filter.")
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
    args = parser.parse_args()

    goldset_root = Path(args.goldset_root).expanduser().resolve()
    reviewed_dir = (
        Path(args.reviewed_dir).expanduser().resolve()
        if args.reviewed_dir
        else goldset_root / "reviews" / "claim_evidence_eval_candidates" / "reviewed"
    )
    out_path, fixture_count = write_claim_evidence_reviewed_eval_fixtures_sidecar(
        reviewed_dir=reviewed_dir,
        run_dir=Path(args.run_dir).expanduser().resolve(),
        paper_id=args.paper_id,
        run_id=args.run_id,
        claim_id=args.claim_id,
    )
    print(f"[claim_evidence_reviewed_fixtures] fixture_count={fixture_count}")
    print(f"[claim_evidence_reviewed_fixtures] out={out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
