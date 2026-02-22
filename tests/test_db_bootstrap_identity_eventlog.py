from __future__ import annotations

import sqlite3
from pathlib import Path

import src.db_utils as db_utils


def test_init_db_adds_paper_key_and_event_tables(tmp_path: Path):
    db_path = tmp_path / "state.db"

    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE papers (
            paper_id TEXT PRIMARY KEY,
            doi TEXT,
            title TEXT NOT NULL,
            updated_at TEXT
        )
        """
    )
    conn.execute(
        "INSERT INTO papers (paper_id, doi, title, updated_at) VALUES (?, ?, ?, CURRENT_TIMESTAMP)",
        ("doi:10.1000/alpha", "10.1000/alpha", "Alpha"),
    )
    conn.commit()
    conn.close()

    old_db = db_utils.DB_PATH
    db_utils.DB_PATH = db_path
    try:
        db_utils.init_db()

        conn = sqlite3.connect(db_path)
        tables = {
            row[0]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        }
        assert "jobs" in tables
        assert "runs" in tables
        assert "job_events" in tables
        assert "user_actions" in tables

        paper_cols = {
            row[1]
            for row in conn.execute("PRAGMA table_info(papers)").fetchall()
        }
        assert "paper_key" in paper_cols

        paper_key = conn.execute(
            "SELECT paper_key FROM papers WHERE paper_id = ?",
            ("doi:10.1000/alpha",),
        ).fetchone()[0]
        assert isinstance(paper_key, str)
        assert paper_key

        runs_cols = {
            row[1]
            for row in conn.execute("PRAGMA table_info(runs)").fetchall()
        }
        assert "run_id" in runs_cols
        assert "paper_id" in runs_cols
        assert "pipeline_profile" in runs_cols
        conn.close()
    finally:
        db_utils.DB_PATH = old_db


def test_init_db_backfills_run_id_for_legacy_runs_table(tmp_path: Path):
    db_path = tmp_path / "state.db"

    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE runs (
            date TEXT PRIMARY KEY,
            status TEXT,
            processed_count INTEGER,
            last_run_at TIMESTAMP
        )
        """
    )
    conn.execute(
        "INSERT INTO runs (date, status, processed_count, last_run_at) VALUES (?, ?, ?, CURRENT_TIMESTAMP)",
        ("2026-02-22", "SUCCESS", 1),
    )
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

    old_db = db_utils.DB_PATH
    db_utils.DB_PATH = db_path
    try:
        db_utils.init_db()

        conn = sqlite3.connect(db_path)
        row = conn.execute(
            "SELECT run_id FROM runs WHERE date = ?",
            ("2026-02-22",),
        ).fetchone()
        conn.close()

        assert row is not None
        assert isinstance(row[0], str)
        assert row[0].startswith("legacy-")
    finally:
        db_utils.DB_PATH = old_db
