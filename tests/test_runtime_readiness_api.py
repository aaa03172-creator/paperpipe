import base64

from fastapi.testclient import TestClient

from backend import main as api_main
from src.schemas.ops import RuntimeReadinessCheck, RuntimeReadinessResponse


def _basic_auth_headers(password: str, username: str = "beta") -> dict[str, str]:
    token = base64.b64encode(f"{username}:{password}".encode("utf-8")).decode("ascii")
    return {"Authorization": f"Basic {token}"}


def test_health_ready_reports_runtime_checks():
    client = TestClient(api_main.app)

    resp = client.get("/health/ready")
    assert resp.status_code == 200
    payload = resp.json()

    assert payload["status"] in {"ok", "degraded", "error"}
    names = {entry["name"] for entry in payload["checks"]}
    assert {
        "config_file",
        "obsidian_vault",
        "zotero_base_dir",
        "watch_folder",
        "watch_folder_boundary",
        "downloads_watch_dir",
        "downloads_watch_dir_boundary",
        "pdf_storage_dir",
        "runtime_db",
        "queue_health",
        "storage_root",
        "logs_root",
        "cache_root",
        "ui_bundle",
        "cli_entrypoint",
        "privacy_preflight_config",
        "latest_intake_override_audit",
        "latest_intake_override_audit_quality",
        "latest_intake_override_threshold_review",
        "latest_processor_gate_threshold_review",
    } <= names
    privacy_preflight = next(entry for entry in payload["checks"] if entry["name"] == "privacy_preflight_config")
    assert privacy_preflight["status"] == "ok"
    assert privacy_preflight["metadata"]["rollback_flag"] == "LATTICE_PRIVACY_PREFLIGHT_MODE"
    assert privacy_preflight["metadata"]["effective_mode"] in {"off", "report_only", "block_on_review"}
    assert privacy_preflight["metadata"]["mode_valid"] is True
    latest_check = next(entry for entry in payload["checks"] if entry["name"] == "latest_intake_override_audit")
    assert "available" in latest_check["metadata"]
    if latest_check["metadata"]["available"]:
        assert "run_id" in latest_check["metadata"]
        assert "source" in latest_check["metadata"]
        assert "slot_disagreement_rate" in latest_check["metadata"]
        assert "llm_slot_adjudication_rate" in latest_check["metadata"]
        assert "llm_tagging_adjudication_rate" in latest_check["metadata"]
        assert "quality_signals" in latest_check["metadata"]
    latest_quality = next(entry for entry in payload["checks"] if entry["name"] == "latest_intake_override_audit_quality")
    assert "min_audited_docs" in latest_quality["metadata"]
    assert "sample_sufficient" in latest_quality["metadata"]
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
        assert "review_ready" in latest_threshold_review["metadata"]
        assert "next_step" in latest_threshold_review["metadata"]
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
        assert "candidate_count" in latest_processor_gate_threshold_review["metadata"]
        assert "drift_rate" in latest_processor_gate_threshold_review["metadata"]
    queue_health = next(entry for entry in payload["checks"] if entry["name"] == "queue_health")
    assert "available" in queue_health["metadata"]
    assert "queued_jobs_total" in queue_health["metadata"]
    assert "running_jobs_total" in queue_health["metadata"]
    assert "oldest_queued_age_seconds" in queue_health["metadata"]
    assert "stale_running_suspected_total" in queue_health["metadata"]
    assert "stale_running_reclaimed_total" in queue_health["metadata"]
    assert "last_stale_running_reclaimed_at" in queue_health["metadata"]
    assert "stale_running_requeued_total" in queue_health["metadata"]
    assert "last_stale_running_requeued_at" in queue_health["metadata"]
    assert "recent_stale_running_reclaims" in queue_health["metadata"]
    assert "stale_after_seconds" in queue_health["metadata"]
    assert "queued_age_warn_after_seconds" in queue_health["metadata"]


