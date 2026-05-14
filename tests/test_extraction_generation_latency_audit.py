from __future__ import annotations

import json
from pathlib import Path

from scripts.eval.audit_extraction_generation_latency import classify_attempts, run_audit


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def test_classify_attempts_buckets_by_best_success_timeout() -> None:
    default_timeout_seconds = 90
    escalated_timeout_seconds = 120

    within_default = classify_attempts(
        [
            {"timeout_seconds": 20, "status": "error", "error": "ReadTimeout"},
            {"timeout_seconds": 90, "status": "ok", "error": ""},
        ],
        default_timeout_seconds=default_timeout_seconds,
        escalated_timeout_seconds=escalated_timeout_seconds,
    )
    requires_escalation = classify_attempts(
        [
            {"timeout_seconds": 90, "status": "error", "error": "ReadTimeout"},
            {"timeout_seconds": 120, "status": "ok", "error": ""},
        ],
        default_timeout_seconds=default_timeout_seconds,
        escalated_timeout_seconds=escalated_timeout_seconds,
    )
    still_blocked = classify_attempts(
        [
            {"timeout_seconds": 90, "status": "error", "error": "ReadTimeout"},
            {"timeout_seconds": 120, "status": "error", "error": "ReadTimeout"},
        ],
        default_timeout_seconds=default_timeout_seconds,
        escalated_timeout_seconds=escalated_timeout_seconds,
    )

    assert within_default["bucket"] == "success_within_default_budget"
    assert within_default["best_success_timeout_seconds"] == 90
    assert requires_escalation["bucket"] == "requires_escalated_budget"
    assert requires_escalation["best_success_timeout_seconds"] == 120
    assert still_blocked["bucket"] == "still_blocked_within_escalated_budget"
    assert still_blocked["best_success_timeout_seconds"] is None


def test_run_audit_skips_raw_replay_and_writes_bucket_summary(tmp_path: Path) -> None:
    metrics_root = tmp_path / "metrics"
    out_dir = tmp_path / "out"

    _write_json(
        metrics_root / "live_20" / "metrics.json",
        {
            "schema_version": "extraction_prediction_generation.v1",
            "generated_at": "2026-03-28T00:00:00+00:00",
            "run_id": "live_20",
            "timeout_seconds": 20,
            "rows": [
                {
                    "paper_id": "paper-a",
                    "status": "error",
                    "error": "ReadTimeout model=x timeout_seconds=20",
                    "prediction_path": None,
                    "raw_path": "/tmp/a.txt",
                },
                {
                    "paper_id": "paper-b",
                    "status": "error",
                    "error": "ReadTimeout model=x timeout_seconds=20",
                    "prediction_path": None,
                    "raw_path": "/tmp/b.txt",
                },
            ],
        },
    )
    _write_json(
        metrics_root / "live_90" / "metrics.json",
        {
            "schema_version": "extraction_prediction_generation.v1",
            "generated_at": "2026-03-28T00:01:00+00:00",
            "run_id": "live_90",
            "timeout_seconds": 90,
            "rows": [
                {
                    "paper_id": "paper-a",
                    "status": "ok",
                    "error": None,
                    "prediction_path": "/tmp/a.json",
                    "raw_path": "/tmp/a.txt",
                },
                {
                    "paper_id": "paper-c",
                    "status": "error",
                    "error": "ReadTimeout model=x timeout_seconds=90",
                    "prediction_path": None,
                    "raw_path": "/tmp/c.txt",
                },
            ],
        },
    )
    _write_json(
        metrics_root / "live_120" / "metrics.json",
        {
            "schema_version": "extraction_prediction_generation.v1",
            "generated_at": "2026-03-28T00:02:00+00:00",
            "run_id": "live_120",
            "timeout_seconds": 120,
            "rows": [
                {
                    "paper_id": "paper-b",
                    "status": "ok",
                    "error": None,
                    "prediction_path": "/tmp/b.json",
                    "raw_path": "/tmp/b.txt",
                },
                {
                    "paper_id": "paper-c",
                    "status": "error",
                    "error": "ReadTimeout model=x timeout_seconds=120",
                    "prediction_path": None,
                    "raw_path": "/tmp/c.txt",
                },
            ],
        },
    )
    _write_json(
        metrics_root / "raw_replay" / "metrics.json",
        {
            "schema_version": "extraction_prediction_generation.v1",
            "generated_at": "2026-03-28T00:03:00+00:00",
            "run_id": "raw_replay",
            "mode": "raw_replay_current_repair_demo",
            "timeout_seconds": 0,
            "rows": [
                {
                    "paper_id": "paper-ignore",
                    "status": "ok",
                    "error": None,
                    "prediction_path": "/tmp/ignore.json",
                    "raw_path": "/tmp/ignore.txt",
                }
            ],
        },
    )

    run_root = run_audit(
        metrics_root=metrics_root,
        out_dir=out_dir,
        run_id="latency_audit_test",
        default_timeout_seconds=90,
        escalated_timeout_seconds=120,
    )

    summary = json.loads((run_root / "summary.json").read_text(encoding="utf-8"))
    details = json.loads((run_root / "details.json").read_text(encoding="utf-8"))

    assert summary["inputs"]["metrics_file_count"] == 3
    assert summary["bucket_counts"] == {
        "success_within_default_budget": 1,
        "requires_escalated_budget": 1,
        "still_blocked_within_escalated_budget": 1,
    }
    assert summary["documents_requiring_escalation"] == ["paper-b"]
    assert summary["documents_still_blocked"] == ["paper-c"]
    assert [item["paper_id"] for item in details["documents"]] == ["paper-a", "paper-b", "paper-c"]
