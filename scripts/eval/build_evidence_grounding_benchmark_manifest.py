#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.services.evidence_grounding_benchmark import build_evidence_grounding_benchmark_manifest_from_goldset
from src.schemas.evidence_grounding_benchmark import EvidenceGroundingCandidateConfig


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build an evidence-grounding benchmark manifest from a fixed paper-understanding goldset manifest."
    )
    parser.add_argument("--benchmark-id", required=True)
    parser.add_argument("--goldset-manifest", required=True)
    parser.add_argument("--run-root", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument(
        "--run-dir-template",
        default="{paper_id}",
        help="Run directory template relative to --run-root. Supports {paper_id} and {safe_paper_id}.",
    )
    parser.add_argument("--candidate-prefix", default="")
    parser.add_argument("--parser-version", help="Parser version for every generated candidate item")
    parser.add_argument("--llm-provider", help="LLM provider for every generated candidate item")
    parser.add_argument("--llm-model", help="LLM model name for every generated candidate item")
    parser.add_argument("--llm-model-version", help="LLM model version for every generated candidate item")
    parser.add_argument("--prompt-version", help="Prompt version for every generated candidate item")
    parser.add_argument("--reader-profile-version", help="Reader/profile version for every generated candidate item")
    parser.add_argument(
        "--require-complete-candidate-config",
        action="store_true",
        help=(
            "Fail unless candidate config includes parser, provider, model, model-version, "
            "prompt, and reader-profile lineage."
        ),
    )
    parser.add_argument(
        "--allow-not-ready-gold",
        action="store_true",
        help="Allow schema-valid but not eval-ready gold records in the generated benchmark manifest.",
    )
    parser.add_argument(
        "--allow-missing-runs",
        action="store_true",
        help="Include only existing run directories instead of failing on missing runs.",
    )
    args = parser.parse_args()

    manifest = build_evidence_grounding_benchmark_manifest_from_goldset(
        benchmark_id=args.benchmark_id,
        goldset_manifest_path=Path(args.goldset_manifest),
        run_root=Path(args.run_root),
        out=Path(args.out).expanduser().resolve(),
        run_dir_template=args.run_dir_template,
        candidate_prefix=args.candidate_prefix,
        candidate_config=_candidate_config_from_args(args),
        require_complete_candidate_config=args.require_complete_candidate_config,
        require_ready=not args.allow_not_ready_gold,
        require_existing_runs=not args.allow_missing_runs,
    )
    print(f"[evidence_grounding_benchmark_manifest] benchmark_id={manifest.benchmark_id}")
    print(f"[evidence_grounding_benchmark_manifest] item_count={len(manifest.items)}")
    print(f"[evidence_grounding_benchmark_manifest] out={Path(args.out).expanduser().resolve()}")
    return 0


def _candidate_config_from_args(args: argparse.Namespace) -> EvidenceGroundingCandidateConfig | None:
    config = EvidenceGroundingCandidateConfig(
        parser_version=args.parser_version,
        llm_provider=args.llm_provider,
        llm_model=args.llm_model,
        llm_model_version=args.llm_model_version,
        prompt_version=args.prompt_version,
        reader_profile_version=args.reader_profile_version,
    )
    return config if config.has_lineage() else None


if __name__ == "__main__":
    raise SystemExit(main())
