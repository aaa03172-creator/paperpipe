#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.schemas.evidence_grounding_scorecard import EvidenceGroundingCandidateConfig
from src.services.evidence_grounding_scorecard import (
    build_evidence_grounding_scorecard_from_run_dir,
    write_evidence_grounding_scorecard_to_path,
)
from src.services.path_masking import mask_local_paths_in_text
from src.services.paper_understanding_gold_validation import validate_gold_path


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build an additive evidence grounding scorecard from an existing deepread run directory."
    )
    parser.add_argument("--run-dir", required=True, help="Deepread run directory containing saved sidecars")
    parser.add_argument(
        "--out",
        default=None,
        help="Output scorecard JSON path. Defaults to evidence_grounding_scorecard.json inside --run-dir.",
    )
    parser.add_argument(
        "--paper-understanding-gold",
        default=None,
        help="Optional paper_understanding_gold.v1 JSON path for eval-only gold-scored metrics.",
    )
    parser.add_argument(
        "--candidate-config",
        default=None,
        help="Optional EvidenceGroundingCandidateConfig JSON path. Overrides run-dir candidate_config.json.",
    )
    parser.add_argument(
        "--no-write",
        action="store_true",
        help="Build and print scorecard status without writing an output JSON file.",
    )
    parser.add_argument(
        "--print-json",
        action="store_true",
        help="Print a path-masked scorecard JSON preview to stdout. Status lines are printed to stderr.",
    )
    args = parser.parse_args()

    run_dir = Path(args.run_dir).expanduser().resolve()
    gold_path = Path(args.paper_understanding_gold).expanduser().resolve() if args.paper_understanding_gold else None
    candidate_config_path = Path(args.candidate_config).expanduser().resolve() if args.candidate_config else None
    out = Path(args.out).expanduser().resolve() if args.out else run_dir / "evidence_grounding_scorecard.json"

    gold = None
    if gold_path is not None:
        gold, error = validate_gold_path(gold_path)
        if gold is None:
            raise ValueError(
                f"paper_understanding_gold path is invalid: path={gold_path} error={error or 'unknown validation error'}"
            )

    candidate_config = _load_candidate_config(candidate_config_path) if candidate_config_path is not None else None
    scorecard = build_evidence_grounding_scorecard_from_run_dir(
        run_dir,
        paper_understanding_gold=gold,
        paper_understanding_gold_source=str(gold_path) if gold_path is not None else None,
        candidate_config=candidate_config,
        candidate_config_source=str(candidate_config_path) if candidate_config_path is not None else None,
    )
    if not args.no_write:
        write_evidence_grounding_scorecard_to_path(scorecard, out, run_dir=run_dir)

    status_stream = sys.stderr if args.print_json else sys.stdout
    print(f"[evidence_grounding_scorecard] paper_id={scorecard.paper_id}", file=status_stream)
    print(f"[evidence_grounding_scorecard] run_id={scorecard.run_id}", file=status_stream)
    print(
        f"[evidence_grounding_scorecard] readiness_status={scorecard.readiness_status}",
        file=status_stream,
    )
    print(
        f"[evidence_grounding_scorecard] reason_codes={','.join(scorecard.reason_codes) or '-'}",
        file=status_stream,
    )
    print(
        "[evidence_grounding_scorecard] input_artifact_summary="
        f"source_artifact_count:{scorecard.input_artifact_summary.source_artifact_count},"
        f"input_artifact_diagnostic_count:{scorecard.input_artifact_summary.input_artifact_diagnostic_count},"
        f"core_input_artifact_count:{scorecard.input_artifact_summary.core_input_artifact_count},"
        f"loaded_core_input_artifact_count:{scorecard.input_artifact_summary.loaded_core_input_artifact_count},"
        f"missing_core_input_artifact_count:{scorecard.input_artifact_summary.missing_core_input_artifact_count},"
        f"load_failed_core_input_artifact_count:{scorecard.input_artifact_summary.load_failed_core_input_artifact_count},"
        f"non_core_input_artifact_count:{scorecard.input_artifact_summary.non_core_input_artifact_count}",
        file=status_stream,
    )
    print(
        f"[evidence_grounding_scorecard] write={str(not args.no_write).lower()}",
        file=status_stream,
    )
    print(
        "[evidence_grounding_scorecard] "
        f"out={mask_local_paths_in_text(str(out)) if not args.no_write else '-'}",
        file=status_stream,
    )
    if args.print_json:
        print(_masked_scorecard_json(scorecard))
    return 0


def _load_candidate_config(path: Path) -> EvidenceGroundingCandidateConfig:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return EvidenceGroundingCandidateConfig.model_validate(payload)


def _masked_scorecard_json(scorecard) -> str:
    return mask_local_paths_in_text(scorecard.model_dump_json(indent=2))


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ValueError as exc:
        print(f"[evidence_grounding_scorecard] error={mask_local_paths_in_text(str(exc))}", file=sys.stderr)
        raise SystemExit(2) from exc
