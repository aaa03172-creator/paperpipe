#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.services.paper_understanding_gold_validation import (  # noqa: E402
    build_paper_understanding_gold_release_split_plan_from_staging_manifest,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Split one ready paper_understanding_gold_staging_manifest.v1 into seed/eval/holdout "
            "staging manifests and a release package build plan."
        )
    )
    parser.add_argument("staging_manifest", help="Input paper_understanding_gold_staging_manifest.v1 JSON")
    parser.add_argument("--out-dir", required=True, help="Directory for split staging manifests")
    parser.add_argument("--manifest-out-dir", help="Directory where fixed release manifest outputs should be written later")
    parser.add_argument("--plan-id", default="paper-understanding-gold-release-split-plan")
    parser.add_argument("--split", action="append", default=None, help="Split name. May be repeated.")
    parser.add_argument("--min-ready-per-split", type=int, default=1)
    parser.add_argument("--allow-not-ready", action="store_true")
    parser.add_argument("--out", required=True, help="Output split-plan report JSON path")
    args = parser.parse_args()

    report = build_paper_understanding_gold_release_split_plan_from_staging_manifest(
        staging_manifest_path=Path(args.staging_manifest),
        out_dir=Path(args.out_dir),
        manifest_out_dir=Path(args.manifest_out_dir) if args.manifest_out_dir else None,
        plan_id=args.plan_id,
        split_names=args.split,
        min_ready_per_split=args.min_ready_per_split,
        require_ready=not args.allow_not_ready,
        out=Path(args.out),
    )
    print(f"[paper_understanding_gold_release_split_plan] plan_id={report.plan_id}")
    print(f"[paper_understanding_gold_release_split_plan] ready_input_count={report.ready_input_count}")
    print(f"[paper_understanding_gold_release_split_plan] invalid_input_count={report.invalid_input_count}")
    print(f"[paper_understanding_gold_release_split_plan] release_ready_candidate={report.release_ready_candidate}")
    print(f"[paper_understanding_gold_release_split_plan] split_count={len(report.split_items)}")
    print(f"[paper_understanding_gold_release_split_plan] out={Path(args.out).expanduser().resolve()}")
    return 0 if report.release_ready_candidate else 1


if __name__ == "__main__":
    raise SystemExit(main())
