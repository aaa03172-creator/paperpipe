from fastapi.testclient import TestClient

import src.db_utils as db_utils
from src.jobs.queue import JobQueue
from backend import main as api_main


def test_jobs_list_endpoint_supports_paper_filter(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()
        client = TestClient(api_main.app)
        queue = JobQueue()

        job_id_a = queue.enqueue(paper_id="paper_jobs_list_001")
        queue.enqueue(paper_id="paper_jobs_list_002")

        response = client.get("/jobs", params={"paper_id": "paper_jobs_list_001"})
        assert response.status_code == 200
        payload = response.json()
        assert len(payload) == 1
        assert payload[0]["job_id"] == job_id_a
        assert payload[0]["paper_id"] == "paper_jobs_list_001"
    finally:
        db_utils.DB_PATH = original_db_path


def test_jobs_list_endpoint_supports_status_and_limit_filters(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()
        client = TestClient(api_main.app)
        queue = JobQueue()

        completed_job = queue.enqueue(paper_id="paper_jobs_status_001")
        queued_job = queue.enqueue(paper_id="paper_jobs_status_002")
        queue.update_job(completed_job, {"status": "completed", "progress": 100, "stage": "completed"})

        completed_response = client.get("/jobs", params={"status": "completed"})
        assert completed_response.status_code == 200
        completed_payload = completed_response.json()
        assert len(completed_payload) == 1
        assert completed_payload[0]["job_id"] == completed_job
        assert completed_payload[0]["status"] == "completed"

        limited_response = client.get("/jobs", params={"limit": 1})
        assert limited_response.status_code == 200
        limited_payload = limited_response.json()
        assert len(limited_payload) == 1
        assert limited_payload[0]["job_id"] in {completed_job, queued_job}
    finally:
        db_utils.DB_PATH = original_db_path
