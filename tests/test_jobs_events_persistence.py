from pathlib import Path

from fastapi.testclient import TestClient

import src.db_utils as db_utils
from backend import main as api_main
from src.jobs.queue import JobQueue


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
        assert "event: status" in response.text
        assert '"status": "completed"' in response.text
        assert "event: log" in response.text
        assert "line one" in response.text
        assert "event: done" in response.text
        assert "data: completed" in response.text
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
    assert "event: error" in response.text
    assert "Job not found" in response.text


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
        assert "event: done" in first.text
        assert "data: completed" in first.text
        assert "event: done" in second.text
        assert "data: completed" in second.text
    finally:
        db_utils.DB_PATH = original_db_path
