import src.db_utils as db_utils
import src.jobs.worker as worker_mod
from src.jobs.queue import JobQueue


def test_worker_syncs_cancelled_status_when_runner_returns_cancelled(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()
        queue = JobQueue()
        job_id = queue.enqueue(
            paper_id="paper_cancel_sync",
            clean_reindex=False,
            run_verify=False,
            persona_id="default",
        )
        claimed = queue.claim_next_job()
        assert claimed is not None
        assert claimed.status == "running"

        async def fake_run_deepread_job(*args, **kwargs):
            return {"status": "cancelled", "run_id": claimed.run_id}

        monkeypatch.setattr(worker_mod, "run_deepread_job", fake_run_deepread_job)

        worker = worker_mod.Worker()
        worker.process_job(claimed)

        done = queue.get_job(job_id)
        assert done is not None
        assert done.status == "cancelled"
        assert done.stage == "cancelled"
        assert done.finished_at is not None
    finally:
        db_utils.DB_PATH = original_db_path
