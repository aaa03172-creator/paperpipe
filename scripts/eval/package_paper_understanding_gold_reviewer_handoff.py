#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.services.paper_understanding_gold_drafts import (  # noqa: E402
    write_paper_understanding_gold_reviewer_handoff_package,
)


def _format_counts(counts: dict[str, int]) -> str:
    if not counts:
        return "-"
    return ",".join(f"{key}:{value}" for key, value in sorted(counts.items()))


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Build a non-canonical reviewer handoff package from teacher_verification.v1 files: "
            "candidate drafts, curation report, patch templates, progress report, and task export."
        )
    )
    parser.add_argument("paths", nargs="+", help="teacher_verification.v1 files or directories.")
    parser.add_argument("--out-dir", required=True, help="Output directory for the reviewer handoff package.")
    parser.add_argument("--include-unaccepted", action="store_true")
    parser.add_argument("--package-id", default="paper-understanding-gold-reviewer-handoff")
    parser.add_argument("--report-id", default="paper-understanding-gold-teacher-verification-curation")
    parser.add_argument("--reviewer-id", help="Reviewer identifier to prefill in generated patch templates.")
    parser.add_argument("--review-notes", help="Review notes to prefill in generated patch templates.")
    parser.add_argument("--reviewer-guide-out", help="Optional output Markdown reviewer guide path.")
    parser.add_argument("--out", help="Optional output handoff package JSON path.")
    args = parser.parse_args()

    package = write_paper_understanding_gold_reviewer_handoff_package(
        paths=[Path(path).expanduser().resolve() for path in args.paths],
        out_dir=Path(args.out_dir).expanduser().resolve(),
        require_accepted=not args.include_unaccepted,
        package_id=args.package_id,
        report_id=args.report_id,
        reviewer_id=args.reviewer_id,
        review_notes=args.review_notes,
        reviewer_guide_out=Path(args.reviewer_guide_out).expanduser().resolve() if args.reviewer_guide_out else None,
        package_out=Path(args.out).expanduser().resolve() if args.out else None,
    )
    print(f"[paper_understanding_gold_reviewer_handoff_package] package_id={package.package_id}")
    print(f"[paper_understanding_gold_reviewer_handoff_package] draft_count={package.draft_count}")
    print(f"[paper_understanding_gold_reviewer_handoff_package] template_count={package.patch_template_manifest.template_count}")
    print(f"[paper_understanding_gold_reviewer_handoff_package] open_task_count={package.open_task_count}")
    print(
        "[paper_understanding_gold_reviewer_handoff_package] "
        f"curation_stage_counts={_format_counts(package.curation_task_export.curation_stage_counts)}"
    )
    print(
        "[paper_understanding_gold_reviewer_handoff_package] "
        f"review_priority_counts={_format_counts(package.curation_task_export.review_priority_counts)}"
    )
    print(f"[paper_understanding_gold_reviewer_handoff_package] curation_ready={package.curation_ready}")
    print(f"[paper_understanding_gold_reviewer_handoff_package] curation_package={package.curation_package_path}")
    print(
        "[paper_understanding_gold_reviewer_handoff_package] "
        f"patch_template_manifest={package.patch_template_manifest_path}"
    )
    print(f"[paper_understanding_gold_reviewer_handoff_package] task_export={package.curation_task_export_path}")
    if package.curation_task_export_csv_path:
        print(f"[paper_understanding_gold_reviewer_handoff_package] task_export_csv={package.curation_task_export_csv_path}")
    if package.reviewer_guide_path:
        print(f"[paper_understanding_gold_reviewer_handoff_package] reviewer_guide={package.reviewer_guide_path}")
    if args.out:
        print(f"[paper_understanding_gold_reviewer_handoff_package] package={Path(args.out).expanduser().resolve()}")
    return 0 if package.curation_ready else 1


if __name__ == "__main__":
    raise SystemExit(main())
