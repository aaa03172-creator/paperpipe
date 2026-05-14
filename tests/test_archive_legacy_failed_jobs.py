import sqlite3
from pathlib import Path

from scripts.archive_legacy_failed_jobs import apply_archive, select_archive_candidates


def _create_jobs_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE jobs (
            job_id TEXT PRIMARY KEY,
            run_id TEXT,
            paper_id TEXT,
            status TEXT,
            progress INTEGER,
            stage TEXT,
            created_at TEXT,
            started_at TEXT,
            finished_at TEXT,
            artifact_dir TEXT,
            log_path TEXT,
            error_code TEXT,
            error_message TEXT,
            persona_id TEXT,
            run_verify INTEGER,
            clean_reindex INTEGER,
            run_profile TEXT,
            job_type TEXT,
            params_json TEXT,
            result_ref TEXT,
            error_taxonomy_code TEXT,
            error_detail TEXT,
            metrics_json TEXT
        )
        """
    )


def test_select_archive_candidates_classifies_recovered_and_fixture():
    conn = sqlite3.connect(":memory:")
    _create_jobs_table(conn)
    conn.execute(
        """
        INSERT INTO jobs (job_id, paper_id, status, error_message, created_at, finished_at)
        VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """,
        ("f1", "paper_recovered", "failed", "PDF not found for paper_recovered"),
    )
    conn.execute(
        """
        INSERT INTO jobs (job_id, paper_id, status, created_at, finished_at)
        VALUES (?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """,
        ("c1", "paper_recovered", "completed"),
    )
    conn.execute(
        """
        INSERT INTO jobs (job_id, paper_id, status, error_message, created_at, finished_at)
        VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """,
        ("f2", "paper_unrecovered", "failed", "PDF not found for paper_unrecovered"),
    )
    conn.execute(
        """
        INSERT INTO jobs (job_id, paper_id, status, error_message, created_at, finished_at)
        VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """,
        ("f3", "integration_test_paper", "failed", "anything"),
    )
    conn.commit()

    candidates = select_archive_candidates(conn)
    ids = {c.job_id for c in candidates}
    reasons = {c.job_id: c.reason for c in candidates}

    assert "f1" in ids
    assert "f3" in ids
    assert "f2" not in ids
    assert reasons["f1"] == "pdf_not_found_recovered"
    assert reasons["f3"] == "test_fixture_failed_legacy"


def test_apply_archive_moves_rows_and_keeps_unmatched():
    conn = sqlite3.connect(":memory:")
    _create_jobs_table(conn)
    conn.execute(
        """
        INSERT INTO jobs (job_id, paper_id, status, error_message, created_at, finished_at)
        VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """,
        ("f1", "paper_recovered", "failed", "PDF not found for paper_recovered"),
    )
    conn.execute(
        """
        INSERT INTO jobs (job_id, paper_id, status, created_at, finished_at)
        VALUES (?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """,
        ("c1", "paper_recovered", "completed"),
    )
    conn.execute(
        """
        INSERT INTO jobs (job_id, paper_id, status, error_message, created_at, finished_at)
        VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """,
        ("f2", "paper_unrecovered", "failed", "PDF not found for paper_unrecovered"),
    )
    conn.commit()

    candidates = select_archive_candidates(conn)
    moved = apply_archive(conn, candidates)

    assert moved == 1
    archived_count = conn.execute("SELECT COUNT(*) FROM job_failures_archive").fetchone()[0]
    failed_count = conn.execute("SELECT COUNT(*) FROM jobs WHERE status='failed'").fetchone()[0]
    remaining_failed_ids = {
        row[0] for row in conn.execute("SELECT job_id FROM jobs WHERE status='failed'")
    }

    assert archived_count == 1
    assert failed_count == 1
    assert remaining_failed_ids == {"f2"}

