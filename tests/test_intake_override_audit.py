from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

from scripts.eval.audit_intake_override_logs import run_audit
from src.services.intake_override_audit import (
    build_intake_override_audit_calibration_snapshot,
    build_intake_override_audit,
    latest_intake_override_audit_summary,
    latest_intake_override_audit_run,
    latest_intake_override_threshold_review_run,
)


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n",
        encoding="utf-8",
    )


def _feedback_payload(intake_log: dict | None) -> str:
    payload = {"soft_tags": ["#demo"]}
    if intake_log is not None:
        payload["intake_override_log"] = intake_log
    return json.dumps(payload, ensure_ascii=False)


def _feedback_payload_with_selection(intake_log: dict, selection: dict) -> str:
    payload = {"soft_tags": ["#demo"], "intake_override_log": intake_log, "selection": selection}
    return json.dumps(payload, ensure_ascii=False)


def test_build_intake_override_audit_reports_missing_and_disagreement_metrics() -> None:
    rows = [
        {
            "paper_id": "paper-a",
            "title": "Paper A",
            "feedback_json": _feedback_payload_with_selection(
                {
                    "producer": "processor_daily_slots",
                    "analysis_available": True,
                    "llm_tagging_used": True,
                    "llm_slot_classification_used": True,
                    "llm_tagging_adjudication_used": True,
                    "llm_tagging_adjudication_reason": "schema_invalid",
                    "llm_slot_adjudication_used": True,
                    "llm_slot_adjudication_reason": "signal_conflict",
                    "input_slot": "mechanism",
                    "stored_slot": "clinical",
                    "slot_changed": True,
                    "input_tags": ["#flagged"],
                    "stored_tags": ["#flagged"],
                    "tags_changed": False,
                    "processing_status": "PENDING_REVIEW",
                    "issues_state": "flagged",
                    "confidence": 0.74,
                },
                {
                    "method": "daily_slot_rank_v1",
                    "selected_rank": 2,
                    "candidate_count": 4,
                    "selected_manual_rank_score": 0.61,
                    "skipped_processed_candidates": ["paper-a-existing"],
                },
            ),
        },
        {
            "paper_id": "paper-b",
            "title": "Paper B",
            "feedback_json": _feedback_payload(
                {
                    "producer": "watcher_local_pdf",
                    "analysis_available": False,
                    "llm_tagging_used": False,
                    "llm_slot_classification_used": False,
                    "input_slot": "manual",
                    "stored_slot": "manual",
                    "slot_changed": False,
                    "input_tags": [],
                    "stored_tags": [],
                    "tags_changed": False,
                    "processing_status": "FAILED",
                    "issues_state": "unavailable",
                    "confidence": 0.0,
                }
            ),
        },
        {
            "paper_id": "paper-c",
            "title": "Paper C",
            "feedback_json": _feedback_payload(None),
        },
        {
            "paper_id": "paper-d",
            "title": "Paper D",
            "feedback_json": "{bad json",
        },
        {
            "paper_id": "paper-e",
            "title": "Paper E",
            "feedback_json": None,
        },
    ]

    summary, details = build_intake_override_audit(
        rows=rows,
        run_id="intake_override_audit_test",
        source="rows_jsonl",
        rows_jsonl_path=Path("/tmp/test.jsonl"),
    )

    assert summary.metrics.document_count == 5
    assert summary.metrics.test_fixture_document_count == 0
    assert summary.metrics.non_fixture_document_count == 5
    assert summary.metrics.audited_document_count == 2
    assert summary.metrics.has_feedback_json_count == 4
    assert summary.metrics.no_feedback_json_count == 1
    assert summary.metrics.test_fixture_no_feedback_json_count == 0
    assert summary.metrics.non_fixture_no_feedback_json_count == 1
    assert summary.metrics.missing_intake_override_log_count == 1
    assert summary.metrics.invalid_feedback_json_count == 1
    assert summary.metrics.invalid_intake_override_log_count == 0
    assert summary.metrics.triage_override_count == 1
    assert summary.metrics.slot_disagreement_count == 1
    assert summary.metrics.tag_disagreement_count == 0
    assert summary.metrics.analysis_unavailable_count == 1
    assert summary.metrics.issues_state_unavailable_count == 1
    assert summary.metrics.selection_context_count == 1
    assert summary.metrics.selection_fallback_count == 1
    assert summary.metrics.llm_slot_classification_used_count == 1
    assert summary.metrics.llm_tagging_used_count == 1
    assert summary.metrics.llm_slot_adjudication_used_count == 1
    assert summary.metrics.llm_tagging_adjudication_used_count == 1
    assert summary.metrics.triage_override_rate == 0.5
    assert summary.metrics.slot_disagreement_rate == 1.0
    assert summary.metrics.tag_disagreement_rate == 0.0
    assert summary.metrics.analysis_unavailable_rate == 0.5
    assert summary.metrics.issues_state_unavailable_rate == 0.5
    assert summary.metrics.selection_context_rate == 0.5
    assert summary.metrics.selection_fallback_rate == 1.0
    assert summary.metrics.llm_slot_adjudication_rate == 1.0
    assert summary.metrics.llm_tagging_adjudication_rate == 1.0
    assert summary.metrics.producer_counts == {
        "processor_daily_slots": 1,
        "watcher_local_pdf": 1,
    }
    assert summary.documents_with_slot_disagreement == ["paper-a"]
    assert summary.documents_with_selection_context == ["paper-a"]
    assert summary.documents_with_selection_fallback == ["paper-a"]
    assert summary.documents_with_missing_log == ["paper-c", "paper-e"]
    assert summary.documents_with_missing_log_non_fixture == ["paper-c", "paper-e"]
    assert summary.documents_with_invalid_log == ["paper-d"]
    assert len(details.documents) == 5
    assert details.documents[0].paper_id == "paper-a"
    assert details.documents[0].has_selection_context is True
    assert details.documents[0].selection_method == "daily_slot_rank_v1"
    assert details.documents[0].selection_selected_rank == 2
    assert details.documents[0].selection_candidate_count == 4
    assert details.documents[0].selection_score == 0.61
    assert details.documents[0].selection_skipped_processed_count == 1
    assert details.documents[0].llm_slot_adjudication_used is True
    assert details.documents[0].llm_slot_adjudication_reason == "signal_conflict"
    assert details.documents[0].llm_tagging_adjudication_used is True
    assert details.documents[0].llm_tagging_adjudication_reason == "schema_invalid"


