from fastapi.testclient import TestClient

import src.db_utils as db_utils
from src.jobs.queue import JobQueue
from backend import main as api_main


def test_job_events_emits_done_for_completed_job(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()
        queue = JobQueue()
        job_id = queue.enqueue(paper_id="paper_events_done")
        queue.update_job(
            job_id,
            {
                "status": "completed",
                "progress": 100,
                "stage": "completed",
            },
        )

        with TestClient(api_main.app) as client:
            with client.stream("GET", f"/jobs/{job_id}/events") as response:
                assert response.status_code == 200
                payload = "".join(response.iter_text())

        assert "event: status" in payload
        assert "event: done" in payload
        assert "data: completed" in payload
    finally:
        db_utils.DB_PATH = original_db_path


def test_job_events_emits_error_for_unknown_job(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()
        with TestClient(api_main.app) as client:
            with client.stream("GET", "/jobs/not-found/events") as response:
                assert response.status_code == 200
                payload = "".join(response.iter_text())

        assert "event: error" in payload
        assert "Job not found" in payload
    finally:
        db_utils.DB_PATH = original_db_path
