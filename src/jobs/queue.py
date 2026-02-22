from datetime import datetime
import json
import logging
import sqlite3
import uuid
import re
from pathlib import Path
from typing import Optional, Dict, List

from src.db_utils import get_db_connection, init_db
from src.jobs.schemas import JobStatus

logger = logging.getLogger(__name__)

class JobQueue:
    def __init__(self):
        # Database connection is handled per-method to avoid thread safety issues
        pass

    def enqueue(
        self,
        paper_id: str,
        clean_reindex: bool = False,
        run_verify: bool = False,
        persona_id: str = "default",
        run_profile: str | None = None,
    ) -> str:
        """Enqueue a new job for the given paper_id."""
        job_id = str(uuid.uuid4())
        run_id = f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        params = (
            job_id,
            run_id,
            paper_id,
            persona_id,
            run_profile,
            int(bool(clean_reindex)),
            int(bool(run_verify)),
        )

        def _insert(connection):
            connection.execute("""
                INSERT INTO jobs (
                    job_id,
                    run_id,
                    paper_id,
                    persona_id,
                    run_profile,
                    clean_reindex,
                    run_verify,
                    status,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, 'queued', CURRENT_TIMESTAMP)
            """, params)

        conn = get_db_connection()
        try:
            try:
                _insert(conn)
            except sqlite3.OperationalError as exc:
                err = str(exc)
                legacy_schema_error = (
                    "no such table: jobs" in err
                    or "no such column:" in err
                    or "has no column named" in err
                )
                if not legacy_schema_error:
                    raise
                conn.close()
                init_db()
                conn = get_db_connection()
                _insert(conn)
            conn.commit()
            logger.info(f"Enqueued job {job_id} for paper {paper_id}")
            return job_id
        finally:
            conn.close()

    def get_job(self, job_id: str) -> Optional[JobStatus]:
        conn = get_db_connection()
        try:
            row = conn.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
            if row:
                # Convert row to dict, then handle datetime strings if needed by Pydantic
                d = dict(row)
                return JobStatus(**d)
            return None
        finally:
            conn.close()
            
    def list_jobs(self, limit: int = 10, status: Optional[str] = None) -> List[JobStatus]:
        conn = get_db_connection()
        try:
            query = "SELECT * FROM jobs"
            params = []
            if status:
                query += " WHERE status = ?"
                params.append(status)
            
            query += " ORDER BY created_at DESC LIMIT ?"
            params.append(limit)
            
            rows = conn.execute(query, params).fetchall()
            return [JobStatus(**dict(r)) for r in rows]
        finally:
            conn.close()

    def claim_next_job(self) -> Optional[JobStatus]:
        """
        Atomically claim the next queued job.
        Implements Max Concurrency check (Limit 1 running job).
        """
        conn = get_db_connection()
        try:
            # Transaction lock prevents parallel workers from claiming simultaneously.
            conn.execute("BEGIN IMMEDIATE")

            running_count = conn.execute(
                "SELECT COUNT(*) FROM jobs WHERE status = 'running'"
            ).fetchone()[0]
            if running_count >= 1:  # Strict Limit 1 for now
                conn.rollback()
                return None

            row = conn.execute("""
                SELECT job_id FROM jobs 
                WHERE status = 'queued' 
                ORDER BY created_at ASC 
                LIMIT 1
            """)
            row = row.fetchone()
            if not row:
                conn.rollback()
                return None

            job_id = row[0]

            updated = conn.execute("""
                UPDATE jobs 
                SET status = 'running', started_at = CURRENT_TIMESTAMP 
                WHERE job_id = ? AND status = 'queued'
            """, (job_id,))

            if updated.rowcount != 1:
                conn.rollback()
                return None

            full_row = conn.execute(
                "SELECT * FROM jobs WHERE job_id = ?",
                (job_id,),
            ).fetchone()
            conn.commit()
            if not full_row:
                return None
            return JobStatus(**dict(full_row))
        except sqlite3.OperationalError as e:
            try:
                conn.rollback()
            except Exception:
                pass
            logger.error(f"DB Error claiming job: {e}")
            return None
        finally:
            conn.close()

    def update_job(self, job_id: str, updates: Dict) -> None:
        conn = get_db_connection()
        try:
            cols = {row[1] for row in conn.execute("PRAGMA table_info(jobs)").fetchall()}
            fields = []
            params = []
            for k, v in updates.items():
                if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", str(k)):
                    continue
                if k not in cols or k == "job_id":
                    continue
                fields.append(f"{k} = ?")
                params.append(v)
            
            if not fields:
                return
                
            params.append(job_id)
            conn.execute(f"UPDATE jobs SET {', '.join(fields)} WHERE job_id = ?", params)
            conn.commit()
        finally:
            conn.close()
            
    def cancel_job(self, job_id: str):
        conn = get_db_connection()
        try:
            conn.execute("""
                UPDATE jobs 
                SET status = 'cancelled', finished_at = CURRENT_TIMESTAMP
                WHERE job_id = ? AND status IN ('queued', 'running')
            """, (job_id,))
            conn.commit()
        finally:
            conn.close()
