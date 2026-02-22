import sqlite3

from src.db_paper_write_ops import update_paper_status_with_connection


def _make_conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE papers (
            paper_id TEXT PRIMARY KEY,
            status TEXT,
            title TEXT,
            updated_at TEXT
        )
        """
    )
    conn.execute(
        "INSERT INTO papers (paper_id, status, title, updated_at) VALUES (?, ?, ?, CURRENT_TIMESTAMP)",
        ("p1", "NEW", "old",),
    )
    conn.commit()
    return conn


def test_update_paper_status_ignores_unknown_update_keys():
    conn = _make_conn()
    try:
        update_paper_status_with_connection(
            conn,
            "p1",
            "GATED",
            updates={"unknown_col": "x", "title": "updated"},
        )
        conn.commit()

        row = conn.execute("SELECT status, title FROM papers WHERE paper_id='p1'").fetchone()
        assert row["status"] == "GATED"
        assert row["title"] == "updated"
    finally:
        conn.close()


def test_update_paper_status_ignores_non_identifier_keys():
    conn = _make_conn()
    try:
        update_paper_status_with_connection(
            conn,
            "p1",
            "FAILED",
            updates={"title = 'pwned' --": "x", "title": "safe"},
        )
        conn.commit()

        row = conn.execute("SELECT status, title FROM papers WHERE paper_id='p1'").fetchone()
        assert row["status"] == "FAILED"
        assert row["title"] == "safe"
    finally:
        conn.close()
