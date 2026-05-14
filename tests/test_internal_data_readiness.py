from __future__ import annotations

import json
import os
import sqlite3
import subprocess
from pathlib import Path

import pytest

import scripts.eval.check_internal_data_readiness as internal_data_readiness
from scripts.eval.check_internal_data_readiness import (
    build_internal_data_readiness_summary,
    run_internal_data_readiness,
)


def _make_intake_override_feedback_json(
    *,
    producer: str,
    status: str = "INDEXED",
    slot: str = "clinical",
    confidence: float = 0.91,
    analysis_available: bool = True,
    llm_tagging_used: bool = False,
    llm_slot_classification_used: bool = False,
) -> str:
    return json.dumps(
        {
            "soft_tags": ["#Clinical"],
            "confidence": confidence,
            "intake_override_log": {
                "schema_version": "intake_override_log.v1",
                "producer": producer,
                "analysis_available": analysis_available,
                "llm_tagging_used": llm_tagging_used,
                "llm_slot_classification_used": llm_slot_classification_used,
                "input_slot": slot,
                "stored_slot": slot,
                "slot_changed": False,
                "input_tags": ["#Clinical"],
                "stored_tags": ["#Clinical"],
                "tags_changed": False,
                "processing_status": status,
                "issues_state": "clear",
                "confidence": confidence,
            },
        }
    )


def _init_intake_override_db(path: Path, rows: list[dict[str, str]] | None = None) -> None:
    conn = sqlite3.connect(path)
    conn.execute(
        """
        CREATE TABLE papers (
            paper_id TEXT PRIMARY KEY,
            status TEXT,
            feedback_json TEXT
        )
        """
    )
    seed_rows = rows or [
        {
            "paper_id": "paper-001",
            "status": "INDEXED",
            "feedback_json": _make_intake_override_feedback_json(
                producer="backfill_analysis",
                status="INDEXED",
            ),
        }
    ]
    conn.executemany(
        """
        INSERT INTO papers (paper_id, status, feedback_json)
        VALUES (:paper_id, :status, :feedback_json)
        """,
        seed_rows,
    )
    conn.commit()
    conn.close()


def _set_empty_artifact_history_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    review_log = tmp_path / "artifact_review_feedback.jsonl"
    outcome_log = tmp_path / "artifact_generation_outcomes.jsonl"
    review_log.write_text("", encoding="utf-8")
    outcome_log.write_text("", encoding="utf-8")
    monkeypatch.setenv("PAPERPIPE_ARTIFACT_REVIEW_FEEDBACK_LOG_PATH", str(review_log))
    monkeypatch.setenv("PAPERPIPE_ARTIFACT_GENERATION_OUTCOME_LOG_PATH", str(outcome_log))


def _set_fake_slot_tuning_review(
    monkeypatch: pytest.MonkeyPatch,
    *,
    summary: dict[str, object] | None,
    run_path: Path | None = None,
    error: str | None = None,
) -> None:
    monkeypatch.setattr(
        internal_data_readiness,
        "_latest_slot_classification_tuning_review_summary",
        lambda: (summary, run_path, error),
    )