def test_health_ready_reports_latest_slot_tuning_review_metadata():
    client = TestClient(api_main.app)

    resp = client.get("/health/ready")
    assert resp.status_code == 200
    payload = resp.json()

    latest_slot_tuning_review = next(
        entry for entry in payload["checks"] if entry["name"] == "latest_slot_classification_tuning_review"
    )
    assert "available" in latest_slot_tuning_review["metadata"]
    if latest_slot_tuning_review["metadata"]["available"]:
        assert "run_id" in latest_slot_tuning_review["metadata"]
        assert "recommended_action" in latest_slot_tuning_review["metadata"]
        assert "review_ready" in latest_slot_tuning_review["metadata"]
        assert "next_step" in latest_slot_tuning_review["metadata"]
        assert "paired_compare_status" in latest_slot_tuning_review["metadata"]
        assert "default_rerun_status" in latest_slot_tuning_review["metadata"]
        assert "boundary_rerun_status" in latest_slot_tuning_review["metadata"]
        assert "prompt_change_ready" in latest_slot_tuning_review["metadata"]
        assert "prompt_change_status" in latest_slot_tuning_review["metadata"]
        assert "prompt_change_blocker" in latest_slot_tuning_review["metadata"]
        assert "paired_compare_failed_checks" in latest_slot_tuning_review["metadata"]
        assert "default_rerun_drift_rate" in latest_slot_tuning_review["metadata"]
        assert "boundary_rerun_drift_rate" in latest_slot_tuning_review["metadata"]


def test_health_ready_reports_invalid_privacy_preflight_mode_without_echoing_value(monkeypatch):
    monkeypatch.setenv("LATTICE_PRIVACY_PREFLIGHT_MODE", "secret-looking-surprise")

    client = TestClient(api_main.app)
    resp = client.get("/health/ready")

    assert resp.status_code == 200
    assert "secret-looking-surprise" not in resp.text
    payload = resp.json()
    assert payload["status"] == "error"
    privacy_preflight = next(entry for entry in payload["checks"] if entry["name"] == "privacy_preflight_config")
    assert privacy_preflight["status"] == "error"
    assert "secret-looking-surprise" not in privacy_preflight["detail"]
    assert "secret-looking-surprise" not in str(privacy_preflight["metadata"])
    assert privacy_preflight["metadata"]["configured"] is True
    assert privacy_preflight["metadata"]["mode_valid"] is False
    assert privacy_preflight["metadata"]["effective_mode"] is None


def test_api_health_ready_bridge_reports_runtime_checks():
    client = TestClient(api_main.app)

    resp = client.get("/api/health/ready")
    assert resp.status_code == 200
    payload = resp.json()

    assert payload["status"] in {"ok", "degraded", "error"}
    names = {entry["name"] for entry in payload["checks"]}
    assert {
        "config_file",
        "obsidian_vault",
        "zotero_base_dir",
        "watch_folder",
        "watch_folder_boundary",
        "downloads_watch_dir",
        "downloads_watch_dir_boundary",
        "pdf_storage_dir",
        "runtime_db",
        "queue_health",
        "storage_root",
        "logs_root",
        "cache_root",
        "ui_bundle",
        "cli_entrypoint",
        "privacy_preflight_config",
        "latest_intake_override_audit",
        "latest_intake_override_audit_quality",
        "latest_intake_override_threshold_review",
        "latest_processor_gate_threshold_review",
    } <= names
    privacy_preflight = next(entry for entry in payload["checks"] if entry["name"] == "privacy_preflight_config")
    assert privacy_preflight["metadata"]["rollback_flag"] == "LATTICE_PRIVACY_PREFLIGHT_MODE"
    assert privacy_preflight["metadata"]["mode_valid"] is True
    latest_check = next(entry for entry in payload["checks"] if entry["name"] == "latest_intake_override_audit")
    assert "available" in latest_check["metadata"]
    if latest_check["metadata"]["available"]:
        assert "run_id" in latest_check["metadata"]
        assert "source" in latest_check["metadata"]
        assert "slot_disagreement_rate" in latest_check["metadata"]
        assert "llm_slot_adjudication_rate" in latest_check["metadata"]
        assert "llm_tagging_adjudication_rate" in latest_check["metadata"]
        assert "quality_signals" in latest_check["metadata"]
    latest_quality = next(entry for entry in payload["checks"] if entry["name"] == "latest_intake_override_audit_quality")
    assert "min_audited_docs" in latest_quality["metadata"]
    assert "sample_sufficient" in latest_quality["metadata"]
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
        assert "review_ready" in latest_threshold_review["metadata"]
        assert "next_step" in latest_threshold_review["metadata"]
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
        assert "candidate_count" in latest_processor_gate_threshold_review["metadata"]
        assert "drift_rate" in latest_processor_gate_threshold_review["metadata"]
    queue_health = next(entry for entry in payload["checks"] if entry["name"] == "queue_health")
    assert "available" in queue_health["metadata"]
    assert "queued_jobs_total" in queue_health["metadata"]
    assert "running_jobs_total" in queue_health["metadata"]
    assert "oldest_queued_age_seconds" in queue_health["metadata"]
    assert "stale_running_suspected_total" in queue_health["metadata"]
    assert "stale_running_reclaimed_total" in queue_health["metadata"]
    assert "last_stale_running_reclaimed_at" in queue_health["metadata"]
    assert "stale_running_requeued_total" in queue_health["metadata"]
    assert "last_stale_running_requeued_at" in queue_health["metadata"]
    assert "recent_stale_running_reclaims" in queue_health["metadata"]
    assert "stale_after_seconds" in queue_health["metadata"]
    assert "queued_age_warn_after_seconds" in queue_health["metadata"]