def test_latest_intake_override_audit_run_selects_most_recent_summary(tmp_path: Path) -> None:
    audit_root = tmp_path / "snapshots" / "intake_override_audits"
    older_run = audit_root / "intake_override_audit_old"
    newer_run = audit_root / "intake_override_audit_new"
    incomplete_run = audit_root / "intake_override_audit_incomplete"
    older_run.mkdir(parents=True, exist_ok=True)
    newer_run.mkdir(parents=True, exist_ok=True)
    incomplete_run.mkdir(parents=True, exist_ok=True)
    older_summary = older_run / "summary.json"
    newer_summary = newer_run / "summary.json"
    older_summary.write_text("{}", encoding="utf-8")
    newer_summary.write_text("{}", encoding="utf-8")
    os.utime(older_summary, (1_700_000_000, 1_700_000_000))
    os.utime(newer_summary, (1_800_000_000, 1_800_000_000))

    assert latest_intake_override_audit_run(audit_root) == newer_run


def test_latest_intake_override_audit_summary_loads_latest_summary(tmp_path: Path) -> None:
    audit_root = tmp_path / "snapshots" / "intake_override_audits"
    run_root = audit_root / "intake_override_audit_new"
    run_root.mkdir(parents=True, exist_ok=True)
    summary_payload = {
        "schema_version": "intake_override_audit_summary.v1",
        "generated_at": "2026-04-20T05:00:00+00:00",
        "run_id": "intake_override_audit_new",
        "inputs": {"source": "rows_jsonl", "row_count": 7},
        "metrics": {
            "document_count": 7,
            "audited_document_count": 3,
            "selection_fallback_count": 1,
            "slot_disagreement_count": 2,
        },
        "producer_metrics": [],
        "documents_with_slot_disagreement": [],
        "documents_with_tag_disagreement": [],
        "documents_with_missing_log": [],
        "documents_with_missing_log_non_fixture": [],
        "documents_with_invalid_log": [],
        "documents_with_selection_context": [],
        "documents_with_selection_fallback": [],
    }
    (run_root / "summary.json").write_text(json.dumps(summary_payload), encoding="utf-8")

    summary = latest_intake_override_audit_summary(audit_root)

    assert summary is not None
    assert summary.run_id == "intake_override_audit_new"
    assert summary.inputs.source == "rows_jsonl"
    assert summary.inputs.row_count == 7
    assert summary.metrics.audited_document_count == 3
    assert summary.metrics.selection_fallback_count == 1


