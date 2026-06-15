#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.services.evidence_grounding_benchmark import (  # noqa: E402
    build_evidence_grounding_benchmark_run_dir_map_from_manifest_package,
)
from src.services.path_masking import mask_local_paths_in_text  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Export a paper_id-to-run_dir JSON map from an evidence-grounding benchmark manifest package."
        )
    )
    parser.add_argument(
        "--benchmark-manifest-package",
        required=True,
        help="evidence_grounding_benchmark_manifest_package.v1 JSON path.",
    )
    parser.add_argument("--out", required=True, help="Output JSON path for the run-dir map.")
    args = parser.parse_args()

    out = Path(args.out).expanduser().resolve()
    run_dir_map = build_evidence_grounding_benchmark_run_dir_map_from_manifest_package(
        benchmark_manifest_package_path=Path(args.benchmark_manifest_package),
        out=out,
    )
    print(f"[evidence_grounding_benchmark_run_dir_map] item_count={len(run_dir_map)}")
    print(f"[evidence_grounding_benchmark_run_dir_map] out={mask_local_paths_in_text(str(out))}")
    return 0 if run_dir_map else 1


if __name__ == "__main__":
    raise SystemExit(main())
