import src.db_utils as db_utils
import src.jobs.worker as worker_mod
from src.jobs.queue import JobQueue
from src.jobs.error_taxonomy import INPUT_PDF_NOT_FOUND, RUNTIME_EXCEPTION


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


def test_worker_classifies_taxonomy_when_runner_omits_it(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()
        queue = JobQueue()
        job_id = queue.enqueue(paper_id="paper_fail_sync")
        claimed = queue.claim_next_job()
        assert claimed is not None

        async def fake_run_deepread_job(*args, **kwargs):
            return {
                "status": "failed",
                "run_id": claimed.run_id,
                "error": "PDF not found for paper_fail_sync",
            }

        monkeypatch.setattr(worker_mod, "run_deepread_job", fake_run_deepread_job)

        worker = worker_mod.Worker()
        worker.process_job(claimed)

        done = queue.get_job(job_id)
        assert done is not None
        assert done.status == "failed"
        assert done.error_code == "PIPELINE_FAILED"
        assert done.error_taxonomy_code == INPUT_PDF_NOT_FOUND
    finally:
        db_utils.DB_PATH = original_db_path


def test_worker_preserves_runner_taxonomy_when_provided(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()
        queue = JobQueue()
        job_id = queue.enqueue(paper_id="paper_fail_runtime")
        claimed = queue.claim_next_job()
        assert claimed is not None

        async def fake_run_deepread_job(*args, **kwargs):
            return {
                "status": "failed",
                "run_id": claimed.run_id,
                "error": "runtime exploded",
                "error_code": "RuntimeError",
                "error_taxonomy_code": RUNTIME_EXCEPTION,
            }

        monkeypatch.setattr(worker_mod, "run_deepread_job", fake_run_deepread_job)

        worker = worker_mod.Worker()
        worker.process_job(claimed)

        done = queue.get_job(job_id)
        assert done is not None
        assert done.status == "failed"
        assert done.error_code == "RuntimeError"
        assert done.error_taxonomy_code == RUNTIME_EXCEPTION
    finally:
        db_utils.DB_PATH = original_db_path
