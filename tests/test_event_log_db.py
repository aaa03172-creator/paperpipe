import json
import sqlite3

from fastapi.testclient import TestClient

import src.db_utils as db_utils
from backend import main as api_main
from src.jobs.queue import JobQueue
from src.services.event_log import (
    ensure_execution_run,
    get_execution_run_params,
    list_job_events,
    list_request_audits,
    list_run_events,
    list_user_actions,
    log_job_event,
    log_request_audit,
    log_user_action,
    update_execution_run,
)


def test_init_db_creates_additive_event_log_tables(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()
        conn = sqlite3.connect(db_utils.DB_PATH)
        tables = {
            row[0]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        }
        conn.close()
        assert "execution_runs" in tables
        assert "job_events" in tables
        assert "user_actions" in tables
        assert "request_audits" in tables
    finally:
        db_utils.DB_PATH = original_db_path


def test_init_db_backfills_missing_job_event_columns(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        conn = sqlite3.connect(db_utils.DB_PATH)
        conn.execute(
            """
            CREATE TABLE job_events (
                event_id TEXT PRIMARY KEY,
                job_id TEXT NOT NULL,
                ts TEXT NOT NULL,
                level TEXT NOT NULL,
                event_type TEXT NOT NULL,
                message TEXT
            )
            """
        )
        conn.commit()
        conn.close()

        db_utils.init_db()

        conn = sqlite3.connect(db_utils.DB_PATH)
        columns = {
            row[1]
            for row in conn.execute("PRAGMA table_info(job_events)").fetchall()
        }
        conn.close()

        assert "run_id" in columns
        assert "payload_json" in columns
    finally:
        db_utils.DB_PATH = original_db_path


def test_init_db_backfills_missing_job_persona_split_columns(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        conn = sqlite3.connect(db_utils.DB_PATH)
        conn.execute(
            """
            CREATE TABLE jobs (
                job_id TEXT PRIMARY KEY,
                run_id TEXT,
                paper_id TEXT,
                persona_id TEXT DEFAULT 'default',
                status TEXT DEFAULT 'queued'
            )
            """
        )
        conn.commit()
        conn.close()

        db_utils.init_db()

        conn = sqlite3.connect(db_utils.DB_PATH)
        columns = {
            row[1]
            for row in conn.execute("PRAGMA table_info(jobs)").fetchall()
        }
        conn.close()

        assert "reasoning_persona" in columns
        assert "profile_id" in columns
    finally:
        db_utils.DB_PATH = original_db_path


def test_queue_enqueue_creates_execution_run_and_structured_event(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()
        queue = JobQueue()
        job_id = queue.enqueue(
            "paper_eventlog_001",
            run_verify=True,
            reasoning_persona="researcher",
            profile_id="persona-a",
            parser_backend="docling",
        )
        job = queue.get_job(job_id)
        assert job is not None

        conn = db_utils.get_db_connection()
        run_row = conn.execute(
            "SELECT run_id, paper_id, status, pipeline_profile, params_json FROM execution_runs WHERE run_id = ?",
            (job.run_id,),
        ).fetchone()
        job_row = conn.execute(
            "SELECT persona_id, reasoning_persona, profile_id FROM jobs WHERE job_id = ?",
            (job_id,),
        ).fetchone()
        event_row = conn.execute(
            "SELECT event_type, message FROM job_events WHERE job_id = ? ORDER BY ts ASC LIMIT 1",
            (job_id,),
        ).fetchone()
        conn.close()

        assert run_row is not None
        assert run_row["paper_id"] == "paper_eventlog_001"
        assert run_row["status"] == "queued"
        assert run_row["pipeline_profile"] == "deepread"
        assert json.loads(run_row["params_json"])["reasoning_persona"] == "researcher"
        assert json.loads(run_row["params_json"])["profile_id"] == "persona-a"
        assert json.loads(run_row["params_json"])["parser_backend"] == "docling"
        assert job_row is not None
        assert job_row["persona_id"] == "persona-a"
        assert job_row["reasoning_persona"] == "researcher"
        assert job_row["profile_id"] == "persona-a"
        assert event_row is not None
        assert event_row["event_type"] == "job_enqueued"
        assert event_row["message"] == "queued"
    finally:
        db_utils.DB_PATH = original_db_path


def test_execution_run_params_and_metrics_redact_secret_like_values(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()
        ensure_execution_run(
            run_id="run_secret_params",
            paper_id="paper_eventlog_secret_001",
            trigger_source="test",
            pipeline_profile="deepread",
            params={
                "OPENAI_API_KEY": "sk-proj-paperpipe-param-abcdef",
                "note": "Authorization: Basic beta:wrong-pass",
            },
        )
        update_execution_run(
            run_id="run_secret_params",
            metrics={"database_url": "postgresql://paperpipe:secret@example.local/db"},
        )

        conn = db_utils.get_db_connection()
        row = conn.execute(
            "SELECT params_json, metrics_json FROM execution_runs WHERE run_id = ?",
            ("run_secret_params",),
        ).fetchone()
        conn.close()

        assert row is not None
        raw_params = row["params_json"]
        raw_metrics = row["metrics_json"]
        assert "sk-proj-paperpipe-param-abcdef" not in raw_params
        assert "Basic beta:wrong-pass" not in raw_params
        assert "postgresql://paperpipe:secret@example.local/db" not in raw_metrics
        assert json.loads(raw_params)["OPENAI_API_KEY"] == "<redacted>"
        assert json.loads(raw_params)["note"] == "Authorization: <redacted>"
        assert json.loads(raw_metrics)["database_url"] == "<redacted>"
        assert get_execution_run_params("run_secret_params")["OPENAI_API_KEY"] == "<redacted>"
    finally:
        db_utils.DB_PATH = original_db_path


def test_event_log_read_helpers_sanitize_legacy_rows(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()
        queue = JobQueue()
        job_id = queue.enqueue("paper_legacy_secret_001")
        job = queue.get_job(job_id)
        assert job is not None
        conn = db_utils.get_db_connection()
        conn.execute(
            "UPDATE execution_runs SET params_json = ? WHERE run_id = ?",
            (json.dumps({"OPENAI_API_KEY": "sk-proj-paperpipe-legacy-param"}), job.run_id),
        )
        conn.execute(
            """
            INSERT INTO job_events (
                event_id, job_id, run_id, ts, level, event_type, message, payload_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "event_legacy_secret",
                job_id,
                job.run_id,
                "2026-04-24T00:00:01+00:00",
                "ERROR",
                "provider_error",
                "Provider failed with Bearer legacy-token-123",
                json.dumps({"error": "Authorization: Basic beta:wrong-pass"}),
            ),
        )
        conn.execute(
            """
            INSERT INTO user_actions (action_id, ts, paper_id, action_type, source, payload_json)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                "action_legacy_secret",
                "2026-04-24T00:00:02+00:00",
                "paper_legacy_secret_001",
                "debug",
                "ui",
                json.dumps({"cookie": "session=abc123"}),
            ),
        )
        conn.execute(
            """
            INSERT INTO request_audits (
                audit_id, ts, source, client_ip, host, method, path, status_code, outcome, payload_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "audit_legacy_secret",
                "2026-04-24T00:00:03+00:00",
                "browser_security",
                "10.0.0.8",
                "beta.example",
                "POST",
                "/api/jobs/deepread",
                403,
                "denied",
                json.dumps({"headers": {"X-API-Key": "legacy-secret-key"}}),
            ),
        )
        conn.commit()
        conn.close()

        params = get_execution_run_params(str(job.run_id))
        events = list_run_events(str(job.run_id))
        actions = list_user_actions(paper_id="paper_legacy_secret_001")
        audits = list_request_audits(path="/api/jobs/deepread", outcome="denied")

        assert params["OPENAI_API_KEY"] == "<redacted>"
        assert "legacy-token-123" not in events[0]["message"]
        assert events[0]["message"] == "Provider failed with <redacted>"
        event_payload = json.loads(events[0]["payload_json"])
        assert event_payload["error"] == "Authorization: <redacted>"
        assert actions[0]["payload"]["cookie"] == "<redacted>"
        assert audits[0]["payload"]["headers"]["X-API-Key"] == "<redacted>"
    finally:
        db_utils.DB_PATH = original_db_path


def test_event_log_helpers_persist_job_events_and_user_actions(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()
        queue = JobQueue()
        job_id = queue.enqueue("paper_evt_001")
        job = queue.get_job(job_id)
        assert job is not None
        ensure_execution_run(
            run_id=str(job.run_id),
            paper_id="paper_evt_001",
            trigger_source="chat",
            pipeline_profile="deepread",
        )
        event_id = log_job_event(
            job_id=job_id,
            run_id=str(job.run_id),
            level="INFO",
            event_type="step_start",
            message="ingest started",
            payload={"stage": "ingest", "progress": 10},
        )
        action_id = log_user_action(
            paper_id="paper_evt_001",
            action_type="important",
            source="ui",
            payload={"reason": "user flagged"},
        )

        rows = list_job_events(job_id)
        assert any(row["event_id"] == event_id for row in rows)

        conn = db_utils.get_db_connection()
        action_row = conn.execute(
            "SELECT action_id, action_type, source, payload_json FROM user_actions WHERE action_id = ?",
            (action_id,),
        ).fetchone()
        conn.close()

        assert action_row is not None
        assert action_row["action_type"] == "important"
        assert action_row["source"] == "ui"
        assert json.loads(action_row["payload_json"])["reason"] == "user flagged"

        listed = list_user_actions(paper_id="paper_evt_001", limit=10)
        assert len(listed) == 1
        assert listed[0]["action_id"] == action_id
        assert listed[0]["action_type"] == "important"
        assert listed[0]["payload"]["reason"] == "user flagged"
    finally:
        db_utils.DB_PATH = original_db_path


def test_job_events_and_user_actions_redact_secret_like_payload_values(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()
        queue = JobQueue()
        job_id = queue.enqueue("paper_evt_secret_001")
        job = queue.get_job(job_id)
        assert job is not None

        event_id = log_job_event(
            job_id=job_id,
            run_id=str(job.run_id),
            level="ERROR",
            event_type="provider_error",
            message="provider failed: Bearer provider-token-123",
            payload={
                "status": "failed",
                "error": "Authorization: Bearer provider-token-123",
                "nested": {"OPENAI_API_KEY": "sk-proj-paperpipe-job-abcdef"},
            },
        )
        action_id = log_user_action(
            paper_id="paper_evt_secret_001",
            action_type="debug",
            source="ui",
            payload={
                "reason": "operator note",
                "cookie": "session=abc123",
                "metadata": ["postgresql://paperpipe:secret@example.local/db"],
            },
        )

        conn = db_utils.get_db_connection()
        event_row = conn.execute(
            "SELECT message, payload_json FROM job_events WHERE event_id = ?",
            (event_id,),
        ).fetchone()
        action_row = conn.execute(
            "SELECT payload_json FROM user_actions WHERE action_id = ?",
            (action_id,),
        ).fetchone()
        conn.close()

        assert event_row is not None
        assert action_row is not None
        assert event_row["message"] == "provider failed: <redacted>"
        raw_event_payload = event_row["payload_json"]
        raw_action_payload = action_row["payload_json"]
        assert "provider-token-123" not in raw_event_payload
        assert "sk-proj-paperpipe-job-abcdef" not in raw_event_payload
        assert "session=abc123" not in raw_action_payload
        assert "postgresql://paperpipe:secret@example.local/db" not in raw_action_payload

        event_payload = json.loads(raw_event_payload)
        action_payload = json.loads(raw_action_payload)
        assert event_payload["error"] == "Authorization: <redacted>"
        assert event_payload["nested"]["OPENAI_API_KEY"] == "<redacted>"
        assert action_payload["reason"] == "operator note"
        assert action_payload["cookie"] == "<redacted>"
        assert action_payload["metadata"] == ["<redacted>"]
    finally:
        db_utils.DB_PATH = original_db_path


def test_request_audit_helpers_persist_and_filter_rows(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()
        audit_id = log_request_audit(
            source="browser_api",
            client_ip="10.0.0.8",
            host="beta.example",
            method="POST",
            path="/api/jobs/deepread",
            status_code=200,
            outcome="allowed",
            payload={"scope": "browser_write"},
        )

        conn = db_utils.get_db_connection()
        row = conn.execute(
            "SELECT audit_id, source, client_ip, host, method, path, status_code, outcome, payload_json FROM request_audits WHERE audit_id = ?",
            (audit_id,),
        ).fetchone()
        conn.close()

        assert row is not None
        assert row["source"] == "browser_api"
        assert row["client_ip"] == "10.0.0.8"
        assert row["host"] == "beta.example"
        assert row["method"] == "POST"
        assert row["path"] == "/api/jobs/deepread"
        assert row["status_code"] == 200
        assert row["outcome"] == "allowed"
        assert json.loads(row["payload_json"])["scope"] == "browser_write"

        listed = list_request_audits(path="/api/jobs/deepread", outcome="allowed", limit=10)
        assert len(listed) == 1
        assert listed[0]["audit_id"] == audit_id
        assert listed[0]["payload"]["scope"] == "browser_write"
    finally:
        db_utils.DB_PATH = original_db_path


def test_request_audit_payload_redacts_auth_headers_and_key_like_values(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()
        audit_id = log_request_audit(
            source="browser_security",
            client_ip="10.0.0.8",
            host="beta.example",
            method="POST",
            path="/api/jobs/deepread",
            status_code=403,
            outcome="denied",
            payload={
                "scope": "browser_write",
                "headers": {
                    "Authorization": "Basic beta:wrong-pass",
                    "X-API-Key": "secret-key",
                    "Content-Type": "application/json",
                },
                "notes": [
                    "OPENAI_API_KEY=sk-proj-paperpipe-abcdef",
                    "db=postgresql://paperpipe:secret@example.local/db",
                ],
            },
        )

        conn = db_utils.get_db_connection()
        row = conn.execute(
            "SELECT payload_json FROM request_audits WHERE audit_id = ?",
            (audit_id,),
        ).fetchone()
        conn.close()

        assert row is not None
        raw_payload = row["payload_json"]
        assert "Basic beta:wrong-pass" not in raw_payload
        assert "secret-key" not in raw_payload
        assert "sk-proj-paperpipe-abcdef" not in raw_payload
        assert "postgresql://paperpipe:secret@example.local/db" not in raw_payload

        payload = json.loads(raw_payload)
        assert payload["scope"] == "browser_write"
        assert payload["headers"]["Authorization"] == "<redacted>"
        assert payload["headers"]["X-API-Key"] == "<redacted>"
        assert payload["headers"]["Content-Type"] == "application/json"
        assert payload["notes"] == ["OPENAI_API_KEY=<redacted>", "db=<redacted>"]

        listed = list_request_audits(path="/api/jobs/deepread", outcome="denied", limit=10)
        assert listed[0]["payload"]["headers"]["Authorization"] == "<redacted>"
    finally:
        db_utils.DB_PATH = original_db_path


def test_list_run_events_returns_empty_for_legacy_job_events_without_run_id(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        conn = sqlite3.connect(db_utils.DB_PATH)
        conn.execute(
            """
            CREATE TABLE job_events (
                event_id TEXT PRIMARY KEY,
                job_id TEXT NOT NULL,
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
            INSERT INTO job_events (event_id, job_id, ts, level, event_type, message, payload_json)
            VALUES ('evt-1', 'job-1', '2026-03-13T00:00:00Z', 'INFO', 'legacy', 'legacy row', '{}')
            """
        )
        conn.commit()
        conn.close()

        assert list_run_events("run-legacy-001") == []
    finally:
        db_utils.DB_PATH = original_db_path


def test_runs_timeline_prefers_db_events_when_present(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()
        queue = JobQueue()
        job_id = queue.enqueue("paper_timeline_db_001")
        job = queue.get_job(job_id)
        assert job is not None

        log_job_event(
            job_id=job_id,
            run_id=job.run_id,
            level="INFO",
            event_type="progress",
            message="db ingest",
            payload={"stage": "ingest", "progress": 10, "message": "db ingest"},
        )
        queue.update_job(
            job_id,
            {"status": "completed", "progress": 100, "stage": "completed", "finished_at": "2026-03-13T00:00:03+00:00"},
        )

        client = TestClient(api_main.app)
        response = client.get(f"/runs/{job.run_id}/timeline")
        assert response.status_code == 200
        payload = response.json()
        assert payload["run_id"] == job.run_id
        assert any(evt["source"] == "db_event" and evt["message"] == "db ingest" for evt in payload["events"])
        assert any(evt["event"] == "done" and evt["message"] == "completed" for evt in payload["events"])
    finally:
        db_utils.DB_PATH = original_db_path


def test_job_status_timeline_and_log_replay_sanitize_legacy_file_log_secrets(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()
        queue = JobQueue()
        job_id = queue.enqueue("paper_timeline_file_secret_001")
        job = queue.get_job(job_id)
        assert job is not None

        log_file = tmp_path / "job-secret.jsonl"
        log_file.write_text(
            "\n".join(
                [
                    json.dumps(
                        {
                            "stage": "read",
                            "progress": 42,
                            "level": "ERROR",
                            "message": "Provider failed with Bearer file-token-123",
                            "timestamp": "2026-04-24T00:00:01+00:00",
                        }
                    ),
                    "plain Authorization: Bearer raw-line-token",
                ]
            ),
            encoding="utf-8",
        )
        queue.update_job(
            job_id,
            {
                "status": "failed",
                "progress": 42,
                "stage": "failed",
                "log_path": str(log_file),
                "error_message": "Provider failed with Bearer status-token-123",
                "finished_at": "2026-04-24T00:00:02+00:00",
            },
        )
        conn = db_utils.get_db_connection()
        row = conn.execute("SELECT error_message FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
        conn.close()
        assert row is not None
        assert row["error_message"] == "Provider failed with <redacted>"

        client = TestClient(api_main.app)
        status_response = client.get(f"/jobs/{job_id}")
        assert status_response.status_code == 200
        status_payload = status_response.json()
        assert "status-token-123" not in json.dumps(status_payload)
        assert status_payload["error_message"] == "Provider failed with <redacted>"

        timeline_response = client.get(f"/runs/{job.run_id}/timeline")
        assert timeline_response.status_code == 200
        timeline_payload = timeline_response.json()
        serialized_timeline = json.dumps(timeline_payload)
        assert "file-token-123" not in serialized_timeline
        assert "raw-line-token" not in serialized_timeline
        assert "status-token-123" not in serialized_timeline
        assert any(
            event["source"] == "job_log" and event["message"] == "Provider failed with <redacted>"
            for event in timeline_payload["events"]
        )
        assert any(
            event["source"] == "job_log" and event.get("raw") == "plain Authorization: <redacted>"
            for event in timeline_payload["events"]
        )
        assert any(
            event["source"] == "synthetic" and event["message"] == "Provider failed with <redacted>"
            for event in timeline_payload["events"]
        )

        replay_lines = api_main._read_log_lines(str(log_file))
        serialized_replay = "\n".join(replay_lines)
        assert "file-token-123" not in serialized_replay
        assert "raw-line-token" not in serialized_replay
        assert json.loads(replay_lines[0])["message"] == "Provider failed with <redacted>"
        assert replay_lines[1] == "plain Authorization: <redacted>"
    finally:
        db_utils.DB_PATH = original_db_path


def test_runs_timeline_includes_matching_user_actions(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()
        queue = JobQueue()
        job_id = queue.enqueue("paper_timeline_actions_001")
        job = queue.get_job(job_id)
        assert job is not None

        log_user_action(
            paper_id="paper_timeline_actions_001",
            action_type="deepread_enqueued",
            source="ui",
            payload={"run_id": job.run_id},
        )
        log_user_action(
            paper_id="paper_timeline_actions_001",
            action_type="obsidian_sync",
            source="obsidian",
            payload={"run_id": "run_other"},
        )

        client = TestClient(api_main.app)
        response = client.get(f"/runs/{job.run_id}/timeline")
        assert response.status_code == 200
        payload = response.json()

        assert any(
            evt["source"] == "user_action" and evt["message"] == "User queued deep read"
            for evt in payload["events"]
        )
        assert all(
            not (evt["source"] == "user_action" and evt["stage"] == "obsidian_sync")
            for evt in payload["events"]
        )
    finally:
        db_utils.DB_PATH = original_db_path


def test_user_actions_api_lists_and_filters_rows(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()
        log_user_action(
            paper_id="paper_action_001",
            action_type="deepread_enqueued",
            source="ui",
            payload={"job_id": "job-1"},
        )
        log_user_action(
            paper_id="paper_action_001",
            action_type="obsidian_sync",
            source="obsidian",
            payload={"run_id": "run-1"},
        )
        log_user_action(
            paper_id="paper_action_002",
            action_type="repair_stats",
            source="ui",
            payload={"run_id": "run-2"},
        )

        client = TestClient(api_main.app)

        response = client.get("/user-actions", params={"paper_id": "paper_action_001", "limit": 10})
        assert response.status_code == 200
        payload = response.json()
        assert len(payload["actions"]) == 2
        assert {item["action_type"] for item in payload["actions"]} == {"deepread_enqueued", "obsidian_sync"}
        assert payload["actions"][0]["payload"] is not None

        filtered = client.get(
            "/user-actions",
            params={"paper_id": "paper_action_001", "source": "obsidian", "action_type": "obsidian_sync"},
        )
        assert filtered.status_code == 200
        filtered_payload = filtered.json()
        assert len(filtered_payload["actions"]) == 1
        assert filtered_payload["actions"][0]["source"] == "obsidian"
        assert filtered_payload["actions"][0]["action_type"] == "obsidian_sync"
        assert filtered_payload["actions"][0]["payload"]["run_id"] == "run-1"
    finally:
        db_utils.DB_PATH = original_db_path


def test_user_actions_api_creates_row(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()
        client = TestClient(api_main.app)

        response = client.post(
            "/user-actions",
            json={
                "paper_id": "paper_action_create_001",
                "action_type": "open_workbench",
                "source": "ui",
                "payload": {"origin": "triage_dashboard"},
            },
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["paper_id"] == "paper_action_create_001"
        assert payload["action_type"] == "open_workbench"
        assert payload["source"] == "ui"
        assert payload["payload"]["origin"] == "triage_dashboard"

        conn = db_utils.get_db_connection()
        row = conn.execute(
            "SELECT paper_id, action_type, source, payload_json FROM user_actions WHERE action_id = ?",
            (payload["action_id"],),
        ).fetchone()
        conn.close()

        assert row is not None
        assert row["paper_id"] == "paper_action_create_001"
        assert row["action_type"] == "open_workbench"
        assert row["source"] == "ui"
        assert json.loads(row["payload_json"])["origin"] == "triage_dashboard"
    finally:
        db_utils.DB_PATH = original_db_path


def test_user_actions_api_recovers_when_additive_table_is_missing(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()
        conn = db_utils.get_db_connection()
        conn.execute("DROP TABLE user_actions")
        conn.commit()
        conn.close()

        client = TestClient(api_main.app)
        response = client.post(
            "/user-actions",
            json={
                "paper_id": "paper_action_recover_001",
                "action_type": "open_workbench",
                "source": "ui",
                "payload": {"origin": "triage_dashboard"},
            },
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["paper_id"] == "paper_action_recover_001"
        assert payload["action_type"] == "open_workbench"

        conn = db_utils.get_db_connection()
        row = conn.execute(
            "SELECT paper_id, action_type, source, payload_json FROM user_actions WHERE action_id = ?",
            (payload["action_id"],),
        ).fetchone()
        conn.close()

        assert row is not None
        assert row["paper_id"] == "paper_action_recover_001"
        assert row["action_type"] == "open_workbench"
        assert row["source"] == "ui"
        assert json.loads(row["payload_json"])["origin"] == "triage_dashboard"
    finally:
        db_utils.DB_PATH = original_db_path
