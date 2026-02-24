import importlib

from fastapi.testclient import TestClient

import src.db_utils as db_utils
from backend import main as api_main
from src.jobs.queue import JobQueue


def test_job_status_and_events_survive_backend_reload(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()
        queue = JobQueue()
        job_id = queue.enqueue("paper_restart_001")

        log_path = tmp_path / "restart.log"
        log_path.write_text("persisted log line\n", encoding="utf-8")
        queue.update_job(
            job_id,
            {
                "status": "completed",
                "progress": 100,
                "stage": "completed",
                "log_path": str(log_path),
            },
        )

        # Simulate API server process/module reload.
        reloaded_main = importlib.reload(api_main)
        client = TestClient(reloaded_main.app)

        detail = client.get(f"/jobs/{job_id}")
        assert detail.status_code == 200
        payload = detail.json()
        assert payload["status"] == "completed"
        assert payload["progress"] == 100
        assert payload["stage"] == "completed"
        assert payload["log_path"] == str(log_path)

        events = client.get(f"/jobs/{job_id}/events")
        assert events.status_code == 200
        assert "event: status" in events.text
        assert '"status": "completed"' in events.text
        assert "event: log" in events.text
        assert "persisted log line" in events.text
        assert "event: done" in events.text
        assert "data: completed" in events.text
    finally:
        db_utils.DB_PATH = original_db_path
        importlib.reload(api_main)