def test_latest_threshold_review_run_prefers_operator_run_over_newer_synthetic(tmp_path: Path) -> None:
    review_root = tmp_path / "snapshots" / "intake_override_threshold_review"
    operator_run = review_root / "audit_with_review_smoke2__threshold_review"
    smoke_run = review_root / "intake_override_curated_replay_20260417_r1__threshold_review"
    test_run = review_root / "audit_script_threshold_review_test__threshold_review"
    operator_run.mkdir(parents=True, exist_ok=True)
    smoke_run.mkdir(parents=True, exist_ok=True)
    test_run.mkdir(parents=True, exist_ok=True)

    operator_summary = operator_run / "summary.json"
    smoke_summary = smoke_run / "summary.json"
    test_summary = test_run / "summary.json"
    operator_summary.write_text(
        json.dumps({"provenance": {"kind": "operator", "latest_eligible": True}}),
        encoding="utf-8",
    )
    smoke_summary.write_text(
        json.dumps({"provenance": {"kind": "operator", "latest_eligible": False}}),
        encoding="utf-8",
    )
    test_summary.write_text(
        json.dumps({"provenance": {"kind": "synthetic", "latest_eligible": False}}),
        encoding="utf-8",
    )
    os.utime(operator_summary, (1_900_000_000, 1_900_000_000))
    os.utime(smoke_summary, (1_800_000_000, 1_800_000_000))
    os.utime(test_summary, (2_000_000_000, 2_000_000_000))

    assert latest_intake_override_threshold_review_run(review_root) == operator_run
    assert latest_intake_override_threshold_review_run(review_root, include_synthetic=True) == test_run


def test_latest_threshold_review_run_returns_none_when_only_synthetic_runs_exist(tmp_path: Path) -> None:
    review_root = tmp_path / "snapshots" / "intake_override_threshold_review"
    smoke_run = review_root / "audit_with_review_smoke__threshold_review"
    test_run = review_root / "audit_script_threshold_review_test__threshold_review"
    smoke_run.mkdir(parents=True, exist_ok=True)
    test_run.mkdir(parents=True, exist_ok=True)

    smoke_summary = smoke_run / "summary.json"
    test_summary = test_run / "summary.json"
    smoke_summary.write_text(
        json.dumps({"provenance": {"kind": "synthetic", "latest_eligible": False}}),
        encoding="utf-8",
    )
    test_summary.write_text(
        json.dumps({"provenance": {"kind": "synthetic", "latest_eligible": False}}),
        encoding="utf-8",
    )
    os.utime(smoke_summary, (1_900_000_000, 1_900_000_000))
    os.utime(test_summary, (2_000_000_000, 2_000_000_000))

    assert latest_intake_override_threshold_review_run(review_root) is None
    assert latest_intake_override_threshold_review_run(review_root, include_synthetic=True) == test_run


