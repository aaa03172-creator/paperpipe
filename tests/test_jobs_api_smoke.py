from pathlib import Path

from fastapi.testclient import TestClient

import src.db_utils as db_utils
import src.jobs.worker as worker_mod
from src.jobs.queue import JobQueue
from backend import main as api_main


def test_jobs_deepread_enqueue_worker_smoke(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()
        client = TestClient(api_main.app)

        # 1) Enqueue from API with extended fields.
        resp = client.post(
            "/jobs/deepread",
            json={
                "paper_id": "paper_smoke_001",
                "clean_reindex": False,
                "run_verify": True,
                "persona_id": "smoke-persona",
            },
        )
        assert resp.status_code == 200
        payload = resp.json()
        job_id = payload["job_id"]
        assert payload["status"] == "queued"

        queued = client.get(f"/jobs/{job_id}")
        assert queued.status_code == 200
        queued_data = queued.json()
        assert queued_data["status"] == "queued"
        assert queued_data["persona_id"] == "smoke-persona"
        assert queued_data["run_verify"] == 1

        # 2) Worker claims job and runs pipeline (patched to smoke implementation).
        queue = JobQueue()
        claimed = queue.claim_next_job()
        assert claimed is not None
        assert claimed.job_id == job_id
        assert claimed.status == "running"

        async def fake_run_deepread_job(
            job_id: str,
            paper_id: str,
            persona_id: str = "default",
            run_verify: bool = False,
            run_id: str = None,
            progress_callback=None,
            cancel_check=None,
        ):
            if progress_callback:
                await progress_callback(
                    {
                        "job_id": job_id,
                        "run_id": run_id,
                        "stage": "ingest",
                        "progress": 25,
                        "message": "smoke ingest",
                        "level": "INFO",
                        "timestamp": "2026-02-19T00:00:00Z",
                    }
                )
                await progress_callback(
                    {
                        "job_id": job_id,
                        "run_id": run_id,
                        "stage": "read",
                        "progress": 75,
                        "message": "smoke read",
                        "level": "INFO",
                        "timestamp": "2026-02-19T00:00:01Z",
                    }
                )
            return {
                "status": "succeeded",
                "run_id": run_id,
                "artifact_dir": f"storage/artifacts/{paper_id}/{run_id}",
            }

        monkeypatch.setattr(worker_mod, "run_deepread_job", fake_run_deepread_job)
        worker = worker_mod.Worker()
        worker.process_job(claimed)

        # 3) Validate API status/progress/artifact surface after worker execution.
        done = client.get(f"/jobs/{job_id}")
        assert done.status_code == 200
        done_data = done.json()

        assert done_data["status"] == "completed"
        assert done_data["progress"] == 100
        assert done_data["stage"] == "completed"
        assert done_data["artifact_dir"] is not None
        assert done_data["log_path"] is not None
        assert Path(done_data["log_path"]).exists()
    finally:
        db_utils.DB_PATH = original_db_path
