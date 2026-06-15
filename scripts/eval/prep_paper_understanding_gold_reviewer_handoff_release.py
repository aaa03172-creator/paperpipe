#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.schemas.paper_understanding_gold import (  # noqa: E402
    PaperUnderstandingGoldReviewerHandoffReleasePrepRequest,
)
from src.services.paper_understanding_gold_drafts import (  # noqa: E402
    build_paper_understanding_gold_reviewer_handoff_release_prep_package,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Prepare fixed paper-understanding gold release artifacts from a staged reviewer handoff package."
        )
    )
    parser.add_argument("reviewer_handoff_stage_package", help="Reviewer handoff stage package JSON.")
    parser.add_argument("--out-dir", required=True, help="Output directory for release-prep artifacts.")
    parser.add_argument("--goldset-id", required=True)
    parser.add_argument(
        "--release-prep-id",
        default="paper-understanding-gold-reviewer-handoff-release-prep",
    )
    parser.add_argument("--split", action="append", default=None, help="Split name. May be repeated.")
    parser.add_argument("--required-split", action="append", default=None, help="Required split name. May be repeated.")
    parser.add_argument("--min-ready-per-split", type=int, default=1)
    parser.add_argument("--allow-not-ready", action="store_true")
    parser.add_argument("--allow-multiple-goldset-ids", action="store_true")
    parser.add_argument("--skip-release-package", action="store_true")
    parser.add_argument("--split-staging-out-dir")
    parser.add_argument("--manifest-out-dir")
    parser.add_argument("--split-plan-out")
    parser.add_argument("--release-readiness-out")
    parser.add_argument("--release-package-out")
    parser.add_argument("--out", help="Optional output path for release-prep package JSON.")
    args = parser.parse_args()

    package = build_paper_understanding_gold_reviewer_handoff_release_prep_package(
        PaperUnderstandingGoldReviewerHandoffReleasePrepRequest(
            reviewer_handoff_stage_package_path=str(
                Path(args.reviewer_handoff_stage_package).expanduser().resolve()
            ),
            out_dir=str(Path(args.out_dir).expanduser().resolve()),
            goldset_id=args.goldset_id,
            release_prep_id=args.release_prep_id,
            split_names=args.split or ["seed", "eval", "holdout"],
            required_splits=args.required_split,
            min_ready_per_split=args.min_ready_per_split,
            require_ready=not args.allow_not_ready,
            require_single_goldset_id=not args.allow_multiple_goldset_ids,
            build_release_package=not args.skip_release_package,
            split_staging_out_dir=(
                str(Path(args.split_staging_out_dir).expanduser().resolve())
                if args.split_staging_out_dir
                else None
            ),
            manifest_out_dir=(
                str(Path(args.manifest_out_dir).expanduser().resolve())
                if args.manifest_out_dir
                else None
            ),
            split_plan_out=(
                str(Path(args.split_plan_out).expanduser().resolve())
                if args.split_plan_out
                else None
            ),
            release_readiness_out=(
                str(Path(args.release_readiness_out).expanduser().resolve())
                if args.release_readiness_out
                else None
            ),
            release_package_out=(
                str(Path(args.release_package_out).expanduser().resolve())
                if args.release_package_out
                else None
            ),
            out=str(Path(args.out).expanduser().resolve()) if args.out else None,
        )
    )
    print(f"[paper_understanding_gold_reviewer_handoff_release_prep] staged_count={package.staged_count}")
    print(f"[paper_understanding_gold_reviewer_handoff_release_prep] split_count={package.split_count}")
    print(
        "[paper_understanding_gold_reviewer_handoff_release_prep] "
        f"release_ready_candidate={package.release_ready_candidate}"
    )
    print(f"[paper_understanding_gold_reviewer_handoff_release_prep] release_ready={package.release_ready}")
    print(f"[paper_understanding_gold_reviewer_handoff_release_prep] split_plan={package.split_plan_path}")
    if package.release_package_path:
        print(f"[paper_understanding_gold_reviewer_handoff_release_prep] package={package.release_package_path}")
    return 0 if package.release_ready else 1


if __name__ == "__main__":
    raise SystemExit(main())
