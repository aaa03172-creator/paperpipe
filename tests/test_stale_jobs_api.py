from datetime import datetime, timezone
import json
from pathlib import Path

from fastapi.testclient import TestClient

import src.db_utils as db_utils
import src.services.stale_jobs as stale_jobs_service
from backend import main as api_main


def test_stale_jobs_endpoint_surfaces_stale_running_candidates(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()
        fixed_now = datetime(2026, 4, 22, 3, 0, 0, tzinfo=timezone.utc)
        monkeypatch.setattr(stale_jobs_service, "utc_now", lambda: fixed_now)

        stale_log = tmp_path / "logs" / "jobs" / "job-stale.jsonl"
        stale_log.parent.mkdir(parents=True, exist_ok=True)
        stale_log.write_text('{"level":"INFO","message":"still running"}\n', encoding="utf-8")

        stale_artifact_dir = tmp_path / "storage" / "artifacts" / "paper-stale" / "run-stale"
        stale_artifact_dir.mkdir(parents=True, exist_ok=True)

        conn = db_utils.get_db_connection()
        conn.execute(
            """
            INSERT INTO jobs (
                job_id, run_id, paper_id, status, progress, stage, created_at, started_at, artifact_dir, log_path
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "job_stale_running_001",
                "run_stale_running_001",
                "paper_stale_running_001",
                "running",
                42,
                "read",
                "2026-04-22 01:00:00",
                "2026-04-22 01:15:00",
                str(stale_artifact_dir),
                str(stale_log),
            ),
        )
        conn.execute(
            """
            INSERT INTO jobs (
                job_id, run_id, paper_id, status, progress, stage, created_at, started_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "job_fresh_running_001",
                "run_fresh_running_001",
                "paper_fresh_running_001",
                "running",
                5,
                "read",
                "2026-04-22 02:40:00",
                "2026-04-22 02:50:00",
            ),
        )
        conn.commit()
        conn.close()

        client = TestClient(api_main.app)
        response = client.get("/ops/stale-jobs", params={"stale_after_seconds": 1800, "limit": 10})

        assert response.status_code == 200
        payload = response.json()
        assert payload["running_jobs_total"] == 2
        assert payload["stale_candidates_total"] == 1
        assert len(payload["stale_jobs"]) == 1

        stale = payload["stale_jobs"][0]
        assert stale["job_id"] == "job_stale_running_001"
        assert stale["paper_id"] == "paper_stale_running_001"
        assert stale["run_id"] == "run_stale_running_001"
        assert stale["running_for_seconds"] == 6300
        assert stale["log_exists"] is True
        assert stale["artifact_dir_exists"] is True
        assert stale["recommended_action"] == "inspect_artifacts_and_log_before_manual_recovery"
    finally:
        db_utils.DB_PATH = original_db_path


def test_stale_jobs_endpoint_handles_missing_jobs_table(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        client = TestClient(api_main.app)
        response = client.get("/ops/stale-jobs")

        assert response.status_code == 200
        payload = response.json()
        assert payload["running_jobs_total"] == 0
        assert payload["stale_candidates_total"] == 0
        assert payload["stale_jobs"] == []
    finally:
        db_utils.DB_PATH = original_db_path


def test_stale_jobs_endpoint_preserves_reclaim_summary_when_jobs_table_is_missing(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        fixed_now = datetime(2026, 4, 22, 3, 0, 0, tzinfo=timezone.utc)
        monkeypatch.setattr(stale_jobs_service, "utc_now", lambda: fixed_now)

        conn = db_utils.get_db_connection()
        conn.execute(
            """
            CREATE TABLE job_events (
                event_id TEXT PRIMARY KEY,
                job_id TEXT NOT NULL,
                run_id TEXT,
                ts TEXT NOT NULL,
                level TEXT NOT NULL,
                event_type TEXT NOT NULL,
                message TEXT,
                payload_json TEXT
            )
            """
        )
        conn.execute(
            """
            INSERT INTO job_events (
                event_id, job_id, run_id, ts, level, event_type, message, payload_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "event_reclaim_missing_jobs_001",
                "job_reclaim_missing_jobs_001",
                "run_reclaim_missing_jobs_001",
                "2026-04-22T02:55:00+00:00",
                "ERROR",
                "job_reclaimed_stale_running",
                "reclaimed without jobs table",
                '{"paper_id":"paper_reclaim_missing_jobs_001","error_code":"STALE_RUNNING_RECLAIMED"}',
            ),
        )
        conn.commit()
        conn.close()

        client = TestClient(api_main.app)
        response = client.get("/ops/stale-jobs")

        assert response.status_code == 200
        payload = response.json()
        assert payload["running_jobs_total"] == 0
        assert payload["stale_candidates_total"] == 0
        assert payload["stale_jobs"] == []
        assert payload["stale_running_reclaimed_total"] == 1
        assert payload["last_stale_running_reclaimed_at"] == "2026-04-22T02:55:00+00:00"
        assert payload["recent_stale_running_reclaims"] == [
            {
                "job_id": "job_reclaim_missing_jobs_001",
                "run_id": "run_reclaim_missing_jobs_001",
                "paper_id": "paper_reclaim_missing_jobs_001",
                "reclaimed_at": "2026-04-22T02:55:00+00:00",
                "error_code": "STALE_RUNNING_RECLAIMED",
                "replacement_job_id": None,
                "replacement_run_id": None,
                "requeued_at": None,
            }
        ]
    finally:
        db_utils.DB_PATH = original_db_path


def test_stale_jobs_endpoint_prefers_recent_heartbeat_over_old_started_at(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()
        fixed_now = datetime(2026, 4, 22, 3, 0, 0, tzinfo=timezone.utc)
        monkeypatch.setattr(stale_jobs_service, "utc_now", lambda: fixed_now)

        conn = db_utils.get_db_connection()
        conn.execute(
            """
            INSERT INTO jobs (
                job_id, run_id, paper_id, status, progress, stage, created_at, started_at, heartbeat_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "job_running_recent_heartbeat_001",
                "run_running_recent_heartbeat_001",
                "paper_running_recent_heartbeat_001",
                "running",
                42,
                "read",
                "2026-04-22 01:00:00",
                "2026-04-22 01:15:00",
                "2026-04-22T02:55:00+00:00",
            ),
        )
        conn.commit()
        conn.close()

        client = TestClient(api_main.app)
        response = client.get("/ops/stale-jobs", params={"stale_after_seconds": 1800, "limit": 10})

        assert response.status_code == 200
        payload = response.json()
        assert payload["running_jobs_total"] == 1
        assert payload["stale_candidates_total"] == 0
        assert payload["stale_jobs"] == []
    finally:
        db_utils.DB_PATH = original_db_path


def test_stale_incident_snapshot_captures_bounded_support_artifact(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()
        fixed_now = datetime(2026, 4, 22, 3, 20, 0, tzinfo=timezone.utc)
        monkeypatch.setattr(stale_jobs_service, "utc_now", lambda: fixed_now)

        incident_log = tmp_path / "logs" / "jobs" / "job-incident.jsonl"
        incident_log.parent.mkdir(parents=True, exist_ok=True)
        incident_log.write_text('{"level":"INFO","message":"started"}\n', encoding="utf-8")

        incident_artifact_dir = tmp_path / "storage" / "artifacts" / "paper-incident" / "run-incident"
        incident_artifact_dir.mkdir(parents=True, exist_ok=True)

        conn = db_utils.get_db_connection()
        conn.execute(
            """
            INSERT INTO execution_runs (
                run_id, paper_id, trigger_source, pipeline_profile, status, created_at, started_at,
                params_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "run_incident_snapshot_001",
                "paper_incident_snapshot_001",
                "api",
                "deepread",
                "running",
                "2026-04-22T01:00:00+00:00",
                "2026-04-22T01:15:00+00:00",
                json.dumps({"parser_backend": "docling", "api_key": "sk-secret-local-test"}),
            ),
        )
        conn.execute(
            """
            INSERT INTO jobs (
                job_id, run_id, paper_id, status, progress, stage, created_at, started_at,
                heartbeat_at, artifact_dir, log_path
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "job_incident_snapshot_001",
                "run_incident_snapshot_001",
                "paper_incident_snapshot_001",
                "running",
                48,
                "read",
                "2026-04-22 01:00:00",
                "2026-04-22 01:15:00",
                "2026-04-22T01:20:00+00:00",
                str(incident_artifact_dir),
                str(incident_log),
            ),
        )
        conn.execute(
            """
            INSERT INTO job_events (
                event_id, job_id, run_id, ts, level, event_type, message, payload_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "event_incident_snapshot_001",
                "job_incident_snapshot_001",
                "run_incident_snapshot_001",
                "2026-04-22T01:20:00+00:00",
                "INFO",
                "job_heartbeat",
                "heartbeat before stall",
                '{"paper_id":"paper_incident_snapshot_001","stage":"read","token":"secret-token"}',
            ),
        )
        conn.commit()
        conn.close()

        client = TestClient(api_main.app)
        response = client.post(
            "/ops/jobs/job_incident_snapshot_001/stale-incident-snapshot",
            params={"stale_after_seconds": 1800},
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["job_id"] == "job_incident_snapshot_001"
        assert payload["run_id"] == "run_incident_snapshot_001"
        assert payload["paper_id"] == "paper_incident_snapshot_001"
        assert payload["status"] == "running"
        assert payload["is_stale_candidate"] is True
        assert payload["running_for_seconds"] == 7200
        assert payload["captured_at"] == "2026-04-22T03:20:00+00:00"

        incident_path = Path(payload["incident_path"])
        assert incident_path.exists()
        snapshot = json.loads(incident_path.read_text(encoding="utf-8"))
        assert snapshot["artifact_kind"] == "review_support"
        assert snapshot["layer"] == "review_gate_artifact"
        assert snapshot["incident_type"] == "stale_running_suspicion"
        assert snapshot["job"]["heartbeat_at"] == "2026-04-22T01:20:00+00:00"
        assert snapshot["execution_run"]["run_id"] == "run_incident_snapshot_001"
        assert snapshot["execution_run"]["params_json"]["api_key"] == "<redacted>"
        assert snapshot["path_observations"]["log_path"]["exists"] is True
        assert snapshot["path_observations"]["artifact_dir"]["exists"] is True
        assert snapshot["recent_job_events"][0]["event_type"] == "job_heartbeat"
        assert snapshot["recent_job_events"][0]["payload"]["token"] == "<redacted>"
        assert "contents" not in json.dumps(snapshot["path_observations"])
        assert "sk-secret-local-test" not in json.dumps(snapshot)

        conn = db_utils.get_db_connection()
        event_row = conn.execute(
            """
            SELECT event_type, payload_json
            FROM job_events
            WHERE job_id = ?
            ORDER BY ts DESC
            LIMIT 1
            """,
            ("job_incident_snapshot_001",),
        ).fetchone()
        conn.close()

        assert event_row["event_type"] == "job_stale_incident_snapshot_captured"
        event_payload = json.loads(event_row["payload_json"])
        assert event_payload["incident_id"] == payload["incident_id"]
        assert event_payload["is_stale_candidate"] is True

        incidents = client.get("/ops/stale-incidents", params={"limit": 10})
        assert incidents.status_code == 200
        incidents_payload = incidents.json()
        assert incidents_payload["incidents_total"] == 1
        assert incidents_payload["returned_total"] == 1
        incident = incidents_payload["incidents"][0]
        assert incident["incident_id"] == payload["incident_id"]
        assert incident["job_id"] == "job_incident_snapshot_001"
        assert incident["run_id"] == "run_incident_snapshot_001"
        assert incident["paper_id"] == "paper_incident_snapshot_001"
        assert incident["is_stale_candidate"] is True
        assert incident["running_for_seconds"] == 7200
        assert incident["recent_job_events_count"] == 1
        assert incident["path_observations_available"] is True
        assert incident["parse_error"] is False
        assert "sk-secret-local-test" not in json.dumps(incidents_payload)
    finally:
        db_utils.DB_PATH = original_db_path


def test_stale_incidents_endpoint_returns_empty_list_without_snapshot_root(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()
        client = TestClient(api_main.app)
        response = client.get("/ops/stale-incidents")

        assert response.status_code == 200
        payload = response.json()
        assert payload["incidents_total"] == 0
        assert payload["returned_total"] == 0
        assert payload["incidents"] == []
    finally:
        db_utils.DB_PATH = original_db_path


def test_stale_incident_snapshot_rejects_missing_job(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()
        client = TestClient(api_main.app)
        response = client.post("/ops/jobs/job_missing_snapshot_001/stale-incident-snapshot")

        assert response.status_code == 404
        assert response.json()["detail"] == "Job not found"
    finally:
        db_utils.DB_PATH = original_db_path


def test_reclaim_stale_job_marks_running_job_failed_and_logs_event(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()
        fixed_now = datetime(2026, 4, 22, 3, 0, 0, tzinfo=timezone.utc)
        monkeypatch.setattr(stale_jobs_service, "utc_now", lambda: fixed_now)

        conn = db_utils.get_db_connection()
        conn.execute(
            """
            INSERT INTO execution_runs (
                run_id, paper_id, trigger_source, pipeline_profile, status, created_at, started_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "run_reclaim_stale_001",
                "paper_reclaim_stale_001",
                "api",
                "deepread",
                "running",
                "2026-04-22T01:00:00+00:00",
                "2026-04-22T01:15:00+00:00",
            ),
        )
        conn.execute(
            """
            INSERT INTO jobs (
                job_id, run_id, paper_id, status, progress, stage, created_at, started_at, heartbeat_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "job_reclaim_stale_001",
                "run_reclaim_stale_001",
                "paper_reclaim_stale_001",
                "running",
                42,
                "read",
                "2026-04-22 01:00:00",
                "2026-04-22 01:15:00",
                "2026-04-22T01:20:00+00:00",
            ),
        )
        conn.commit()
        conn.close()

        client = TestClient(api_main.app)
        response = client.post(
            "/ops/jobs/job_reclaim_stale_001/reclaim-stale",
            params={"stale_after_seconds": 1800},
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["job_id"] == "job_reclaim_stale_001"
        assert payload["status"] == "failed"
        assert payload["previous_status"] == "running"
        assert payload["error_code"] == "STALE_RUNNING_RECLAIMED"
        assert payload["running_for_seconds"] == 6000

        job_status = client.get("/jobs/job_reclaim_stale_001")
        assert job_status.status_code == 200
        assert job_status.json()["status"] == "failed"
        assert job_status.json()["error_code"] == "STALE_RUNNING_RECLAIMED"

        conn = db_utils.get_db_connection()
        job_row = conn.execute(
            "SELECT status, error_code, error_message, finished_at FROM jobs WHERE job_id = ?",
            ("job_reclaim_stale_001",),
        ).fetchone()
        run_row = conn.execute(
            "SELECT status, finished_at FROM execution_runs WHERE run_id = ?",
            ("run_reclaim_stale_001",),
        ).fetchone()
        event_row = conn.execute(
            """
            SELECT level, event_type, message
            FROM job_events
            WHERE job_id = ?
            ORDER BY ts DESC
            LIMIT 1
            """,
            ("job_reclaim_stale_001",),
        ).fetchone()
        conn.close()

        assert job_row["status"] == "failed"
        assert job_row["error_code"] == "STALE_RUNNING_RECLAIMED"
        assert "fresh heartbeat" in str(job_row["error_message"])
        assert str(job_row["finished_at"]).strip() != ""
        assert run_row["status"] == "failed"
        assert str(run_row["finished_at"]).strip() != ""
        assert event_row["level"] == "ERROR"
        assert event_row["event_type"] == "job_reclaimed_stale_running"
        assert "fresh heartbeat" in str(event_row["message"])

        stale_jobs = client.get("/ops/stale-jobs", params={"stale_after_seconds": 1800, "limit": 10})
        assert stale_jobs.status_code == 200
        stale_payload = stale_jobs.json()
        assert stale_payload["stale_running_reclaimed_total"] == 1
        assert stale_payload["last_stale_running_reclaimed_at"] == payload["reclaimed_at"]
        assert stale_payload["recent_stale_running_reclaims"] == [
            {
                "job_id": "job_reclaim_stale_001",
                "run_id": "run_reclaim_stale_001",
                "paper_id": "paper_reclaim_stale_001",
                "reclaimed_at": payload["reclaimed_at"],
                "error_code": "STALE_RUNNING_RECLAIMED",
                "replacement_job_id": None,
                "replacement_run_id": None,
                "requeued_at": None,
            }
        ]
    finally:
        db_utils.DB_PATH = original_db_path


def test_requeue_reclaimed_job_enqueues_explicit_replacement_and_logs_link(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()
        fixed_now = datetime(2026, 4, 22, 3, 10, 0, tzinfo=timezone.utc)
        monkeypatch.setattr(stale_jobs_service, "utc_now", lambda: fixed_now)

        conn = db_utils.get_db_connection()
        conn.execute(
            """
            INSERT INTO execution_runs (
                run_id, paper_id, trigger_source, pipeline_profile, status, created_at, started_at,
                finished_at, params_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "run_requeue_reclaimed_001",
                "paper_requeue_reclaimed_001",
                "api",
                "deepread",
                "failed",
                "2026-04-22T01:00:00+00:00",
                "2026-04-22T01:15:00+00:00",
                "2026-04-22T03:00:00+00:00",
                json.dumps(
                    {
                        "persona_id": "clinician",
                        "reasoning_persona": "researcher",
                        "profile_id": "profile-requeue-001",
                        "parser_backend": "docling",
                        "run_verify": True,
                        "clean_reindex": True,
                    }
                ),
            ),
        )
        conn.execute(
            """
            INSERT INTO jobs (
                job_id, run_id, paper_id, persona_id, reasoning_persona, profile_id,
                run_verify, clean_reindex, status, progress, stage, created_at, started_at,
                heartbeat_at, finished_at, error_code, error_message
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "job_requeue_reclaimed_001",
                "run_requeue_reclaimed_001",
                "paper_requeue_reclaimed_001",
                "clinician",
                "researcher",
                "profile-requeue-001",
                1,
                1,
                "failed",
                42,
                "read",
                "2026-04-22 01:00:00",
                "2026-04-22 01:15:00",
                "2026-04-22T01:20:00+00:00",
                "2026-04-22T03:00:00+00:00",
                "STALE_RUNNING_RECLAIMED",
                "Operator reclaimed stale running job after 6000s without a fresh heartbeat.",
            ),
        )
        conn.execute(
            """
            INSERT INTO job_events (
                event_id, job_id, run_id, ts, level, event_type, message, payload_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "event_requeue_reclaimed_001",
                "job_requeue_reclaimed_001",
                "run_requeue_reclaimed_001",
                "2026-04-22T03:00:00+00:00",
                "ERROR",
                "job_reclaimed_stale_running",
                "reclaimed before replacement",
                '{"paper_id":"paper_requeue_reclaimed_001","error_code":"STALE_RUNNING_RECLAIMED"}',
            ),
        )
        conn.commit()
        conn.close()

        client = TestClient(api_main.app)
        response = client.post("/ops/jobs/job_requeue_reclaimed_001/requeue-reclaimed")

        assert response.status_code == 200
        payload = response.json()
        assert payload["original_job_id"] == "job_requeue_reclaimed_001"
        assert payload["original_run_id"] == "run_requeue_reclaimed_001"
        assert payload["paper_id"] == "paper_requeue_reclaimed_001"
        assert payload["status"] == "queued"
        assert payload["job_id"] != "job_requeue_reclaimed_001"
        assert payload["run_id"] != "run_requeue_reclaimed_001"
        assert payload["requeued_at"] == "2026-04-22T03:10:00+00:00"

        conn = db_utils.get_db_connection()
        replacement = conn.execute(
            """
            SELECT job_id, run_id, paper_id, persona_id, reasoning_persona, profile_id,
                   run_verify, clean_reindex, status
            FROM jobs
            WHERE job_id = ?
            """,
            (payload["job_id"],),
        ).fetchone()
        run_row = conn.execute(
            "SELECT trigger_source, status, params_json FROM execution_runs WHERE run_id = ?",
            (payload["run_id"],),
        ).fetchone()
        link_events = conn.execute(
            """
            SELECT job_id, run_id, event_type, payload_json
            FROM job_events
            WHERE event_type IN ('job_requeued_replacement', 'job_requeued_from_reclaimed')
            ORDER BY event_type
            """
        ).fetchall()
        conn.close()

        assert replacement["paper_id"] == "paper_requeue_reclaimed_001"
        assert replacement["persona_id"] == "clinician"
        assert replacement["reasoning_persona"] == "researcher"
        assert replacement["profile_id"] == "profile-requeue-001"
        assert replacement["run_verify"] == 1
        assert replacement["clean_reindex"] == 1
        assert replacement["status"] == "queued"
        assert run_row["trigger_source"] == "ops_requeue_reclaimed"
        assert run_row["status"] == "queued"
        run_params = json.loads(run_row["params_json"])
        assert run_params["parser_backend"] == "docling"
        assert run_params["reasoning_persona"] == "researcher"
        assert run_params["profile_id"] == "profile-requeue-001"
        assert len(link_events) == 2
        link_payloads = [json.loads(row["payload_json"]) for row in link_events]
        assert any(item.get("replacement_job_id") == payload["job_id"] for item in link_payloads)
        assert any(item.get("original_job_id") == "job_requeue_reclaimed_001" for item in link_payloads)

        stale_jobs = client.get("/ops/stale-jobs", params={"stale_after_seconds": 1800, "limit": 10})
        assert stale_jobs.status_code == 200
        stale_payload = stale_jobs.json()
        assert stale_payload["stale_running_requeued_total"] == 1
        assert stale_payload["last_stale_running_requeued_at"] == "2026-04-22T03:10:00+00:00"
        assert stale_payload["recent_stale_running_reclaims"] == [
            {
                "job_id": "job_requeue_reclaimed_001",
                "run_id": "run_requeue_reclaimed_001",
                "paper_id": "paper_requeue_reclaimed_001",
                "reclaimed_at": "2026-04-22T03:00:00+00:00",
                "error_code": "STALE_RUNNING_RECLAIMED",
                "replacement_job_id": payload["job_id"],
                "replacement_run_id": payload["run_id"],
                "requeued_at": "2026-04-22T03:10:00+00:00",
            }
        ]
    finally:
        db_utils.DB_PATH = original_db_path


def test_requeue_reclaimed_job_rejects_non_reclaimed_failure(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()
        conn = db_utils.get_db_connection()
        conn.execute(
            """
            INSERT INTO jobs (
                job_id, run_id, paper_id, status, error_code, created_at, finished_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "job_requeue_not_reclaimed_001",
                "run_requeue_not_reclaimed_001",
                "paper_requeue_not_reclaimed_001",
                "failed",
                "READER_FAILED",
                "2026-04-22 01:00:00",
                "2026-04-22 01:30:00",
            ),
        )
        conn.commit()
        conn.close()

        client = TestClient(api_main.app)
        response = client.post("/ops/jobs/job_requeue_not_reclaimed_001/requeue-reclaimed")

        assert response.status_code == 409
        assert response.json()["detail"] == "Job is not a reclaimed stale-running failure"
    finally:
        db_utils.DB_PATH = original_db_path


def test_reclaim_stale_job_rejects_running_job_with_recent_heartbeat(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()
        fixed_now = datetime(2026, 4, 22, 3, 0, 0, tzinfo=timezone.utc)
        monkeypatch.setattr(stale_jobs_service, "utc_now", lambda: fixed_now)

        conn = db_utils.get_db_connection()
        conn.execute(
            """
            INSERT INTO jobs (
                job_id, run_id, paper_id, status, progress, stage, created_at, started_at, heartbeat_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "job_recent_heartbeat_001",
                "run_recent_heartbeat_001",
                "paper_recent_heartbeat_001",
                "running",
                12,
                "read",
                "2026-04-22 01:00:00",
                "2026-04-22 01:15:00",
                "2026-04-22T02:55:00+00:00",
            ),
        )
        conn.commit()
        conn.close()

        client = TestClient(api_main.app)
        response = client.post(
            "/ops/jobs/job_recent_heartbeat_001/reclaim-stale",
            params={"stale_after_seconds": 1800},
        )

        assert response.status_code == 409
        assert response.json()["detail"] == "Job is not stale enough to reclaim"

        job_status = client.get("/jobs/job_recent_heartbeat_001")
        assert job_status.status_code == 200
        assert job_status.json()["status"] == "running"
        assert job_status.json()["error_code"] is None
    finally:
        db_utils.DB_PATH = original_db_path