def test_build_intake_override_audit_calibration_snapshot_summarizes_recent_runs(tmp_path: Path) -> None:
    audit_root = tmp_path / "snapshots" / "intake_override_audits"
    runs = [
        (
            "intake_override_audit_latest",
            "2026-04-20T05:00:00+00:00",
            "rows_jsonl",
            4,
            {
                "audited_document_count": 3,
                "triage_override_rate": 0.3333,
                "slot_disagreement_rate": 0.5,
                "selection_fallback_rate": 0.0,
                "analysis_unavailable_rate": 0.3333,
                "issues_state_unavailable_rate": 0.0,
            },
        ),
        (
            "intake_override_audit_ok",
            "2026-04-19T05:00:00+00:00",
            "runtime_db",
            12,
            {
                "audited_document_count": 4,
                "triage_override_rate": 0.0,
                "slot_disagreement_rate": 0.0,
                "selection_fallback_rate": 0.0,
                "analysis_unavailable_rate": 0.0,
                "issues_state_unavailable_rate": 0.0,
            },
        ),
        (
            "intake_override_audit_small",
            "2026-04-18T05:00:00+00:00",
            "runtime_db",
            20,
            {
                "audited_document_count": 2,
                "triage_override_rate": 1.0,
                "slot_disagreement_rate": 1.0,
                "selection_fallback_rate": 0.0,
                "analysis_unavailable_rate": 0.0,
                "issues_state_unavailable_rate": 0.0,
            },
        ),
    ]
    for run_id, generated_at, source, row_count, metrics in runs:
        run_root = audit_root / run_id
        run_root.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema_version": "intake_override_audit_summary.v1",
            "generated_at": generated_at,
            "run_id": run_id,
            "inputs": {"source": source, "row_count": row_count},
            "metrics": metrics,
            "producer_metrics": [],
            "documents_with_slot_disagreement": [],
            "documents_with_tag_disagreement": [],
            "documents_with_missing_log": [],
            "documents_with_missing_log_non_fixture": [],
            "documents_with_invalid_log": [],
            "documents_with_selection_context": [],
            "documents_with_selection_fallback": [],
        }
        (run_root / "summary.json").write_text(json.dumps(payload), encoding="utf-8")

    snapshot = build_intake_override_audit_calibration_snapshot(
        root=audit_root,
        warn_threshold=0.25,
        min_audited_docs=3,
        calibration_target_runs=3,
    )

    assert snapshot["total_runs"] == 3
    assert snapshot["eligible_runs"] == 2
    assert snapshot["warn_runs"] == 1
    assert snapshot["runs"][0]["run_id"] == "intake_override_audit_latest"
    assert snapshot["runs"][0]["status"] == "warn"
    assert snapshot["runs"][1]["status"] == "ok"
    assert snapshot["runs"][2]["status"] == "small_sample"
    slot_summary = next(item for item in snapshot["signal_summary"] if item["signal"] == "slot")
    slot_adjudication_summary = next(item for item in snapshot["signal_summary"] if item["signal"] == "slot_adjudication")
    assert slot_summary["latest_rate"] == 0.5
    assert slot_summary["max_rate"] == 0.5
    assert slot_summary["warn_run_count"] == 1
    assert slot_adjudication_summary["latest_rate"] == 0.0
    assert slot_adjudication_summary["warn_run_count"] == 0
    assert "Keep the current 25%" in snapshot["recommendations"][0]
    assert "Most persistent sufficiently-audited signals" in snapshot["recommendations"][1]
    assert "Latest run intake_override_audit_latest still crosses" in snapshot["recommendations"][2]


