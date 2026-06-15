#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.services.evidence_grounding_benchmark import (
    run_evidence_grounding_fixed_goldset_comparison_suite,
    threshold_metric_values_from_calibration_report,
)
from src.schemas.evidence_grounding_benchmark import EvidenceGroundingCandidateConfig


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run baseline and candidate evidence-grounding benchmarks against the same fixed "
            "paper-understanding goldset manifest, then compare the reports."
        )
    )
    parser.add_argument("--goldset-manifest", required=True)
    parser.add_argument("--baseline-run-root", required=True)
    parser.add_argument("--candidate-run-root", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--suite-id", default="evidence-grounding-fixed-goldset-comparison")
    parser.add_argument("--baseline-benchmark-id", default="baseline")
    parser.add_argument("--candidate-benchmark-id", default="candidate")
    parser.add_argument("--baseline-parser-version", help="Baseline parser version")
    parser.add_argument("--baseline-llm-provider", help="Baseline LLM provider")
    parser.add_argument("--baseline-llm-model", help="Baseline LLM model name")
    parser.add_argument("--baseline-llm-model-version", help="Baseline LLM model version")
    parser.add_argument("--baseline-prompt-version", help="Baseline prompt version")
    parser.add_argument("--baseline-reader-profile-version", help="Baseline reader/profile version")
    parser.add_argument("--candidate-parser-version", help="Candidate parser version")
    parser.add_argument("--candidate-llm-provider", help="Candidate LLM provider")
    parser.add_argument("--candidate-llm-model", help="Candidate LLM model name")
    parser.add_argument("--candidate-llm-model-version", help="Candidate LLM model version")
    parser.add_argument("--candidate-prompt-version", help="Candidate prompt version")
    parser.add_argument("--candidate-reader-profile-version", help="Candidate reader/profile version")
    parser.add_argument(
        "--require-complete-candidate-config",
        action="store_true",
        help=(
            "Fail unless both baseline and candidate configs include parser, provider, model, model-version, "
            "prompt, and reader-profile lineage."
        ),
    )
    parser.add_argument(
        "--run-dir-template",
        default="{paper_id}",
        help="Run directory template relative to each run root. Supports {paper_id} and {safe_paper_id}.",
    )
    parser.add_argument("--tolerance", type=float, default=0.0)
    parser.add_argument(
        "--gate-metric",
        action="append",
        default=None,
        help="Optional metric name to include in the hard regression gate. May be repeated.",
    )
    parser.add_argument(
        "--gate-preset",
        choices=("all-comparable", "p0-gold"),
        default="all-comparable",
    )
    parser.add_argument(
        "--threshold-preset",
        choices=("none", "p0-gold-minimum"),
        default="none",
    )
    parser.add_argument(
        "--threshold-metric",
        action="append",
        default=None,
        metavar="NAME=VALUE",
        help="Optional absolute candidate threshold. May be repeated.",
    )
    parser.add_argument(
        "--threshold-calibration-report",
        default=None,
        help=(
            "Optional evidence_grounding_threshold_calibration.v1 report. Available recommendations are "
            "applied as explicit threshold metrics. Repeated --threshold-metric values override matching recommendations."
        ),
    )
    parser.add_argument(
        "--allow-not-ready-gold",
        action="store_true",
        help="Allow schema-valid but not eval-ready gold records in generated benchmark manifests.",
    )
    parser.add_argument(
        "--allow-missing-runs",
        action="store_true",
        help="Skip missing paper run directories instead of failing manifest generation.",
    )
    args = parser.parse_args()
    threshold_metric_values = _load_threshold_metric_values(
        calibration_report=args.threshold_calibration_report,
        explicit_values=args.threshold_metric,
    )

    report = run_evidence_grounding_fixed_goldset_comparison_suite(
        goldset_manifest_path=Path(args.goldset_manifest),
        baseline_run_root=Path(args.baseline_run_root),
        candidate_run_root=Path(args.candidate_run_root),
        out_dir=Path(args.out_dir),
        suite_id=args.suite_id,
        baseline_benchmark_id=args.baseline_benchmark_id,
        candidate_benchmark_id=args.candidate_benchmark_id,
        run_dir_template=args.run_dir_template,
        tolerance=args.tolerance,
        gate_metric_names=args.gate_metric,
        gate_preset=args.gate_preset.replace("-", "_"),
        threshold_preset=args.threshold_preset.replace("-", "_"),
        threshold_metric_values=threshold_metric_values,
        baseline_candidate_config=_candidate_config_from_args(args, prefix="baseline"),
        candidate_candidate_config=_candidate_config_from_args(args, prefix="candidate"),
        require_complete_candidate_config=args.require_complete_candidate_config,
        require_ready=not args.allow_not_ready_gold,
        require_existing_runs=not args.allow_missing_runs,
    )
    out_dir = Path(args.out_dir).expanduser().resolve()
    print(f"[evidence_grounding_fixed_goldset_comparison] passed={report.decision.passed}")
    print(f"[evidence_grounding_fixed_goldset_comparison] failed_checks={','.join(report.decision.failed_checks) or '-'}")
    print(f"[evidence_grounding_fixed_goldset_comparison] regressions={','.join(report.decision.regressions) or '-'}")
    print(f"[evidence_grounding_fixed_goldset_comparison] out_dir={out_dir}")
    return 0 if report.decision.passed else 1


def _load_threshold_metric_values(
    *,
    calibration_report: str | None,
    explicit_values: list[str] | None,
) -> dict[str, float] | None:
    values: dict[str, float] = {}
    if calibration_report:
        values.update(threshold_metric_values_from_calibration_report(Path(calibration_report).expanduser().resolve()))
    values.update(_parse_threshold_metrics(explicit_values) or {})
    return values or None


def _candidate_config_from_args(args: argparse.Namespace, *, prefix: str) -> EvidenceGroundingCandidateConfig | None:
    config = EvidenceGroundingCandidateConfig(
        parser_version=getattr(args, f"{prefix}_parser_version"),
        llm_provider=getattr(args, f"{prefix}_llm_provider"),
        llm_model=getattr(args, f"{prefix}_llm_model"),
        llm_model_version=getattr(args, f"{prefix}_llm_model_version"),
        prompt_version=getattr(args, f"{prefix}_prompt_version"),
        reader_profile_version=getattr(args, f"{prefix}_reader_profile_version"),
    )
    return config if config.has_lineage() else None


def _parse_threshold_metrics(raw_values: list[str] | None) -> dict[str, float] | None:
    if not raw_values:
        return None
    parsed: dict[str, float] = {}
    for raw_value in raw_values:
        if "=" not in raw_value:
            raise ValueError(f"--threshold-metric must use NAME=VALUE: {raw_value!r}")
        name, value = raw_value.split("=", 1)
        name = name.strip()
        if not name:
            raise ValueError(f"--threshold-metric requires a metric name: {raw_value!r}")
        parsed[name] = float(value.strip())
    return parsed


if __name__ == "__main__":
    raise SystemExit(main())
