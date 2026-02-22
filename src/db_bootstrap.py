from __future__ import annotations

from datetime import datetime, timezone
import sqlite3

from src.core.paper_identity import make_paper_key


def ensure_jobs_table(conn: sqlite3.Connection) -> None:
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS jobs (
            job_id TEXT PRIMARY KEY,
            run_id TEXT,
            paper_id TEXT,
            persona_id TEXT DEFAULT 'default',
            run_profile TEXT,
            clean_reindex INTEGER DEFAULT 0,
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
    backfill_columns = {
        "run_id": "TEXT",
        "paper_id": "TEXT",
        "persona_id": "TEXT DEFAULT 'default'",
        "run_profile": "TEXT",
        "clean_reindex": "INTEGER DEFAULT 0",
        "run_verify": "INTEGER DEFAULT 0",
        "status": "TEXT DEFAULT 'queued'",
        "progress": "INTEGER DEFAULT 0",
        "stage": "TEXT",
        "created_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
        "started_at": "TIMESTAMP",
        "finished_at": "TIMESTAMP",
        "artifact_dir": "TEXT",
        "log_path": "TEXT",
        "error_code": "TEXT",
        "error_message": "TEXT",
        "job_type": "TEXT",
        "params_json": "TEXT",
        "result_ref": "TEXT",
        "error_taxonomy_code": "TEXT",
        "error_detail": "TEXT",
        "metrics_json": "TEXT",
    }
    for col, ddl in backfill_columns.items():
        if col in existing_cols:
            continue
        cursor.execute(f"ALTER TABLE jobs ADD COLUMN {col} {ddl}")

    cursor.execute("CREATE INDEX IF NOT EXISTS idx_jobs_run ON jobs(run_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_jobs_paper ON jobs(paper_id)")


def ensure_runs_table(conn: sqlite3.Connection) -> None:
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS runs (
            run_id TEXT PRIMARY KEY,
            date TEXT,
            status TEXT,
            processed_count INTEGER,
            last_run_at TIMESTAMP,
            paper_id TEXT,
            trigger_source TEXT,
            pipeline_profile TEXT,
            created_at TEXT,
            finished_at TEXT,
            params_json TEXT,
            metrics_json TEXT
        )
        """
    )

    cursor.execute("PRAGMA table_info(runs)")
    existing_cols = {row[1] for row in cursor.fetchall()}
    backfill_columns = {
        "run_id": "TEXT",
        "date": "TEXT",
        "status": "TEXT",
        "processed_count": "INTEGER",
        "last_run_at": "TIMESTAMP",
        "paper_id": "TEXT",
        "trigger_source": "TEXT",
        "pipeline_profile": "TEXT",
        "created_at": "TEXT",
        "finished_at": "TEXT",
        "params_json": "TEXT",
        "metrics_json": "TEXT",
    }
    for col, ddl in backfill_columns.items():
        if col in existing_cols:
            continue
        cursor.execute(f"ALTER TABLE runs ADD COLUMN {col} {ddl}")

    # Legacy compatibility: ensure rows that only had legacy date PK get a deterministic run_id.
    now_iso = datetime.now(timezone.utc).isoformat()
    rows = cursor.execute(
        "SELECT rowid, date, run_id FROM runs WHERE run_id IS NULL OR TRIM(run_id) = ''"
    ).fetchall()
    for row in rows:
        rowid, date_text, _ = row
        seed = str(date_text or f"legacy-{rowid}")
        run_id = f"legacy-{make_paper_key(seed)}"
        cursor.execute(
            "UPDATE runs SET run_id = ?, created_at = COALESCE(created_at, ?) WHERE rowid = ?",
            (run_id, now_iso, rowid),
        )

    cursor.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_runs_run_id_unique ON runs(run_id) WHERE run_id IS NOT NULL"
    )
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_runs_paper ON runs(paper_id)")


def ensure_event_log_tables(conn: sqlite3.Connection) -> None:
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS job_events (
            event_id TEXT PRIMARY KEY,
            job_id TEXT NOT NULL,
            ts TEXT NOT NULL,
            level TEXT NOT NULL,
            event_type TEXT NOT NULL,
            message TEXT,
            payload_json TEXT
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS user_actions (
            action_id TEXT PRIMARY KEY,
            ts TEXT NOT NULL,
            paper_id TEXT,
            action_type TEXT NOT NULL,
            source TEXT NOT NULL,
            payload_json TEXT
        )
        """
    )
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_job ON job_events(job_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_actions_paper ON user_actions(paper_id)")


def ensure_paper_key_column(conn: sqlite3.Connection) -> None:
    cursor = conn.cursor()
    try:
        cursor.execute("PRAGMA table_info(papers)")
        rows = cursor.fetchall()
    except sqlite3.OperationalError:
        return

    if not rows:
        return

    columns = {row[1] for row in rows}
    if "paper_key" not in columns:
        cursor.execute("ALTER TABLE papers ADD COLUMN paper_key TEXT")

    papers = cursor.execute(
        "SELECT paper_id, paper_key FROM papers WHERE paper_id IS NOT NULL"
    ).fetchall()
    for paper_id, paper_key in papers:
        if paper_key and str(paper_key).strip():
            continue
        cursor.execute(
            "UPDATE papers SET paper_key = ? WHERE paper_id = ?",
            (make_paper_key(str(paper_id)), str(paper_id)),
        )

    cursor.execute("CREATE INDEX IF NOT EXISTS idx_papers_paper_key ON papers(paper_key)")


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
