#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.schemas.paper_understanding_gold import (  # noqa: E402
    PaperUnderstandingGoldCandidateDraftPatchTemplateManifestRequest,
)
from src.services.paper_understanding_gold_drafts import (  # noqa: E402
    write_paper_understanding_gold_candidate_draft_patch_template_manifest,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build patch-template JSON files for every draft in a teacher-verification curation package."
    )
    parser.add_argument("curation_package", help="paper_understanding_gold_teacher_verification_curation_package.v1 JSON")
    parser.add_argument("--out-dir", required=True, help="Output directory for patch templates.")
    parser.add_argument("--patched-draft-out-dir", help="Suggested output directory for patched candidate drafts.")
    parser.add_argument("--reviewer-id", help="Reviewer identifier to prefill in every template patch_request.")
    parser.add_argument("--review-notes", help="Review notes to prefill in every template patch_request.")
    args = parser.parse_args()

    manifest = write_paper_understanding_gold_candidate_draft_patch_template_manifest(
        PaperUnderstandingGoldCandidateDraftPatchTemplateManifestRequest(
            curation_package_path=str(Path(args.curation_package).expanduser().resolve()),
            out_dir=str(Path(args.out_dir).expanduser().resolve()),
            patched_draft_out_dir=(
                str(Path(args.patched_draft_out_dir).expanduser().resolve())
                if args.patched_draft_out_dir
                else None
            ),
            reviewer_id=args.reviewer_id,
            review_notes=args.review_notes,
        )
    )
    print(f"[paper_understanding_gold_candidate_draft_patch_templates] template_count={manifest.template_count}")
    print(f"[paper_understanding_gold_candidate_draft_patch_templates] open_task_count={manifest.open_task_count}")
    print(f"[paper_understanding_gold_candidate_draft_patch_templates] readiness_summary={manifest.readiness_summary}")
    print(f"[paper_understanding_gold_candidate_draft_patch_templates] manifest={Path(args.out_dir).expanduser().resolve() / 'manifest.json'}")
    return 0 if manifest.open_task_count == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