def test_health_ready_masks_paths_by_default(monkeypatch):
    client = TestClient(api_main.app)

    resp = client.get("/health/ready")
    assert resp.status_code == 200
    payload = resp.json()

    path_values = [entry.get("path") for entry in payload["checks"] if entry.get("path")]
    assert path_values
    assert all(not value.startswith("/Users/") for value in path_values)


def test_health_ready_returns_browser_safe_summary_when_beta_gate_enabled(monkeypatch):
    monkeypatch.setenv("LATTICE_BETA_PASSWORD", "beta-pass")
    monkeypatch.delenv("LATTICE_BROWSER_DETAILED_RUNTIME_READINESS", raising=False)
    monkeypatch.delenv("PAPERPIPE_BROWSER_DETAILED_RUNTIME_READINESS", raising=False)

    client = TestClient(api_main.app)
    resp = client.get("/api/health/ready", headers=_basic_auth_headers("beta-pass"))

    assert resp.status_code == 200
    payload = resp.json()
    names = {entry["name"] for entry in payload["checks"]}
    assert {
        "config_file",
        "external_roots",
        "watch_folder",
        "downloads_watch_dir",
        "pdf_storage_dir",
        "runtime_storage",
        "queue_health",
        "ui_bundle",
        "backend_runtime",
        "privacy_preflight_config",
        "latest_intake_override_audit",
        "latest_intake_override_audit_quality",
        "latest_intake_override_threshold_review",
        "latest_processor_gate_threshold_review",
    } <= names
    privacy_preflight = next(entry for entry in payload["checks"] if entry["name"] == "privacy_preflight_config")
    assert privacy_preflight["path"] is None
    assert privacy_preflight["metadata"]["rollback_flag"] == "LATTICE_PRIVACY_PREFLIGHT_MODE"
    assert privacy_preflight["metadata"]["mode_valid"] is True
    assert "runtime_db" not in names
    assert "storage_root" not in names
    assert "logs_root" not in names
    assert "cache_root" not in names
    assert "backend_entrypoint" not in names
    assert all(entry.get("path") is None for entry in payload["checks"])
    latest_check = next(entry for entry in payload["checks"] if entry["name"] == "latest_intake_override_audit")
    assert "available" in latest_check["metadata"]
    if latest_check["metadata"]["available"]:
        assert "run_id" in latest_check["metadata"]
        assert "source" in latest_check["metadata"]
        assert "slot_disagreement_rate" in latest_check["metadata"]
        assert "llm_slot_adjudication_rate" in latest_check["metadata"]
        assert "llm_tagging_adjudication_rate" in latest_check["metadata"]
        assert "quality_signals" in latest_check["metadata"]
    latest_quality = next(entry for entry in payload["checks"] if entry["name"] == "latest_intake_override_audit_quality")
    assert "min_audited_docs" in latest_quality["metadata"]
    assert "sample_sufficient" in latest_quality["metadata"]
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
        assert "review_ready" in latest_threshold_review["metadata"]
        assert "next_step" in latest_threshold_review["metadata"]
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
        assert "candidate_count" in latest_processor_gate_threshold_review["metadata"]
        assert "drift_rate" in latest_processor_gate_threshold_review["metadata"]
    queue_health = next(entry for entry in payload["checks"] if entry["name"] == "queue_health")
    assert "available" in queue_health["metadata"]
    assert "queued_jobs_total" in queue_health["metadata"]
    assert "running_jobs_total" in queue_health["metadata"]
    assert "oldest_queued_age_seconds" in queue_health["metadata"]
    assert "stale_running_suspected_total" in queue_health["metadata"]
    assert "stale_running_reclaimed_total" in queue_health["metadata"]
    assert "last_stale_running_reclaimed_at" in queue_health["metadata"]
    assert "stale_running_requeued_total" in queue_health["metadata"]
    assert "last_stale_running_requeued_at" in queue_health["metadata"]
    assert "recent_stale_running_reclaims" not in queue_health["metadata"]
    assert "stale_after_seconds" in queue_health["metadata"]
    assert "queued_age_warn_after_seconds" in queue_health["metadata"]


