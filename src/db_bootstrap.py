from __future__ import annotations

import sqlite3


def ensure_jobs_table(conn: sqlite3.Connection) -> None:
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS jobs (
            job_id TEXT PRIMARY KEY,
            run_id TEXT,
            paper_id TEXT,
            persona_id TEXT DEFAULT 'default',
            run_verify INTEGER DEFAULT 0,
            status TEXT DEFAULT 'queued',
            progress INTEGER DEFAULT 0,
            stage TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            started_at TIMESTAMP,
            finished_at TIMESTAMP,
            artifact_dir TEXT,
            log_path TEXT,
            error_code TEXT,
            error_message TEXT
        )
        """
    )

    cursor.execute("PRAGMA table_info(jobs)")
    existing_cols = {row[1] for row in cursor.fetchall()}
    if "persona_id" not in existing_cols:
        cursor.execute("ALTER TABLE jobs ADD COLUMN persona_id TEXT DEFAULT 'default'")
    if "run_verify" not in existing_cols:
        cursor.execute("ALTER TABLE jobs ADD COLUMN run_verify INTEGER DEFAULT 0")


def ensure_review_queue_open_unique_index(conn: sqlite3.Connection) -> None:
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            UPDATE review_queue
            SET resolved_at = CURRENT_TIMESTAMP,
                resolution = COALESCE(resolution, 'AUTO_DEDUP_DUPLICATE_OPEN'),
                owner = COALESCE(owner, 'SYSTEM')
            WHERE resolved_at IS NULL
              AND EXISTS (
                SELECT 1
                FROM review_queue rq2
                WHERE rq2.paper_id = review_queue.paper_id
                  AND rq2.decision = review_queue.decision
                  AND rq2.resolved_at IS NULL
                  AND rq2.id < review_queue.id
              )
            """
        )
        cursor.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS idx_review_queue_open_unique
            ON review_queue (paper_id, decision)
            WHERE resolved_at IS NULL
            """
        )
    except sqlite3.OperationalError:
        pass
