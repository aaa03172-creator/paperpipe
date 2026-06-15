#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.schemas.paper_understanding_gold import PaperUnderstandingGoldCandidateDraftPatchRequest  # noqa: E402
from src.services.paper_understanding_gold_drafts import patch_paper_understanding_gold_candidate_draft  # noqa: E402
from src.skills.storage import atomic_write_text  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Apply a structured non-canonical curation patch to a paper_understanding_gold_candidate_draft.v1 file "
            "and recalculate readiness."
        )
    )
    parser.add_argument("patch_json", help="Patch JSON matching PaperUnderstandingGoldCandidateDraftPatchRequest.")
    parser.add_argument("--out", help="Optional output patched candidate draft path; overrides patch JSON out.")
    parser.add_argument("--result-out", help="Optional output patch result JSON path.")
    args = parser.parse_args()

    payload = json.loads(Path(args.patch_json).expanduser().read_text(encoding="utf-8"))
    if args.out:
        payload["out"] = str(Path(args.out).expanduser().resolve())
    request = PaperUnderstandingGoldCandidateDraftPatchRequest.model_validate(payload)
    result = patch_paper_understanding_gold_candidate_draft(request)
    if args.result_out:
        atomic_write_text(Path(args.result_out).expanduser().resolve(), result.model_dump_json(indent=2))
    print(f"[paper_understanding_gold_candidate_draft_patch] source={result.source_draft_path}")
    print(f"[paper_understanding_gold_candidate_draft_patch] patched={result.patched_draft_path or '-'}")
    print(f"[paper_understanding_gold_candidate_draft_patch] changed_fields={','.join(result.changed_fields) or '-'}")
    print(f"[paper_understanding_gold_candidate_draft_patch] before_readiness={result.before_readiness.status}")
    print(f"[paper_understanding_gold_candidate_draft_patch] after_readiness={result.after_readiness.status}")
    print(f"[paper_understanding_gold_candidate_draft_patch] curation_ready={result.curation_ready}")
    return 0 if result.curation_ready else 1


if __name__ == "__main__":
    raise SystemExit(main())
