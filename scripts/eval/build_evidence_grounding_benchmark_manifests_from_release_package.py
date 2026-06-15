#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.schemas.evidence_grounding_benchmark import EvidenceGroundingCandidateConfig  # noqa: E402
from src.services.evidence_grounding_benchmark import (  # noqa: E402
    build_evidence_grounding_benchmark_manifest_package_from_release_package,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Build one evidence-grounding benchmark manifest per split from a fixed "
            "paper-understanding gold release package."
        )
    )
    parser.add_argument("--release-package", required=True)
    parser.add_argument("--run-root", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--package-id", default="evidence-grounding-benchmark-manifest-package")
    parser.add_argument("--benchmark-id-prefix", default="evidence-grounding")
    parser.add_argument(
        "--run-dir-template",
        default="{paper_id}",
        help="Run directory template relative to --run-root. Supports {paper_id} and {safe_paper_id}.",
    )
    parser.add_argument(
        "--run-dir-map",
        help=(
            "Optional JSON object or list mapping paper_id to an explicit run_dir. "
            "Relative run_dir values are resolved from the map file directory."
        ),
    )
    parser.add_argument("--candidate-prefix", default="")
    parser.add_argument("--parser-version")
    parser.add_argument("--llm-provider")
    parser.add_argument("--llm-model")
    parser.add_argument("--llm-model-version")
    parser.add_argument("--prompt-version")
    parser.add_argument("--reader-profile-version")
    parser.add_argument(
        "--require-complete-candidate-config",
        action="store_true",
        help=(
            "Fail unless candidate config includes parser, provider, model, model-version, "
            "prompt, and reader-profile lineage."
        ),
    )
    parser.add_argument("--allow-not-ready-gold", action="store_true")
    parser.add_argument("--allow-missing-runs", action="store_true")
    parser.add_argument("--out", help="Optional output path for the package JSON.")
    args = parser.parse_args()

    package = build_evidence_grounding_benchmark_manifest_package_from_release_package(
        release_package_path=Path(args.release_package),
        run_root=Path(args.run_root),
        out_dir=Path(args.out_dir),
        package_id=args.package_id,
        benchmark_id_prefix=args.benchmark_id_prefix,
        run_dir_template=args.run_dir_template,
        run_dir_map_path=Path(args.run_dir_map).expanduser().resolve() if args.run_dir_map else None,
        candidate_prefix=args.candidate_prefix,
        candidate_config=_candidate_config_from_args(args),
        require_complete_candidate_config=args.require_complete_candidate_config,
        require_ready=not args.allow_not_ready_gold,
        require_existing_runs=not args.allow_missing_runs,
        out=Path(args.out).expanduser().resolve() if args.out else None,
    )
    print(f"[evidence_grounding_benchmark_manifest_package] package_id={package.package_id}")
    print(f"[evidence_grounding_benchmark_manifest_package] manifest_count={package.manifest_count}")
    print(f"[evidence_grounding_benchmark_manifest_package] item_count={package.item_count}")
    print(f"[evidence_grounding_benchmark_manifest_package] out_dir={package.out_dir}")
    if args.out:
        print(f"[evidence_grounding_benchmark_manifest_package] package={Path(args.out).expanduser().resolve()}")
    return 0 if package.manifest_count > 0 and package.item_count > 0 else 1


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
