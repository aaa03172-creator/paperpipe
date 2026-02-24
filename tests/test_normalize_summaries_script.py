import sqlite3

from scripts.normalize_summaries import apply_candidates, collect_candidates


def _create_papers_table(conn: sqlite3.Connection, with_updated_at: bool = True) -> None:
    if with_updated_at:
        conn.execute(
            """
            CREATE TABLE papers (
                paper_id TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                summary TEXT,
                pdf_path TEXT,
                updated_at TEXT
            )
            """
        )
    else:
        conn.execute(
            """
            CREATE TABLE papers (
                paper_id TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                summary TEXT,
                pdf_path TEXT
            )
            """
        )


def test_collect_and_apply_candidates_updates_only_changed_rows():
    conn = sqlite3.connect(":memory:")
    _create_papers_table(conn, with_updated_at=True)
    conn.execute(
        "INSERT INTO papers (paper_id, status, summary, pdf_path, updated_at) VALUES (?, ?, ?, ?, datetime('now'))",
        ("p1", "APPROVED", "요약입니다. (Translation: summary)", "/tmp/p1.pdf"),
    )
    conn.execute(
        "INSERT INTO papers (paper_id, status, summary, pdf_path, updated_at) VALUES (?, ?, ?, ?, datetime('now'))",
        ("p2", "APPROVED", "정상 요약 문장입니다.", "/tmp/p2.pdf"),
    )
    conn.commit()

    candidates = collect_candidates(conn, statuses=["APPROVED"], max_chars=320)
    assert len(candidates) == 1
    assert candidates[0].paper_id == "p1"

    updated = apply_candidates(conn, candidates)
    assert updated == 1

    row1 = conn.execute("SELECT summary FROM papers WHERE paper_id = 'p1'").fetchone()
    row2 = conn.execute("SELECT summary FROM papers WHERE paper_id = 'p2'").fetchone()
    assert row1 is not None and "Translation:" not in row1[0]
    assert row2 is not None and row2[0] == "정상 요약 문장입니다."

    # Idempotent: no remaining candidates.
    candidates_second = collect_candidates(conn, statuses=["APPROVED"], max_chars=320)
    assert candidates_second == []


def test_apply_candidates_works_without_updated_at_column():
    conn = sqlite3.connect(":memory:")
    _create_papers_table(conn, with_updated_at=False)
    conn.execute(
        "INSERT INTO papers (paper_id, status, summary, pdf_path) VALUES (?, ?, ?, ?)",
        ("p_no_ts", "INDEXED", "Here is a possible TL;DR in one single Korean sentence: 요약문", "/tmp/p_no_ts.pdf"),
    )
    conn.commit()

    candidates = collect_candidates(conn, statuses=["INDEXED"], max_chars=320)
    assert len(candidates) == 1

    updated = apply_candidates(conn, candidates)
    assert updated == 1

    row = conn.execute("SELECT summary FROM papers WHERE paper_id = 'p_no_ts'").fetchone()
    assert row is not None
    assert "Here is a possible TL;DR" not in row[0]


def test_collect_candidates_respects_paper_id_filter():
    conn = sqlite3.connect(":memory:")
    _create_papers_table(conn, with_updated_at=True)
    conn.execute(
        "INSERT INTO papers (paper_id, status, summary, pdf_path, updated_at) VALUES (?, ?, ?, ?, datetime('now'))",
        ("p1", "APPROVED", "요약 A (Translation: a)", "/tmp/a.pdf"),
    )
    conn.execute(
        "INSERT INTO papers (paper_id, status, summary, pdf_path, updated_at) VALUES (?, ?, ?, ?, datetime('now'))",
        ("p2", "APPROVED", "요약 B (Translation: b)", "/tmp/b.pdf"),
    )
    conn.commit()

    candidates = collect_candidates(conn, statuses=["APPROVED"], max_chars=320, paper_ids={"p2"})
    assert len(candidates) == 1
    assert candidates[0].paper_id == "p2"


def test_collect_candidates_excludes_test_fixtures_by_default():
    conn = sqlite3.connect(":memory:")
    _create_papers_table(conn, with_updated_at=True)
    conn.execute(
        "INSERT INTO papers (paper_id, status, summary, pdf_path, updated_at) VALUES (?, ?, ?, ?, datetime('now'))",
        ("phase0_test", "INDEXED", "Here is a possible TL;DR in one single Korean sentence: 요약문", "tests/data/a.pdf"),
    )
    conn.commit()

    candidates = collect_candidates(conn, statuses=["INDEXED"], max_chars=320)
    assert candidates == []

    included = collect_candidates(
        conn,
        statuses=["INDEXED"],
        max_chars=320,
        include_test_fixtures=True,
    )
    assert len(included) == 1
    assert included[0].paper_id == "phase0_test"
