from datetime import datetime
import json
import logging
import sqlite3
import uuid
from pathlib import Path
from typing import Optional, Dict, List

from src.db_utils import get_db_connection
from src.jobs.schemas import JobStatus

logger = logging.getLogger(__name__)

class JobQueue:
    def __init__(self):
        # Keep queue stateless; each method manages its own DB connection lifecycle.
        pass

    def enqueue(self, paper_id: str, clean_reindex: bool = False) -> str:
        """Enqueue a new job for the given paper_id."""
        job_id = str(uuid.uuid4())
        run_id = f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        conn = get_db_connection()
        try:
            conn.execute("""
                INSERT INTO jobs (job_id, run_id, paper_id, status, created_at)
                VALUES (?, ?, ?, 'queued', CURRENT_TIMESTAMP)
            """, (job_id, run_id, paper_id))
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
        cursor = conn.cursor()
        try:
            # 1. Check running jobs count
            cursor.execute("SELECT COUNT(*) FROM jobs WHERE status = 'running'")
            running_count = cursor.fetchone()[0]
            if running_count >= 1: # Strict Limit 1 for now
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
