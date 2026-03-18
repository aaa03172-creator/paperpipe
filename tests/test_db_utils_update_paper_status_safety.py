import sqlite3
from pathlib import Path

import pytest

import src.db_utils as db_utils


def test_update_paper_status_rejects_unknown_update_columns(tmp_path: Path):
    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        conn = sqlite3.connect(db_utils.DB_PATH)
        conn.execute(
            """
            CREATE TABLE papers (
                paper_id TEXT PRIMARY KEY,
                status TEXT,
                feedback_json TEXT,
                updated_at TIMESTAMP
            )
            """
        )
        conn.execute(
            "INSERT INTO papers (paper_id, status, feedback_json) VALUES (?, ?, ?)",
            ("paper-1", "NEW", "{}"),
        )
        conn.commit()
        conn.close()

        with pytest.raises(ValueError, match="Unsupported paper update columns: not_a_real_column"):
            db_utils.update_paper_status(
                "paper-1",
                "FAILED",
                {"not_a_real_column": "boom"},
            )

        conn = sqlite3.connect(db_utils.DB_PATH)
        row = conn.execute(
            "SELECT status, feedback_json FROM papers WHERE paper_id = ?",
            ("paper-1",),
        ).fetchone()
        conn.close()

        assert row == ("NEW", "{}")
    finally:
        db_utils.DB_PATH = original_db_path


def test_update_paper_status_rejects_reserved_status_and_timestamp_columns(tmp_path: Path):
    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        conn = sqlite3.connect(db_utils.DB_PATH)
        conn.execute(
            """
            CREATE TABLE papers (
                paper_id TEXT PRIMARY KEY,
                status TEXT,
                feedback_json TEXT,
                updated_at TIMESTAMP
            )
            """
        )
        conn.execute(
            "INSERT INTO papers (paper_id, status, feedback_json, updated_at) VALUES (?, ?, ?, ?)",
            ("paper-1", "NEW", "{}", "original-ts"),
        )
        conn.commit()
        conn.close()

        with pytest.raises(ValueError, match="Unsupported paper update columns: status, updated_at"):
            db_utils.update_paper_status(
                "paper-1",
                "FAILED",
                {"status": "INDEXED", "updated_at": "manual-ts"},
            )

        conn = sqlite3.connect(db_utils.DB_PATH)
        row = conn.execute(
            "SELECT status, feedback_json, updated_at FROM papers WHERE paper_id = ?",
            ("paper-1",),
        ).fetchone()
        conn.close()

        assert row == ("NEW", "{}", "original-ts")
    finally:
        db_utils.DB_PATH = original_db_path
