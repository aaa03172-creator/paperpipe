#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.services.paper_understanding_gold_drafts import stage_paper_understanding_gold_from_patch_results
from src.services.runtime_paths import goldset_root as default_goldset_root


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Stage paper-understanding gold JSON files from ready non-canonical candidate-draft patch results."
        )
    )
    parser.add_argument(
        "patch_results",
        nargs="+",
        help="Patch-result JSON, patch-result manifest JSON, or directory.",
    )
    parser.add_argument(
        "--goldset-root",
        default=str(default_goldset_root()),
        help="Goldset root. Defaults to PAPERPIPE_GOLDSET_DIR or ./goldset.",
    )
    parser.add_argument(
        "--out-dir",
        default="",
        help="Output directory. Defaults to <goldset>/reviews/paper_understanding_gold_staged.",
    )
    parser.add_argument(
        "--allow-not-ready",
        action="store_true",
        help="Write staged gold files even when readiness is warn/fail.",
    )
    args = parser.parse_args()

    goldset_root = Path(args.goldset_root).expanduser().resolve()
    out_dir = (
        Path(args.out_dir).expanduser().resolve()
        if args.out_dir
        else goldset_root / "reviews" / "paper_understanding_gold_staged"
    )
    manifest = stage_paper_understanding_gold_from_patch_results(
        patch_result_paths=[Path(path).expanduser().resolve() for path in args.patch_results],
        out_dir=out_dir,
        require_ready=not args.allow_not_ready,
    )
    print(f"[paper_understanding_gold_staging_from_patch_results] staged_count={manifest.staged_count}")
    print(f"[paper_understanding_gold_staging_from_patch_results] out_dir={manifest.out_dir}")
    print(f"[paper_understanding_gold_staging_from_patch_results] manifest={out_dir / 'staging_manifest.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
