#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.services.evidence_grounding_benchmark import (  # noqa: E402
    discover_evidence_grounding_benchmark_run_dir_map_from_release_package,
)
from src.services.path_masking import mask_local_paths_in_text  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Discover a paper_id-to-run_dir JSON map for a fixed gold release package "
            "from an existing run root."
        )
    )
    parser.add_argument("--release-package", required=True)
    parser.add_argument("--run-root", required=True)
    parser.add_argument("--out", required=True, help="Output JSON path for the raw run-dir map.")
    parser.add_argument("--report-out", help="Optional output path for the schema-backed discovery report.")
    parser.add_argument(
        "--required-artifact",
        action="append",
        default=[],
        help=(
            "Artifact filename required inside a selectable run directory. May be repeated. "
            "When omitted, the latest run-like child directory is selected if present."
        ),
    )
    args = parser.parse_args()

    report = discover_evidence_grounding_benchmark_run_dir_map_from_release_package(
        release_package_path=Path(args.release_package),
        run_root=Path(args.run_root),
        out=Path(args.out),
        report_out=Path(args.report_out) if args.report_out else None,
        required_artifacts=args.required_artifact,
    )
    print(
        "[evidence_grounding_benchmark_run_dir_map_discovery] "
        f"requested_paper_count={report.requested_paper_count}"
    )
    print(
        "[evidence_grounding_benchmark_run_dir_map_discovery] "
        f"selected_run_dir_count={report.selected_run_dir_count}"
    )
    print(
        "[evidence_grounding_benchmark_run_dir_map_discovery] "
        f"missing_paper_count={report.missing_paper_count}"
    )
    print(
        "[evidence_grounding_benchmark_run_dir_map_discovery] "
        f"missing_paper_ids={','.join(report.missing_paper_ids) or '-'}"
    )
    alternate_paper_ids = sorted(report.candidate_alternate_run_dirs)
    alternate_run_dir_count = sum(
        len(run_dirs) for run_dirs in report.candidate_alternate_run_dirs.values()
    )
    print(
        "[evidence_grounding_benchmark_run_dir_map_discovery] "
        f"candidate_alternate_run_dir_count={alternate_run_dir_count}"
    )
    print(
        "[evidence_grounding_benchmark_run_dir_map_discovery] "
        f"candidate_alternate_paper_ids={','.join(alternate_paper_ids) or '-'}"
    )
    print(
        "[evidence_grounding_benchmark_run_dir_map_discovery] "
        f"out={mask_local_paths_in_text(str(Path(args.out).expanduser().resolve()))}"
    )
    if args.report_out:
        print(
            "[evidence_grounding_benchmark_run_dir_map_discovery] "
            f"report_out={mask_local_paths_in_text(str(Path(args.report_out).expanduser().resolve()))}"
        )
    return 0 if report.selected_run_dir_count > 0 and report.missing_paper_count == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
