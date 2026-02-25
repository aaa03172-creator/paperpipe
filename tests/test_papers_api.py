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
        assert by_id["p_missing_pdf"]["pdf_status"] == "missing"
        assert by_id["p_has_pdf"]["pdf_exists"] is True
        assert by_id["p_has_pdf"]["pdf_status"] is None
    finally:
        db_utils.DB_PATH = original_db_path


def test_papers_list_is_limited_and_sorted_by_updated_at(tmp_path, monkeypatch):
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
        for idx in range(60):
            conn.execute(
                """
                INSERT INTO papers (paper_id, title, status, pdf_path, summary, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    f"p_{idx:02d}",
                    f"Paper {idx:02d}",
                    "INDEXED",
                    None,
                    "summary",
                    f"2026-02-01 00:{idx % 60:02d}:00",
                    f"2026-02-01 00:{idx % 60:02d}:00",
                ),
            )
        conn.commit()
        conn.close()

        client = TestClient(api_main.app)
        listing = client.get("/papers")

        assert listing.status_code == 200
        rows = listing.json()
        assert len(rows) == 50
        assert rows[0]["paper_id"] == "p_59"
        assert rows[-1]["paper_id"] == "p_10"
        assert rows[0]["pdf_exists"] is False
        assert rows[0]["pdf_status"] is None
    finally:
        db_utils.DB_PATH = original_db_path


def test_paper_pdf_endpoint_serves_existing_file_and_handles_missing(tmp_path, monkeypatch):
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
        existing_pdf = tmp_path / "served.pdf"
        existing_pdf.write_bytes(b"%PDF-1.4\n%test\n")
        conn.execute(
            """
            INSERT INTO papers (paper_id, title, status, pdf_path, summary, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            ("p_served", "Served PDF", "INDEXED", str(existing_pdf), "summary"),
        )
        conn.execute(
            """
            INSERT INTO papers (paper_id, title, status, pdf_path, summary, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            ("p_missing_path", "Missing Path", "INDEXED", "", "summary"),
        )
        conn.execute(
            """
            INSERT INTO papers (paper_id, title, status, pdf_path, summary, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            ("p_missing_file", "Missing File", "INDEXED", str(tmp_path / "gone.pdf"), "summary"),
        )
        conn.commit()
        conn.close()

        client = TestClient(api_main.app)

        served = client.get("/papers/p_served/pdf")
        assert served.status_code == 200
        assert served.headers.get("content-type", "").startswith("application/pdf")
        assert served.content.startswith(b"%PDF")

        missing_path = client.get("/papers/p_missing_path/pdf")
        assert missing_path.status_code == 404
        assert "PDF path not registered" in missing_path.json()["detail"]

        missing_file = client.get("/papers/p_missing_file/pdf")
        assert missing_file.status_code == 404
        assert "PDF file not found" in missing_file.json()["detail"]

        missing_paper = client.get("/papers/nope/pdf")
        assert missing_paper.status_code == 404
        assert missing_paper.json()["detail"] == "Paper not found"
    finally:
        db_utils.DB_PATH = original_db_path
