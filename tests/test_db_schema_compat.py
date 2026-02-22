import sqlite3
from pathlib import Path

import pytest

import src.db as legacy_db


def test_save_paper_state_and_status_work_with_canonical_schema(tmp_path: Path):
    original_db_path = legacy_db.DB_PATH
    legacy_db.DB_PATH = tmp_path / "state.db"
    try:
        conn = sqlite3.connect(legacy_db.DB_PATH)
        conn.execute(
            """
            CREATE TABLE papers (
                paper_id TEXT PRIMARY KEY,
                doi TEXT,
                title TEXT,
                source TEXT,
                status TEXT,
                reading_status TEXT,
                updated_at TIMESTAMP,
                processed_at TIMESTAMP
            )
            """
        )
        conn.commit()
        conn.close()

        legacy_db.save_paper_state("10.1000/abc", "Canonical Paper", "pubmed", "2026-02-21")

        conn = sqlite3.connect(legacy_db.DB_PATH)
        row = conn.execute(
            "SELECT paper_id, doi, title, source FROM papers WHERE paper_id = ?",
            ("10.1000/abc",),
        ).fetchone()
        conn.close()

        assert row is not None
        assert row[0] == "10.1000/abc"
        assert row[1] == "10.1000/abc"
        assert row[2] == "Canonical Paper"
        assert row[3] == "pubmed"

        with pytest.warns(DeprecationWarning):
            legacy_db.update_paper_status("10.1000/abc", "Reading")
        assert legacy_db.get_paper_status("10.1000/abc") == "Reading"
        assert legacy_db.is_paper_processed("10.1000/abc") is True
    finally:
        legacy_db.DB_PATH = original_db_path


def test_update_reading_status_aliases_are_consistent(tmp_path: Path):
    original_db_path = legacy_db.DB_PATH
    legacy_db.DB_PATH = tmp_path / "state.db"
    try:
        conn = sqlite3.connect(legacy_db.DB_PATH)
        conn.execute(
            """
            CREATE TABLE papers (
                paper_id TEXT PRIMARY KEY,
                doi TEXT,
                title TEXT,
                reading_status TEXT,
                updated_at TIMESTAMP
            )
            """
        )
        conn.execute(
            "INSERT INTO papers (paper_id, doi, title, reading_status) VALUES (?, ?, ?, ?)",
            ("10.1000/alias", "10.1000/alias", "Alias Test", "Inbox"),
        )
        conn.commit()
        conn.close()

        legacy_db.update_reading_status("10.1000/alias", "Reading")
        assert legacy_db.get_paper_status("10.1000/alias") == "Reading"
    finally:
        legacy_db.DB_PATH = original_db_path


def test_mark_as_retracted_works_without_existing_column(tmp_path: Path):
    original_db_path = legacy_db.DB_PATH
    legacy_db.DB_PATH = tmp_path / "state.db"
    try:
        conn = sqlite3.connect(legacy_db.DB_PATH)
        conn.execute(
            """
            CREATE TABLE papers (
                paper_id TEXT PRIMARY KEY,
                doi TEXT,
                title TEXT
            )
            """
        )
        conn.execute(
            "INSERT INTO papers (paper_id, doi, title) VALUES (?, ?, ?)",
            ("p1", "10.2000/x", "Retractable"),
        )
        conn.commit()
        conn.close()

        legacy_db.mark_as_retracted("10.2000/x")

        conn = sqlite3.connect(legacy_db.DB_PATH)
        value = conn.execute(
            "SELECT is_retracted FROM papers WHERE doi = ?",
            ("10.2000/x",),
        ).fetchone()[0]
        conn.close()
        assert value == 1
    finally:
        legacy_db.DB_PATH = original_db_path


def test_init_db_bootstraps_canonical_tables(tmp_path: Path):
    original_db_path = legacy_db.DB_PATH
    legacy_db.DB_PATH = tmp_path / "state.db"
    try:
        legacy_db.init_db()
        conn = sqlite3.connect(legacy_db.DB_PATH)
        tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        conn.close()
        assert "papers" in tables
        assert "review_queue" in tables
        assert "jobs" in tables
        assert "run_stats" in tables
        assert "embeddings" in tables
    finally:
        legacy_db.DB_PATH = original_db_path


def test_check_run_exists_returns_false_when_runs_table_missing(tmp_path: Path):
    original_db_path = legacy_db.DB_PATH
    legacy_db.DB_PATH = tmp_path / "state.db"
    try:
        conn = sqlite3.connect(legacy_db.DB_PATH)
        conn.execute(
            """
            CREATE TABLE papers (
                paper_id TEXT PRIMARY KEY
            )
            """
        )
        conn.commit()
        conn.close()

        assert legacy_db.check_run_exists("2026-02-22") is False
    finally:
        legacy_db.DB_PATH = original_db_path