def test_build_intake_override_audit_calibration_snapshot_includes_adjudication_signals(tmp_path: Path) -> None:
    audit_root = tmp_path / "snapshots" / "intake_override_audits"
    run_root = audit_root / "intake_override_audit_adjudication"
    run_root.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": "intake_override_audit_summary.v1",
        "generated_at": "2026-04-20T05:00:00+00:00",
        "run_id": "intake_override_audit_adjudication",
        "inputs": {"source": "rows_jsonl", "row_count": 4},
        "metrics": {
            "audited_document_count": 4,
            "triage_override_rate": 0.0,
            "slot_disagreement_rate": 0.0,
            "selection_fallback_rate": 0.0,
            "analysis_unavailable_rate": 0.0,
            "issues_state_unavailable_rate": 0.0,
            "llm_slot_adjudication_rate": 0.5,
            "llm_tagging_adjudication_rate": 0.25,
        },
        "producer_metrics": [],
        "documents_with_slot_disagreement": [],
        "documents_with_tag_disagreement": [],
        "documents_with_missing_log": [],
        "documents_with_missing_log_non_fixture": [],
        "documents_with_invalid_log": [],
        "documents_with_selection_context": [],
        "documents_with_selection_fallback": [],
    }
    (run_root / "summary.json").write_text(json.dumps(payload), encoding="utf-8")

    snapshot = build_intake_override_audit_calibration_snapshot(
        root=audit_root,
        warn_threshold=0.25,
        min_audited_docs=3,
        calibration_target_runs=1,
    )

    slot_adjudication_summary = next(item for item in snapshot["signal_summary"] if item["signal"] == "slot_adjudication")
    tagging_adjudication_summary = next(item for item in snapshot["signal_summary"] if item["signal"] == "tagging_adjudication")
    assert slot_adjudication_summary["latest_rate"] == 0.5
    assert slot_adjudication_summary["warn_run_count"] == 1
    assert tagging_adjudication_summary["latest_rate"] == 0.25
    assert tagging_adjudication_summary["warn_run_count"] == 1
    assert "slot_adjudication" in snapshot["recommendations"][1]


def test_run_audit_supports_rows_jsonl_input(tmp_path: Path) -> None:
    rows_path = tmp_path / "rows.jsonl"
    out_dir = tmp_path / "out"
    _write_jsonl(
        rows_path,
        [
            {
                "paper_id": "paper-a",
                "title": "Paper A",
                "feedback_json": _feedback_payload(
                    {
                        "producer": "processor_daily_slots",
                        "analysis_available": True,
                        "llm_tagging_used": True,
                        "llm_slot_classification_used": True,
                        "llm_tagging_adjudication_used": True,
                        "llm_tagging_adjudication_reason": "schema_invalid",
                        "llm_slot_adjudication_used": True,
                        "llm_slot_adjudication_reason": "signal_conflict",
                        "input_slot": "mechanism",
                        "stored_slot": "clinical",
                        "slot_changed": True,
                        "input_tags": ["#flagged"],
                        "stored_tags": ["#flagged"],
                        "tags_changed": False,
                        "processing_status": "PENDING_REVIEW",
                        "issues_state": "flagged",
                        "confidence": 0.74,
                    }
                ),
            },
            {
                "paper_id": "paper-b",
                "title": "Paper B",
                "feedback_json": None,
            },
        ],
    )

    run_root = run_audit(
        db_path=None,
        rows_jsonl_path=rows_path,
        out_dir=out_dir,
        run_id="rows_jsonl_audit",
    )

    summary = json.loads((run_root / "summary.json").read_text(encoding="utf-8"))
    details = json.loads((run_root / "details.json").read_text(encoding="utf-8"))
    markdown = (run_root / "audit.md").read_text(encoding="utf-8")
    assert summary["inputs"]["source"] == "rows_jsonl"
    assert summary["metrics"]["document_count"] == 2
    assert summary["metrics"]["audited_document_count"] == 1
    assert summary["metrics"]["no_feedback_json_count"] == 1
    assert summary["metrics"]["test_fixture_document_count"] == 0
    assert summary["metrics"]["non_fixture_no_feedback_json_count"] == 1
    assert summary["documents_with_slot_disagreement"] == ["paper-a"]
    assert [item["paper_id"] for item in details["documents"]] == ["paper-a", "paper-b"]
    assert "# Intake Override Audit: rows_jsonl_audit" in markdown
    assert "## Operator Flow" in markdown
    assert str(run_root) in markdown
    assert str(run_root / "summary.json") in markdown
    assert "show-intake-override-audit" in markdown
    assert "## Warnings" in markdown
    assert "Slot adjudication is firing frequently" in markdown
    assert "Tagging adjudication is firing frequently" in markdown
    assert "## Slot Disagreements" in markdown
    assert "| Slot adjudication used | 1 | 100.0% |" in markdown