def test_api_health_ready_browser_safe_summary_reports_invalid_privacy_preflight_mode_without_echoing_value(
    monkeypatch,
):
    monkeypatch.setenv("LATTICE_BETA_PASSWORD", "beta-pass")
    monkeypatch.setenv("LATTICE_PRIVACY_PREFLIGHT_MODE", "secret-looking-surprise")
    monkeypatch.delenv("LATTICE_BROWSER_DETAILED_RUNTIME_READINESS", raising=False)
    monkeypatch.delenv("PAPERPIPE_BROWSER_DETAILED_RUNTIME_READINESS", raising=False)

    client = TestClient(api_main.app)
    resp = client.get("/api/health/ready", headers=_basic_auth_headers("beta-pass"))

    assert resp.status_code == 200
    assert "secret-looking-surprise" not in resp.text
    payload = resp.json()
    assert payload["status"] == "error"
    privacy_preflight = next(entry for entry in payload["checks"] if entry["name"] == "privacy_preflight_config")
    assert privacy_preflight["path"] is None
    assert privacy_preflight["status"] == "error"
    assert "secret-looking-surprise" not in privacy_preflight["detail"]
    assert "secret-looking-surprise" not in str(privacy_preflight["metadata"])
    assert privacy_preflight["metadata"]["mode_valid"] is False
    assert privacy_preflight["metadata"]["effective_mode"] is None


def test_api_health_ready_browser_safe_summary_scrubs_processor_gate_commands(monkeypatch):
    monkeypatch.setenv("LATTICE_BETA_PASSWORD", "beta-pass")
    monkeypatch.delenv("LATTICE_BROWSER_DETAILED_RUNTIME_READINESS", raising=False)
    monkeypatch.delenv("PAPERPIPE_BROWSER_DETAILED_RUNTIME_READINESS", raising=False)

    def fake_collect_runtime_readiness() -> RuntimeReadinessResponse:
        return RuntimeReadinessResponse(
            status="ok",
            checks=[
                RuntimeReadinessCheck(
                    name="latest_processor_gate_threshold_review",
                    status="ok",
                    detail="latest processor gate threshold review is available",
                    path="/Users/example/repo/snapshots/summary.json",
                    metadata={
                        "available": True,
                        "threshold_replay_review_command": "secret-review-command",
                        "threshold_review_command": "secret-threshold-command",
                        "threshold_change_validation_replay_command_template": (
                            "secret-validation-command"
                        ),
                        "validation_replay_command_template": "secret-validation-alias",
                        "threshold_change_decision_path": "secret-decision-path",
                        "threshold_change_decision_markdown_path": (
                            "secret-decision-markdown-path"
                        ),
                        "threshold_change_preflight_path": "secret-preflight-path",
                        "threshold_change_preflight_markdown_path": (
                            "secret-preflight-markdown-path"
                        ),
                        "threshold_change_decision": {
                            "final_status": "threshold_change_validation_replay_required",
                            "recommended_action": (
                                "run_threshold_change_validation_replay_before_decision"
                            ),
                            "manual_review_counts": {
                                "total": 1,
                                "completed": 1,
                                "supports_high_threshold_change": 1,
                            },
                            "high_threshold_candidate_ids": ["secret-paper-id"],
                            "operator_note": "secret-decision-note",
                            "threshold_change_preflight": {
                                "required": True,
                                "ready": False,
                                "status": "missing_threshold_change_proposal",
                                "blocker": "missing_threshold_change_proposal",
                                "validation_replay_status": "not_applicable",
                                "validation_replay_matches_proposal": False,
                                "secret_raw_field": "secret-preflight-field",
                            },
                        },
                        "threshold_change_preflight": {
                            "required": True,
                            "ready": False,
                            "status": "missing_threshold_change_proposal",
                            "blocker": "missing_threshold_change_proposal",
                            "validation_replay_status": "not_applicable",
                            "validation_replay_matches_proposal": False,
                            "secret_raw_field": "secret-preflight-alias-field",
                        },
                    },
                )
            ],
        )

    monkeypatch.setattr(
        api_main,
        "collect_runtime_readiness",
        fake_collect_runtime_readiness,
    )

    client = TestClient(api_main.app)
    resp = client.get("/api/health/ready", headers=_basic_auth_headers("beta-pass"))

    assert resp.status_code == 200
    assert "secret-review-command" not in resp.text
    assert "secret-threshold-command" not in resp.text
    assert "secret-validation-command" not in resp.text
    assert "secret-validation-alias" not in resp.text
    assert "secret-decision-path" not in resp.text
    assert "secret-decision-markdown-path" not in resp.text
    assert "secret-preflight-path" not in resp.text
    assert "secret-preflight-markdown-path" not in resp.text
    assert "secret-paper-id" not in resp.text
    assert "secret-decision-note" not in resp.text
    assert "secret-preflight-field" not in resp.text
    assert "secret-preflight-alias-field" not in resp.text
    payload = resp.json()
    check = next(
        entry
        for entry in payload["checks"]
        if entry["name"] == "latest_processor_gate_threshold_review"
    )
    assert check["path"] is None
    assert check["metadata"]["threshold_replay_review_command_available"] is True
    assert (
        check["metadata"]["threshold_change_validation_replay_command_available"]
        is True
    )
    assert check["metadata"]["threshold_change_decision_available"] is True
    assert check["metadata"]["threshold_change_preflight_available"] is True
    assert check["metadata"]["threshold_change_decision_text"] == (
        "status=threshold_change_validation_replay_required, "
        "action=run_threshold_change_validation_replay_before_decision, "
        "reviewed=1/1, high=1, preflight=missing_threshold_change_proposal, "
        "blocker=missing_threshold_change_proposal"
    )
    assert check["metadata"]["threshold_change_preflight_text"] == (
        "required=yes, ready=no, status=missing_threshold_change_proposal, "
        "blocker=missing_threshold_change_proposal"
    )
    assert "threshold_replay_review_command" not in check["metadata"]
    assert "threshold_review_command" not in check["metadata"]
    assert "threshold_change_validation_replay_command_template" not in check["metadata"]
    assert "validation_replay_command_template" not in check["metadata"]
    assert "threshold_change_decision_path" not in check["metadata"]
    assert "threshold_change_decision_markdown_path" not in check["metadata"]
    assert "threshold_change_preflight_path" not in check["metadata"]
    assert "threshold_change_preflight_markdown_path" not in check["metadata"]
    assert "threshold_change_decision" not in check["metadata"]
    assert "threshold_change_preflight" not in check["metadata"]


