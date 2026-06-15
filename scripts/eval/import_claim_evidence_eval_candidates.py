#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.services.claim_evidence_corrections import (
    claim_evidence_eval_candidate_export_replayability_findings,
    load_claim_evidence_eval_candidate_export_from_path,
    write_claim_evidence_eval_review_intake,
)
from src.services.runtime_paths import goldset_root as default_goldset_root


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Import exported claim/evidence eval candidates into the goldset review intake lane "
            "without promoting them to accepted gold."
        )
    )
    parser.add_argument("--export", required=True, help="Candidate export JSON or JSONL path.")
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
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing intake records.")
    parser.add_argument(
        "--require-replayable",
        action="store_true",
        help="Exit nonzero without writing intake records when the export is not replayable evidence.",
    )
    args = parser.parse_args()

    export_path = Path(args.export).expanduser().resolve()
    goldset_root = Path(args.goldset_root).expanduser().resolve()
    records_dir = (
        Path(args.records_dir).expanduser().resolve()
        if args.records_dir
        else goldset_root / "reviews" / "claim_evidence_eval_candidates"
    )
    export = load_claim_evidence_eval_candidate_export_from_path(export_path)
    replayability_findings = claim_evidence_eval_candidate_export_replayability_findings(export)
    if args.require_replayable and replayability_findings:
        print("[claim_evidence_eval_intake] replayable_evidence=false")
        print(f"[claim_evidence_eval_intake] blocking_findings={','.join(replayability_findings)}")
        return 1
    manifest = write_claim_evidence_eval_review_intake(
        export,
        records_dir=records_dir,
        source_export_path=export_path,
        overwrite=bool(args.overwrite),
    )
    if args.require_replayable:
        print("[claim_evidence_eval_intake] replayable_evidence=true")
    print(f"[claim_evidence_eval_intake] record_count={manifest.record_count}")
    print(f"[claim_evidence_eval_intake] skipped_existing_count={manifest.skipped_existing_count}")
    print(f"[claim_evidence_eval_intake] records_dir={manifest.records_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
