import src.db_utils as db_utils
from src.jobs.queue import JobQueue


def test_claim_next_job_claims_oldest_queued(tmp_path):
    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()
        queue = JobQueue()
        first = queue.enqueue("paper_oldest")
        second = queue.enqueue("paper_newer")

        claimed = queue.claim_next_job()
        assert claimed is not None
        assert claimed.job_id == first
        assert claimed.paper_id == "paper_oldest"
        assert claimed.status == "running"

        remaining = queue.get_job(second)
        assert remaining is not None
        assert remaining.status == "queued"
    finally:
        db_utils.DB_PATH = original_db_path


def test_claim_next_job_respects_single_running_limit(tmp_path):
    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()
        queue = JobQueue()
        queue.enqueue("paper_one")
        queue.enqueue("paper_two")

        first = queue.claim_next_job()
        assert first is not None
        assert first.status == "running"

        blocked = queue.claim_next_job()
        assert blocked is None
    finally:
        db_utils.DB_PATH = original_db_path


def test_claim_next_job_skips_non_queued_jobs(tmp_path):
    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()
        queue = JobQueue()
        queued_id = queue.enqueue("paper_queued")
        cancelled_id = queue.enqueue("paper_cancelled")
        queue.cancel_job(cancelled_id)

        claimed = queue.claim_next_job()
        assert claimed is not None
        assert claimed.job_id == queued_id
        assert claimed.paper_id == "paper_queued"
    finally:
        db_utils.DB_PATH = original_db_path
