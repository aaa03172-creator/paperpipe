import json
import sqlite3

from scripts.archive_fixture_no_feedback_papers import apply_archive, select_archive_candidates


def _create_papers_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE papers (
            paper_id TEXT PRIMARY KEY,
            title TEXT,
            status TEXT,
            pdf_path TEXT,
            feedback_json TEXT
        )
        """
    )


def test_select_archive_candidates_only_returns_fixture_rows_with_missing_feedback():
    conn = sqlite3.connect(":memory:")
    _create_papers_table(conn)
    conn.execute(
        """
        INSERT INTO papers (paper_id, title, status, pdf_path, feedback_json)
        VALUES (?, ?, ?, ?, ?)
        """,
        ("paper-e2e-001", "E2E Seed Paper", "NEW", "tests/temp_rag_test/Library/Test_ID.pdf", None),
    )
    conn.execute(
        """
        INSERT INTO papers (paper_id, title, status, pdf_path, feedback_json)
        VALUES (?, ?, ?, ?, ?)
        """,
        ("test_local_id", "Test Local Paper Title", "FETCHED", "test_paper.pdf", ""),
    )
    conn.execute(
        """
        INSERT INTO papers (paper_id, title, status, pdf_path, feedback_json)
        VALUES (?, ?, ?, ?, ?)
        """,
        ("paper-real-001", "Real Paper", "INDEXED", "/tmp/real.pdf", None),
    )
    conn.execute(
        """
        INSERT INTO papers (paper_id, title, status, pdf_path, feedback_json)
        VALUES (?, ?, ?, ?, ?)
        """,
        ("paper-e2e-processed", "E2E Processed Paper", "INDEXED", "tests/temp_rag_test/Library/Test_ID.pdf", '{"ok": true}'),
    )
    conn.commit()

    candidates = select_archive_candidates(conn)

    assert [candidate.paper_id for candidate in candidates] == ["paper-e2e-001", "test_local_id"]
    assert [candidate.fixture_reason for candidate in candidates] == [
        "fixture_visibility_rule",
        "paper_id_test_prefix",
    ]
    assert all(candidate.archive_reason == "fixture_no_feedback_json" for candidate in candidates)


def test_apply_archive_moves_fixture_rows_and_keeps_non_fixture_rows():
    conn = sqlite3.connect(":memory:")
    _create_papers_table(conn)
    conn.execute(
        """
        INSERT INTO papers (paper_id, title, status, pdf_path, feedback_json)
        VALUES (?, ?, ?, ?, ?)
        """,
        ("paper-e2e-001", "E2E Seed Paper", "NEW", "tests/temp_rag_test/Library/Test_ID.pdf", None),
    )
    conn.execute(
        """
        INSERT INTO papers (paper_id, title, status, pdf_path, feedback_json)
        VALUES (?, ?, ?, ?, ?)
        """,
        ("paper-real-001", "Real Paper", "INDEXED", "/tmp/real.pdf", None),
    )
    conn.commit()

    candidates = select_archive_candidates(conn)
    archived = apply_archive(conn, candidates)

    assert archived == 1
    remaining_ids = {row[0] for row in conn.execute("SELECT paper_id FROM papers")}
    archived_row = conn.execute(
        """
        SELECT paper_id, title, status, fixture_reason, archive_reason, row_json
        FROM fixture_papers_archive
        """
    ).fetchone()

    assert remaining_ids == {"paper-real-001"}
    assert archived_row[0:5] == (
        "paper-e2e-001",
        "E2E Seed Paper",
        "NEW",
        "fixture_visibility_rule",
        "fixture_no_feedback_json",
    )
    archived_payload = json.loads(archived_row[5])
    assert archived_payload["paper_id"] == "paper-e2e-001"
