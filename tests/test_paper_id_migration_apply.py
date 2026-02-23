import sqlite3

from scripts.apply_paper_id_migration import apply_mappings, collect_impacts, validate_plan


def _make_conn():
    conn = sqlite3.connect(":memory:")
    conn.execute(
        """
        CREATE TABLE papers (
            paper_id TEXT PRIMARY KEY,
            doi TEXT,
            pdf_path TEXT,
            status TEXT,
            paper_key TEXT,
            updated_at TEXT
        )
        """
    )
    conn.execute("CREATE TABLE review_queue (paper_id TEXT, decision TEXT)")
    conn.execute("CREATE TABLE jobs (paper_id TEXT)")
    conn.execute("CREATE TABLE runs (paper_id TEXT)")
    conn.execute("CREATE TABLE user_actions (paper_id TEXT)")
    return conn


def test_validate_plan_detects_existing_target_conflict():
    conn = _make_conn()
    try:
        conn.execute("INSERT INTO papers (paper_id, status) VALUES ('legacy:a', 'INDEXED')")
        conn.execute("INSERT INTO papers (paper_id, status) VALUES ('doi:10.1/existing', 'INDEXED')")
        conn.commit()

        ok, errors = validate_plan(conn, [("legacy:a", "doi:10.1/existing")])
        assert ok is False
        assert any("already exists" in item for item in errors)
    finally:
        conn.close()


def test_collect_impacts_counts_referencing_rows():
    conn = _make_conn()
    try:
        conn.execute("INSERT INTO papers (paper_id, status) VALUES ('legacy:a', 'INDEXED')")
        conn.execute("INSERT INTO review_queue (paper_id, decision) VALUES ('legacy:a', 'NEEDS_READER')")
        conn.execute("INSERT INTO jobs (paper_id) VALUES ('legacy:a')")
        conn.execute("INSERT INTO runs (paper_id) VALUES ('legacy:a')")
        conn.execute("INSERT INTO user_actions (paper_id) VALUES ('legacy:a')")
        conn.commit()

        impacts = collect_impacts(conn, [("legacy:a", "doi:10.1/a")])
        assert impacts["papers"] == 1
        assert impacts["review_queue"] == 1
        assert impacts["jobs"] == 1
        assert impacts["runs"] == 1
        assert impacts["user_actions"] == 1
    finally:
        conn.close()


def test_apply_mappings_updates_all_known_tables():
    conn = _make_conn()
    try:
        conn.execute("INSERT INTO papers (paper_id, status) VALUES ('legacy:a', 'INDEXED')")
        conn.execute("INSERT INTO review_queue (paper_id, decision) VALUES ('legacy:a', 'NEEDS_READER')")
        conn.execute("INSERT INTO jobs (paper_id) VALUES ('legacy:a')")
        conn.execute("INSERT INTO runs (paper_id) VALUES ('legacy:a')")
        conn.execute("INSERT INTO user_actions (paper_id) VALUES ('legacy:a')")
        conn.commit()

        apply_mappings(conn, [("legacy:a", "doi:10.1/a")])
        conn.commit()

        assert conn.execute(
            "SELECT COUNT(*) FROM papers WHERE paper_id = 'doi:10.1/a'"
        ).fetchone()[0] == 1
        assert conn.execute(
            "SELECT COUNT(*) FROM papers WHERE paper_id = 'legacy:a'"
        ).fetchone()[0] == 0
        assert conn.execute(
            "SELECT COUNT(*) FROM review_queue WHERE paper_id = 'doi:10.1/a'"
        ).fetchone()[0] == 1
        assert conn.execute(
            "SELECT COUNT(*) FROM jobs WHERE paper_id = 'doi:10.1/a'"
        ).fetchone()[0] == 1
        assert conn.execute(
            "SELECT COUNT(*) FROM runs WHERE paper_id = 'doi:10.1/a'"
        ).fetchone()[0] == 1
        assert conn.execute(
            "SELECT COUNT(*) FROM user_actions WHERE paper_id = 'doi:10.1/a'"
        ).fetchone()[0] == 1
    finally:
        conn.close()
