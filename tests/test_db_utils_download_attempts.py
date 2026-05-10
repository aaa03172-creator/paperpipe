import json
import logging
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


def test_save_paper_state_logs_schema_write_failure(tmp_path: Path, caplog):
    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        conn = sqlite3.connect(db_utils.DB_PATH)
        conn.execute(
            """
            CREATE TABLE papers (
                paper_id TEXT,
                title TEXT,
                source TEXT
            )
            """
        )
        conn.commit()
        conn.close()

        caplog.set_level(logging.WARNING, logger="src.db_utils")
        db_utils.save_paper_state(
            "10.5000/broken-schema",
            "Broken Schema Paper",
            "pubmed",
            "2026-02-24",
        )

        conn = sqlite3.connect(db_utils.DB_PATH)
        rows = conn.execute("SELECT paper_id FROM papers").fetchall()
        conn.close()

        assert rows == []
        assert "Failed to save paper state for 10.5000/broken-schema" in caplog.text
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
                pdf_status TEXT,
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
            pdf_status="downloaded",
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
        assert row["pdf_status"] == "downloaded"
        assert row["issues_state"] == "clear"
        assert row["pdf_path"] == "/tmp/example.pdf"
        assert row["feedback_json"] == '{"decision":"APPROVED"}'
        parsed = json.loads(row["download_attempts"])
        assert isinstance(parsed, list)
        assert parsed[0]["provider"] == "unpaywall"
        assert parsed[0]["retry_no"] == 1
    finally:
        db_utils.DB_PATH = original_db_path


def test_save_paper_state_reuses_existing_row_for_duplicate_doi(tmp_path: Path):
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
                processed_date TEXT,
                processed_at TIMESTAMP,
                updated_at TIMESTAMP,
                pdf_path TEXT
            )
            """
        )
        conn.commit()
        conn.close()

        db_utils.save_paper_state(
            "paper-original",
            "Original Title",
            "pubmed",
            "2026-02-24",
            doi="https://doi.org/10.5000/DUPLICATE",
            status="NEW",
        )
        db_utils.save_paper_state(
            "paper-second",
            "Updated Title",
            "user_imported_pdf",
            "2026-02-25",
            doi="10.5000/duplicate",
            status="APPROVED",
            local_pdf_path="/tmp/second.pdf",
        )

        conn = sqlite3.connect(db_utils.DB_PATH)
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT * FROM papers ORDER BY paper_id").fetchall()
        conn.close()

        assert len(rows) == 1
        assert rows[0]["paper_id"] == "paper-original"
        assert rows[0]["doi"] == "10.5000/duplicate"
        assert rows[0]["title"] == "Updated Title"
        assert rows[0]["status"] == "APPROVED"
        assert rows[0]["pdf_path"] == "/tmp/second.pdf"
    finally:
        db_utils.DB_PATH = original_db_path


def test_save_paper_state_does_not_store_non_doi_identifier_as_doi(tmp_path: Path):
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
                processed_date TEXT,
                updated_at TIMESTAMP
            )
            """
        )
        conn.commit()
        conn.close()

        db_utils.save_paper_state(
            "zotero:smith2024",
            "Zotero Paper",
            "zotero",
            "2026-05-10",
            status="NEW",
        )
        db_utils.save_paper_state(
            "10.5000/UPPER",
            "Bare DOI Paper",
            "pubmed",
            "2026-05-10",
            status="NEW",
        )

        conn = sqlite3.connect(db_utils.DB_PATH)
        conn.row_factory = sqlite3.Row
        zotero_row = conn.execute(
            "SELECT paper_id, doi FROM papers WHERE paper_id = ?",
            ("zotero:smith2024",),
        ).fetchone()
        doi_row = conn.execute(
            "SELECT paper_id, doi FROM papers WHERE paper_id = ?",
            ("10.5000/UPPER",),
        ).fetchone()
        conn.close()

        assert zotero_row is not None
        assert zotero_row["doi"] is None
        assert doi_row is not None
        assert doi_row["doi"] == "10.5000/upper"
    finally:
        db_utils.DB_PATH = original_db_path


def test_find_duplicate_doi_paper_rows_reports_existing_normalized_duplicates(tmp_path: Path):
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
                pdf_path TEXT,
                created_at TIMESTAMP,
                updated_at TIMESTAMP
            )
            """
        )
        conn.executemany(
            """
            INSERT INTO papers (paper_id, doi, title, source, status, pdf_path)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    "paper-a",
                    "https://doi.org/10.5000/DUPLICATE",
                    "First copy",
                    "pubmed",
                    "NEW",
                    "/tmp/a.pdf",
                ),
                (
                    "paper-b",
                    "10.5000/duplicate",
                    "Second copy",
                    "user_imported_pdf",
                    "APPROVED",
                    "/tmp/b.pdf",
                ),
                ("paper-c", "10.5000/unique", "Unique", "pubmed", "NEW", None),
                ("paper-legacy-a", "zotero:legacy", "Legacy A", "zotero", "NEW", None),
                ("paper-legacy-b", "zotero:legacy", "Legacy B", "zotero", "NEW", None),
                ("paper-empty", "", "No DOI", "pubmed", "NEW", None),
                ("paper-null", None, "Null DOI", "pubmed", "NEW", None),
            ],
        )
        conn.commit()
        conn.close()

        duplicates = db_utils.find_duplicate_doi_paper_rows()

        assert duplicates == [
            {
                "normalized_doi": "10.5000/duplicate",
                "row_count": 2,
                "paper_ids": ["paper-a", "paper-b"],
                "rows": [
                    {
                        "paper_id": "paper-a",
                        "doi": "https://doi.org/10.5000/DUPLICATE",
                        "title": "First copy",
                        "source": "pubmed",
                        "status": "NEW",
                        "pdf_path": "/tmp/a.pdf",
                        "created_at": None,
                        "updated_at": None,
                        "normalized_doi": "10.5000/duplicate",
                    },
                    {
                        "paper_id": "paper-b",
                        "doi": "10.5000/duplicate",
                        "title": "Second copy",
                        "source": "user_imported_pdf",
                        "status": "APPROVED",
                        "pdf_path": "/tmp/b.pdf",
                        "created_at": None,
                        "updated_at": None,
                        "normalized_doi": "10.5000/duplicate",
                    },
                ],
            }
        ]
    finally:
        db_utils.DB_PATH = original_db_path


def test_find_duplicate_doi_paper_rows_returns_empty_for_minimal_schema(tmp_path: Path):
    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        conn = sqlite3.connect(db_utils.DB_PATH)
        conn.execute(
            """
            CREATE TABLE papers (
                paper_id TEXT PRIMARY KEY,
                title TEXT
            )
            """
        )
        conn.commit()
        conn.close()

        assert db_utils.find_duplicate_doi_paper_rows() == []
    finally:
        db_utils.DB_PATH = original_db_path
