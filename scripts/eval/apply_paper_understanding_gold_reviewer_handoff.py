#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.schemas.paper_understanding_gold import (  # noqa: E402
    PaperUnderstandingGoldReviewerHandoffApplyRequest,
)
from src.services.paper_understanding_gold_drafts import (  # noqa: E402
    ReviewerHandoffApplyRequiresEditedError,
    apply_paper_understanding_gold_reviewer_handoff_package,
)


def _format_counts(counts: dict[str, int]) -> str:
    if not counts:
        return "-"
    return ",".join(f"{key}:{value}" for key, value in sorted(counts.items()))


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Apply edited patch templates from a paper-understanding gold reviewer handoff package, "
            "then refresh patch-result, curation-progress, and curation-task export artifacts."
        )
    )
    parser.add_argument("reviewer_handoff_package", help="Reviewer handoff package JSON.")
    parser.add_argument("--out-dir", required=True, help="Output directory for refreshed apply artifacts.")
    parser.add_argument(
        "--apply-id",
        default="paper-understanding-gold-reviewer-handoff-apply",
        help="Stable identifier for the apply package.",
    )
    parser.add_argument("--patch-results-dir", help="Optional output directory for patch result JSON files.")
    parser.add_argument("--progress-out", help="Optional output path for curation progress JSON.")
    parser.add_argument("--tasks-out", help="Optional output path for curation task export JSON.")
    parser.add_argument("--tasks-csv-out", help="Optional output path for curation task export CSV.")
    parser.add_argument("--out", help="Optional output path for the reviewer handoff apply package JSON.")
    parser.add_argument(
        "--require-edited",
        action="store_true",
        help="Exit nonzero without writing the apply package if patch templates are still unedited.",
    )
    args = parser.parse_args()

    try:
        package = apply_paper_understanding_gold_reviewer_handoff_package(
            PaperUnderstandingGoldReviewerHandoffApplyRequest(
                reviewer_handoff_package_path=str(Path(args.reviewer_handoff_package).expanduser().resolve()),
                out_dir=str(Path(args.out_dir).expanduser().resolve()),
                apply_id=args.apply_id,
                patch_results_dir=(
                    str(Path(args.patch_results_dir).expanduser().resolve())
                    if args.patch_results_dir
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
                out=str(Path(args.out).expanduser().resolve()) if args.out else None,
                require_edited=bool(args.require_edited),
            )
        )
    except ReviewerHandoffApplyRequiresEditedError as exc:
        print(f"[paper_understanding_gold_reviewer_handoff_apply] error={exc}")
        print(f"[paper_understanding_gold_reviewer_handoff_apply] finding_count={len(exc.findings)}")
        for index, finding in enumerate(exc.findings, start=1):
            print(f"[paper_understanding_gold_reviewer_handoff_apply] finding.{index}={finding}")
        return 1
    except ValueError as exc:
        print(f"[paper_understanding_gold_reviewer_handoff_apply] error={exc}")
        return 1
    print(f"[paper_understanding_gold_reviewer_handoff_apply] result_count={package.result_count}")
    print(
        "[paper_understanding_gold_reviewer_handoff_apply] "
        f"curation_ready_count={package.curation_ready_count}"
    )
    print(f"[paper_understanding_gold_reviewer_handoff_apply] not_ready_count={package.not_ready_count}")
    print(
        "[paper_understanding_gold_reviewer_handoff_apply] "
        f"ready_to_stage_count={package.ready_to_stage_count}"
    )
    print(
        "[paper_understanding_gold_reviewer_handoff_apply] "
        f"remaining_task_count={package.remaining_task_count}"
    )
    print(
        "[paper_understanding_gold_reviewer_handoff_apply] "
        f"edited_result_count={package.patch_result_manifest.edited_result_count}"
    )
    print(
        "[paper_understanding_gold_reviewer_handoff_apply] "
        f"unedited_result_count={package.patch_result_manifest.unedited_result_count}"
    )
    print(
        "[paper_understanding_gold_reviewer_handoff_apply] "
        f"curation_stage_counts={_format_counts(package.curation_task_export.curation_stage_counts)}"
    )
    print(
        "[paper_understanding_gold_reviewer_handoff_apply] "
        f"review_priority_counts={_format_counts(package.curation_task_export.review_priority_counts)}"
    )
    print(
        "[paper_understanding_gold_reviewer_handoff_apply] "
        f"patch_result_manifest={package.patch_result_manifest_path}"
    )
    return 0 if package.result_count > 0 and package.not_ready_count == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
