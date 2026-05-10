import json
from pathlib import Path

import src.db_utils as db_utils
from scripts import init_db as init_db_script


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


def test_sync_zotero_to_db_persists_normalized_doi_when_column_exists(tmp_path: Path):
    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()
        conn = db_utils.get_db_connection()
        conn.execute(
            """
            CREATE TABLE papers (
                paper_id TEXT PRIMARY KEY,
                doi TEXT,
                title TEXT,
                summary TEXT,
                source TEXT,
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
                            "citationKey": "zotero-key-with-doi",
                            "title": "Synced DOI Paper",
                            "abstractNote": "summary",
                            "DOI": "https://doi.org/10.5555/ABC.DEF",
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
            "SELECT paper_id, doi, source FROM papers WHERE paper_id = ?",
            ("zotero-key-with-doi",),
        ).fetchone()
        conn.close()

        assert row is not None
        assert row["doi"] == "10.5555/abc.def"
        assert row["source"] == "zotero"
    finally:
        db_utils.DB_PATH = original_db_path


def test_sync_zotero_to_db_reuses_existing_row_for_duplicate_doi(tmp_path: Path):
    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()
        conn = db_utils.get_db_connection()
        conn.execute(
            """
            CREATE TABLE papers (
                paper_id TEXT PRIMARY KEY,
                doi TEXT,
                title TEXT,
                summary TEXT,
                source TEXT,
                status TEXT,
                issues_state TEXT,
                pdf_path TEXT,
                created_at TIMESTAMP,
                updated_at TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            INSERT INTO papers (paper_id, doi, title, source, status)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                "paper-imported-existing",
                "https://doi.org/10.7777/DUP",
                "Imported Existing",
                "user_imported_pdf",
                "APPROVED",
            ),
        )
        conn.commit()
        conn.close()

        pdf_path = tmp_path / "zotero.pdf"
        zotero_path = tmp_path / "zotero_export.json"
        zotero_path.write_text(
            json.dumps(
                {
                    "items": [
                        {
                            "citationKey": "zotero-duplicate-key",
                            "title": "Zotero Duplicate",
                            "abstractNote": "Zotero abstract",
                            "DOI": "10.7777/dup",
                            "attachments": [{"path": str(pdf_path)}],
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )

        inserted = db_utils.sync_zotero_to_db(zotero_path)
        assert inserted == 0

        conn = db_utils.get_db_connection()
        rows = conn.execute("SELECT paper_id, doi, title, summary, source, status, pdf_path FROM papers").fetchall()
        conn.close()

        assert len(rows) == 1
        row = rows[0]
        assert row["paper_id"] == "paper-imported-existing"
        assert row["doi"] == "https://doi.org/10.7777/DUP"
        assert row["title"] == "Imported Existing"
        assert row["summary"] == "Zotero abstract"
        assert row["source"] == "user_imported_pdf"
        assert row["status"] == "APPROVED"
        assert row["pdf_path"] == str(pdf_path)
    finally:
        db_utils.DB_PATH = original_db_path


def test_fresh_script_schema_supports_zotero_summary_sync(tmp_path: Path):
    original_db_path = db_utils.DB_PATH
    original_script_db_path = init_db_script.DB_PATH
    db_path = tmp_path / "state.db"
    db_utils.DB_PATH = db_path
    init_db_script.DB_PATH = db_path
    try:
        init_db_script.init_db()
        db_utils.init_db()

        zotero_path = tmp_path / "zotero_export.json"
        zotero_path.write_text(
            json.dumps(
                {
                    "items": [
                        {
                            "citationKey": "fresh-schema-paper",
                            "title": "Fresh Schema Paper",
                            "abstractNote": "Fresh schema summary",
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
            "SELECT title, summary, status FROM papers WHERE paper_id = ?",
            ("fresh-schema-paper",),
        ).fetchone()
        conn.close()

        assert row is not None
        assert row["title"] == "Fresh Schema Paper"
        assert row["summary"] == "Fresh schema summary"
        assert row["status"] == "NEW"
    finally:
        db_utils.DB_PATH = original_db_path
        init_db_script.DB_PATH = original_script_db_path
