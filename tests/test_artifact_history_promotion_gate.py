from __future__ import annotations

import json
import subprocess
from pathlib import Path

from scripts.eval.check_artifact_history_promotion_gate import (
    build_artifact_history_promotion_gate_summary,
    run_artifact_history_promotion_gate,
)


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )


def test_build_artifact_history_promotion_gate_summary_reports_missing_history() -> None:
    summary = build_artifact_history_promotion_gate_summary(
        review_feedback_rows=[],
        generation_outcome_rows=[],
        required_families=["meeting_pack", "protocol_card"],
        min_review_feedback_events=2,
        min_generation_outcome_events=2,
        min_paired_artifacts=1,
        run_id="artifact_history_missing",
    )

    assert summary["decision"]["history_collection_started"] is False
    assert summary["decision"]["promotion_ready"] is False
    assert summary["decision"]["blockers"] == [
        "meeting_pack:insufficient_review_feedback_history",
        "meeting_pack:insufficient_generation_outcome_history",
        "meeting_pack:insufficient_paired_artifact_history",
        "protocol_card:insufficient_review_feedback_history",
        "protocol_card:insufficient_generation_outcome_history",
        "protocol_card:insufficient_paired_artifact_history",
    ]


def test_build_artifact_history_promotion_gate_summary_passes_threshold_with_paired_history() -> None:
    review_rows = [
        {
            "artifact_type": "meeting_pack",
            "artifact_id": "meetingpack_001",
            "run_id": "run_001",
            "decision": "correct",
            "reason_code": "framing",
            "actor_id": "reviewer",
            "note": "Tighten framing.",
        },
        {
            "artifact_type": "meeting_pack",
            "artifact_id": "meetingpack_002",
            "run_id": "run_002",
            "decision": "accept",
            "reason_code": "ready",
            "actor_id": "reviewer",
            "note": "Ready.",
        },
        {
            "artifact_type": "protocol_card",
            "artifact_id": "protocol_001",
            "paper_id": "paper_001",
            "decision": "correct",
            "reason_code": "detail",
            "actor_id": "reviewer",
            "note": "Add detail.",
        },
        {
            "artifact_type": "protocol_card",
            "artifact_id": "protocol_002",
            "paper_id": "paper_002",
            "decision": "accept",
            "reason_code": "ready",
            "actor_id": "reviewer",
            "note": "Ready.",
        },
    ]
    outcome_rows = [
        {
            "artifact_type": "meeting_pack",
            "artifact_id": "meetingpack_001",
            "run_id": "run_001",
            "decision": "reused_after_correction",
            "downstream_use": "final_deliverable",
            "actor_id": "reviewer",
            "note": "Used after correction.",
        },
        {
            "artifact_type": "meeting_pack",
            "artifact_id": "meetingpack_002",
            "run_id": "run_002",
            "decision": "reused",
            "downstream_use": "supporting_context",
            "actor_id": "reviewer",
            "note": "Used as context.",
        },
        {
            "artifact_type": "protocol_card",
            "artifact_id": "protocol_001",
            "paper_id": "paper_001",
            "decision": "reused_after_correction",
            "downstream_use": "follow_on_artifact",
            "actor_id": "reviewer",
            "note": "Used after correction.",
        },
        {
            "artifact_type": "protocol_card",
            "artifact_id": "protocol_002",
            "paper_id": "paper_002",
            "decision": "reused",
            "downstream_use": "supporting_context",
            "actor_id": "reviewer",
            "note": "Used as context.",
        },
    ]

    summary = build_artifact_history_promotion_gate_summary(
        review_feedback_rows=review_rows,
        generation_outcome_rows=outcome_rows,
        required_families=["meeting_pack", "protocol_card"],
        min_review_feedback_events=2,
        min_generation_outcome_events=2,
        min_paired_artifacts=1,
        run_id="artifact_history_ready",
    )

    assert summary["decision"]["history_collection_started"] is True
    assert summary["decision"]["promotion_ready"] is True
    assert summary["families"]["meeting_pack"]["paired_artifact_count"] == 2
    assert summary["families"]["meeting_pack"]["positive_outcome_count"] == 2
    assert summary["families"]["protocol_card"]["paired_artifact_count"] == 2
    assert summary["families"]["protocol_card"]["generation_decision_counts"] == {
        "reused": 1,
        "reused_after_correction": 1,
    }


def test_run_artifact_history_promotion_gate_writes_summary(tmp_path: Path) -> None:
    review_log = tmp_path / "artifact_review_feedback.jsonl"
    outcome_log = tmp_path / "artifact_generation_outcomes.jsonl"
    out_dir = tmp_path / "out"
    _write_jsonl(
        review_log,
        [
            {
                "artifact_type": "meeting_pack",
                "artifact_id": "meetingpack_001",
                "run_id": "run_001",
                "decision": "correct",
                "reason_code": "framing",
                "actor_id": "reviewer",
                "note": "Tighten framing.",
            },
            {
                "artifact_type": "meeting_pack",
                "artifact_id": "meetingpack_002",
                "run_id": "run_002",
                "decision": "accept",
                "reason_code": "ready",
                "actor_id": "reviewer",
                "note": "Ready.",
            },
        ],
    )
    _write_jsonl(
        outcome_log,
        [
            {
                "artifact_type": "meeting_pack",
                "artifact_id": "meetingpack_001",
                "run_id": "run_001",
                "decision": "reused_after_correction",
                "downstream_use": "final_deliverable",
                "actor_id": "reviewer",
                "note": "Used after correction.",
            },
            {
                "artifact_type": "meeting_pack",
                "artifact_id": "meetingpack_002",
                "run_id": "run_002",
                "decision": "reused",
                "downstream_use": "supporting_context",
                "actor_id": "reviewer",
                "note": "Used as context.",
            },
        ],
    )

    run_root = run_artifact_history_promotion_gate(
        review_feedback_log_path=review_log,
        generation_outcome_log_path=outcome_log,
        required_families=["meeting_pack"],
        min_review_feedback_events=2,
        min_generation_outcome_events=2,
        min_paired_artifacts=1,
        out_dir=out_dir,
        run_id="artifact_history_run",
    )

    payload = json.loads((run_root / "summary.json").read_text(encoding="utf-8"))
    assert payload["run_id"] == "artifact_history_run"
    assert payload["decision"]["promotion_ready"] is True
    assert payload["inputs"]["review_feedback_log_path"] == str(review_log)


def test_artifact_history_promotion_gate_script_runs_as_cli(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    script = repo_root / "scripts" / "eval" / "check_artifact_history_promotion_gate.py"
    review_log = tmp_path / "artifact_review_feedback.jsonl"
    outcome_log = tmp_path / "artifact_generation_outcomes.jsonl"
    out_dir = tmp_path / "out"
    _write_jsonl(review_log, [])
    _write_jsonl(outcome_log, [])

    completed = subprocess.run(
        [
            "python3",
            str(script),
            "--review-feedback-log",
            str(review_log),
            "--generation-outcome-log",
            str(outcome_log),
            "--run-id",
            "artifact_history_cli_run",
            "--out-dir",
            str(out_dir),
        ],
        cwd=repo_root,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    payload = json.loads((out_dir / "artifact_history_cli_run" / "summary.json").read_text(encoding="utf-8"))
    assert payload["run_id"] == "artifact_history_cli_run"
    assert payload["decision"]["promotion_ready"] is False