def test_run_audit_supports_db_input(tmp_path: Path) -> None:
    db_path = tmp_path / "state.db"
    out_dir = tmp_path / "out"
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            """
            CREATE TABLE papers (
                paper_id TEXT PRIMARY KEY,
                title TEXT,
                feedback_json TEXT
            )
            """
        )
        conn.execute(
            "INSERT INTO papers (paper_id, title, feedback_json) VALUES (?, ?, ?)",
            (
                "paper-db",
                "DB Paper",
                _feedback_payload(
                    {
                        "producer": "watcher_local_pdf",
                        "analysis_available": True,
                        "llm_tagging_used": True,
                        "llm_slot_classification_used": False,
                        "input_slot": "manual",
                        "stored_slot": "manual",
                        "slot_changed": False,
                        "input_tags": ["#clear"],
                        "stored_tags": ["#clear"],
                        "tags_changed": False,
                        "processing_status": "APPROVED",
                        "issues_state": "clear",
                        "confidence": 0.95,
                    }
                ),
            ),
        )
        conn.commit()
    finally:
        conn.close()

    run_root = run_audit(
        db_path=db_path,
        rows_jsonl_path=None,
        out_dir=out_dir,
        run_id="db_audit",
    )

    summary = json.loads((run_root / "summary.json").read_text(encoding="utf-8"))
    markdown = (run_root / "audit.md").read_text(encoding="utf-8")
    assert summary["inputs"]["source"] == "runtime_db"
    assert summary["inputs"]["db_path"] == str(db_path)
    assert summary["metrics"]["document_count"] == 1
    assert summary["metrics"]["audited_document_count"] == 1
    assert summary["metrics"]["producer_counts"] == {"watcher_local_pdf": 1}
    assert "## Operator Flow" in markdown
    assert str(run_root / "details.json") in markdown
    assert "## Metrics" in markdown
    assert "| Audited documents | 1 | - |" in markdown


def test_audit_script_reports_markdown_path_and_viewer_command(tmp_path: Path) -> None:
    rows_path = tmp_path / "rows.jsonl"
    out_dir = tmp_path / "out"
    _write_jsonl(
        rows_path,
        [
            {
                "paper_id": "paper-a",
                "title": "Paper A",
                "feedback_json": _feedback_payload(
                    {
                        "producer": "processor_daily_slots",
                        "analysis_available": True,
                        "llm_tagging_used": True,
                        "llm_slot_classification_used": False,
                        "input_slot": "mechanism",
                        "stored_slot": "mechanism",
                        "slot_changed": False,
                        "input_tags": ["#demo"],
                        "stored_tags": ["#demo"],
                        "tags_changed": False,
                        "processing_status": "APPROVED",
                        "issues_state": "clear",
                        "confidence": 0.9,
                    }
                ),
            }
        ],
    )

    script = Path(__file__).resolve().parents[1] / "scripts" / "eval" / "audit_intake_override_logs.py"
    completed = subprocess.run(
        [
            sys.executable,
            str(script),
            "--rows-jsonl",
            str(rows_path),
            "--out-dir",
            str(out_dir),
            "--run-id",
            "audit_script_cli_test",
        ],
        cwd=Path(__file__).resolve().parents[1],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout)
    markdown = Path(payload["markdown_path"]).read_text(encoding="utf-8")
    assert payload["markdown_path"].endswith("/audit_script_cli_test/audit.md")
    assert "show-intake-override-audit" in payload["viewer_command"]
    assert payload["viewer_command"].startswith("PYTHONPATH=") or "paperpipe" in payload["viewer_command"]
    assert payload["viewer_command"].endswith("audit_script_cli_test")
    assert payload["viewer_command"] in markdown


