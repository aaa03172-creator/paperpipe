import json
from pathlib import Path

from fastapi.testclient import TestClient

import src.db_utils as db_utils
from backend import main as api_main
from src.jobs.queue import JobQueue


def _parse_sse_events(raw: str) -> list[dict]:
    events: list[dict] = []
    current: dict[str, str] = {}
    for line in raw.splitlines():
        if not line.strip():
            if current:
                events.append(current)
                current = {}
            continue
        if line.startswith("event:"):
            current["event"] = line.split(":", 1)[1].strip()
        elif line.startswith("id:"):
            current["id"] = line.split(":", 1)[1].strip()
        elif line.startswith("data:"):
            current["data"] = line.split(":", 1)[1].strip()
    if current:
        events.append(current)
    return events


def test_jobs_events_stream_emits_status_log_and_done_for_terminal_job(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()
        queue = JobQueue()
        job_id = queue.enqueue("paper_events_001")

        log_path = tmp_path / "job.log"
        log_path.write_text("line one\n", encoding="utf-8")
        queue.update_job(
            job_id,
            {
                "status": "completed",
                "progress": 100,
                "stage": "completed",
                "log_path": str(log_path),
            },
        )

        client = TestClient(api_main.app)
        response = client.get(f"/jobs/{job_id}/events")

        assert response.status_code == 200
        assert response.headers.get("content-type", "").startswith("text/event-stream")
        events = _parse_sse_events(response.text)
        names = [e.get("event") for e in events]
        assert "status" in names
        assert "log" in names
        assert names.count("done") == 1

        status_payload = json.loads(next(e["data"] for e in events if e.get("event") == "status"))
        assert status_payload["status"] == "completed"
        assert status_payload["progress"] == 100
        assert "bootstrap_meta_path" in status_payload

        assert any(e.get("event") == "log" and e.get("data") == "line one" for e in events)
        assert any(e.get("event") == "done" and e.get("data") == "completed" for e in events)
    finally:
        db_utils.DB_PATH = original_db_path


def test_jobs_events_stream_emits_artifact_ready_when_artifact_dir_exists(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()
        queue = JobQueue()
        job_id = queue.enqueue("paper_events_artifact_001")

        artifact_dir = tmp_path / "storage" / "artifacts" / "paper_events_artifact_001" / "run_ready"
        artifact_dir.mkdir(parents=True, exist_ok=True)
        (artifact_dir / "document_artifact.json").write_text(json.dumps({"ok": True}), encoding="utf-8")
        queue.update_job(
            job_id,
            {
                "status": "completed",
                "progress": 100,
                "stage": "completed",
                "artifact_dir": str(artifact_dir),
            },
        )

        client = TestClient(api_main.app)
        response = client.get(f"/jobs/{job_id}/events")

        assert response.status_code == 200
        events = _parse_sse_events(response.text)
        artifact_evt = next(e for e in events if e.get("event") == "artifact_ready")
        payload = json.loads(artifact_evt["data"])
        assert payload["artifact_dir"] == str(artifact_dir)
        assert payload["paper_id"] == "paper_events_artifact_001"
    finally:
        db_utils.DB_PATH = original_db_path


def test_job_queue_state_persists_across_instances(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()

        queue_a = JobQueue()
        job_id = queue_a.enqueue(
            paper_id="paper_persist_001",
            run_verify=True,
            persona_id="persist-persona",
        )

        queue_b = JobQueue()
        queued = queue_b.get_job(job_id)
        assert queued is not None
        assert queued.status == "queued"
        assert queued.paper_id == "paper_persist_001"
        assert queued.persona_id == "persist-persona"
        assert queued.run_verify == 1
        assert queued.clean_reindex == 0

        queue_b.update_job(
            job_id,
            {
                "status": "running",
                "progress": 50,
                "stage": "read",
            },
        )

        queue_c = JobQueue()
        running = queue_c.get_job(job_id)
        assert running is not None
        assert running.status == "running"
        assert running.progress == 50
        assert running.stage == "read"
    finally:
        db_utils.DB_PATH = original_db_path


def test_jobs_events_stream_emits_done_for_cancelled_job(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()
        queue = JobQueue()
        job_id = queue.enqueue("paper_cancelled_001")
        queue.cancel_job(job_id)

        client = TestClient(api_main.app)
        response = client.get(f"/jobs/{job_id}/events")

        assert response.status_code == 200
        assert response.headers.get("content-type", "").startswith("text/event-stream")
        assert "event: status" in response.text
        assert '"status": "cancelled"' in response.text
        assert "event: done" in response.text
        assert "data: cancelled" in response.text
    finally:
        db_utils.DB_PATH = original_db_path


def test_jobs_events_stream_returns_error_event_for_unknown_job():
    client = TestClient(api_main.app)
    response = client.get("/jobs/no_such_job/events")

    assert response.status_code == 200
    assert response.headers.get("content-type", "").startswith("text/event-stream")
    events = _parse_sse_events(response.text)
    assert events[0]["event"] == "error"
    assert "Job not found" in events[0]["data"]
    assert all(e["event"] != "done" for e in events)


def test_jobs_events_stream_reconnect_replays_terminal_state(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()
        queue = JobQueue()
        job_id = queue.enqueue("paper_reconnect_001")
        queue.update_job(job_id, {"status": "completed", "progress": 100, "stage": "completed"})

        client = TestClient(api_main.app)
        first = client.get(f"/jobs/{job_id}/events")
        second = client.get(f"/jobs/{job_id}/events")

        assert first.status_code == 200
        assert second.status_code == 200
        first_events = _parse_sse_events(first.text)
        second_events = _parse_sse_events(second.text)
        assert any(e.get("event") == "done" and e.get("data") == "completed" for e in first_events)
        assert any(e.get("event") == "done" and e.get("data") == "completed" for e in second_events)
        assert sum(1 for e in first_events if e.get("event") == "done") == 1
        assert sum(1 for e in second_events if e.get("event") == "done") == 1
    finally:
        db_utils.DB_PATH = original_db_path


def test_jobs_events_stream_last_event_id_replays_only_new_logs(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()
        queue = JobQueue()
        job_id = queue.enqueue("paper_last_event_id_001")

        log_path = tmp_path / "job_last_event.log"
        log_path.write_text("line one\nline two\nline three\n", encoding="utf-8")
        queue.update_job(
            job_id,
            {
                "status": "completed",
                "progress": 100,
                "stage": "completed",
                "log_path": str(log_path),
            },
        )

        client = TestClient(api_main.app)

        first = client.get(f"/jobs/{job_id}/events")
        assert first.status_code == 200
        first_events = _parse_sse_events(first.text)
        first_logs = [e for e in first_events if e.get("event") == "log"]
        assert [e.get("data") for e in first_logs] == ["line one", "line two", "line three"]
        assert [e.get("id") for e in first_logs] == ["log-1", "log-2", "log-3"]
        assert any(e.get("event") == "done" and e.get("id") == "done-4" for e in first_events)

        resumed = client.get(f"/jobs/{job_id}/events", headers={"Last-Event-ID": "log-1"})
        assert resumed.status_code == 200
        resumed_events = _parse_sse_events(resumed.text)
        resumed_logs = [e for e in resumed_events if e.get("event") == "log"]
        assert [e.get("data") for e in resumed_logs] == ["line two", "line three"]
        assert [e.get("id") for e in resumed_logs] == ["log-2", "log-3"]
        assert any(e.get("event") == "done" and e.get("id") == "done-4" for e in resumed_events)
    finally:
        db_utils.DB_PATH = original_db_path


def test_jobs_events_stream_stale_last_event_id_replays_from_head(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()
        queue = JobQueue()
        job_id = queue.enqueue("paper_stale_cursor_001")

        log_path = tmp_path / "job_stale_cursor.log"
        log_path.write_text("line one\nline two\n", encoding="utf-8")
        queue.update_job(
            job_id,
            {
                "status": "completed",
                "progress": 100,
                "stage": "completed",
                "log_path": str(log_path),
            },
        )

        client = TestClient(api_main.app)
        response = client.get(f"/jobs/{job_id}/events", headers={"Last-Event-ID": "log-99"})
        assert response.status_code == 200
        events = _parse_sse_events(response.text)

        logs = [e for e in events if e.get("event") == "log"]
        assert [e.get("data") for e in logs] == ["line one", "line two"]
        assert [e.get("id") for e in logs] == ["log-1", "log-2"]
        assert any(e.get("event") == "done" and e.get("id") == "done-3" for e in events)
    finally:
        db_utils.DB_PATH = original_db_path


def test_jobs_events_stream_done_cursor_does_not_replay_done(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()
        queue = JobQueue()
        job_id = queue.enqueue("paper_done_cursor_001")

        log_path = tmp_path / "job_done_cursor.log"
        log_path.write_text("line one\nline two\n", encoding="utf-8")
        queue.update_job(
            job_id,
            {
                "status": "completed",
                "progress": 100,
                "stage": "completed",
                "log_path": str(log_path),
            },
        )

        client = TestClient(api_main.app)
        response = client.get(f"/jobs/{job_id}/events", headers={"Last-Event-ID": "done-3"})
        assert response.status_code == 200
        events = _parse_sse_events(response.text)

        assert any(e.get("event") == "status" for e in events)
        assert all(e.get("event") != "log" for e in events)
        assert all(e.get("event") != "done" for e in events)
    finally:
        db_utils.DB_PATH = original_db_path


def test_jobs_events_stream_status_includes_bootstrap_meta_fields(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()
        queue = JobQueue()
        job_id = queue.enqueue("paper_bootstrap_events_001")

        artifact_dir = tmp_path / "storage" / "artifacts" / "paper_bootstrap_events_001" / "run_1"
        artifact_dir.mkdir(parents=True, exist_ok=True)
        (artifact_dir / "bootstrap_meta.json").write_text(
            json.dumps(
                {
                    "similar_feedback_count": 3,
                    "persona_applied": True,
                    "claimset_readiness": "ready",
                    "claimset_readiness_reason": "claims_present",
                    "claimset_ops_alert": False,
                }
            ),
            encoding="utf-8",
        )
        queue.update_job(
            job_id,
            {
                "status": "completed",
                "progress": 100,
                "stage": "completed",
                "artifact_dir": str(artifact_dir),
            },
        )

        client = TestClient(api_main.app)
        response = client.get(f"/jobs/{job_id}/events")
        assert response.status_code == 200

        status_payload = json.loads(
            next(e["data"] for e in _parse_sse_events(response.text) if e.get("event") == "status")
        )
        assert status_payload["bootstrap_meta_path"] == str(artifact_dir / "bootstrap_meta.json")
        assert status_payload["similar_feedback_count"] == 3
        assert status_payload["persona_applied"] is True
        assert status_payload["claimset_readiness"] == "ready"
        assert status_payload["claimset_readiness_reason"] == "claims_present"
        assert status_payload["claimset_readiness_badge"] == "READY"
        assert status_payload["claimset_ops_alert"] is False
    finally:
        db_utils.DB_PATH = original_db_path
