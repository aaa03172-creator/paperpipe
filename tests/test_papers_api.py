from pathlib import Path

from fastapi.testclient import TestClient

import src.db_utils as db_utils
from backend import main as api_main


def test_papers_detail_includes_pdf_exists_and_missing_status(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()
        conn = db_utils.get_db_connection()
        conn.execute(
            """
            CREATE TABLE papers (
                paper_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                status TEXT NOT NULL,
                pdf_path TEXT,
                pdf_status TEXT,
                summary TEXT,
                created_at TIMESTAMP,
                updated_at TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            INSERT INTO papers (paper_id, title, status, pdf_path, summary, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            (
                "p_missing_pdf",
                "Missing PDF Paper",
                "INDEXED",
                str(tmp_path / "no_such_file.pdf"),
                "summary",
            ),
        )
        existing_pdf = tmp_path / "existing.pdf"
        existing_pdf.write_text("%PDF", encoding="utf-8")
        conn.execute(
            """
            INSERT INTO papers (paper_id, title, status, pdf_path, summary, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            (
                "p_has_pdf",
                "Has PDF Paper",
                "INDEXED",
                str(existing_pdf),
                "summary",
            ),
        )
        conn.commit()
        conn.close()

        client = TestClient(api_main.app)

        detail_missing = client.get("/papers/p_missing_pdf")
        assert detail_missing.status_code == 200
        payload_missing = detail_missing.json()
        assert payload_missing["paper_id"] == "p_missing_pdf"
        assert payload_missing["pdf_exists"] is False
        assert payload_missing["pdf_status"] == "missing"

        detail_ok = client.get("/papers/p_has_pdf")
        assert detail_ok.status_code == 200
        payload_ok = detail_ok.json()
        assert payload_ok["paper_id"] == "p_has_pdf"
        assert payload_ok["pdf_exists"] is True

        missing = client.get("/papers/nope")
        assert missing.status_code == 404

        listing = client.get("/papers")
        assert listing.status_code == 200
        rows = listing.json()
        by_id = {row["paper_id"]: row for row in rows}
        assert by_id["p_missing_pdf"]["pdf_exists"] is False
        assert by_id["p_has_pdf"]["pdf_exists"] is True
    finally:
        db_utils.DB_PATH = original_db_path


def test_papers_list_returns_empty_when_papers_table_missing(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()
        client = TestClient(api_main.app)
        resp = client.get("/papers")
        assert resp.status_code == 200
        assert resp.json() == []
    finally:
        db_utils.DB_PATH = original_db_path


def test_paper_detail_returns_404_when_papers_table_missing(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()
        client = TestClient(api_main.app)
        resp = client.get("/papers/missing")
        assert resp.status_code == 404
    finally:
        db_utils.DB_PATH = original_db_path