def test_audit_script_can_emit_threshold_review_summary(tmp_path: Path) -> None:
    rows_path = tmp_path / "rows.jsonl"
    out_dir = tmp_path / "out"
    _write_jsonl(
        rows_path,
        [
            {
                "paper_id": "paper-a",
                "title": "Paper A",
                "feedback_json": _feedback_payload(
                    {
                        "producer": "processor_daily_slots",
                        "analysis_available": True,
                        "llm_tagging_used": True,
                        "llm_slot_classification_used": True,
                        "input_slot": "mechanism",
                        "stored_slot": "clinical",
                        "slot_changed": True,
                        "input_tags": ["#demo"],
                        "stored_tags": ["#demo"],
                        "tags_changed": False,
                        "processing_status": "PENDING_REVIEW",
                        "issues_state": "flagged",
                        "confidence": 0.74,
                    }
                ),
            }
        ],
    )

    script = Path(__file__).resolve().parents[1] / "scripts" / "eval" / "audit_intake_override_logs.py"
    completed = subprocess.run(
        [
            sys.executable,
            str(script),
            "--rows-jsonl",
            str(rows_path),
            "--out-dir",
            str(out_dir),
            "--run-id",
            "audit_script_threshold_review_test",
            "--emit-threshold-review",
        ],
        cwd=Path(__file__).resolve().parents[1],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout)
    threshold_summary_path = Path(payload["threshold_review_summary_path"])
    threshold_payload = json.loads(threshold_summary_path.read_text(encoding="utf-8"))
    assert payload["threshold_review_run_root"].endswith("audit_script_threshold_review_test__threshold_review")
    assert threshold_payload["run_id"] == "audit_script_threshold_review_test__threshold_review"
    assert threshold_payload["provenance"]["kind"] == "operator"
    assert threshold_payload["provenance"]["latest_eligible"] is False
    assert threshold_payload["decision"]["recommended_action"] == "hold_current_threshold"
    assert threshold_payload["snapshot"]["total_runs"] == 1
    assert "show-intake-override-threshold-review" in payload["threshold_review_viewer_command"]
    assert payload["threshold_review_viewer_command"].endswith("audit_script_threshold_review_test__threshold_review")


def test_audit_script_can_emit_synthetic_threshold_review_summary(tmp_path: Path) -> None:
    rows_path = tmp_path / "rows.jsonl"
    out_dir = tmp_path / "out"
    _write_jsonl(
        rows_path,
        [
            {
                "paper_id": "paper-a",
                "title": "Paper A",
                "feedback_json": _feedback_payload(
                    {
                        "producer": "processor_daily_slots",
                        "analysis_available": True,
                        "llm_tagging_used": True,
                        "llm_slot_classification_used": True,
                        "input_slot": "mechanism",
                        "stored_slot": "clinical",
                        "slot_changed": True,
                        "input_tags": ["#demo"],
                        "stored_tags": ["#demo"],
                        "tags_changed": False,
                        "processing_status": "PENDING_REVIEW",
                        "issues_state": "flagged",
                        "confidence": 0.74,
                    }
                ),
            }
        ],
    )

    script = Path(__file__).resolve().parents[1] / "scripts" / "eval" / "audit_intake_override_logs.py"
    completed = subprocess.run(
        [
            sys.executable,
            str(script),
            "--rows-jsonl",
            str(rows_path),
            "--out-dir",
            str(out_dir),
            "--run-id",
            "audit_script_threshold_review_synth",
            "--emit-threshold-review",
            "--threshold-review-provenance-kind",
            "synthetic",
        ],
        cwd=Path(__file__).resolve().parents[1],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout)
    threshold_summary_path = Path(payload["threshold_review_summary_path"])
    threshold_payload = json.loads(threshold_summary_path.read_text(encoding="utf-8"))
    assert threshold_payload["provenance"]["kind"] == "synthetic"
    assert threshold_payload["provenance"]["latest_eligible"] is False