def test_build_internal_data_readiness_summary_reports_present_and_missing_surfaces(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db_path = tmp_path / "state.db"
    _init_intake_override_db(db_path)
    monkeypatch.setenv("PAPERPIPE_DB_PATH", str(db_path))
    _set_empty_artifact_history_env(tmp_path, monkeypatch)
    _set_fake_slot_tuning_review(
        monkeypatch,
        summary={
            "decision": {
                "recommended_action": "hold_current_prompt_policy",
                "review_ready": False,
                "paired_compare_status": "regressed",
                "default_rerun_status": "warn",
                "boundary_rerun_status": "warn",
            },
            "signal_summary": {
                "default_rerun_drift_rate": 0.0909,
                "boundary_rerun_drift_rate": 0.25,
            },
        },
        run_path=tmp_path / "snapshots" / "slot_classification_tuning_review" / "slot_review",
    )

    summary = build_internal_data_readiness_summary(run_id="internal_data_repo_check")

    assert summary["decision"]["internal_data_bootstrap_ready"] is True
    assert summary["decision"]["runtime_promotion_ready"] is False
    assert isinstance(summary["decision"]["blockers"], list)
    assert "selected artifact families accumulate enough paired history" in summary["decision"]["runtime_promotion_reason"]

    assert summary["surfaces"]["feedback_corrections"]["status"] == "present"
    assert summary["surfaces"]["feedback_corrections"]["claim_level_link_supported"] is True
    assert summary["surfaces"]["feedback_corrections"]["artifact_family_label_supported"] is False

    assert summary["surfaces"]["project_memory"]["status"] == "present_noncanonical"
    assert summary["surfaces"]["project_memory"]["layer"] == "raw_memory"
    assert summary["surfaces"]["project_memory"]["canonical_status"] == "non_canonical"
    assert summary["surfaces"]["project_context_link_decisions"]["status"] == "present"
    assert summary["surfaces"]["project_context_link_decisions"]["project_scoped_id_validation"] is True

    assert summary["surfaces"]["research_dna_state_transition"]["status"] == "present"
    assert summary["surfaces"]["research_dna_state_transition"]["log_files"]["screening"] == "screening.jsonl"
    assert summary["surfaces"]["request_audits"]["browser_request_audit_table_present"] is True
    assert summary["surfaces"]["artifact_review_feedback"]["status"] == "present"
    assert summary["surfaces"]["artifact_review_feedback"]["artifact_family_label_supported"] is True
    assert summary["surfaces"]["artifact_review_feedback"]["decision_label_supported"] is True
    assert summary["surfaces"]["artifact_generation_outcomes"]["status"] == "present"
    assert summary["surfaces"]["artifact_generation_outcomes"]["downstream_use_label_supported"] is True
    assert summary["surfaces"]["artifact_history_promotion_gate"]["status"] == "present"
    assert summary["surfaces"]["artifact_history_promotion_gate"]["advisory_only"] is True
    assert summary["surfaces"]["artifact_history_promotion_gate"]["required_families"] == [
        "meeting_pack",
        "protocol_card",
    ]
    assert summary["surfaces"]["artifact_history_promotion_gate"]["thresholds"]["min_review_feedback_events"] == 2
    assert isinstance(summary["surfaces"]["artifact_history_promotion_gate"]["decision"]["promotion_ready"], bool)
    assert summary["surfaces"]["artifact_history_promotion_policy"]["status"] == "present"
    assert summary["surfaces"]["artifact_history_promotion_policy"]["policy_mode"] == "manual_review_only"
    assert summary["surfaces"]["artifact_history_promotion_policy"]["allows_automatic_runtime_promotion"] is False
    assert summary["surfaces"]["intake_override_coverage_gate"]["status"] == "present"
    assert summary["surfaces"]["intake_override_coverage_gate"]["decision"]["gate_applies"] is True
    assert summary["surfaces"]["intake_override_coverage_gate"]["decision"]["passed"] is True
    assert summary["surfaces"]["intake_override_producer_ownership"]["status"] == "present"
    assert summary["surfaces"]["intake_override_producer_ownership"]["decision"]["runtime_producer_present"] is False
    assert summary["surfaces"]["intake_override_producer_ownership"]["decision"]["repair_only_mode"] is True
    assert summary["surfaces"]["intake_override_producer_ownership"]["decision"]["runtime_producer_document_count"] == 0
    assert summary["surfaces"]["intake_override_producer_ownership"]["decision"]["repair_producer_document_count"] == 1
    assert summary["surfaces"]["intake_override_producer_ownership"]["decision"]["runtime_producer_coverage_rate"] == 0.0
    assert summary["surfaces"]["intake_override_producer_ownership"]["decision"]["producer_counts"] == {
        "backfill_analysis": 1
    }
    assert summary["surfaces"]["slot_classification_tuning_review"]["status"] == "present"
    assert summary["surfaces"]["slot_classification_tuning_review"]["decision"]["recommended_action"] == "hold_current_prompt_policy"
    assert summary["surfaces"]["slot_classification_tuning_review"]["signal_summary"]["default_rerun_drift_rate"] == 0.0909

    assert summary["category_status"]["project_context_relevance"] == "bootstrap_ready"
    assert summary["category_status"]["state_transition"] == "bootstrap_ready"
    assert summary["category_status"]["artifact_generation"] == "bootstrap_ready"
    assert summary["category_status"]["human_correction"] == "bootstrap_ready"
    assert summary["category_status"]["classification_audit"] == "bootstrap_ready"
    assert summary["category_status"]["classification_runtime_producer"] == "repair_only"
    assert summary["category_status"]["classification_tuning_review"] == "advisory_hold"


def test_compact_internal_data_readiness_text_summarizes_classification_posture() -> None:
    text = internal_data_readiness._compact_internal_data_readiness_text(
        {
            "category_status": {
                "classification_audit": "bootstrap_ready",
                "classification_runtime_producer": "repair_only",
                "classification_tuning_review": "advisory_hold",
            },
            "decision": {
                "internal_data_bootstrap_ready": True,
                "runtime_promotion_ready": False,
                "policy_mode": "manual_review_only",
                "blockers": ["automatic_default_promotion_not_allowed_by_policy"],
            },
        }
    )

    assert text == (
        "bootstrap_ready=True runtime_promotion_ready=False policy=manual_review_only "
        "classification_audit=bootstrap_ready classification_runtime_producer=repair_only "
        "classification_tuning_review=advisory_hold blockers=1"
    )


def test_run_internal_data_readiness_writes_summary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db_path = tmp_path / "state.db"
    _init_intake_override_db(db_path)
    monkeypatch.setenv("PAPERPIPE_DB_PATH", str(db_path))
    _set_empty_artifact_history_env(tmp_path, monkeypatch)
    _set_fake_slot_tuning_review(
        monkeypatch,
        summary={
            "decision": {
                "recommended_action": "manual_slot_tuning_review",
                "review_ready": True,
            },
            "signal_summary": {},
        },
        run_path=tmp_path / "snapshots" / "slot_classification_tuning_review" / "slot_review_ready",
    )

    run_root = run_internal_data_readiness(
        out_dir=tmp_path / "out",
        run_id="internal_data_repo_run",
    )

    payload = json.loads((run_root / "summary.json").read_text(encoding="utf-8"))
    assert payload["run_id"] == "internal_data_repo_run"
    assert payload["decision"]["internal_data_bootstrap_ready"] is True
    assert payload["decision"]["runtime_promotion_ready"] is False
    assert payload["decision"]["runtime_promotion_discussion_ready"] is False
    assert isinstance(payload["minimum_next_events"], list)
    assert payload["surfaces"]["artifact_history_promotion_gate"]["thresholds"]["min_paired_artifacts"] == 1
    assert payload["surfaces"]["intake_override_coverage_gate"]["decision"]["passed"] is True
    assert payload["category_status"]["classification_audit"] == "bootstrap_ready"
    assert payload["category_status"]["classification_runtime_producer"] == "repair_only"
    assert payload["surfaces"]["slot_classification_tuning_review"]["status"] == "present"
    assert payload["category_status"]["classification_tuning_review"] == "review_ready"


def test_internal_data_readiness_script_runs_as_cli(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    script = repo_root / "scripts" / "eval" / "check_internal_data_readiness.py"
    out_dir = tmp_path / "out"
    db_path = tmp_path / "state.db"
    _init_intake_override_db(db_path)
    review_log = tmp_path / "artifact_review_feedback.jsonl"
    outcome_log = tmp_path / "artifact_generation_outcomes.jsonl"
    review_log.write_text("", encoding="utf-8")
    outcome_log.write_text("", encoding="utf-8")

    completed = subprocess.run(
        [
            "python3",
            str(script),
            "--run-id",
            "internal_data_cli_run",
            "--out-dir",
            str(out_dir),
        ],
        cwd=repo_root,
        check=False,
        capture_output=True,
        text=True,
        env={
            **dict(os.environ),
            "PAPERPIPE_DB_PATH": str(db_path),
            "PAPERPIPE_ARTIFACT_REVIEW_FEEDBACK_LOG_PATH": str(review_log),
            "PAPERPIPE_ARTIFACT_GENERATION_OUTCOME_LOG_PATH": str(outcome_log),
        },
    )

    assert completed.returncode == 0, completed.stderr
    normalized_output = " ".join(completed.stdout.split())
    assert "[check_internal_data_readiness] out=" in completed.stdout
    assert "[check_internal_data_readiness] summary=" in completed.stdout
    assert "[check_internal_data_readiness] bootstrap_ready=" in completed.stdout
    assert "classification_audit=bootstrap_ready" in normalized_output
    assert "classification_runtime_producer=repair_only" in normalized_output
    payload = json.loads((out_dir / "internal_data_cli_run" / "summary.json").read_text(encoding="utf-8"))
    assert payload["run_id"] == "internal_data_cli_run"
    assert payload["surfaces"]["artifact_history_promotion_gate"]["status"] == "present"
    assert payload["surfaces"]["artifact_history_promotion_policy"]["status"] == "present"
    assert payload["surfaces"]["intake_override_coverage_gate"]["decision"]["passed"] is True
    assert payload["surfaces"]["intake_override_producer_ownership"]["decision"]["repair_only_mode"] is True


def test_internal_data_readiness_reports_runtime_producer_when_present(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db_path = tmp_path / "state.db"
    _init_intake_override_db(
        db_path,
        rows=[
            {
                "paper_id": "paper-backfill",
                "status": "INDEXED",
                "feedback_json": _make_intake_override_feedback_json(
                    producer="backfill_analysis",
                    status="INDEXED",
                ),
            },
            {
                "paper_id": "paper-runtime",
                "status": "APPROVED",
                "feedback_json": _make_intake_override_feedback_json(
                    producer="processor_gate",
                    status="APPROVED",
                ),
            },
        ],
    )
    monkeypatch.setenv("PAPERPIPE_DB_PATH", str(db_path))
    _set_empty_artifact_history_env(tmp_path, monkeypatch)

    summary = build_internal_data_readiness_summary(run_id="internal_data_runtime_producer_present")

    assert summary["surfaces"]["intake_override_producer_ownership"]["decision"]["runtime_producer_present"] is True
    assert summary["surfaces"]["intake_override_producer_ownership"]["decision"]["repair_only_mode"] is False
    assert summary["surfaces"]["intake_override_producer_ownership"]["decision"]["runtime_producer_document_count"] == 1
    assert summary["surfaces"]["intake_override_producer_ownership"]["decision"]["repair_producer_document_count"] == 1
    assert summary["surfaces"]["intake_override_producer_ownership"]["decision"]["runtime_producer_coverage_rate"] == 0.5
    assert summary["surfaces"]["intake_override_producer_ownership"]["decision"]["primary_runtime_producer"] == "processor_gate"
    assert summary["surfaces"]["intake_override_producer_ownership"]["decision"]["producer_counts"] == {
        "backfill_analysis": 1,
        "processor_gate": 1,
    }
    assert summary["category_status"]["classification_runtime_producer"] == "runtime_ready"


def test_internal_data_readiness_reports_manual_review_only_policy_after_gate_ready(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    review_log = tmp_path / "artifact_review_feedback.jsonl"
    outcome_log = tmp_path / "artifact_generation_outcomes.jsonl"
    policy_path = tmp_path / "artifact_history_promotion_policy.json"
    db_path = tmp_path / "state.db"
    _init_intake_override_db(db_path)

    review_rows = [
        {
            "feedback_id": "feedback-meeting-1",
            "artifact_type": "meeting_pack",
            "artifact_id": "meeting-pack-001",
            "run_id": "run-meeting",
            "decision": "correct",
            "reason_code": "missing_context",
            "actor_id": "reviewer_001",
            "note": "Needs stronger context.",
        },
        {
            "feedback_id": "feedback-meeting-2",
            "artifact_type": "meeting_pack",
            "artifact_id": "meeting-pack-001",
            "run_id": "run-meeting",
            "decision": "accept",
            "reason_code": "ready_for_use",
            "actor_id": "reviewer_001",
            "note": "Accepted after revision.",
        },
        {
            "feedback_id": "feedback-protocol-1",
            "artifact_type": "protocol_card",
            "artifact_id": "protocol-card-001",
            "paper_id": "paper-001",
            "decision": "correct",
            "reason_code": "missing_detail",
            "actor_id": "reviewer_001",
            "note": "Needs one more procedural detail.",
        },
        {
            "feedback_id": "feedback-protocol-2",
            "artifact_type": "protocol_card",
            "artifact_id": "protocol-card-001",
            "paper_id": "paper-001",
            "decision": "accept",
            "reason_code": "ready_for_use",
            "actor_id": "reviewer_001",
            "note": "Accepted after revision.",
        },
    ]
    outcome_rows = [
        {
            "outcome_id": "outcome-meeting-1",
            "artifact_type": "meeting_pack",
            "artifact_id": "meeting-pack-001",
            "run_id": "run-meeting",
            "review_feedback_id": "feedback-meeting-1",
            "decision": "reused_after_correction",
            "downstream_use": "final_deliverable",
            "actor_id": "reviewer_001",
            "note": "Used after correction.",
        },
        {
            "outcome_id": "outcome-meeting-2",
            "artifact_type": "meeting_pack",
            "artifact_id": "meeting-pack-001",
            "run_id": "run-meeting",
            "review_feedback_id": "feedback-meeting-2",
            "decision": "reused",
            "downstream_use": "supporting_context",
            "actor_id": "reviewer_001",
            "note": "Reused as supporting context.",
        },
        {
            "outcome_id": "outcome-protocol-1",
            "artifact_type": "protocol_card",
            "artifact_id": "protocol-card-001",
            "paper_id": "paper-001",
            "review_feedback_id": "feedback-protocol-1",
            "decision": "reused_after_correction",
            "downstream_use": "follow_on_artifact",
            "actor_id": "reviewer_001",
            "note": "Used to seed a follow-on protocol draft.",
        },
        {
            "outcome_id": "outcome-protocol-2",
            "artifact_type": "protocol_card",
            "artifact_id": "protocol-card-001",
            "paper_id": "paper-001",
            "review_feedback_id": "feedback-protocol-2",
            "decision": "reused",
            "downstream_use": "supporting_context",
            "actor_id": "reviewer_001",
            "note": "Reused in the next packet.",
        },
    ]
    policy_payload = {
        "schema_version": "artifact_history_promotion_policy.v1",
        "status": "active",
        "policy_mode": "manual_review_only",
        "required_families": ["meeting_pack", "protocol_card"],
        "thresholds": {
            "required_families": ["meeting_pack", "protocol_card"],
            "min_review_feedback_events": 2,
            "min_generation_outcome_events": 2,
            "min_paired_artifacts": 1,
        },
        "requires_real_operator_history": True,
        "discussion_ready_when_gate_passes": True,
        "allows_default_owner_change": False,
        "allows_automatic_runtime_promotion": False,
        "required_manual_actions": [
            "review_recent_samples",
            "write_promotion_note",
            "open_explicit_rfc_before_default_owner_change",
        ],
        "notes": ["Manual-review-only posture for selected artifact families."],
    }

    review_log.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in review_rows) + "\n",
        encoding="utf-8",
    )
    outcome_log.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in outcome_rows) + "\n",
        encoding="utf-8",
    )
    policy_path.write_text(json.dumps(policy_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    monkeypatch.setenv("PAPERPIPE_ARTIFACT_REVIEW_FEEDBACK_LOG_PATH", str(review_log))
    monkeypatch.setenv("PAPERPIPE_ARTIFACT_GENERATION_OUTCOME_LOG_PATH", str(outcome_log))
    monkeypatch.setenv("PAPERPIPE_ARTIFACT_HISTORY_PROMOTION_POLICY_PATH", str(policy_path))
    monkeypatch.setenv("PAPERPIPE_DB_PATH", str(db_path))

    summary = build_internal_data_readiness_summary(run_id="internal_data_policy_ready")

    assert summary["surfaces"]["artifact_history_promotion_gate"]["decision"]["promotion_ready"] is True
    assert summary["surfaces"]["artifact_history_promotion_policy"]["status"] == "present"
    assert summary["surfaces"]["intake_override_coverage_gate"]["decision"]["passed"] is True
    assert summary["decision"]["runtime_promotion_discussion_ready"] is True
    assert summary["decision"]["runtime_promotion_ready"] is False
    assert summary["decision"]["blockers"] == ["automatic_default_promotion_not_allowed_by_policy"]
    assert "manual-review-only" in summary["decision"]["runtime_promotion_reason"]
    assert summary["minimum_next_events"] == [
        "review_recent_samples",
        "write_promotion_note",
        "open_explicit_rfc_before_default_owner_change",
    ]


def test_slot_classification_tuning_review_root_can_be_overridden(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    review_root = tmp_path / "slot_review_root"
    monkeypatch.setenv("PAPERPIPE_SLOT_CLASSIFICATION_TUNING_REVIEW_ROOT", str(review_root))

    assert internal_data_readiness._slot_classification_tuning_review_root() == review_root.resolve()
