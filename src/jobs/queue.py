from datetime import datetime
import json
import logging
import os
import sqlite3
import uuid
from pathlib import Path
from typing import Optional, Dict, List

from src.db_utils import get_db_connection
from src.jobs.schemas import JobStatus

logger = logging.getLogger(__name__)


class DuplicateOpenJobError(Exception):
    def __init__(self, *, paper_id: str, job_id: str, run_id: str | None, status: str):
        super().__init__(f"Open job already exists for paper_id={paper_id}: {job_id} ({status})")
        self.paper_id = paper_id
        self.job_id = job_id
        self.run_id = run_id
        self.status = status


class QueueBackpressureError(Exception):
    def __init__(self, *, queued_count: int, limit: int):
        super().__init__(f"Queued jobs limit reached: {queued_count}/{limit}")
        self.queued_count = queued_count
        self.limit = limit


def _resolve_max_queued_jobs() -> int:
    raw = (os.getenv("LATTICE_MAX_QUEUED_JOBS") or os.getenv("PAPERPIPE_MAX_QUEUED_JOBS") or "").strip()
    if not raw:
        return 0
    try:
        value = int(raw)
    except ValueError:
        return 0
    return max(value, 0)


def _resolve_max_concurrent_jobs() -> int:
    raw = (os.getenv("LATTICE_MAX_CONCURRENT_JOBS") or os.getenv("PAPERPIPE_MAX_CONCURRENT_JOBS") or "").strip()
    if not raw:
        return 1
    try:
        value = int(raw)
    except ValueError:
        return 1
    return max(value, 1)


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
    ) -> str:
        """Enqueue a new job for the given paper_id."""
        job_id = str(uuid.uuid4())
        run_id = f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            # Serialize enqueue writes to enforce "one open job per paper_id" reliably.
            cursor.execute("BEGIN IMMEDIATE")
            existing = cursor.execute(
                """
                SELECT job_id, run_id, status
                FROM jobs
                WHERE paper_id = ? AND status IN ('queued', 'running')
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (paper_id,),
            ).fetchone()
            if existing:
                conn.rollback()
                raise DuplicateOpenJobError(
                    paper_id=paper_id,
                    job_id=existing["job_id"],
                    run_id=existing["run_id"],
                    status=existing["status"],
                )

            max_queued_jobs = _resolve_max_queued_jobs()
            if max_queued_jobs > 0:
                queued_count = cursor.execute(
                    "SELECT COUNT(*) AS total FROM jobs WHERE status = 'queued'"
                ).fetchone()["total"]
                if queued_count >= max_queued_jobs:
                    conn.rollback()
                    raise QueueBackpressureError(
                        queued_count=queued_count,
                        limit=max_queued_jobs,
                    )

            cursor.execute("""
                INSERT INTO jobs (job_id, run_id, paper_id, persona_id, run_verify, clean_reindex, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, 'queued', CURRENT_TIMESTAMP)
            """, (job_id, run_id, paper_id, persona_id, int(bool(run_verify)), int(bool(clean_reindex))))
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
        Implements max concurrency guard for running jobs.
        """
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            # 1. Check running jobs count
            cursor.execute("SELECT COUNT(*) FROM jobs WHERE status = 'running'")
            running_count = cursor.fetchone()[0]
            max_concurrent_jobs = _resolve_max_concurrent_jobs()
            if running_count >= max_concurrent_jobs:
                return None
            
            # 2. Find oldest queued job
            cursor.execute("""
                SELECT job_id FROM jobs 
                WHERE status = 'queued' 
                ORDER BY created_at ASC 
                LIMIT 1
            """)
            row = cursor.fetchone()
            if not row:
                return None
                
            job_id = row[0]
            
            # 3. Update to running
            cursor.execute("""
                UPDATE jobs 
                SET status = 'running', started_at = CURRENT_TIMESTAMP 
                WHERE job_id = ?
            """, (job_id,))
            conn.commit()
            
            # 4. Return full object
            return self.get_job(job_id)
            
        except sqlite3.OperationalError as e:
            logger.error(f"DB Error claiming job: {e}")
            return None
        finally:
            conn.close()

    def update_job(self, job_id: str, updates: Dict) -> None:
        conn = get_db_connection()
        try:
            fields = []
            params = []
            for k, v in updates.items():
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