def test_audit_script_help_mentions_markdown_and_viewer_flow() -> None:
    script = Path(__file__).resolve().parents[1] / "scripts" / "eval" / "audit_intake_override_logs.py"
    completed = subprocess.run(
        [sys.executable, str(script), "--help"],
        cwd=Path(__file__).resolve().parents[1],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    normalized_stdout = " ".join(completed.stdout.split())
    assert "summary.json, details.json, and audit.md" in completed.stdout
    if os.name == "nt":
        assert r".venv\Scripts\paperpipe.exe show-intake-override-audit <run_dir>" in normalized_stdout
        assert r".venv\Scripts\paperpipe.exe show-intake-override-threshold-review <run_dir>" in normalized_stdout
    else:
        assert ".venv/bin/paperpipe show-intake-override-audit <run_dir>" in normalized_stdout
        assert ".venv/bin/paperpipe show-intake-override-threshold-review <run_dir>" in normalized_stdout
    assert "intake-override-audit <run_dir>" in normalized_stdout
    assert "--emit-threshold-review" in completed.stdout
    assert "--threshold-review-latest-eligible" in completed.stdout
    assert "latest_eligible=false" in normalized_stdout


def test_build_intake_override_audit_separates_fixture_only_no_feedback_bucket() -> None:
    rows = [
        {
            "paper_id": "paper-e2e-001",
            "title": "E2E Seed Paper",
            "pdf_path": "tests/temp_rag_test/Library/Test_ID.pdf",
            "feedback_json": None,
        },
        {
            "paper_id": "test_local_id",
            "title": "Test Local Paper Title",
            "pdf_path": "test_paper.pdf",
            "feedback_json": None,
        },
        {
            "paper_id": "paper-real-001",
            "title": "Real Indexed Paper",
            "feedback_json": _feedback_payload(
                {
                    "producer": "backfill_analysis",
                    "analysis_available": True,
                    "llm_tagging_used": False,
                    "llm_slot_classification_used": False,
                    "input_slot": "clinical",
                    "stored_slot": "clinical",
                    "slot_changed": False,
                    "input_tags": ["#Clinical"],
                    "stored_tags": ["#Clinical"],
                    "tags_changed": False,
                    "processing_status": "INDEXED",
                    "issues_state": "clear",
                    "confidence": 0.91,
                }
            ),
        },
    ]

    summary, details = build_intake_override_audit(
        rows=rows,
        run_id="intake_override_fixture_bucket_test",
        source="runtime_db",
        db_path=Path("/tmp/state.db"),
    )

    assert summary.metrics.document_count == 3
    assert summary.metrics.test_fixture_document_count == 2
    assert summary.metrics.non_fixture_document_count == 1
    assert summary.metrics.no_feedback_json_count == 2
    assert summary.metrics.test_fixture_no_feedback_json_count == 2
    assert summary.metrics.non_fixture_no_feedback_json_count == 0
    assert summary.documents_with_missing_log == ["paper-e2e-001", "test_local_id"]
    assert summary.documents_with_missing_log_non_fixture == []
    assert details.documents[0].is_test_fixture is True
    assert details.documents[0].fixture_reason == "fixture_visibility_rule"
    assert details.documents[1].is_test_fixture is True
    assert details.documents[1].fixture_reason == "paper_id_test_prefix"
