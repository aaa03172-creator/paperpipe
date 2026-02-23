import json
import sqlite3
from pathlib import Path

import src.db_utils as db_utils
from src.core.ids import make_paper_id


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
        canonical_id = make_paper_id(zotero_key="paper_001")
        row = conn.execute(
            "SELECT paper_id, status, pdf_path FROM papers WHERE paper_id=?",
            (canonical_id,),
        ).fetchone()
        conn.close()

        assert total == 1
        assert row["paper_id"] == canonical_id
        assert row["status"] == "NEW"
        assert row["pdf_path"] == "/tmp/paper_001.pdf"
    finally:
        db_utils.DB_PATH = original_db_path


def test_sync_zotero_to_db_reuses_legacy_citation_key_row(tmp_path):
    db_path = tmp_path / "state.db"
    _init_test_db(db_path)

    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        INSERT INTO papers (paper_id, title, summary, status, pdf_path, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """,
        ("paper_legacy", "Legacy", "old", "NEW", None),
    )
    conn.commit()
    conn.close()

    export_path = tmp_path / "zotero_export.json"
    payload = {
        "items": [
            {
                "citationKey": "paper_legacy",
                "title": "Legacy",
                "abstractNote": "Updated",
                "attachments": [{"path": "/tmp/paper_legacy.pdf"}],
            }
        ]
    }
    export_path.write_text(json.dumps(payload), encoding="utf-8")

    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = db_path
    try:
        created = db_utils.sync_zotero_to_db(export_path)
        assert created == 0

        conn = db_utils.get_db_connection()
        total = conn.execute("SELECT COUNT(*) AS n FROM papers").fetchone()["n"]
        row = conn.execute(
            "SELECT paper_id, summary, pdf_path FROM papers WHERE paper_id='paper_legacy'"
        ).fetchone()
        canonical = conn.execute(
            "SELECT COUNT(*) AS n FROM papers WHERE paper_id=?",
            (make_paper_id(zotero_key="paper_legacy"),),
        ).fetchone()["n"]
        conn.close()

        assert total == 1
        assert row["summary"] == "old"
        assert row["pdf_path"] == "/tmp/paper_legacy.pdf"
        assert canonical == 0
    finally:
        db_utils.DB_PATH = original_db_path
