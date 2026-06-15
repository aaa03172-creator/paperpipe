#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from src.services.evidence_grounding_benchmark import run_evidence_grounding_benchmark_from_manifest_path


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build additive evidence grounding scorecards across a benchmark manifest."
    )
    parser.add_argument("--manifest", required=True, help="Benchmark manifest JSON path")
    parser.add_argument("--out", required=True, help="Output benchmark report JSON path")
    args = parser.parse_args()

    report = run_evidence_grounding_benchmark_from_manifest_path(
        Path(args.manifest).expanduser().resolve(),
        out=Path(args.out).expanduser().resolve(),
    )
    print(f"[evidence_grounding_benchmark] benchmark_id={report.benchmark_id}")
    print(f"[evidence_grounding_benchmark] item_count={report.item_count}")
    print(f"[evidence_grounding_benchmark] out={Path(args.out).expanduser().resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
