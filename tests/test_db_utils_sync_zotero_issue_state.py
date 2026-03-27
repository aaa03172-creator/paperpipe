import json
from pathlib import Path

import src.db_utils as db_utils


def test_sync_zotero_to_db_inserts_unavailable_issues_state_when_column_exists(tmp_path: Path):
    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()
        conn = db_utils.get_db_connection()
        conn.execute(
            """
            CREATE TABLE papers (
                paper_id TEXT PRIMARY KEY,
                title TEXT,
                summary TEXT,
                status TEXT,
                issues_state TEXT,
                pdf_path TEXT,
                created_at TIMESTAMP,
                updated_at TIMESTAMP
            )
            """
        )
        conn.commit()
        conn.close()

        zotero_path = tmp_path / "zotero_export.json"
        zotero_path.write_text(
            json.dumps(
                {
                    "items": [
                        {
                            "citationKey": "zotero-key-001",
                            "title": "Synced Paper",
                            "abstractNote": "summary",
                            "attachments": [],
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )

        inserted = db_utils.sync_zotero_to_db(zotero_path)
        assert inserted == 1

        conn = db_utils.get_db_connection()
        row = conn.execute(
            "SELECT paper_id, status, issues_state FROM papers WHERE paper_id = ?",
            ("zotero-key-001",),
        ).fetchone()
        conn.close()

        assert row is not None
        assert row["status"] == "NEW"
        assert row["issues_state"] == "unavailable"
    finally:
        db_utils.DB_PATH = original_db_path
