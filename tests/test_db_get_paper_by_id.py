import sqlite3
from pathlib import Path

import src.db as legacy_db


def test_get_paper_by_id_supports_canonical_schema_paper_id(tmp_path: Path):
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
            ("p1", "10.1000/test", "Paper One"),
        )
        conn.commit()
        conn.close()

        row = legacy_db.get_paper_by_id("p1")
        assert row is not None
        assert row["paper_id"] == "p1"
        assert row["doi"] == "10.1000/test"
    finally:
        legacy_db.DB_PATH = original_db_path


def test_get_paper_by_id_falls_back_to_doi_in_legacy_schema(tmp_path: Path):
    original_db_path = legacy_db.DB_PATH
    legacy_db.DB_PATH = tmp_path / "state.db"
    try:
        conn = sqlite3.connect(legacy_db.DB_PATH)
        conn.execute(
            """
            CREATE TABLE papers (
                doi TEXT PRIMARY KEY,
                title TEXT
            )
            """
        )
        conn.execute(
            "INSERT INTO papers (doi, title) VALUES (?, ?)",
            ("10.2000/legacy", "Legacy Paper"),
        )
        conn.commit()
        conn.close()

        row = legacy_db.get_paper_by_id("10.2000/legacy")
        assert row is not None
        assert row["doi"] == "10.2000/legacy"
        assert legacy_db.get_paper_by_id("missing") is None
    finally:
        legacy_db.DB_PATH = original_db_path
