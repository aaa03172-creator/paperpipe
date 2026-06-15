#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.services.paper_understanding_gold_drafts import (  # noqa: E402
    write_paper_understanding_gold_candidate_drafts_from_teacher_verification,
)
from src.services.runtime_paths import goldset_root as default_goldset_root  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Draft non-canonical paper-understanding gold candidates from accepted teacher_verification.v1 files. "
            "The output is a curation aid and does not promote records into accepted fixed gold."
        )
    )
    parser.add_argument("paths", nargs="+", help="teacher_verification.v1 files or directories.")
    parser.add_argument(
        "--goldset-root",
        default=str(default_goldset_root()),
        help="Goldset root. Defaults to PAPERPIPE_GOLDSET_DIR or ./goldset.",
    )
    parser.add_argument(
        "--out-dir",
        default="",
        help=(
            "Output directory for candidate drafts. Defaults to "
            "<goldset>/reviews/paper_understanding_gold_teacher_drafts."
        ),
    )
    parser.add_argument(
        "--include-unaccepted",
        action="store_true",
        help="Also draft from teacher_verification files whose accepted flag is not true.",
    )
    args = parser.parse_args()

    goldset_root = Path(args.goldset_root).expanduser().resolve()
    out_dir = (
        Path(args.out_dir).expanduser().resolve()
        if args.out_dir
        else goldset_root / "reviews" / "paper_understanding_gold_teacher_drafts"
    )
    manifest = write_paper_understanding_gold_candidate_drafts_from_teacher_verification(
        paths=[Path(path).expanduser().resolve() for path in args.paths],
        out_dir=out_dir,
        require_accepted=not args.include_unaccepted,
    )
    print(f"[paper_understanding_gold_teacher_drafts] draft_count={manifest.draft_count}")
    print(f"[paper_understanding_gold_teacher_drafts] readiness_summary={manifest.readiness_summary}")
    print(f"[paper_understanding_gold_teacher_drafts] out_dir={manifest.out_dir}")
    print(f"[paper_understanding_gold_teacher_drafts] manifest={out_dir / 'manifest.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
