import sqlite3
from pathlib import Path

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

        legacy_db.update_paper_status("10.1000/abc", "Reading")
        assert legacy_db.get_paper_status("10.1000/abc") == "Reading"
        assert legacy_db.is_paper_processed("10.1000/abc") is True
    finally:
        legacy_db.DB_PATH = original_db_path


def test_legacy_save_paper_state_uses_canonical_doi_handling(tmp_path: Path):
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
                processed_date TEXT,
                updated_at TIMESTAMP
            )
            """
        )
        conn.commit()
        conn.close()

        legacy_db.save_paper_state("zotero:smith2026", "Zotero Paper", "zotero", "2026-05-24")
        legacy_db.save_paper_state("https://doi.org/10.1000/ABC", "DOI Paper", "pubmed", "2026-05-24")

        conn = sqlite3.connect(legacy_db.DB_PATH)
        rows = conn.execute("SELECT paper_id, doi FROM papers ORDER BY paper_id").fetchall()
        conn.close()

        assert rows == [
            ("https://doi.org/10.1000/ABC", "10.1000/abc"),
            ("zotero:smith2026", None),
        ]
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


def test_record_run_status_and_check_run_exists_work_with_runs_table(tmp_path: Path):
    original_db_path = legacy_db.DB_PATH
    legacy_db.DB_PATH = tmp_path / "state.db"
    try:
        legacy_db.record_run_status("2026-04-20", "SUCCESS", processed_count=3, last_run_at="2026-04-20 10:00:00")

        conn = sqlite3.connect(legacy_db.DB_PATH)
        row = conn.execute(
            "SELECT date, status, processed_count, last_run_at FROM runs WHERE date = ?",
            ("2026-04-20",),
        ).fetchone()
        conn.close()

        assert row == ("2026-04-20", "SUCCESS", 3, "2026-04-20 10:00:00")
        assert legacy_db.check_run_exists("2026-04-20") is True
    finally:
        legacy_db.DB_PATH = original_db_path


def test_check_run_exists_falls_back_to_execution_runs(tmp_path: Path):
    original_db_path = legacy_db.DB_PATH
    legacy_db.DB_PATH = tmp_path / "state.db"
    try:
        conn = sqlite3.connect(legacy_db.DB_PATH)
        conn.execute(
            """
            CREATE TABLE execution_runs (
                run_id TEXT PRIMARY KEY,
                paper_id TEXT,
                trigger_source TEXT,
                pipeline_profile TEXT,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                started_at TEXT,
                finished_at TEXT,
                params_json TEXT,
                metrics_json TEXT
            )
            """
        )
        conn.execute(
            """
            INSERT INTO execution_runs (
                run_id, paper_id, trigger_source, pipeline_profile, status, created_at, started_at, finished_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "run_20260420_100000",
                None,
                "cli_run",
                "legacy_daily_slots",
                "completed",
                "2026-04-20T01:00:00+00:00",
                "2026-04-20T01:00:00+00:00",
                "2026-04-20T01:05:00+00:00",
            ),
        )
        conn.commit()
        conn.close()

        assert legacy_db.check_run_exists("2026-04-20") is True
    finally:
        legacy_db.DB_PATH = original_db_path
