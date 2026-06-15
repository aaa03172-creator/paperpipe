#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.services.evidence_grounding_benchmark import (  # noqa: E402
    run_evidence_grounding_benchmark_package_from_manifest_package,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run one evidence-grounding benchmark report per manifest in a "
            "benchmark manifest package."
        )
    )
    parser.add_argument("--manifest-package", required=True, help="Benchmark manifest package JSON path")
    parser.add_argument("--out-dir", required=True, help="Directory for per-split benchmark reports")
    parser.add_argument("--package-id", default="evidence-grounding-benchmark-run-package")
    parser.add_argument("--out", help="Optional output path for the run package JSON")
    args = parser.parse_args()

    package = run_evidence_grounding_benchmark_package_from_manifest_package(
        benchmark_manifest_package_path=Path(args.manifest_package),
        out_dir=Path(args.out_dir),
        package_id=args.package_id,
        out=Path(args.out).expanduser().resolve() if args.out else None,
    )
    print(f"[evidence_grounding_benchmark_run_package] package_id={package.package_id}")
    print(f"[evidence_grounding_benchmark_run_package] report_count={package.report_count}")
    print(f"[evidence_grounding_benchmark_run_package] scorecard_count={package.scorecard_count}")
    print(
        "[evidence_grounding_benchmark_run_package] scorecard_readiness="
        f"pass={package.scorecard_readiness_pass_count} "
        f"warn={package.scorecard_readiness_warn_count} "
        f"fail={package.scorecard_readiness_fail_count}"
    )
    print(f"[evidence_grounding_benchmark_run_package] out_dir={package.out_dir}")
    if args.out:
        print(f"[evidence_grounding_benchmark_run_package] package={Path(args.out).expanduser().resolve()}")
    return 0 if package.report_count > 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
