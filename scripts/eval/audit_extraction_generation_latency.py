#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"invalid_json_object={path}")
    return payload


def _find_live_generation_metrics(metrics_root: Path) -> list[Path]:
    paths: list[Path] = []
    for path in sorted(metrics_root.rglob("metrics.json")):
        payload = _load_json(path)
        if str(payload.get("schema_version") or "") != "extraction_prediction_generation.v1":
            continue
        mode = str(payload.get("mode") or "").strip().lower()
        if mode.startswith("raw_replay"):
            continue
        if not isinstance(payload.get("rows"), list):
            continue
        paths.append(path)
    return paths


def _build_attempts(metrics_paths: list[Path]) -> dict[str, list[dict[str, Any]]]:
    attempts_by_paper: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for metrics_path in metrics_paths:
        payload = _load_json(metrics_path)
        timeout_seconds = int(payload.get("timeout_seconds") or 0)
        run_id = str(payload.get("run_id") or metrics_path.parent.name)
        generated_at = str(payload.get("generated_at") or "")
        model = str(payload.get("model") or "")
        for row in payload.get("rows") or []:
            if not isinstance(row, dict):
                continue
            paper_id = str(row.get("paper_id") or "").strip()
            if not paper_id:
                continue
            attempts_by_paper[paper_id].append(
                {
                    "paper_id": paper_id,
                    "run_id": run_id,
                    "generated_at": generated_at,
                    "timeout_seconds": timeout_seconds,
                    "status": str(row.get("status") or ""),
                    "error": str(row.get("error") or ""),
                    "model": str(row.get("model") or model),
                    "metrics_path": str(metrics_path),
                    "prediction_path": row.get("prediction_path"),
                    "raw_path": row.get("raw_path"),
                }
            )
    for attempts in attempts_by_paper.values():
        attempts.sort(key=lambda item: (int(item.get("timeout_seconds") or 0), str(item.get("generated_at") or ""), str(item.get("run_id") or "")))
    return dict(sorted(attempts_by_paper.items()))


def classify_attempts(
    attempts: list[dict[str, Any]],
    *,
    default_timeout_seconds: int,
    escalated_timeout_seconds: int,
) -> dict[str, Any]:
    success_timeouts = sorted(
        int(item.get("timeout_seconds") or 0)
        for item in attempts
        if str(item.get("status") or "") == "ok"
    )
    best_success_timeout = success_timeouts[0] if success_timeouts else None
    attempts_within_default = [item for item in attempts if int(item.get("timeout_seconds") or 0) <= default_timeout_seconds]
    attempts_within_escalated = [item for item in attempts if int(item.get("timeout_seconds") or 0) <= escalated_timeout_seconds]
    timed_out_default = any("readtimeout" in str(item.get("error") or "").lower() for item in attempts_within_default)
    timed_out_escalated = any("readtimeout" in str(item.get("error") or "").lower() for item in attempts_within_escalated)

    if best_success_timeout is not None and best_success_timeout <= default_timeout_seconds:
        bucket = "success_within_default_budget"
    elif best_success_timeout is not None and best_success_timeout <= escalated_timeout_seconds:
        bucket = "requires_escalated_budget"
    else:
        bucket = "still_blocked_within_escalated_budget"

    return {
        "bucket": bucket,
        "best_success_timeout_seconds": best_success_timeout,
        "attempt_count": len(attempts),
        "attempted_within_default_budget": bool(attempts_within_default),
        "attempted_within_escalated_budget": bool(attempts_within_escalated),
        "timed_out_within_default_budget": timed_out_default,
        "timed_out_within_escalated_budget": timed_out_escalated,
        "timeouts_observed": sorted({int(item.get("timeout_seconds") or 0) for item in attempts}),
        "attempts": attempts,
    }


def run_audit(
    *,
    metrics_root: Path,
    out_dir: Path,
    run_id: str,
    default_timeout_seconds: int,
    escalated_timeout_seconds: int,
) -> Path:
    metrics_paths = _find_live_generation_metrics(metrics_root)
    attempts_by_paper = _build_attempts(metrics_paths)
    documents: list[dict[str, Any]] = []
    bucket_counts: Counter[str] = Counter()

    for paper_id, attempts in attempts_by_paper.items():
        classification = classify_attempts(
            attempts,
            default_timeout_seconds=default_timeout_seconds,
            escalated_timeout_seconds=escalated_timeout_seconds,
        )
        bucket_counts[classification["bucket"]] += 1
        documents.append(
            {
                "paper_id": paper_id,
                **classification,
            }
        )

    run_root = out_dir / run_id
    summary = {
        "schema_version": "extraction_generation_latency_audit.v1",
        "generated_at": _utc_now_iso(),
        "run_id": run_id,
        "inputs": {
            "metrics_root": str(metrics_root),
            "metrics_file_count": len(metrics_paths),
            "default_timeout_seconds": default_timeout_seconds,
            "escalated_timeout_seconds": escalated_timeout_seconds,
        },
        "document_count": len(documents),
        "bucket_counts": {
            "success_within_default_budget": int(bucket_counts.get("success_within_default_budget", 0)),
            "requires_escalated_budget": int(bucket_counts.get("requires_escalated_budget", 0)),
            "still_blocked_within_escalated_budget": int(bucket_counts.get("still_blocked_within_escalated_budget", 0)),
        },
        "documents_requiring_escalation": [
            item["paper_id"] for item in documents if item["bucket"] == "requires_escalated_budget"
        ],
        "documents_still_blocked": [
            item["paper_id"] for item in documents if item["bucket"] == "still_blocked_within_escalated_budget"
        ],
    }
    details = {
        "schema_version": "extraction_generation_latency_audit_details.v1",
        "generated_at": _utc_now_iso(),
        "run_id": run_id,
        "documents": documents,
    }
    _write_json(run_root / "summary.json", summary)
    _write_json(run_root / "details.json", details)
    return run_root


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Audit extraction generation latency buckets across saved live-generation metrics.")
    parser.add_argument("--metrics-root", required=True, help="Root directory containing extraction generation run folders.")
    parser.add_argument("--out-dir", required=True, help="Directory to write audit outputs into.")
    parser.add_argument("--run-id", default="", help="Optional run id. Defaults to a UTC timestamp.")
    parser.add_argument("--default-timeout-seconds", type=int, default=90)
    parser.add_argument("--escalated-timeout-seconds", type=int, default=120)
    return parser


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()
    run_id = args.run_id.strip() or f"extraction_generation_latency_audit_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    run_root = run_audit(
        metrics_root=Path(args.metrics_root).expanduser().resolve(),
        out_dir=Path(args.out_dir).expanduser().resolve(),
        run_id=run_id,
        default_timeout_seconds=int(args.default_timeout_seconds),
        escalated_timeout_seconds=int(args.escalated_timeout_seconds),
    )
    print(f"[audit_extraction_generation_latency] out={run_root}")
    print(f"[audit_extraction_generation_latency] summary={run_root / 'summary.json'}")


if __name__ == "__main__":
    main()
