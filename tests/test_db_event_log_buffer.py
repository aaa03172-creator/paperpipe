from __future__ import annotations

import sqlite3
from pathlib import Path

import src.db_utils as db_utils
from src.db_event_log import (
    flush_event_buffer,
    log_event_buffered,
    set_event_buffer_limit,
)


def _create_papers_table(db_path: Path) -> None:
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE papers (
            paper_id TEXT PRIMARY KEY,
            title TEXT NOT NULL
        )
        """
    )
    conn.commit()
    conn.close()


def test_buffered_event_logging_flushes_on_demand(tmp_path: Path):
    db_path = tmp_path / "state.db"
    _create_papers_table(db_path)

    old_db = db_utils.DB_PATH
    db_utils.DB_PATH = db_path
    old_limit = 25
    try:
        db_utils.init_db()
        set_event_buffer_limit(100)

        event_id = log_event_buffered("job-buffer-1", "info", "step_progress", "hello")

        conn = sqlite3.connect(db_path)
        before = conn.execute("SELECT COUNT(*) FROM job_events").fetchone()[0]
        conn.close()
        assert before == 0

        flushed = flush_event_buffer()
        assert flushed >= 1

        conn = sqlite3.connect(db_path)
        row = conn.execute("SELECT event_id, event_type FROM job_events WHERE event_id = ?", (event_id,)).fetchone()
        conn.close()
        assert row is not None
        assert row[1] == "step_progress"
    finally:
        set_event_buffer_limit(old_limit)
        db_utils.DB_PATH = old_db


def test_buffered_event_logging_auto_flushes_at_limit(tmp_path: Path):
    db_path = tmp_path / "state.db"
    _create_papers_table(db_path)

    old_db = db_utils.DB_PATH
    db_utils.DB_PATH = db_path
    old_limit = 25
    try:
        db_utils.init_db()
        set_event_buffer_limit(2)

        log_event_buffered("job-buffer-2", "info", "step_start", "a")
        log_event_buffered("job-buffer-2", "info", "step_end", "b")

        conn = sqlite3.connect(db_path)
        count = conn.execute("SELECT COUNT(*) FROM job_events WHERE job_id = ?", ("job-buffer-2",)).fetchone()[0]
        conn.close()
        assert count == 2
    finally:
        set_event_buffer_limit(old_limit)
        db_utils.DB_PATH = old_db
