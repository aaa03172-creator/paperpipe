import sqlite3
from pathlib import Path
from types import SimpleNamespace

from scripts import qa_report
import src.db_utils as db_utils


def _create_tables(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE papers (
            paper_id TEXT PRIMARY KEY,
            title TEXT,
            status TEXT,
            summary TEXT,
            feedback_json TEXT,
            pdf_status TEXT,
            pdf_path TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE review_queue (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            paper_id TEXT NOT NULL,
            decision TEXT NOT NULL,
            reason TEXT,
            owner TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            resolved_at TIMESTAMP,
            resolution TEXT
        )
        """
    )


def test_qa_report_counts_institutional_counters(tmp_path: Path, monkeypatch):
    db_path = tmp_path / "state.db"
    vault = tmp_path / "vault"
    inbox = vault / "Inbox" / "PaperPipe"
    inbox.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(db_path)
    _create_tables(conn)
    conn.execute(
        """
        INSERT INTO papers (paper_id, title, status, summary, feedback_json, pdf_status, pdf_path)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        ("p_manual", "Manual", "APPROVED", "s", "{}", "manual_required", None),
    )
    conn.execute(
        """
        INSERT INTO papers (paper_id, title, status, summary, feedback_json, pdf_status, pdf_path)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        ("p_missing_path", "Missing path", "INDEXED", "s", "{}", "downloaded", None),
    )
    conn.execute(
        """
        INSERT INTO papers (paper_id, title, status, summary, feedback_json, pdf_status, pdf_path)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        ("p_ok", "OK", "APPROVED", "s", '{"claims":[{"statement":"x"}]}', "downloaded", "/tmp/f.pdf"),
    )
    conn.execute(
        "INSERT INTO review_queue (paper_id, decision, reason) VALUES (?, ?, ?)",
        ("p_manual", "NEEDS_PDF_MATCH", "unmatched"),
    )
    conn.execute(
        "INSERT INTO review_queue (paper_id, decision, reason, resolved_at) VALUES (?, ?, ?, CURRENT_TIMESTAMP)",
        ("p_ok", "NEEDS_PDF_MATCH", "resolved"),
    )
    conn.commit()
    conn.close()

    monkeypatch.setattr(db_utils, "DB_PATH", db_path)
    unmatched_dir = tmp_path / "storage" / "pdfs" / "_unmatched"
    unmatched_dir.mkdir(parents=True, exist_ok=True)
    (unmatched_dir / "u1.pdf").write_bytes(b"%PDF-1.4")
    (unmatched_dir / "u2.pdf").write_bytes(b"%PDF-1.4")

    monkeypatch.setattr(
        qa_report,
        "load_config",
        lambda: SimpleNamespace(
            paths=SimpleNamespace(obsidian_vault=str(vault), pdf_storage_dir=str(tmp_path / "storage" / "pdfs"))
        ),
    )

    # Minimal markdown files to avoid file-missing noise.
    (inbox / "p_manual.md").write_text("## Critical Review (ClaimSet)\n", encoding="utf-8")
    (inbox / "p_missing_path.md").write_text("## Critical Review (ClaimSet)\n", encoding="utf-8")
    (inbox / "p_ok.md").write_text("## Critical Review (ClaimSet)\n", encoding="utf-8")

    result = qa_report.run_qa_check()
    assert result["manual_required"] == 1
    assert result["downloaded_missing_path"] == 1
    assert result["unmatched"] == 2
    assert result["unmatched_review_open"] == 1
