#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _load_jsonl_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []

    rows: list[dict[str, Any]] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        payload = json.loads(line)
        if isinstance(payload, dict):
            rows.append(payload)
    return rows


def _artifact_ids(rows: list[dict[str, Any]]) -> set[str]:
    ids: set[str] = set()
    for row in rows:
        artifact_id = str(row.get("artifact_id") or "").strip()
        if artifact_id:
            ids.add(artifact_id)
    return ids


def _decision_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts = Counter(str(row.get("decision") or "").strip() for row in rows if str(row.get("decision") or "").strip())
    return {key: int(value) for key, value in sorted(counts.items())}


def _downstream_use_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts = Counter(
        str(row.get("downstream_use") or "").strip()
        for row in rows
        if str(row.get("downstream_use") or "").strip()
    )
    return {key: int(value) for key, value in sorted(counts.items())}


def _reason_code_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts = Counter(
        str(row.get("reason_code") or "").strip()
        for row in rows
        if str(row.get("reason_code") or "").strip()
    )
    return {key: int(value) for key, value in sorted(counts.items())}


def _family_summary(
    *,
    artifact_type: str,
    review_rows: list[dict[str, Any]],
    outcome_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    family_review_rows = [row for row in review_rows if str(row.get("artifact_type") or "").strip() == artifact_type]
    family_outcome_rows = [row for row in outcome_rows if str(row.get("artifact_type") or "").strip() == artifact_type]
    review_artifact_ids = _artifact_ids(family_review_rows)
    outcome_artifact_ids = _artifact_ids(family_outcome_rows)
    paired_artifact_ids = sorted(review_artifact_ids & outcome_artifact_ids)
    positive_outcome_count = sum(
        1
        for row in family_outcome_rows
        if str(row.get("decision") or "").strip() in {"reused", "reused_after_correction"}
    )

    return {
        "artifact_type": artifact_type,
        "review_feedback_count": len(family_review_rows),
        "generation_outcome_count": len(family_outcome_rows),
        "review_decision_counts": _decision_counts(family_review_rows),
        "generation_decision_counts": _decision_counts(family_outcome_rows),
        "review_reason_code_counts": _reason_code_counts(family_review_rows),
        "downstream_use_counts": _downstream_use_counts(family_outcome_rows),
        "reviewed_artifact_count": len(review_artifact_ids),
        "outcome_artifact_count": len(outcome_artifact_ids),
        "paired_artifact_count": len(paired_artifact_ids),
        "paired_artifact_ids": paired_artifact_ids,
        "positive_outcome_count": positive_outcome_count,
    }


def build_artifact_history_promotion_gate_summary(
    *,
    review_feedback_rows: list[dict[str, Any]],
    generation_outcome_rows: list[dict[str, Any]],
    required_families: list[str],
    min_review_feedback_events: int,
    min_generation_outcome_events: int,
    min_paired_artifacts: int,
    run_id: str,
) -> dict[str, Any]:
    family_summaries = {
        artifact_type: _family_summary(
            artifact_type=artifact_type,
            review_rows=review_feedback_rows,
            outcome_rows=generation_outcome_rows,
        )
        for artifact_type in required_families
    }

    blockers: list[str] = []
    for artifact_type in required_families:
        summary = family_summaries[artifact_type]
        if summary["review_feedback_count"] < min_review_feedback_events:
            blockers.append(f"{artifact_type}:insufficient_review_feedback_history")
        if summary["generation_outcome_count"] < min_generation_outcome_events:
            blockers.append(f"{artifact_type}:insufficient_generation_outcome_history")
        if summary["paired_artifact_count"] < min_paired_artifacts:
            blockers.append(f"{artifact_type}:insufficient_paired_artifact_history")

    history_collection_started = any(
        summary["review_feedback_count"] > 0 or summary["generation_outcome_count"] > 0
        for summary in family_summaries.values()
    )

    return {
        "schema_version": "artifact_history_promotion_gate.v1",
        "generated_at": _utc_now_iso(),
        "run_id": run_id,
        "advisory_only": True,
        "thresholds": {
            "required_families": list(required_families),
            "min_review_feedback_events": min_review_feedback_events,
            "min_generation_outcome_events": min_generation_outcome_events,
            "min_paired_artifacts": min_paired_artifacts,
        },
        "inputs": {
            "review_feedback_row_count": len(review_feedback_rows),
            "generation_outcome_row_count": len(generation_outcome_rows),
        },
        "families": family_summaries,
        "decision": {
            "history_collection_started": history_collection_started,
            "promotion_ready": not blockers,
            "blockers": blockers,
            "promotion_reason": (
                "artifact promotion remains advisory-only until required families show enough review/outcome "
                "history and paired artifact coverage"
            ),
        },
    }


def run_artifact_history_promotion_gate(
    *,
    review_feedback_log_path: Path,
    generation_outcome_log_path: Path,
    required_families: list[str],
    min_review_feedback_events: int,
    min_generation_outcome_events: int,
    min_paired_artifacts: int,
    out_dir: Path,
    run_id: str,
) -> Path:
    summary = build_artifact_history_promotion_gate_summary(
        review_feedback_rows=_load_jsonl_rows(review_feedback_log_path),
        generation_outcome_rows=_load_jsonl_rows(generation_outcome_log_path),
        required_families=required_families,
        min_review_feedback_events=min_review_feedback_events,
        min_generation_outcome_events=min_generation_outcome_events,
        min_paired_artifacts=min_paired_artifacts,
        run_id=run_id,
    )
    summary["inputs"]["review_feedback_log_path"] = str(review_feedback_log_path)
    summary["inputs"]["generation_outcome_log_path"] = str(generation_outcome_log_path)
    run_root = out_dir / run_id
    _write_json(run_root / "summary.json", summary)
    return run_root


def build_arg_parser() -> argparse.ArgumentParser:
    from src.services.runtime_paths import artifact_generation_outcome_log_path, artifact_review_feedback_log_path

    parser = argparse.ArgumentParser(
        description="Summarize whether bounded artifact history is sufficient to discuss promotion for selected artifact families."
    )
    parser.add_argument(
        "--review-feedback-log",
        default=str(artifact_review_feedback_log_path()),
        help="Artifact review feedback JSONL log path.",
    )
    parser.add_argument(
        "--generation-outcome-log",
        default=str(artifact_generation_outcome_log_path()),
        help="Artifact generation outcome JSONL log path.",
    )
    parser.add_argument(
        "--required-families",
        nargs="+",
        default=["meeting_pack", "protocol_card"],
        help="Artifact families that must meet the bounded history threshold.",
    )
    parser.add_argument(
        "--min-review-feedback-events",
        type=int,
        default=2,
        help="Minimum artifact review feedback rows required per family for this advisory gate.",
    )
    parser.add_argument(
        "--min-generation-outcome-events",
        type=int,
        default=2,
        help="Minimum artifact generation outcome rows required per family for this advisory gate.",
    )
    parser.add_argument(
        "--min-paired-artifacts",
        type=int,
        default=1,
        help="Minimum count of artifact IDs that appear in both logs per family.",
    )
    parser.add_argument(
        "--out-dir",
        default=str(ROOT / "snapshots" / "artifact_history_promotion_gate"),
        help="Output directory for the gate summary.",
    )
    parser.add_argument("--run-id", required=True, help="Output run identifier.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    run_root = run_artifact_history_promotion_gate(
        review_feedback_log_path=Path(args.review_feedback_log).expanduser().resolve(),
        generation_outcome_log_path=Path(args.generation_outcome_log).expanduser().resolve(),
        required_families=[str(item).strip() for item in args.required_families if str(item).strip()],
        min_review_feedback_events=max(int(args.min_review_feedback_events), 0),
        min_generation_outcome_events=max(int(args.min_generation_outcome_events), 0),
        min_paired_artifacts=max(int(args.min_paired_artifacts), 0),
        out_dir=Path(args.out_dir).expanduser().resolve(),
        run_id=str(args.run_id),
    )
    print(run_root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
