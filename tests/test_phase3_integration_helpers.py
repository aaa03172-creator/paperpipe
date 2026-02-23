from __future__ import annotations

import sqlite3
from pathlib import Path

from scripts import test_phase3_integration as integration_script


def _make_db(path: Path) -> None:
    conn = sqlite3.connect(path)
    try:
        conn.execute(
            """
            CREATE TABLE papers (
                paper_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                status TEXT,
                source TEXT,
                created_at TEXT,
                updated_at TEXT
            )
            """
        )
        conn.commit()
    finally:
        conn.close()


def test_ensure_test_paper_row_upsert(monkeypatch, tmp_path: Path):
    db_path = tmp_path / "state.db"
    _make_db(db_path)

    def _get_conn():
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        return conn

    monkeypatch.setattr(integration_script, "get_db_connection", _get_conn)

    integration_script._ensure_test_paper_row("test_paper_001")
    integration_script._ensure_test_paper_row("test_paper_001")

    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute(
            "SELECT paper_id, source, status FROM papers WHERE paper_id = ?",
            ("test_paper_001",),
        ).fetchone()
        count = conn.execute("SELECT COUNT(*) FROM papers").fetchone()[0]
    finally:
        conn.close()

    assert row is not None
    assert row[0] == "test_paper_001"
    assert row[1] == "integration_test"
    assert row[2] == "NEW"
    assert count == 1
