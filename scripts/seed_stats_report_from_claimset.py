#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.services.stats_repair import (
    DEFAULT_STATS_REPAIR_PAPER_IDS,
    seed_stats_reports_from_claimset,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Seed stats_report.json from claimset artifacts (fallback for missing stats report)."
    )
    parser.add_argument(
        "--paper-id",
        action="append",
        dest="paper_ids",
        help="Target paper ID (repeatable). Defaults to a curated 3-paper set.",
    )
    parser.add_argument("--run-id", default=None, help="Optional run_id override for all selected papers.")
    parser.add_argument("--artifacts-root", default="storage/artifacts", help="Artifacts root directory.")
    parser.add_argument("--max-checks", type=int, default=6, help="Maximum checks to generate per paper.")
    parser.add_argument("--write-bootstrap-meta", action="store_true", help="Also patch bootstrap_meta flags.")
    parser.add_argument("--skip-existing", action="store_true", help="Skip papers with existing stats_report.json.")
    parser.add_argument("--dry-run", action="store_true", help="Plan only; do not write files.")
    args = parser.parse_args()

    paper_ids = args.paper_ids if args.paper_ids else list(DEFAULT_STATS_REPAIR_PAPER_IDS)
    artifacts_root = Path(args.artifacts_root)
    results = seed_stats_reports_from_claimset(
        paper_ids=[str(p) for p in paper_ids],
        artifacts_root=artifacts_root,
        run_id=args.run_id,
        max_checks=int(args.max_checks),
        write_bootstrap_meta=bool(args.write_bootstrap_meta),
        skip_existing=bool(args.skip_existing),
        dry_run=bool(args.dry_run),
    )

    for result in results:
        print(
            f"{result.paper_id} | run={result.run_id or '-'} | {result.status} | "
            f"checks={result.checks} | {result.reason}"
        )

    seeded = sum(1 for r in results if r.status == "seeded")
    planned = sum(1 for r in results if r.status == "planned")
    skipped = sum(1 for r in results if r.status == "skipped")
    print(f"summary: seeded={seeded}, planned={planned}, skipped={skipped}, total={len(results)}")


if __name__ == "__main__":
    main()
