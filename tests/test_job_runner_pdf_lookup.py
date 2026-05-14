from __future__ import annotations

import sqlite3
from pathlib import Path
from types import SimpleNamespace

from backend.services import job_runner


def _make_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE papers (
            paper_id TEXT PRIMARY KEY,
            doi TEXT,
            pdf_path TEXT,
            obsidian_path TEXT
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


def test_resolve_pdf_path_from_note_frontmatter_supports_file_pdf_url(tmp_path: Path, monkeypatch):
    pdf_path = tmp_path / "note-backed.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n")

    vault = tmp_path / "vault"
    note_dir = vault / "Inbox" / "PaperPipe"
    note_dir.mkdir(parents=True)
    note_path = note_dir / "note-backed-paper.md"
    note_path.write_text(
        "\n".join(
            [
                "---",
                "id: zotero:NOTE123",
                f"pdf_url: file://{pdf_path}",
                "---",
                "",
                "# Note backed paper",
            ]
        ),
        encoding="utf-8",
    )

    target = SimpleNamespace(
        note_path=Path("Inbox/PaperPipe/note-backed-paper.md"),
        has_runtime_source_metadata=lambda: False,
        build_runtime_source_frontmatter=lambda: {},
    )

    monkeypatch.setattr(job_runner.paper_notes, "_resolve_vault_path", lambda: vault)
    monkeypatch.setattr(
        job_runner.paper_notes,
        "_build_index",
        lambda _vault_path: SimpleNamespace(items=[target]),
    )
    monkeypatch.setattr(
        job_runner.paper_notes,
        "_find_note_item_for_paper_id",
        lambda items, paper_id: target if paper_id == "zotero:NOTE123" else None,
    )

    resolved = job_runner._resolve_pdf_path_from_note_frontmatter("zotero:NOTE123")
    assert resolved == pdf_path


def test_resolve_note_path_for_paper_falls_back_to_vault_note_resolution(tmp_path: Path, monkeypatch):
    vault = tmp_path / "vault"
    note_dir = vault / "Inbox" / "PaperPipe"
    note_dir.mkdir(parents=True)
    note_path = note_dir / "Alzheimer Disease as a Clinical-Biological Construct.md"
    note_path.write_text(
        "\n".join(
            [
                "---",
                "id: zotero:duboisAlzheimerDiseaseClinicalBiological2024",
                'aliases: ["Dubois 2024"]',
                "tags:",
                "  - Medicine/Neurology",
                "date_processed: 2026-04-18",
                "confidence: 0.95",
                "status: INDEXED",
                "---",
                "",
                "# Dubois 2024",
            ]
        ),
        encoding="utf-8",
    )

    conn = _make_conn()
    try:
        monkeypatch.setattr(job_runner, "get_db_connection", lambda: conn)
        config = SimpleNamespace(
            paths=SimpleNamespace(
                obsidian_vault=vault,
                index_all=Path("00_Index/paper_collection.csv"),
            )
        )

        resolved = job_runner._resolve_note_path_for_paper(
            config,
            "zotero:duboisAlzheimerDiseaseClinicalBiological2024",
        )
        assert resolved == note_path
    finally:
        conn.close()
