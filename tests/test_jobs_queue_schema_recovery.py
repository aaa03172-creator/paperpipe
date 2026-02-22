import sqlite3

import src.db_utils as db_utils
from src.jobs.queue import JobQueue


def test_enqueue_recovers_from_legacy_jobs_schema_missing_columns(tmp_path):
    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        conn = sqlite3.connect(db_utils.DB_PATH)
        conn.execute(
            """
            CREATE TABLE jobs (
                job_id TEXT PRIMARY KEY
            )
            """
        )
        conn.commit()
        conn.close()

        queue = JobQueue()
        job_id = queue.enqueue(paper_id="paper_legacy_schema")
        job = queue.get_job(job_id)
        assert job is not None
        assert job.paper_id == "paper_legacy_schema"
        assert job.persona_id == "default"
        assert job.clean_reindex == 0
        assert job.run_verify == 0
        assert job.status == "queued"
        assert job.progress == 0
        assert job.created_at is not None
    finally:
        db_utils.DB_PATH = original_db_path
