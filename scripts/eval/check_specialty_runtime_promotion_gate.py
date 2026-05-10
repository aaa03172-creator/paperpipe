#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _load_json_object(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"invalid_json_object={path}")
    return payload


def build_promotion_gate_summary(
    *,
    sidecar_metrics: dict[str, Any],
    runtime_shadow_summary: dict[str, Any],
    materialized_shadow_summary: dict[str, Any],
    semantic_shadow_summary: dict[str, Any] | None = None,
    semantic_shadow_compare_metrics: dict[str, Any] | None = None,
    run_id: str,
) -> dict[str, Any]:
    sidecar_passed = bool(
        (((sidecar_metrics.get("comparison") or {}).get("decision") or {}).get("passed"))
    )
    runtime_comparable_count = int(
        runtime_shadow_summary.get("documents_with_shadow_comparable_runtime_artifact") or 0
    )
    materialized_compare_ready_count = int(materialized_shadow_summary.get("compare_ready_count") or 0)
    eligible_document_count = int(materialized_shadow_summary.get("eligible_document_count") or 0)
    runtime_feature_enabled = bool(materialized_shadow_summary.get("runtime_feature_enabled"))
    provider_available = bool(materialized_shadow_summary.get("provider_available"))
    materialized_status_counts = materialized_shadow_summary.get("status_counts") or {}
    materialized_schema_invalid_count = int(materialized_status_counts.get("prediction_schema_invalid") or 0)
    materialized_pairing_mismatch_count = int(materialized_status_counts.get("pairing_mismatch") or 0)
    materialized_schema_invalid_reason_counts = {
        str(code): int(count)
        for code, count in sorted((materialized_shadow_summary.get("schema_invalid_reason_counts") or {}).items())
    }
    semantic_shadow_summary = semantic_shadow_summary or {}
    semantic_shadow_compare_metrics = semantic_shadow_compare_metrics or {}
    semantic_shadow_compare = semantic_shadow_compare_metrics.get("comparison") or {}
    semantic_shadow_compare_decision = semantic_shadow_compare.get("decision") or {}
    semantic_shadow_compare_passed = bool(semantic_shadow_compare_decision.get("passed"))
    semantic_shadow_compare_failed_checks = [
        str(item)
        for item in (semantic_shadow_compare_decision.get("failed_checks") or [])
        if str(item).strip()
    ]
    semantic_compare_ready_count = int(semantic_shadow_summary.get("compare_ready_count") or 0)
    semantic_prediction_written_count = int(semantic_shadow_summary.get("semantic_prediction_written_count") or 0)
    semantic_two_step_rfc_viable = bool(
        semantic_compare_ready_count > 0 and semantic_prediction_written_count > 0 and semantic_shadow_compare_passed
    )

    blockers: list[str] = []
    if not sidecar_passed:
        blockers.append("sidecar_baseline_not_passed")
    if runtime_comparable_count <= 0:
        blockers.append("no_persisted_runtime_specialty_artifact")
    if eligible_document_count <= 0:
        blockers.append("no_eligible_specialty_documents")
    if materialized_compare_ready_count <= 0:
        blockers.append("no_materialized_specialty_shadow_artifact")
    if materialized_schema_invalid_count > 0:
        blockers.append("materialized_shadow_schema_invalid")
    if not provider_available:
        blockers.append("specialty_provider_unavailable")
    if not runtime_feature_enabled:
        blockers.append("runtime_specialty_feature_disabled")

    promotion_ready = not blockers
    return {
        "schema_version": "specialty_runtime_promotion_gate.v1",
        "generated_at": _utc_now_iso(),
        "run_id": run_id,
        "inputs": {
            "sidecar_metrics_run_id": sidecar_metrics.get("run_id"),
            "runtime_shadow_run_id": runtime_shadow_summary.get("run_id"),
            "materialized_shadow_run_id": materialized_shadow_summary.get("run_id"),
            "semantic_shadow_run_id": semantic_shadow_summary.get("run_id"),
            "semantic_shadow_compare_run_id": semantic_shadow_compare_metrics.get("run_id"),
        },
        "sidecar_baseline": {
            "document_count": int(sidecar_metrics.get("document_count") or 0),
            "passed": sidecar_passed,
        },
        "runtime_shadow": {
            "document_count": int(runtime_shadow_summary.get("document_count") or 0),
            "documents_with_shadow_comparable_runtime_artifact": runtime_comparable_count,
        },
        "materialized_shadow": {
            "document_count": int(materialized_shadow_summary.get("document_count") or 0),
            "eligible_document_count": eligible_document_count,
            "compare_ready_count": materialized_compare_ready_count,
            "prediction_schema_invalid_count": materialized_schema_invalid_count,
            "schema_invalid_reason_counts": materialized_schema_invalid_reason_counts,
            "pairing_mismatch_count": materialized_pairing_mismatch_count,
            "runtime_feature_enabled": runtime_feature_enabled,
            "provider_available": provider_available,
        },
        "semantic_shadow": {
            "document_count": int(semantic_shadow_summary.get("document_count") or 0),
            "semantic_prediction_written_count": semantic_prediction_written_count,
            "compare_ready_count": semantic_compare_ready_count,
            "compare_run_document_count": int(semantic_shadow_compare.get("document_count") or 0),
            "compare_passed": semantic_shadow_compare_passed,
            "compare_failed_checks": semantic_shadow_compare_failed_checks,
            "two_step_rfc_viable": semantic_two_step_rfc_viable,
        },
        "decision": {
            "promotion_ready": promotion_ready,
            "blockers": blockers,
        },
    }