def test_health_ready_can_opt_back_into_detailed_mode_under_beta_gate(monkeypatch):
    monkeypatch.setenv("LATTICE_BETA_PASSWORD", "beta-pass")
    monkeypatch.setenv("LATTICE_BROWSER_DETAILED_RUNTIME_READINESS", "true")

    client = TestClient(api_main.app)
    resp = client.get("/health/ready", headers=_basic_auth_headers("beta-pass"))

    assert resp.status_code == 200
    payload = resp.json()
    names = {entry["name"] for entry in payload["checks"]}
    assert "runtime_db" in names
    assert "queue_health" in names
    assert "storage_root" in names
    assert "logs_root" in names
    assert "cache_root" in names
    assert "backend_entrypoint" in names
    assert "cli_entrypoint" in names
    assert "privacy_preflight_config" in names
    assert "latest_intake_override_audit" in names
    assert "latest_intake_override_audit_quality" in names
    assert "latest_intake_override_threshold_review" in names
    assert "latest_processor_gate_threshold_review" in names
    latest_check = next(entry for entry in payload["checks"] if entry["name"] == "latest_intake_override_audit")
    assert "available" in latest_check["metadata"]
    assert "run_id" in latest_check["metadata"]
    assert "source" in latest_check["metadata"]
    assert "slot_disagreement_rate" in latest_check["metadata"]
    assert "quality_signals" in latest_check["metadata"]
    latest_quality = next(entry for entry in payload["checks"] if entry["name"] == "latest_intake_override_audit_quality")
    assert "min_audited_docs" in latest_quality["metadata"]
    assert "sample_sufficient" in latest_quality["metadata"]
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
        assert "review_ready" in latest_threshold_review["metadata"]
        assert "next_step" in latest_threshold_review["metadata"]
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
        assert "candidate_count" in latest_processor_gate_threshold_review["metadata"]
        assert "drift_rate" in latest_processor_gate_threshold_review["metadata"]
    queue_health = next(entry for entry in payload["checks"] if entry["name"] == "queue_health")
    assert "available" in queue_health["metadata"]
    assert "queued_jobs_total" in queue_health["metadata"]
    assert "running_jobs_total" in queue_health["metadata"]
    assert "oldest_queued_age_seconds" in queue_health["metadata"]
    assert "stale_running_suspected_total" in queue_health["metadata"]
    assert "stale_running_reclaimed_total" in queue_health["metadata"]
    assert "last_stale_running_reclaimed_at" in queue_health["metadata"]
    assert "stale_running_requeued_total" in queue_health["metadata"]
    assert "last_stale_running_requeued_at" in queue_health["metadata"]
    assert "recent_stale_running_reclaims" in queue_health["metadata"]
    assert "stale_after_seconds" in queue_health["metadata"]
    assert "queued_age_warn_after_seconds" in queue_health["metadata"]
