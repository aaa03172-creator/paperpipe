import sqlite3
from pathlib import Path

import src.db_utils as db_utils
from scripts import init_db as init_db_script


def _create_review_queue(conn: sqlite3.Connection) -> None:
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


def _seed_duplicate_open_rows(conn: sqlite3.Connection) -> None:
    conn.execute(
        "INSERT INTO review_queue (paper_id, decision, reason) VALUES (?, ?, ?)",
        ("p1", "NEEDS_PDF_MATCH", "first"),
    )
    conn.execute(
        "INSERT INTO review_queue (paper_id, decision, reason) VALUES (?, ?, ?)",
        ("p1", "NEEDS_PDF_MATCH", "second"),
    )
    conn.commit()


def test_db_utils_init_db_dedupes_open_rows_before_unique_index(tmp_path: Path):
    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        conn = sqlite3.connect(db_utils.DB_PATH)
        _create_review_queue(conn)
        _seed_duplicate_open_rows(conn)
        conn.close()

        db_utils.init_db()

        conn = db_utils.get_db_connection()
        open_count = conn.execute(
            """
            SELECT COUNT(*) FROM review_queue
            WHERE paper_id='p1' AND decision='NEEDS_PDF_MATCH' AND resolved_at IS NULL
            """
        ).fetchone()[0]
        resolved_count = conn.execute(
            """
            SELECT COUNT(*) FROM review_queue
            WHERE paper_id='p1' AND decision='NEEDS_PDF_MATCH' AND resolved_at IS NOT NULL
            """
        ).fetchone()[0]
        index_count = conn.execute(
            """
            SELECT COUNT(*) FROM sqlite_master
            WHERE type='index' AND name='idx_review_queue_open_unique'
            """
        ).fetchone()[0]
        conn.close()

        assert open_count == 1
        assert resolved_count == 1
        assert index_count == 1
    finally:
        db_utils.DB_PATH = original_db_path


def test_script_init_db_dedupes_open_rows_before_unique_index(tmp_path: Path):
    original_db_path = init_db_script.DB_PATH
    init_db_script.DB_PATH = tmp_path / "state.db"
    try:
        conn = sqlite3.connect(init_db_script.DB_PATH)
        _create_review_queue(conn)
        _seed_duplicate_open_rows(conn)
        conn.close()

        init_db_script.init_db()

        conn = sqlite3.connect(init_db_script.DB_PATH)
        open_count = conn.execute(
            """
            SELECT COUNT(*) FROM review_queue
            WHERE paper_id='p1' AND decision='NEEDS_PDF_MATCH' AND resolved_at IS NULL
            """
        ).fetchone()[0]
        resolved_count = conn.execute(
            """
            SELECT COUNT(*) FROM review_queue
            WHERE paper_id='p1' AND decision='NEEDS_PDF_MATCH' AND resolved_at IS NOT NULL
            """
        ).fetchone()[0]
        index_count = conn.execute(
            """
            SELECT COUNT(*) FROM sqlite_master
            WHERE type='index' AND name='idx_review_queue_open_unique'
            """
        ).fetchone()[0]
        conn.close()

        assert open_count == 1
        assert resolved_count == 1
        assert index_count == 1
    finally:
        init_db_script.DB_PATH = original_db_path
