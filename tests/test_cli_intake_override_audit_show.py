import json
from pathlib import Path

from typer.testing import CliRunner

import src.cli as cli


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def test_show_intake_override_audit_renders_selection_and_disagreement_tables(tmp_path: Path) -> None:
    runner = CliRunner()
    run_root = tmp_path / "audit_run"
    _write_json(
        run_root / "summary.json",
        {
            "schema_version": "intake_override_audit_summary.v1",
            "generated_at": "2026-04-20T00:00:00Z",
            "run_id": "audit_show_test",
            "inputs": {"source": "rows_jsonl", "row_count": 3},
            "metrics": {
                "audited_document_count": 2,
                "missing_intake_override_log_count": 1,
                "invalid_feedback_json_count": 0,
                "invalid_intake_override_log_count": 0,
                "slot_disagreement_count": 1,
                "slot_disagreement_rate": 1.0,
                "tag_disagreement_count": 0,
                "tag_disagreement_rate": 0.0,
                "selection_context_count": 1,
                "selection_context_rate": 0.5,
                "selection_fallback_count": 1,
                "selection_fallback_rate": 1.0,
            },
            "documents_with_slot_disagreement": ["paper-a"],
            "documents_with_missing_log": ["paper-c"],
            "documents_with_invalid_log": [],
            "documents_with_selection_context": ["paper-a"],
            "documents_with_selection_fallback": ["paper-a"],
        },
    )
    _write_json(
        run_root / "details.json",
        {
            "schema_version": "intake_override_audit_details.v1",
            "generated_at": "2026-04-20T00:00:00Z",
            "run_id": "audit_show_test",
            "documents": [
                {
                    "paper_id": "paper-a",
                    "title": "Selected via fallback",
                    "input_slot": "mechanism",
                    "stored_slot": "clinical",
                    "selection_selected_rank": 2,
                    "selection_candidate_count": 4,
                    "selection_score": 0.61,
                    "selection_skipped_processed_count": 1,
                },
                {
                    "paper_id": "paper-c",
                    "title": "Missing intake log",
                },
            ],
        },
    )

    result = runner.invoke(cli.app, ["show-intake-override-audit", str(run_root)])

    assert result.exit_code == 0
    assert "Intake Override Audit" in result.output
    assert "audit_show_test" in result.output
    assert "Selection Fallback" in result.output
    assert "paper-a" in result.output
    assert "r2/4, s=0.61, skip=1" in result.output
    assert "Slot Disagreements" in result.output
    assert "mechanism -> clinical" in result.output
    assert "Missing Logs" in result.output
    assert "paper-c" in result.output


