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
    list_run_events,
    list_user_actions,
    log_job_event,
    log_user_action,
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

def test_job_event_helpers_return_empty_for_legacy_db_without_job_events_table(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        conn = sqlite3.connect(db_utils.DB_PATH)
        conn.execute("CREATE TABLE jobs (job_id TEXT PRIMARY KEY)")
        conn.commit()
        conn.close()

        assert list_job_events("job-legacy-001") == []
        assert list_run_events("run-legacy-001") == []
    finally:
        db_utils.DB_PATH = original_db_path

def test_get_execution_run_params_returns_empty_for_legacy_db_without_execution_runs_table(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        conn = sqlite3.connect(db_utils.DB_PATH)
        conn.execute("CREATE TABLE jobs (job_id TEXT PRIMARY KEY)")
        conn.commit()
        conn.close()

        assert get_execution_run_params("run-legacy-001") == {}
    finally:
        db_utils.DB_PATH = original_db_path


def test_list_run_events_returns_empty_when_job_events_table_is_missing(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        conn = sqlite3.connect(db_utils.DB_PATH)
        conn.execute("CREATE TABLE jobs (job_id TEXT PRIMARY KEY)")
        conn.commit()
        conn.close()

        assert list_run_events("run-missing-table-001") == []
    finally:
        db_utils.DB_PATH = original_db_path


def test_list_user_actions_returns_empty_for_legacy_db_without_user_actions_table(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        conn = sqlite3.connect(db_utils.DB_PATH)
        conn.execute("CREATE TABLE jobs (job_id TEXT PRIMARY KEY)")
        conn.commit()
        conn.close()

        assert list_user_actions(paper_id="paper-legacy-001") == []
    finally:
        db_utils.DB_PATH = original_db_path


def test_jobs_listing_tolerates_legacy_db_without_execution_runs_table(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()
        queue = JobQueue()
        job_id = queue.enqueue("paper_legacy_jobs_001")
        job = queue.get_job(job_id)
        assert job is not None

        conn = db_utils.get_db_connection()
        conn.execute("DROP TABLE execution_runs")
        conn.commit()
        conn.close()

        client = TestClient(api_main.app)
        response = client.get("/jobs")

        assert response.status_code == 200
        rows = response.json()
        assert any(item["job_id"] == job_id for item in rows)
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
