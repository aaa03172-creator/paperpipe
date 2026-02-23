from __future__ import annotations

import sqlite3
from pathlib import Path

from backend.services import job_runner


def _make_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE papers (
            paper_id TEXT PRIMARY KEY,
            doi TEXT,
            pdf_path TEXT
        )
        """
    )
    conn.commit()
    return conn


def test_resolve_pdf_path_from_db_prefers_exact_paper_id(tmp_path: Path, monkeypatch):
    pdf_path = tmp_path / "custom_name.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n")

    conn = _make_conn()
    try:
        conn.execute(
            "INSERT INTO papers (paper_id, doi, pdf_path) VALUES (?, ?, ?)",
            ("zotero:ABC123", None, str(pdf_path)),
        )
        conn.commit()

        monkeypatch.setattr(job_runner, "get_db_connection", lambda: conn)
        resolved = job_runner._resolve_pdf_path_from_db("zotero:ABC123")
        assert resolved == pdf_path
    finally:
        conn.close()


def test_resolve_pdf_path_from_db_supports_doi_alias_lookup(tmp_path: Path, monkeypatch):
    pdf_path = tmp_path / "doi_file.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n")

    conn = _make_conn()
    try:
        conn.execute(
            "INSERT INTO papers (paper_id, doi, pdf_path) VALUES (?, ?, ?)",
            ("legacy-doi-id", "10.1000/test", str(pdf_path)),
        )
        conn.commit()

        monkeypatch.setattr(job_runner, "get_db_connection", lambda: conn)
        resolved = job_runner._resolve_pdf_path_from_db("doi:10.1000/test")
        assert resolved == pdf_path
    finally:
        conn.close()
