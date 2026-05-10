#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _resolve_summary_path(path: Path) -> Path:
    candidate = path.expanduser().resolve()
    if candidate.is_dir():
        candidate = candidate / "summary.json"
    return candidate


def _load_audit_summary(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"audit_summary_dict_expected={path}")
    return payload


def build_intake_override_coverage_gate_summary(
    *,
    audit_summary: dict[str, Any],
    audit_summary_path: Path | None,
    run_id: str,
    min_feedback_json_rows_for_gate: int,
    min_audited_feedback_coverage: float,
    max_missing_log_count: int,
    max_invalid_feedback_json_count: int,
    max_invalid_intake_override_log_count: int,
) -> dict[str, Any]:
    metrics = audit_summary.get("metrics")
    if not isinstance(metrics, dict):
        raise ValueError("audit_summary_metrics_missing")
    audit_inputs = audit_summary.get("inputs")
    if not isinstance(audit_inputs, dict):
        audit_inputs = {}

    has_feedback_json_count = int(metrics.get("has_feedback_json_count", 0) or 0)
    audited_document_count = int(metrics.get("audited_document_count", 0) or 0)
    missing_log_count = int(metrics.get("missing_intake_override_log_count", 0) or 0)
    invalid_feedback_json_count = int(metrics.get("invalid_feedback_json_count", 0) or 0)
    invalid_intake_override_log_count = int(metrics.get("invalid_intake_override_log_count", 0) or 0)
    feedback_coverage_rate = (
        float(audited_document_count) / float(has_feedback_json_count)
        if has_feedback_json_count > 0
        else None
    )

    gate_applies = has_feedback_json_count >= min_feedback_json_rows_for_gate
    blockers: list[str] = []
    if gate_applies:
        if feedback_coverage_rate is None or feedback_coverage_rate < min_audited_feedback_coverage:
            blockers.append("audited_feedback_coverage_below_threshold")
        if missing_log_count > max_missing_log_count:
            blockers.append("missing_intake_override_logs_above_threshold")
        if invalid_feedback_json_count > max_invalid_feedback_json_count:
            blockers.append("invalid_feedback_json_above_threshold")
        if invalid_intake_override_log_count > max_invalid_intake_override_log_count:
            blockers.append("invalid_intake_override_log_above_threshold")

    return {
        "schema_version": "intake_override_coverage_gate.v1",
        "generated_at": _utc_now_iso(),
        "run_id": run_id,
        "thresholds": {
            "min_feedback_json_rows_for_gate": int(max(min_feedback_json_rows_for_gate, 0)),
            "min_audited_feedback_coverage": float(min_audited_feedback_coverage),
            "max_missing_log_count": int(max(max_missing_log_count, 0)),
            "max_invalid_feedback_json_count": int(max(max_invalid_feedback_json_count, 0)),
            "max_invalid_intake_override_log_count": int(max(max_invalid_intake_override_log_count, 0)),
        },
        "inputs": {
            "audit_summary_path": str(audit_summary_path) if audit_summary_path is not None else None,
            "audit_run_id": audit_summary.get("run_id"),
            "audit_generated_at": audit_summary.get("generated_at"),
            "audit_source": audit_inputs.get("source"),
            "audit_db_path": audit_inputs.get("db_path"),
            "audit_rows_jsonl_path": audit_inputs.get("rows_jsonl_path"),
            "document_count": int(metrics.get("document_count", 0) or 0),
            "has_feedback_json_count": has_feedback_json_count,
            "audited_document_count": audited_document_count,
            "missing_intake_override_log_count": missing_log_count,
            "invalid_feedback_json_count": invalid_feedback_json_count,
            "invalid_intake_override_log_count": invalid_intake_override_log_count,
        },
        "decision": {
            "gate_applies": gate_applies,
            "passed": not blockers,
            "blockers": blockers,
            "feedback_coverage_rate": feedback_coverage_rate,
            "decision_reason": (
                "feedback-bearing rows must stay auditable by intake_override_log once the lane is active"
                if gate_applies
                else "gate skipped because the audit summary does not yet contain enough feedback-bearing rows"
            ),
        },
    }


def run_intake_override_coverage_gate(
    *,
    audit_summary_path: Path,
    out_dir: Path,
    run_id: str,
    min_feedback_json_rows_for_gate: int,
    min_audited_feedback_coverage: float,
    max_missing_log_count: int,
    max_invalid_feedback_json_count: int,
    max_invalid_intake_override_log_count: int,
) -> Path:
    resolved_summary_path = _resolve_summary_path(audit_summary_path)
    summary = build_intake_override_coverage_gate_summary(
        audit_summary=_load_audit_summary(resolved_summary_path),
        audit_summary_path=resolved_summary_path,
        run_id=run_id,
        min_feedback_json_rows_for_gate=min_feedback_json_rows_for_gate,
        min_audited_feedback_coverage=min_audited_feedback_coverage,
        max_missing_log_count=max_missing_log_count,
        max_invalid_feedback_json_count=max_invalid_feedback_json_count,
        max_invalid_intake_override_log_count=max_invalid_intake_override_log_count,
    )
    run_root = out_dir / run_id
    _write_json(run_root / "summary.json", summary)
    return run_root


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Advisory gate that checks whether feedback-bearing rows remain auditable by persisted intake_override_log payloads."
    )
    parser.add_argument(
        "--audit-summary",
        required=True,
        help="Path to an intake override audit summary.json file or its run directory.",
    )
    parser.add_argument(
        "--out-dir",
        default=str(ROOT / "snapshots" / "intake_override_coverage_gate"),
        help="Directory to write the gate summary into.",
    )
    parser.add_argument("--run-id", required=True, help="Output run identifier.")
    parser.add_argument(
        "--min-feedback-json-rows-for-gate",
        type=int,
        default=1,
        help="Minimum count of feedback-bearing rows before the gate starts applying.",
    )
    parser.add_argument(
        "--min-audited-feedback-coverage",
        type=float,
        default=1.0,
        help="Minimum audited_document_count / has_feedback_json_count ratio required when the gate applies.",
    )
    parser.add_argument(
        "--max-missing-log-count",
        type=int,
        default=0,
        help="Maximum allowed missing_intake_override_log_count when the gate applies.",
    )
    parser.add_argument(
        "--max-invalid-feedback-json-count",
        type=int,
        default=0,
        help="Maximum allowed invalid_feedback_json_count when the gate applies.",
    )
    parser.add_argument(
        "--max-invalid-intake-override-log-count",
        type=int,
        default=0,
        help="Maximum allowed invalid_intake_override_log_count when the gate applies.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_arg_parser()
    args = parser.parse_args(argv)
    run_root = run_intake_override_coverage_gate(
        audit_summary_path=Path(args.audit_summary),
        out_dir=Path(args.out_dir).expanduser().resolve(),
        run_id=str(args.run_id),
        min_feedback_json_rows_for_gate=max(int(args.min_feedback_json_rows_for_gate), 0),
        min_audited_feedback_coverage=max(float(args.min_audited_feedback_coverage), 0.0),
        max_missing_log_count=max(int(args.max_missing_log_count), 0),
        max_invalid_feedback_json_count=max(int(args.max_invalid_feedback_json_count), 0),
        max_invalid_intake_override_log_count=max(int(args.max_invalid_intake_override_log_count), 0),
    )
    print(run_root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
