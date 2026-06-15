#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.services.paper_understanding_gold_drafts import (  # noqa: E402
    build_paper_understanding_gold_candidate_draft_curation_report,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Audit non-canonical paper-understanding gold candidate drafts and summarize curation blockers."
        )
    )
    parser.add_argument("drafts", nargs="+", help="Candidate draft JSON files or directories.")
    parser.add_argument("--report-id", default="paper-understanding-gold-candidate-draft-curation")
    parser.add_argument("--out", required=True, help="Output curation report JSON path.")
    args = parser.parse_args()

    out = Path(args.out).expanduser().resolve()
    report = build_paper_understanding_gold_candidate_draft_curation_report(
        draft_paths=[Path(path).expanduser().resolve() for path in args.drafts],
        report_id=args.report_id,
        out=out,
    )
    print(f"[paper_understanding_gold_candidate_draft_curation] report_id={report.report_id}")
    print(f"[paper_understanding_gold_candidate_draft_curation] draft_count={report.draft_count}")
    print(f"[paper_understanding_gold_candidate_draft_curation] ready_count={report.ready_count}")
    print(f"[paper_understanding_gold_candidate_draft_curation] fail_count={report.fail_count}")
    print(f"[paper_understanding_gold_candidate_draft_curation] curation_ready={report.curation_ready}")
    print(f"[paper_understanding_gold_candidate_draft_curation] out={out}")
    return 0 if report.curation_ready else 1


if __name__ == "__main__":
    raise SystemExit(main())
