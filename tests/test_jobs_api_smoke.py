from pathlib import Path
import json

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
        assert queued_data["bootstrap_meta_path"] is None
        assert queued_data["similar_feedback_count"] is None
        assert queued_data["persona_applied"] is None
        assert queued_data["artifact_document_written"] is None
        assert queued_data["artifact_index_written"] is None
        assert queued_data["artifact_claimset_written"] is None
        assert queued_data["artifact_stats_written"] is None
        assert queued_data["claimset_readiness"] is None
        assert queued_data["claimset_ready"] is None
        assert queued_data["claimset_claim_count"] is None
        assert queued_data["claimset_readiness_reason"] is None
        assert queued_data["claimset_readiness_badge"] is None
        assert queued_data["claimset_ops_action"] is None
        assert queued_data["claimset_ops_alert"] is None
        assert queued_data["claimset_ops_note"] is None

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
        assert done_data["bootstrap_meta_path"] is not None
        assert done_data["bootstrap_meta_path"].endswith("bootstrap_meta.json")
        assert done_data["similar_feedback_count"] is None
        assert done_data["persona_applied"] is None
        assert done_data["artifact_document_written"] is None
        assert done_data["artifact_index_written"] is None
        assert done_data["artifact_claimset_written"] is None
        assert done_data["artifact_stats_written"] is None
        assert done_data["claimset_readiness"] is None
        assert done_data["claimset_ready"] is None
        assert done_data["claimset_claim_count"] is None
        assert done_data["claimset_readiness_reason"] is None
        assert done_data["claimset_readiness_badge"] is None
        assert done_data["claimset_ops_action"] is None
        assert done_data["claimset_ops_alert"] is None
        assert done_data["claimset_ops_note"] is None
        assert Path(done_data["log_path"]).exists()

        # bootstrap meta file is not generated in this fake runner path.
        meta_resp = client.get(f"/jobs/{job_id}/bootstrap-meta")
        assert meta_resp.status_code == 404
    finally:
        db_utils.DB_PATH = original_db_path


def test_jobs_bootstrap_meta_endpoint_returns_file_content(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()
        client = TestClient(api_main.app)
        queue = JobQueue()
        job_id = queue.enqueue(paper_id="paper_boot_meta")

        artifact_dir = tmp_path / "storage" / "artifacts" / "paper_boot_meta" / "run_1"
        artifact_dir.mkdir(parents=True, exist_ok=True)
        meta = {"paper_id": "paper_boot_meta", "run_id": "run_1", "persona_applied": True}
        meta["similar_feedback_count"] = 2
        meta["artifact_document_written"] = True
        meta["artifact_index_written"] = True
        meta["artifact_claimset_written"] = True
        meta["artifact_stats_written"] = False
        meta["claimset_readiness"] = "ready"
        meta["claimset_ready"] = True
        meta["claimset_claim_count"] = 3
        meta["claimset_readiness_reason"] = "claims_present"
        meta["claimset_readiness_badge"] = "READY"
        meta["claimset_ops_action"] = "none"
        meta["claimset_ops_alert"] = False
        meta["claimset_ops_note"] = "ready"
        (artifact_dir / "bootstrap_meta.json").write_text(json.dumps(meta), encoding="utf-8")

        queue.update_job(
            job_id,
            {
                "status": "completed",
                "artifact_dir": str(artifact_dir),
                "progress": 100,
                "stage": "completed",
            },
        )

        detail = client.get(f"/jobs/{job_id}")
        assert detail.status_code == 200
        payload = detail.json()
        assert payload["bootstrap_meta_path"] == str(artifact_dir / "bootstrap_meta.json")
        assert payload["similar_feedback_count"] == 2
        assert payload["persona_applied"] is True
        assert payload["artifact_document_written"] is True
        assert payload["artifact_index_written"] is True
        assert payload["artifact_claimset_written"] is True
        assert payload["artifact_stats_written"] is False
        assert payload["claimset_readiness"] == "ready"
        assert payload["claimset_ready"] is True
        assert payload["claimset_claim_count"] == 3
        assert payload["claimset_readiness_reason"] == "claims_present"
        assert payload["claimset_readiness_badge"] == "READY"
        assert payload["claimset_ops_action"] == "none"
        assert payload["claimset_ops_alert"] is False
        assert payload["claimset_ops_note"] == "ready"

        meta_resp = client.get(f"/jobs/{job_id}/bootstrap-meta")
        assert meta_resp.status_code == 200
        assert meta_resp.json()["paper_id"] == "paper_boot_meta"
        assert meta_resp.json()["persona_applied"] is True
        assert meta_resp.json()["artifact_document_written"] is True
        assert meta_resp.json()["claimset_readiness"] == "ready"
        assert meta_resp.json()["claimset_ready"] is True
        assert meta_resp.json()["claimset_readiness_badge"] == "READY"
        assert meta_resp.json()["claimset_ops_action"] == "none"
        assert meta_resp.json()["claimset_ops_alert"] is False
    finally:
        db_utils.DB_PATH = original_db_path
