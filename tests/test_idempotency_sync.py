import json
import sqlite3
from pathlib import Path

import src.db_utils as db_utils


def _init_test_db(path: Path):
    conn = sqlite3.connect(path)
    conn.execute(
        """
        CREATE TABLE papers (
            paper_id TEXT PRIMARY KEY,
            title TEXT,
            summary TEXT,
            status TEXT,
            pdf_path TEXT,
            confidence REAL,
            feedback_json TEXT,
            gate_decision TEXT,
            gate_reason TEXT,
            created_at TEXT,
            updated_at TEXT
        )
        """
    )
    conn.commit()
    conn.close()


def test_sync_zotero_to_db_is_idempotent(tmp_path):
    db_path = tmp_path / "state.db"
    _init_test_db(db_path)

    export_path = tmp_path / "zotero_export.json"
    payload = {
        "items": [
            {
                "citationKey": "paper_001",
                "title": "Idempotent Paper",
                "abstractNote": "A study",
                "attachments": [{"path": "/tmp/paper_001.pdf"}],
            }
        ]
    }
    export_path.write_text(json.dumps(payload), encoding="utf-8")

    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = db_path
    try:
        first = db_utils.sync_zotero_to_db(export_path)
        second = db_utils.sync_zotero_to_db(export_path)

        assert first == 1
        assert second == 0

        conn = db_utils.get_db_connection()
        total = conn.execute("SELECT COUNT(*) AS n FROM papers").fetchone()["n"]
        row = conn.execute(
            "SELECT paper_id, status, pdf_path FROM papers WHERE paper_id='paper_001'"
        ).fetchone()
        conn.close()

        assert total == 1
        assert row["status"] == "NEW"
        assert row["pdf_path"] == "/tmp/paper_001.pdf"
    finally:
        db_utils.DB_PATH = original_db_path
