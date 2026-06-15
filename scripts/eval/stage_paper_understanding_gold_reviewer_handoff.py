#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.schemas.paper_understanding_gold import (  # noqa: E402
    PaperUnderstandingGoldReviewerHandoffStageRequest,
)
from src.services.paper_understanding_gold_drafts import (  # noqa: E402
    stage_paper_understanding_gold_reviewer_handoff_apply_package,
)


def _format_counts(counts: dict[str, int]) -> str:
    if not counts:
        return "-"
    return ",".join(f"{key}:{value}" for key, value in sorted(counts.items()))


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Stage ready paper-understanding gold records from a reviewer handoff apply package, "
            "then refresh curation progress and task export artifacts."
        )
    )
    parser.add_argument("reviewer_handoff_apply_package", help="Reviewer handoff apply package JSON.")
    parser.add_argument("--out-dir", required=True, help="Output directory for staging package artifacts.")
    parser.add_argument(
        "--stage-id",
        default="paper-understanding-gold-reviewer-handoff-stage",
        help="Stable identifier for the stage package.",
    )
    parser.add_argument("--staged-gold-out-dir", help="Optional output directory for staged gold JSON files.")
    parser.add_argument("--progress-out", help="Optional output path for curation progress JSON.")
    parser.add_argument("--tasks-out", help="Optional output path for curation task export JSON.")
    parser.add_argument("--tasks-csv-out", help="Optional output path for curation task export CSV.")
    parser.add_argument(
        "--allow-not-ready",
        action="store_true",
        help="Stage patched drafts even when readiness is warn/fail.",
    )
    parser.add_argument("--out", help="Optional output path for the reviewer handoff stage package JSON.")
    args = parser.parse_args()

    package = stage_paper_understanding_gold_reviewer_handoff_apply_package(
        PaperUnderstandingGoldReviewerHandoffStageRequest(
            reviewer_handoff_apply_package_path=str(
                Path(args.reviewer_handoff_apply_package).expanduser().resolve()
            ),
            out_dir=str(Path(args.out_dir).expanduser().resolve()),
            stage_id=args.stage_id,
            staged_gold_out_dir=(
                str(Path(args.staged_gold_out_dir).expanduser().resolve())
                if args.staged_gold_out_dir
                else None
            ),
            curation_progress_report_out=(
                str(Path(args.progress_out).expanduser().resolve())
                if args.progress_out
                else None
            ),
            curation_task_export_out=(
                str(Path(args.tasks_out).expanduser().resolve())
                if args.tasks_out
                else None
            ),
            curation_task_export_csv_out=(
                str(Path(args.tasks_csv_out).expanduser().resolve())
                if args.tasks_csv_out
                else None
            ),
            require_ready=not args.allow_not_ready,
            out=str(Path(args.out).expanduser().resolve()) if args.out else None,
        )
    )
    print(f"[paper_understanding_gold_reviewer_handoff_stage] staged_count={package.staged_count}")
    print(
        "[paper_understanding_gold_reviewer_handoff_stage] "
        f"curation_complete={package.curation_complete}"
    )
    print(
        "[paper_understanding_gold_reviewer_handoff_stage] "
        f"remaining_task_count={package.remaining_task_count}"
    )
    print(
        "[paper_understanding_gold_reviewer_handoff_stage] "
        f"curation_stage_counts={_format_counts(package.curation_task_export.curation_stage_counts)}"
    )
    print(
        "[paper_understanding_gold_reviewer_handoff_stage] "
        f"review_priority_counts={_format_counts(package.curation_task_export.review_priority_counts)}"
    )
    print(
        "[paper_understanding_gold_reviewer_handoff_stage] "
        f"staging_manifest={package.staging_manifest_path}"
    )
    return 0 if package.staged_count > 0 and package.remaining_task_count == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
