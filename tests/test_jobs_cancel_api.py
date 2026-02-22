from fastapi.testclient import TestClient

import src.db_utils as db_utils
from src.jobs.queue import JobQueue
from backend import main as api_main


def test_cancel_endpoint_marks_queued_job_cancelled(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()
        with TestClient(api_main.app) as client:
            enqueue = client.post(
                "/jobs/deepread",
                json={
                    "paper_id": "paper_cancel_queued",
                    "clean_reindex": False,
                    "run_verify": False,
                    "persona_id": "default",
                },
            )
            assert enqueue.status_code == 200
            job_id = enqueue.json()["job_id"]

            cancel = client.post(f"/jobs/{job_id}/cancel")
            assert cancel.status_code == 200
            assert cancel.json()["status"] == "cancelled"

            detail = client.get(f"/jobs/{job_id}")
            assert detail.status_code == 200
            payload = detail.json()
            assert payload["status"] == "cancelled"
            assert payload["finished_at"] is not None
    finally:
        db_utils.DB_PATH = original_db_path


def test_cancel_endpoint_releases_running_slot_for_next_job(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()
        queue = JobQueue()
        first_id = queue.enqueue(paper_id="paper_running_to_cancel")
        first_claim = queue.claim_next_job()
        assert first_claim is not None
        assert first_claim.job_id == first_id
        assert first_claim.status == "running"

        with TestClient(api_main.app) as client:
            cancel = client.post(f"/jobs/{first_id}/cancel")
            assert cancel.status_code == 200
            assert cancel.json()["status"] == "cancelled"

            first_detail = client.get(f"/jobs/{first_id}")
            assert first_detail.status_code == 200
            assert first_detail.json()["status"] == "cancelled"

        second_id = queue.enqueue(paper_id="paper_after_cancel")
        second_claim = queue.claim_next_job()
        assert second_claim is not None
        assert second_claim.job_id == second_id
        assert second_claim.status == "running"
    finally:
        db_utils.DB_PATH = original_db_path
