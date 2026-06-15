from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.services.paper_understanding_gold_validation import (  # noqa: E402
    build_paper_understanding_gold_manifest,
    validate_gold_paths,
)
from src.skills.storage import atomic_write_text  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build a fixed paper-understanding goldset manifest from validated gold JSON files."
    )
    parser.add_argument("paths", nargs="+", help="paper_understanding_gold.v1 files or directories.")
    parser.add_argument("--goldset-id", required=True, help="Stable goldset identifier.")
    parser.add_argument("--goldset-split", required=True, help="Fixed split name, e.g. seed, eval, holdout.")
    parser.add_argument("--out", required=True, help="Output manifest JSON path.")
    parser.add_argument(
        "--require-ready",
        action="store_true",
        help="Refuse records whose readiness_status is not pass.",
    )
    args = parser.parse_args()

    out = Path(args.out).expanduser().resolve()
    manifest = build_paper_understanding_gold_manifest(
        [Path(path) for path in args.paths],
        goldset_id=args.goldset_id,
        goldset_split=args.goldset_split,
        manifest_path=out,
        require_ready=args.require_ready,
    )
    atomic_write_text(out, manifest.model_dump_json(indent=2))

    validation = validate_gold_paths([out], require_ready=args.require_ready)
    print(f"[paper_understanding_gold_manifest] goldset_id={manifest.goldset_id}")
    print(f"[paper_understanding_gold_manifest] goldset_split={manifest.goldset_split}")
    print(f"[paper_understanding_gold_manifest] item_count={len(manifest.items)}")
    print(f"[paper_understanding_gold_manifest] invalid_count={validation['invalid_count']}")
    print(f"[paper_understanding_gold_manifest] out={out}")
    return 1 if validation["invalid_count"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