def run_promotion_gate(
    *,
    sidecar_metrics_path: Path,
    runtime_shadow_summary_path: Path,
    materialized_shadow_summary_path: Path,
    semantic_shadow_summary_path: Path | None,
    semantic_shadow_compare_metrics_path: Path | None,
    out_dir: Path,
    run_id: str,
) -> Path:
    summary = build_promotion_gate_summary(
        sidecar_metrics=_load_json_object(sidecar_metrics_path),
        runtime_shadow_summary=_load_json_object(runtime_shadow_summary_path),
        materialized_shadow_summary=_load_json_object(materialized_shadow_summary_path),
        semantic_shadow_summary=(
            _load_json_object(semantic_shadow_summary_path) if semantic_shadow_summary_path else None
        ),
        semantic_shadow_compare_metrics=(
            _load_json_object(semantic_shadow_compare_metrics_path) if semantic_shadow_compare_metrics_path else None
        ),
        run_id=run_id,
    )
    run_root = out_dir / run_id
    _write_json(run_root / "summary.json", summary)
    return run_root


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Summarize whether specialty runtime promotion is currently unblocked."
    )
    parser.add_argument("--sidecar-metrics", required=True, help="Sidecar extraction regression metrics JSON.")
    parser.add_argument("--runtime-shadow-summary", required=True, help="Runtime shadow audit summary JSON.")
    parser.add_argument(
        "--materialized-shadow-summary",
        required=True,
        help="Materialized specialty shadow summary JSON.",
    )
    parser.add_argument(
        "--semantic-shadow-summary",
        default=None,
        help="Optional semantic specialty shadow summary JSON.",
    )
    parser.add_argument(
        "--semantic-shadow-compare-metrics",
        default=None,
        help="Optional compare metrics for the semantic specialty shadow lane.",
    )
    parser.add_argument(
        "--out-dir",
        default=str(Path(__file__).resolve().parents[2] / "snapshots" / "extraction_runtime_promotion_gate"),
        help="Output directory for the gate summary.",
    )
    parser.add_argument("--run-id", required=True, help="Output run identifier.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    run_root = run_promotion_gate(
        sidecar_metrics_path=Path(args.sidecar_metrics).expanduser().resolve(),
        runtime_shadow_summary_path=Path(args.runtime_shadow_summary).expanduser().resolve(),
        materialized_shadow_summary_path=Path(args.materialized_shadow_summary).expanduser().resolve(),
        semantic_shadow_summary_path=(
            Path(args.semantic_shadow_summary).expanduser().resolve() if args.semantic_shadow_summary else None
        ),
        semantic_shadow_compare_metrics_path=(
            Path(args.semantic_shadow_compare_metrics).expanduser().resolve()
            if args.semantic_shadow_compare_metrics
            else None
        ),
        out_dir=Path(args.out_dir).expanduser().resolve(),
        run_id=str(args.run_id),
    )
    print(run_root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
