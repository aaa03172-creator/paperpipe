#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.services.paper_understanding_gold_validation import (  # noqa: E402
    build_paper_understanding_gold_release_package_from_split_plan,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Build a non-canonical paper-understanding gold release package from a "
            "paper_understanding_gold_release_split_plan.v1 report."
        )
    )
    parser.add_argument("--goldset-id", required=True)
    parser.add_argument("--split-plan", required=True, help="Input paper_understanding_gold_release_split_plan.v1 JSON")
    parser.add_argument("--release-readiness-out", required=True)
    parser.add_argument("--package-id", default="paper-understanding-gold-release-package")
    parser.add_argument("--package-out")
    parser.add_argument("--allow-not-ready", action="store_true")
    parser.add_argument("--required-split", action="append", default=None)
    parser.add_argument("--min-ready-per-split", type=int, default=1)
    parser.add_argument("--allow-multiple-goldset-ids", action="store_true")
    args = parser.parse_args()

    report = build_paper_understanding_gold_release_package_from_split_plan(
        goldset_id=args.goldset_id,
        split_plan_path=Path(args.split_plan),
        release_readiness_out=Path(args.release_readiness_out),
        package_id=args.package_id,
        package_out=Path(args.package_out) if args.package_out else None,
        require_ready=not args.allow_not_ready,
        required_splits=args.required_split,
        min_ready_per_split=args.min_ready_per_split,
        require_single_goldset_id=not args.allow_multiple_goldset_ids,
    )
    print(f"[paper_understanding_gold_release_package] package_id={report.package_id}")
    print(f"[paper_understanding_gold_release_package] manifest_count={len(report.manifest_paths)}")
    print(f"[paper_understanding_gold_release_package] release_ready={report.release_readiness.release_ready}")
    print(f"[paper_understanding_gold_release_package] release_readiness={report.release_readiness_report_path}")
    if args.package_out:
        print(f"[paper_understanding_gold_release_package] package={Path(args.package_out).expanduser().resolve()}")
    return 0 if report.release_readiness.release_ready else 1


if __name__ == "__main__":
    raise SystemExit(main())
