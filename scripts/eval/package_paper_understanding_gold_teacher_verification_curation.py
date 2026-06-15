#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.services.paper_understanding_gold_drafts import (  # noqa: E402
    write_paper_understanding_gold_teacher_verification_curation_package,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Draft non-canonical paper-understanding gold candidates from teacher_verification.v1 files "
            "and immediately write a curation report for reviewer handoff."
        )
    )
    parser.add_argument("paths", nargs="+", help="teacher_verification.v1 files or directories.")
    parser.add_argument(
        "--out-dir",
        help=(
            "Output directory for candidate drafts. Defaults to "
            "<goldset>/reviews/paper_understanding_gold_teacher_drafts."
        ),
    )
    parser.add_argument(
        "--goldset-root",
        default="goldset",
        help="Goldset root used when --out-dir is omitted.",
    )
    parser.add_argument("--include-unaccepted", action="store_true")
    parser.add_argument(
        "--report-id",
        default="paper-understanding-gold-teacher-verification-curation",
    )
    parser.add_argument("--curation-report-out", help="Output curation report JSON path.")
    parser.add_argument("--out", help="Optional output package JSON path.")
    args = parser.parse_args()

    goldset_root = Path(args.goldset_root).expanduser().resolve()
    out_dir = (
        Path(args.out_dir).expanduser().resolve()
        if args.out_dir
        else goldset_root / "reviews" / "paper_understanding_gold_teacher_drafts"
    )
    package = write_paper_understanding_gold_teacher_verification_curation_package(
        paths=[Path(path).expanduser().resolve() for path in args.paths],
        out_dir=out_dir,
        require_accepted=not args.include_unaccepted,
        report_id=args.report_id,
        curation_report_out=Path(args.curation_report_out).expanduser().resolve()
        if args.curation_report_out
        else None,
        package_out=Path(args.out).expanduser().resolve() if args.out else None,
    )
    print(f"[paper_understanding_gold_teacher_curation_package] draft_count={package.draft_manifest.draft_count}")
    print(
        "[paper_understanding_gold_teacher_curation_package] "
        f"readiness_summary={package.draft_manifest.readiness_summary}"
    )
    print(f"[paper_understanding_gold_teacher_curation_package] curation_ready={package.curation_ready}")
    print(f"[paper_understanding_gold_teacher_curation_package] draft_manifest={package.draft_manifest_path}")
    print(f"[paper_understanding_gold_teacher_curation_package] curation_report={package.curation_report_path}")
    if args.out:
        print(f"[paper_understanding_gold_teacher_curation_package] package={Path(args.out).expanduser().resolve()}")
    return 0 if package.curation_ready else 1


if __name__ == "__main__":
    raise SystemExit(main())
