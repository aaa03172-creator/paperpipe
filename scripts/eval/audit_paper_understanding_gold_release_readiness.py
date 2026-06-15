#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.services.paper_understanding_gold_validation import (
    build_paper_understanding_gold_release_readiness_report,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Audit whether paper_understanding_gold_manifest.v1 split manifests form a ready fixed-goldset "
            "release candidate. This writes a non-canonical review artifact and does not promote gold records."
        )
    )
    parser.add_argument("manifest_paths", nargs="+", help="paper_understanding_gold_manifest.v1 JSON paths")
    parser.add_argument("--out", required=True, help="Output paper_understanding_gold_release_readiness.v1 JSON path")
    parser.add_argument("--readiness-id", default="paper-understanding-gold-release-readiness")
    parser.add_argument(
        "--required-split",
        action="append",
        default=None,
        help="Required fixed split; may be repeated. Defaults to seed, eval, holdout.",
    )
    parser.add_argument("--min-ready-per-split", type=int, default=1)
    parser.add_argument("--allow-multiple-goldset-ids", action="store_true")
    args = parser.parse_args()

    report = build_paper_understanding_gold_release_readiness_report(
        [Path(path) for path in args.manifest_paths],
        readiness_id=args.readiness_id,
        required_splits=args.required_split,
        min_ready_per_split=args.min_ready_per_split,
        require_single_goldset_id=not args.allow_multiple_goldset_ids,
        out=Path(args.out).expanduser().resolve(),
    )
    print(f"[paper_understanding_gold_release_readiness] readiness_id={report.readiness_id}")
    print(f"[paper_understanding_gold_release_readiness] manifest_count={report.manifest_count}")
    print(f"[paper_understanding_gold_release_readiness] ready_count={report.ready_count}")
    print(f"[paper_understanding_gold_release_readiness] missing_splits={','.join(report.missing_splits) or '-'}")
    print(f"[paper_understanding_gold_release_readiness] blockers={','.join(report.blockers) or '-'}")
    print(f"[paper_understanding_gold_release_readiness] release_ready={report.release_ready}")
    print(f"[paper_understanding_gold_release_readiness] out={Path(args.out).expanduser().resolve()}")
    return 0 if report.release_ready else 1


if __name__ == "__main__":
    raise SystemExit(main())
