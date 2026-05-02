from fastapi.testclient import TestClient

from backend import main as api_main


def test_health_ready_reports_runtime_checks():
    client = TestClient(api_main.app)

    response = client.get("/health/ready")
    assert response.status_code == 200
    payload = response.json()

    assert payload["status"] in {"ok", "degraded", "error"}
    names = {entry["name"] for entry in payload["checks"]}
    assert {
        "config_file",
        "obsidian_vault",
        "zotero_base_dir",
        "watch_folder",
        "downloads_watch_dir",
        "pdf_storage_dir",
        "runtime_db",
        "storage_root",
        "logs_root",
        "cache_root",
        "ui_bundle",
        "latest_intake_override_audit",
        "latest_intake_override_audit_quality",
        "latest_intake_override_threshold_review",
        "latest_processor_gate_threshold_review",
    } <= names
    latest_check = next(entry for entry in payload["checks"] if entry["name"] == "latest_intake_override_audit")
    assert "available" in latest_check["metadata"]
    if latest_check["metadata"]["available"]:
        assert "llm_slot_adjudication_rate" in latest_check["metadata"]
        assert "llm_tagging_adjudication_rate" in latest_check["metadata"]
    latest_quality = next(entry for entry in payload["checks"] if entry["name"] == "latest_intake_override_audit_quality")
    assert "calibration" in latest_quality["metadata"]
    latest_threshold_review = next(
        entry for entry in payload["checks"] if entry["name"] == "latest_intake_override_threshold_review"
    )
    assert "available" in latest_threshold_review["metadata"]
    if latest_threshold_review["metadata"]["available"]:
        assert "run_id" in latest_threshold_review["metadata"]
        assert "provenance_kind" in latest_threshold_review["metadata"]
        assert "latest_eligible" in latest_threshold_review["metadata"]
        assert "recommended_action" in latest_threshold_review["metadata"]
    latest_processor_gate_threshold_review = next(
        entry for entry in payload["checks"] if entry["name"] == "latest_processor_gate_threshold_review"
    )
    assert "available" in latest_processor_gate_threshold_review["metadata"]
    if latest_processor_gate_threshold_review["metadata"]["available"]:
        assert "run_id" in latest_processor_gate_threshold_review["metadata"]
        assert "recommended_action" in latest_processor_gate_threshold_review["metadata"]
        assert "review_ready" in latest_processor_gate_threshold_review["metadata"]
        assert "next_step" in latest_processor_gate_threshold_review["metadata"]
        assert "threshold_change_ready" in latest_processor_gate_threshold_review["metadata"]
        assert "threshold_change_status" in latest_processor_gate_threshold_review["metadata"]
        assert "threshold_change_next_step" in latest_processor_gate_threshold_review["metadata"]
        assert "threshold_change_blocker" in latest_processor_gate_threshold_review["metadata"]
        assert "threshold_change_text" in latest_processor_gate_threshold_review["metadata"]
        assert "threshold_change_decision_text" in latest_processor_gate_threshold_review["metadata"]
        assert "tuning_targets" in latest_processor_gate_threshold_review["metadata"]
        assert "action_plan" in latest_processor_gate_threshold_review["metadata"]
        assert "manual_review_rows_available" in latest_processor_gate_threshold_review["metadata"]
        assert "manual_review_markdown_available" in latest_processor_gate_threshold_review["metadata"]
        assert "manual_review_checklist_available" in latest_processor_gate_threshold_review["metadata"]
        assert "manual_review_basis_markdown_available" in latest_processor_gate_threshold_review["metadata"]
        assert "threshold_change_proposal_available" in latest_processor_gate_threshold_review["metadata"]
        assert "threshold_change_proposal_markdown_available" in latest_processor_gate_threshold_review["metadata"]
        assert (
            "threshold_change_validation_replay_command_available"
            in latest_processor_gate_threshold_review["metadata"]
        )
        assert (
            "threshold_change_validation_replay_available"
            in latest_processor_gate_threshold_review["metadata"]
        )
        assert (
            "threshold_change_validation_replay_matches_proposal"
            in latest_processor_gate_threshold_review["metadata"]
        )
        assert (
            "threshold_change_validation_replay_needs_rerun"
            in latest_processor_gate_threshold_review["metadata"]
        )
        assert (
            "threshold_change_validation_replay_status"
            in latest_processor_gate_threshold_review["metadata"]
        )
        assert (
            "threshold_change_manual_decision_ready"
            in latest_processor_gate_threshold_review["metadata"]
        )
        assert (
            "threshold_change_manual_decision_status"
            in latest_processor_gate_threshold_review["metadata"]
        )
        assert (
            "threshold_change_manual_decision_blocker"
            in latest_processor_gate_threshold_review["metadata"]
        )
        assert (
            "threshold_change_decision_available"
            in latest_processor_gate_threshold_review["metadata"]
        )
        assert (
            "threshold_change_preflight_available"
            in latest_processor_gate_threshold_review["metadata"]
        )
        assert (
            "threshold_change_preflight_required"
            in latest_processor_gate_threshold_review["metadata"]
        )
        assert (
            "threshold_change_preflight_ready"
            in latest_processor_gate_threshold_review["metadata"]
        )
        assert (
            "threshold_change_preflight_status"
            in latest_processor_gate_threshold_review["metadata"]
        )
        assert (
            "threshold_change_preflight_blocker"
            in latest_processor_gate_threshold_review["metadata"]
        )
        assert (
            "threshold_change_preflight_validation_replay_status"
            in latest_processor_gate_threshold_review["metadata"]
        )
        assert (
            "threshold_change_preflight_validation_replay_matches_proposal"
            in latest_processor_gate_threshold_review["metadata"]
        )
        assert (
            "threshold_change_preflight_text"
            in latest_processor_gate_threshold_review["metadata"]
        )
        assert "drift_summary_available" in latest_processor_gate_threshold_review["metadata"]
        assert "drift_details_available" in latest_processor_gate_threshold_review["metadata"]
        assert "drift_markdown_available" in latest_processor_gate_threshold_review["metadata"]
        assert "threshold_replay_available" in latest_processor_gate_threshold_review["metadata"]
        assert (
            "threshold_replay_markdown_available"
            in latest_processor_gate_threshold_review["metadata"]
        )
        assert (
            "threshold_replay_review_command_available"
            in latest_processor_gate_threshold_review["metadata"]
        )
        assert "threshold_replay_text" in latest_processor_gate_threshold_review["metadata"]
        assert "threshold_replay_mode" in latest_processor_gate_threshold_review["metadata"]
        assert "threshold_replay_high_threshold" in latest_processor_gate_threshold_review["metadata"]
        assert "threshold_replay_low_threshold" in latest_processor_gate_threshold_review["metadata"]
        assert (
            "threshold_replay_reviewed_high_threshold"
            in latest_processor_gate_threshold_review["metadata"]
        )
        assert "threshold_replay_proposal_run_id" in latest_processor_gate_threshold_review["metadata"]
        assert "threshold_relevant_count" in latest_processor_gate_threshold_review["metadata"]
        assert "manual_review_scope_text" in latest_processor_gate_threshold_review["metadata"]
        assert "manual_review_scope_samples_text" in latest_processor_gate_threshold_review["metadata"]
        assert "threshold_relevant_sample_ids" in latest_processor_gate_threshold_review["metadata"]
        assert "manual_review_focus_recommendation" in latest_processor_gate_threshold_review["metadata"]
        assert "worksheet_text" in latest_processor_gate_threshold_review["metadata"]
        assert "worksheet_summary" in latest_processor_gate_threshold_review["metadata"]
        assert "manual_review_basis_text" in latest_processor_gate_threshold_review["metadata"]
        assert "manual_review_basis_summary" in latest_processor_gate_threshold_review["metadata"]
        assert "candidate_count" in latest_processor_gate_threshold_review["metadata"]
        assert "drift_rate" in latest_processor_gate_threshold_review["metadata"]


def test_health_ready_masks_paths_when_enabled(monkeypatch):
    monkeypatch.setenv("LATTICE_MASK_LOCAL_PATHS", "true")

    client = TestClient(api_main.app)

    response = client.get("/health/ready")
    assert response.status_code == 200
    payload = response.json()

    path_values = [entry.get("path") for entry in payload["checks"] if entry.get("path")]
    assert path_values
    assert all(not value.startswith("/Users/") for value in path_values)
