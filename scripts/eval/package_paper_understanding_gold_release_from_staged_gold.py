#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.schemas.paper_understanding_gold import PaperUnderstandingGoldReleaseManifestBuildItem
from src.services.paper_understanding_gold_validation import (
    build_paper_understanding_gold_release_package_from_staged_gold,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Build fixed seed/eval/holdout paper-understanding gold manifests from staged review-gold manifests, "
            "then write a non-canonical release-readiness report."
        )
    )
    parser.add_argument("--goldset-id", required=True)
    parser.add_argument(
        "--split-manifest",
        action="append",
        required=True,
        help=(
            "Split build spec as split=NAME,staging=PATH,out=PATH. May be repeated for seed/eval/holdout."
        ),
    )
    parser.add_argument("--release-readiness-out", required=True)
    parser.add_argument("--package-id", default="paper-understanding-gold-release-package")
    parser.add_argument("--package-out")
    parser.add_argument("--allow-not-ready", action="store_true")
    parser.add_argument("--required-split", action="append", default=None)
    parser.add_argument("--min-ready-per-split", type=int, default=1)
    parser.add_argument("--allow-multiple-goldset-ids", action="store_true")
    args = parser.parse_args()

    report = build_paper_understanding_gold_release_package_from_staged_gold(
        goldset_id=args.goldset_id,
        split_manifests=[_parse_split_manifest(raw) for raw in args.split_manifest],
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


def _parse_split_manifest(raw: str) -> PaperUnderstandingGoldReleaseManifestBuildItem:
    values: dict[str, str] = {}
    for item in raw.split(","):
        if "=" not in item:
            raise SystemExit(f"invalid --split-manifest item={item!r}; expected key=value")
        key, value = item.split("=", 1)
        key = key.strip().lower().replace("-", "_")
        value = value.strip()
        if key == "split":
            values["goldset_split"] = value
        elif key in {"staging", "staging_manifest", "staging_manifest_path"}:
            values["staging_manifest_path"] = value
        elif key in {"out", "manifest_out"}:
            values["manifest_out"] = value
        else:
            raise SystemExit(f"unsupported --split-manifest key={key!r}")
    return PaperUnderstandingGoldReleaseManifestBuildItem.model_validate(values)


if __name__ == "__main__":
    raise SystemExit(main())
