from pathlib import Path

import src.db_utils as db_utils
from src.jobs.queue import JobQueue


def test_job_queue_update_ignores_unknown_and_invalid_keys(tmp_path):
    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()
        queue = JobQueue()
        job_id = queue.enqueue(paper_id="paper_safe")

        queue.update_job(
            job_id,
            {
                "status": "running",
                "progress": 42,
                "bad key": "x",
                "status = 'failed' --": "x",
                "nonexistent_col": "x",
            },
        )

        job = queue.get_job(job_id)
        assert job is not None
        assert job.status == "running"
        assert job.progress == 42
    finally:
        db_utils.DB_PATH = original_db_path


def test_job_queue_update_no_valid_fields_is_noop(tmp_path):
    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()
        queue = JobQueue()
        job_id = queue.enqueue(paper_id="paper_noop")

        before = queue.get_job(job_id)
        assert before is not None

        queue.update_job(job_id, {"bad key": "x", "unknown": "y"})

        after = queue.get_job(job_id)
        assert after is not None
        assert after.status == before.status
        assert after.progress == before.progress
    finally:
        db_utils.DB_PATH = original_db_path
