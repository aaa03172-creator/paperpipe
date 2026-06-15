#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.schemas.paper_understanding_gold import PaperUnderstandingGoldCandidateDraftPatchTemplateRequest  # noqa: E402
from src.services.paper_understanding_gold_drafts import (  # noqa: E402
    build_paper_understanding_gold_candidate_draft_patch_template,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Build a valid patch-request scaffold from a paper_understanding_gold_candidate_draft.v1 file."
        )
    )
    parser.add_argument("draft", help="Candidate draft JSON path.")
    parser.add_argument("--patched-draft-out", help="Suggested patched draft output path in the template patch_request.")
    parser.add_argument("--reviewer-id", help="Reviewer identifier to prefill in the template patch_request.")
    parser.add_argument("--review-notes", help="Review notes to prefill in the template patch_request.")
    parser.add_argument("--out", required=True, help="Output patch template JSON path.")
    args = parser.parse_args()

    template = build_paper_understanding_gold_candidate_draft_patch_template(
        PaperUnderstandingGoldCandidateDraftPatchTemplateRequest(
            draft_path=str(Path(args.draft).expanduser().resolve()),
            patched_draft_out=(
                str(Path(args.patched_draft_out).expanduser().resolve()) if args.patched_draft_out else None
            ),
            reviewer_id=args.reviewer_id,
            review_notes=args.review_notes,
            out=str(Path(args.out).expanduser().resolve()),
        )
    )
    print(f"[paper_understanding_gold_candidate_draft_patch_template] paper_id={template.paper_id}")
    print(f"[paper_understanding_gold_candidate_draft_patch_template] readiness={template.readiness.status}")
    print(f"[paper_understanding_gold_candidate_draft_patch_template] open_task_count={len(template.open_tasks)}")
    print(f"[paper_understanding_gold_candidate_draft_patch_template] out={Path(args.out).expanduser().resolve()}")
    return 0 if template.readiness.status == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
