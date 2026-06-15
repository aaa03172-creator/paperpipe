#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.services.paper_understanding_gold_drafts import (  # noqa: E402
    build_paper_understanding_gold_candidate_draft_curation_progress_report,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Audit progress from a teacher-verification curation package through patch results and staged gold files."
        )
    )
    parser.add_argument("curation_package", help="paper_understanding_gold_teacher_verification_curation_package.v1 JSON")
    parser.add_argument("--patch-template", action="append", default=[], help="Patch template JSON, manifest JSON, or directory.")
    parser.add_argument("--patch-result", action="append", default=[], help="Patch result JSON file or directory.")
    parser.add_argument("--staged", action="append", default=[], help="Staged paper_understanding_gold JSON file or directory.")
    parser.add_argument("--report-id", default="paper-understanding-gold-candidate-draft-curation-progress")
    parser.add_argument("--out", required=True, help="Output curation progress report JSON path.")
    args = parser.parse_args()

    report = build_paper_understanding_gold_candidate_draft_curation_progress_report(
        curation_package_path=Path(args.curation_package).expanduser().resolve(),
        patch_template_paths=[Path(path).expanduser().resolve() for path in args.patch_template],
        patch_result_paths=[Path(path).expanduser().resolve() for path in args.patch_result],
        staged_paths=[Path(path).expanduser().resolve() for path in args.staged],
        report_id=args.report_id,
        out=Path(args.out).expanduser().resolve(),
    )
    print(f"[paper_understanding_gold_curation_progress] report_id={report.report_id}")
    print(f"[paper_understanding_gold_curation_progress] draft_count={report.draft_count}")
    print(f"[paper_understanding_gold_curation_progress] templated_count={report.templated_count}")
    print(f"[paper_understanding_gold_curation_progress] patched_count={report.patched_count}")
    print(f"[paper_understanding_gold_curation_progress] ready_to_stage_count={report.ready_to_stage_count}")
    print(f"[paper_understanding_gold_curation_progress] staged_count={report.staged_count}")
    print(f"[paper_understanding_gold_curation_progress] remaining_task_count={report.remaining_task_count}")
    print(f"[paper_understanding_gold_curation_progress] curation_complete={report.curation_complete}")
    return 0 if report.curation_complete else 1


if __name__ == "__main__":
    raise SystemExit(main())
