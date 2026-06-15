#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.services.paper_understanding_gold_drafts import (  # noqa: E402
    build_paper_understanding_gold_curation_task_export_report,
)


def _format_counts(counts: dict[str, int]) -> str:
    if not counts:
        return "-"
    return ",".join(f"{key}:{value}" for key, value in sorted(counts.items()))


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Export open paper-understanding gold curation tasks from a teacher-verification "
            "curation package into a non-canonical reviewer handoff artifact."
        )
    )
    parser.add_argument("curation_package", help="paper_understanding_gold_teacher_verification_curation_package.v1 JSON")
    parser.add_argument("--patch-template", action="append", default=[], help="Patch template JSON, manifest JSON, or directory.")
    parser.add_argument("--patch-result", action="append", default=[], help="Patch result JSON file or directory.")
    parser.add_argument("--staged", action="append", default=[], help="Staged paper_understanding_gold JSON file or directory.")
    parser.add_argument("--export-id", default="paper-understanding-gold-curation-task-export")
    parser.add_argument("--progress-report-out", help="Optional curation progress report JSON sidecar path.")
    parser.add_argument("--csv-out", help="Optional CSV copy of the open task list.")
    parser.add_argument("--out", required=True, help="Output curation task export JSON path.")
    args = parser.parse_args()

    report = build_paper_understanding_gold_curation_task_export_report(
        curation_package_path=Path(args.curation_package).expanduser().resolve(),
        patch_template_paths=[Path(path).expanduser().resolve() for path in args.patch_template],
        patch_result_paths=[Path(path).expanduser().resolve() for path in args.patch_result],
        staged_paths=[Path(path).expanduser().resolve() for path in args.staged],
        export_id=args.export_id,
        progress_report_out=Path(args.progress_report_out).expanduser().resolve()
        if args.progress_report_out
        else None,
        csv_out=Path(args.csv_out).expanduser().resolve() if args.csv_out else None,
        out=Path(args.out).expanduser().resolve(),
    )
    print(f"[paper_understanding_gold_curation_task_export] export_id={report.export_id}")
    print(f"[paper_understanding_gold_curation_task_export] paper_count={report.paper_count}")
    print(f"[paper_understanding_gold_curation_task_export] open_task_count={report.open_task_count}")
    print(
        "[paper_understanding_gold_curation_task_export] "
        f"curation_stage_counts={_format_counts(report.curation_stage_counts)}"
    )
    print(
        "[paper_understanding_gold_curation_task_export] "
        f"review_priority_counts={_format_counts(report.review_priority_counts)}"
    )
    print(f"[paper_understanding_gold_curation_task_export] out={Path(args.out).expanduser().resolve()}")
    if args.csv_out:
        print(f"[paper_understanding_gold_curation_task_export] csv={Path(args.csv_out).expanduser().resolve()}")
    return 0 if report.open_task_count == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
