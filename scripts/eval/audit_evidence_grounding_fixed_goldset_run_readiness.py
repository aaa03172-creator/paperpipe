#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.services.evidence_grounding_benchmark import (
    build_evidence_grounding_fixed_goldset_run_readiness_report,
    load_evidence_grounding_benchmark_run_dir_map,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Audit whether baseline and candidate run roots cover the same fixed paper-understanding "
            "goldset manifest and contain the required sidecars for evidence-grounding comparison."
        )
    )
    parser.add_argument("--goldset-manifest", required=True)
    parser.add_argument("--baseline-run-root", required=True)
    parser.add_argument("--candidate-run-root", required=True)
    parser.add_argument(
        "--baseline-run-dir-map",
        help="Optional JSON map from paper_id to baseline run_dir.",
    )
    parser.add_argument(
        "--candidate-run-dir-map",
        help="Optional JSON map from paper_id to candidate run_dir.",
    )
    parser.add_argument("--out", required=True)
    parser.add_argument("--readiness-id", default="evidence-grounding-fixed-goldset-run-readiness")
    parser.add_argument(
        "--run-dir-template",
        default="{paper_id}",
        help="Run directory template relative to each run root. Supports {paper_id} and {safe_paper_id}.",
    )
    parser.add_argument(
        "--required-artifact",
        action="append",
        default=None,
        help="Required artifact filename inside each run directory. May be repeated.",
    )
    parser.add_argument(
        "--optional-artifact",
        action="append",
        default=None,
        help="Optional artifact filename inside each run directory. May be repeated.",
    )
    parser.add_argument(
        "--allow-not-ready-gold",
        action="store_true",
        help="Allow schema-valid but not eval-ready gold records in the readiness audit.",
    )
    args = parser.parse_args()

    report = build_evidence_grounding_fixed_goldset_run_readiness_report(
        goldset_manifest_path=Path(args.goldset_manifest),
        baseline_run_root=Path(args.baseline_run_root),
        candidate_run_root=Path(args.candidate_run_root),
        readiness_id=args.readiness_id,
        run_dir_template=args.run_dir_template,
        baseline_run_dir_map=(
            load_evidence_grounding_benchmark_run_dir_map(Path(args.baseline_run_dir_map))
            if args.baseline_run_dir_map
            else None
        ),
        candidate_run_dir_map=(
            load_evidence_grounding_benchmark_run_dir_map(Path(args.candidate_run_dir_map))
            if args.candidate_run_dir_map
            else None
        ),
        required_artifacts=args.required_artifact,
        optional_artifacts=args.optional_artifact,
        require_ready=not args.allow_not_ready_gold,
        out=Path(args.out).expanduser().resolve(),
    )
    print(f"[evidence_grounding_fixed_goldset_run_readiness] readiness_id={report.readiness_id}")
    print(f"[evidence_grounding_fixed_goldset_run_readiness] goldset_item_count={report.goldset_item_count}")
    print(f"[evidence_grounding_fixed_goldset_run_readiness] fail_count={report.fail_count}")
    print(f"[evidence_grounding_fixed_goldset_run_readiness] comparison_run_ready={report.comparison_run_ready}")
    print(f"[evidence_grounding_fixed_goldset_run_readiness] out={Path(args.out).expanduser().resolve()}")
    return 0 if report.comparison_run_ready else 1


if __name__ == "__main__":
    raise SystemExit(main())
