#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.schemas.paper_understanding_gold import (  # noqa: E402
    PaperUnderstandingGoldCandidateDraftPatchResultManifestRequest,
)
from src.services.paper_understanding_gold_drafts import (  # noqa: E402
    write_paper_understanding_gold_candidate_draft_patch_result_manifest,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Apply edited paper-understanding gold candidate draft patch-template JSON files "
            "and write non-canonical patch results."
        )
    )
    parser.add_argument(
        "patch_template",
        action="append",
        help="Patch-template JSON, patch-template manifest JSON, or directory.",
    )
    parser.add_argument("--out-dir", required=True, help="Output directory for patch result JSON files.")
    args = parser.parse_args()

    manifest = write_paper_understanding_gold_candidate_draft_patch_result_manifest(
        PaperUnderstandingGoldCandidateDraftPatchResultManifestRequest(
            patch_template_paths=[str(Path(path).expanduser().resolve()) for path in args.patch_template],
            out_dir=str(Path(args.out_dir).expanduser().resolve()),
        )
    )
    print(f"[paper_understanding_gold_candidate_draft_patch_results] result_count={manifest.result_count}")
    print(f"[paper_understanding_gold_candidate_draft_patch_results] curation_ready_count={manifest.curation_ready_count}")
    print(f"[paper_understanding_gold_candidate_draft_patch_results] not_ready_count={manifest.not_ready_count}")
    print(f"[paper_understanding_gold_candidate_draft_patch_results] readiness_summary={manifest.readiness_summary}")
    print(
        "[paper_understanding_gold_candidate_draft_patch_results] "
        f"manifest={Path(args.out_dir).expanduser().resolve() / 'manifest.json'}"
    )
    return 0 if manifest.result_count > 0 and manifest.not_ready_count == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
