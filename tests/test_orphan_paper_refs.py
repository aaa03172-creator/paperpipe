from __future__ import annotations

import sqlite3

from src.db_orphan_refs import apply_cleanup, collect_orphans, select_cleanup_candidates


def _make_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE papers (paper_id TEXT PRIMARY KEY)")
    conn.execute(
        """
        CREATE TABLE jobs (
            job_id TEXT PRIMARY KEY,
            paper_id TEXT,
            status TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE runs (
            run_id TEXT PRIMARY KEY,
            paper_id TEXT,
            status TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE review_queue (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            paper_id TEXT,
            decision TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE user_actions (
            action_id TEXT PRIMARY KEY,
            paper_id TEXT,
            action_type TEXT,
            source TEXT
        )
        """
    )
    return conn


def test_collect_orphans_counts_by_table():
    conn = _make_conn()
    try:
        conn.execute("INSERT INTO papers (paper_id) VALUES ('doi:10.1000/a')")
        conn.execute("INSERT INTO jobs (job_id, paper_id, status) VALUES ('j1', 'test_paper_001', 'completed')")
        conn.execute("INSERT INTO jobs (job_id, paper_id, status) VALUES ('j2', 'doi:10.1000/a', 'completed')")
        conn.execute("INSERT INTO runs (run_id, paper_id, status) VALUES ('r1', 'legacy:x', 'failed')")
        conn.execute("INSERT INTO review_queue (paper_id, decision) VALUES ('doi:10.1000/a', 'PENDING')")
        conn.commit()

        orphans = collect_orphans(conn)
        assert len(orphans["jobs"]) == 1
        assert len(orphans["runs"]) == 1
        assert len(orphans["review_queue"]) == 0
    finally:
        conn.close()


def test_select_cleanup_candidates_test_terminal_mode():
    conn = _make_conn()
    try:
        conn.execute("INSERT INTO jobs (job_id, paper_id, status) VALUES ('j1', 'test_paper_001', 'completed')")
        conn.execute("INSERT INTO jobs (job_id, paper_id, status) VALUES ('j2', 'legacy:a', 'completed')")
        conn.execute("INSERT INTO runs (run_id, paper_id, status) VALUES ('r1', 'test_paper_001', 'succeeded')")
        conn.execute("INSERT INTO runs (run_id, paper_id, status) VALUES ('r2', 'test_paper_001', 'running')")
        conn.commit()

        orphans = collect_orphans(conn)
        candidates = select_cleanup_candidates(orphans, mode="test_terminal")
        ids = {(item.table, item.pk_value) for item in candidates}
        assert ("jobs", "j1") in ids
        assert ("runs", "r1") in ids
        assert ("jobs", "j2") not in ids
        assert ("runs", "r2") not in ids
    finally:
        conn.close()


def test_apply_cleanup_deletes_and_logs():
    conn = _make_conn()
    try:
        conn.execute("INSERT INTO jobs (job_id, paper_id, status) VALUES ('j1', 'test_paper_001', 'completed')")
        conn.execute("INSERT INTO runs (run_id, paper_id, status) VALUES ('r1', 'test_paper_001', 'succeeded')")
        conn.commit()

        orphans = collect_orphans(conn)
        candidates = select_cleanup_candidates(orphans, mode="test_terminal")
        deleted = apply_cleanup(conn, candidates=candidates, batch_id="batch-test")
        conn.commit()

        assert deleted["jobs"] == 1
        assert deleted["runs"] == 1
        assert deleted["total"] == 2
        assert conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM runs").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM orphan_cleanup_log").fetchone()[0] == 2
    finally:
        conn.close()