def test_show_intake_override_audit_supports_json_output(tmp_path: Path) -> None:
    runner = CliRunner()
    summary_path = tmp_path / "audit_run" / "summary.json"
    _write_json(
        summary_path,
        {
            "schema_version": "intake_override_audit_summary.v1",
            "generated_at": "2026-04-20T00:00:00Z",
            "run_id": "audit_show_json_test",
            "inputs": {"source": "runtime_db", "row_count": 1},
            "metrics": {"audited_document_count": 1, "selection_context_count": 1},
            "documents_with_slot_disagreement": [],
            "documents_with_missing_log": [],
            "documents_with_invalid_log": [],
            "documents_with_selection_context": ["paper-z"],
            "documents_with_selection_fallback": [],
        },
    )

    result = runner.invoke(cli.app, ["show-intake-override-audit", str(summary_path), "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["run_id"] == "audit_show_json_test"
    assert payload["metrics"]["selection_context_count"] == 1
    assert payload["documents_with_selection_context"] == ["paper-z"]


def test_show_intake_override_audit_calibration_renders_recent_runs(tmp_path: Path) -> None:
    runner = CliRunner()
    audit_root = tmp_path / "audits"
    threshold_review_root = tmp_path / "intake_override_threshold_review"
    for run_id, generated_at, audited_count, triage_rate, slot_rate in (
        ("audit_latest", "2026-04-20T05:00:00Z", 3, 0.3333, 0.5),
        ("audit_ok", "2026-04-19T05:00:00Z", 4, 0.0, 0.0),
        ("audit_small", "2026-04-18T05:00:00Z", 2, 1.0, 1.0),
    ):
        _write_json(
            audit_root / run_id / "summary.json",
            {
                "schema_version": "intake_override_audit_summary.v1",
                "generated_at": generated_at,
                "run_id": run_id,
                "inputs": {"source": "rows_jsonl", "row_count": 4},
                "metrics": {
                    "audited_document_count": audited_count,
                    "triage_override_rate": triage_rate,
                    "slot_disagreement_rate": slot_rate,
                    "llm_slot_adjudication_rate": triage_rate,
                    "llm_tagging_adjudication_rate": slot_rate / 2,
                    "selection_fallback_rate": 0.0,
                    "analysis_unavailable_rate": 0.0,
                    "issues_state_unavailable_rate": 0.0,
                },
                "documents_with_slot_disagreement": [],
                "documents_with_missing_log": [],
                "documents_with_invalid_log": [],
                "documents_with_selection_context": [],
                "documents_with_selection_fallback": [],
            },
        )
    _write_json(
        threshold_review_root / "threshold_review_latest" / "summary.json",
        {
            "schema_version": "intake_override_threshold_review.v1",
            "generated_at": "2026-04-21T00:00:00Z",
            "run_id": "threshold_review_latest",
            "decision": {
                "recommended_action": "hold_current_threshold",
                "blocking_summary": "1.collect_more_audit_runs: 1/3 sufficiently-audited runs currently meet the review floor, so threshold changes should stay blocked until more audit evidence accumulates.",
            },
        },
    )

    result = runner.invoke(
        cli.app,
        ["show-intake-override-audit-calibration", "--root", str(audit_root)],
    )

    assert result.exit_code == 0
    assert "Intake Override Audit Calibration" in result.output
    assert "audit_latest" in result.output
    assert "Recent Audit Runs" in result.output
    assert "Signal Summary" in result.output
    assert "slot_adjudication" in result.output
    assert "tagging_adjudication" in result.output
    assert "Latest Threshold Review: threshold_review_latest" in result.output
    assert "Threshold Action: hold_current_threshold" in result.output
    assert "Threshold Blocker:" in result.output
    assert "Keep the current 25%" in result.output
    assert "Most persistent sufficiently-audited signals" in result.output


def test_show_intake_override_audit_calibration_supports_json_output(tmp_path: Path) -> None:
    runner = CliRunner()
    audit_root = tmp_path / "audits"
    threshold_review_root = tmp_path / "intake_override_threshold_review"
    _write_json(
        audit_root / "audit_latest" / "summary.json",
        {
            "schema_version": "intake_override_audit_summary.v1",
            "generated_at": "2026-04-20T05:00:00Z",
            "run_id": "audit_latest",
            "inputs": {"source": "rows_jsonl", "row_count": 4},
            "metrics": {
                "audited_document_count": 3,
                "triage_override_rate": 0.3333,
                "slot_disagreement_rate": 0.5,
                "selection_fallback_rate": 0.0,
                "analysis_unavailable_rate": 0.0,
                "issues_state_unavailable_rate": 0.0,
            },
            "documents_with_slot_disagreement": [],
            "documents_with_missing_log": [],
            "documents_with_invalid_log": [],
            "documents_with_selection_context": [],
            "documents_with_selection_fallback": [],
        },
    )
    _write_json(
        threshold_review_root / "threshold_review_latest" / "summary.json",
        {
            "schema_version": "intake_override_threshold_review.v1",
            "generated_at": "2026-04-21T00:00:00Z",
            "run_id": "threshold_review_latest",
            "decision": {
                "recommended_action": "hold_current_threshold",
                "blocking_summary": "1.collect_more_audit_runs: 1/3 sufficiently-audited runs currently meet the review floor, so threshold changes should stay blocked until more audit evidence accumulates.",
            },
        },
    )

    result = runner.invoke(
        cli.app,
        ["show-intake-override-audit-calibration", "--root", str(audit_root), "--json"],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["total_runs"] == 1
    assert payload["eligible_runs"] == 1
    assert payload["warn_runs"] == 1
    assert payload["runs"][0]["run_id"] == "audit_latest"
    assert payload["latest_threshold_review"]["run_id"] == "threshold_review_latest"
    assert payload["latest_threshold_review"]["recommended_action"] == "hold_current_threshold"
    assert "collect_more_audit_runs" in payload["latest_threshold_review"]["blocking_summary"]
