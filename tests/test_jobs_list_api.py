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


def test_jobs_list_endpoint_prefers_newer_queued_job_over_older_iso_completed_fixture(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()
        client = TestClient(api_main.app)
        queue = JobQueue()

        queued_job = queue.enqueue(paper_id="paper_jobs_order_001")
        conn = db_utils.get_db_connection()
        conn.execute(
            "UPDATE jobs SET created_at = ? WHERE job_id = ?",
            ("2026-04-01 09:05:18", queued_job),
        )
        conn.execute(
            """
            INSERT INTO jobs (
                job_id, run_id, paper_id, persona_id, status, progress, stage,
                created_at, started_at, finished_at, artifact_dir
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "job-e2e-fixture-completed",
                "run_e2e_fixture_older",
                "paper_jobs_order_001",
                "default",
                "completed",
                100,
                "completed",
                "2026-04-01T09:05:00",
                "2026-04-01T09:05:05",
                "2026-04-01T09:05:07",
                "./storage/artifacts/paper_jobs_order_001/run_e2e_fixture_older",
            ),
        )
        conn.commit()
        conn.close()

        response = client.get("/jobs", params={"paper_id": "paper_jobs_order_001"})
        assert response.status_code == 200
        payload = response.json()
        assert len(payload) == 2
        assert payload[0]["job_id"] == queued_job
        assert payload[0]["status"] == "queued"
        assert payload[1]["job_id"] == "job-e2e-fixture-completed"
        assert payload[1]["status"] == "completed"
    finally:
        db_utils.DB_PATH = original_db_path
