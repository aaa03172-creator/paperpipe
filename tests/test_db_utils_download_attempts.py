import json
import sqlite3
from pathlib import Path

import src.db_utils as db_utils


def test_init_db_adds_download_attempts_column_when_papers_exists(tmp_path: Path):
    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        conn = sqlite3.connect(db_utils.DB_PATH)
        conn.execute(
            """
            CREATE TABLE papers (
                paper_id TEXT PRIMARY KEY,
                doi TEXT,
                title TEXT,
                source TEXT
            )
            """
        )
        conn.commit()
        conn.close()

        db_utils.init_db()

        conn = sqlite3.connect(db_utils.DB_PATH)
        cols = {row[1] for row in conn.execute("PRAGMA table_info(papers)").fetchall()}
        conn.close()
        assert "download_attempts" in cols
    finally:
        db_utils.DB_PATH = original_db_path


def test_save_paper_state_persists_download_attempts_payload(tmp_path: Path):
    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        conn = sqlite3.connect(db_utils.DB_PATH)
        conn.execute(
            """
            CREATE TABLE papers (
                paper_id TEXT PRIMARY KEY,
                doi TEXT,
                title TEXT,
                source TEXT,
                status TEXT,
                issues_state TEXT,
                processed_date TEXT,
                processed_at TIMESTAMP,
                updated_at TIMESTAMP,
                pdf_path TEXT,
                feedback_json TEXT
            )
            """
        )
        conn.commit()
        conn.close()

        attempts = [
            {
                "provider": "unpaywall",
                "status": "rate_limit",
                "retry_no": 1,
                "will_retry": False,
            }
        ]
        db_utils.save_paper_state(
            "10.5000/example",
            "Example Paper",
            "pubmed",
            "2026-02-24",
            local_pdf_path="/tmp/example.pdf",
            feedback_json='{"decision":"APPROVED"}',
            download_attempts=attempts,
            status="APPROVED",
            issues_state="clear",
        )

        conn = sqlite3.connect(db_utils.DB_PATH)
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM papers WHERE paper_id = ?", ("10.5000/example",)).fetchone()
        cols = {r[1] for r in conn.execute("PRAGMA table_info(papers)").fetchall()}
        conn.close()

        assert row is not None
        assert "download_attempts" in cols
        assert row["status"] == "APPROVED"
        assert row["issues_state"] == "clear"
        assert row["pdf_path"] == "/tmp/example.pdf"
        assert row["feedback_json"] == '{"decision":"APPROVED"}'
        parsed = json.loads(row["download_attempts"])
        assert isinstance(parsed, list)
        assert parsed[0]["provider"] == "unpaywall"
        assert parsed[0]["retry_no"] == 1
    finally:
        db_utils.DB_PATH = original_db_path
