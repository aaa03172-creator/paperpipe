import sqlite3
from pathlib import Path
from types import SimpleNamespace

import src.db_utils as db_utils
import src.downloads_watcher as downloads_watcher
from src.downloads_watcher import process_downloaded_pdf


def _create_tables(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE papers (
            paper_id TEXT PRIMARY KEY,
            doi TEXT,
            title TEXT,
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


def test_downloads_watcher_matches_by_doi_and_updates_db(tmp_path):
    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        conn = db_utils.get_db_connection()
        _create_tables(conn)
        conn.execute(
            """
            INSERT INTO papers (paper_id, doi, title, pdf_status, pdf_path)
            VALUES (?, ?, ?, ?, ?)
            """,
            ("paper_doi_1", "10.1000/xyz123", "Unrelated Title", "manual_required", None),
        )
        conn.commit()
        conn.close()

        downloads_dir = tmp_path / "Downloads"
        storage_dir = tmp_path / "storage" / "pdfs"
        downloads_dir.mkdir(parents=True, exist_ok=True)
        source_pdf = downloads_dir / "10.1000_xyz123.pdf"
        source_pdf.write_bytes(b"%PDF-1.4\n%fake\n")

        result = process_downloaded_pdf(source_pdf, downloads_watch_dir=downloads_dir, pdf_storage_dir=storage_dir)
        assert result.status == "matched_doi"
        assert result.destination is not None
        assert result.destination.exists()
        assert not source_pdf.exists()
        assert result.matched_paper_id == "paper_doi_1"

        conn = db_utils.get_db_connection()
        row = conn.execute(
            "SELECT pdf_status, pdf_path FROM papers WHERE paper_id = ?",
            ("paper_doi_1",),
        ).fetchone()
        qcount = conn.execute("SELECT COUNT(*) FROM review_queue").fetchone()[0]
        conn.close()

        assert row is not None
        assert row["pdf_status"] == "downloaded"
        assert row["pdf_path"] == str(result.destination)
        assert qcount == 0
    finally:
        db_utils.DB_PATH = original_db_path


def test_downloads_watcher_uses_runtime_storage_root_by_default(tmp_path, monkeypatch):
    monkeypatch.setenv("PAPERPIPE_HOME", str(tmp_path / "app-home"))

    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        conn = db_utils.get_db_connection()
        _create_tables(conn)
        conn.execute(
            """
            INSERT INTO papers (paper_id, doi, title, pdf_status, pdf_path)
            VALUES (?, ?, ?, ?, ?)
            """,
            ("paper_runtime_storage", "10.5555/runtime", "Runtime Storage Paper", "manual_required", None),
        )
        conn.commit()
        conn.close()

        downloads_dir = tmp_path / "Downloads"
        downloads_dir.mkdir(parents=True, exist_ok=True)
        source_pdf = downloads_dir / "10.5555_runtime.pdf"
        source_pdf.write_bytes(b"%PDF-1.4\n%runtime\n")

        result = process_downloaded_pdf(source_pdf, downloads_watch_dir=downloads_dir)

        expected_root = (tmp_path / "app-home" / "storage" / "pdfs").resolve()
        assert result.status == "matched_doi"
        assert result.destination is not None
        assert result.destination.parent == expected_root
        assert result.destination.exists()
    finally:
        db_utils.DB_PATH = original_db_path


def test_downloads_watcher_ambiguous_doi_moves_unmatched_and_queues_review(tmp_path):
    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        conn = db_utils.get_db_connection()
        _create_tables(conn)
        conn.execute(
            "INSERT INTO papers (paper_id, doi, title, pdf_status) VALUES (?, ?, ?, ?)",
            ("p_a", "10.2000/abc", "Paper A", "manual_required"),
        )
        conn.execute(
            "INSERT INTO papers (paper_id, doi, title, pdf_status) VALUES (?, ?, ?, ?)",
            ("p_b", "10.2000/abc", "Paper B", "manual_required"),
        )
        conn.commit()
        conn.close()

        downloads_dir = tmp_path / "Downloads"
        storage_dir = tmp_path / "storage" / "pdfs"
        downloads_dir.mkdir(parents=True, exist_ok=True)
        source_pdf = downloads_dir / "10.2000_abc.pdf"
        source_pdf.write_bytes(b"%PDF-1.4\n%fake\n")

        result = process_downloaded_pdf(source_pdf, downloads_watch_dir=downloads_dir, pdf_storage_dir=storage_dir)
        assert result.status == "ambiguous_doi"
        assert result.destination is not None
        assert "_unmatched" in str(result.destination)
        assert result.destination.exists()
        assert not source_pdf.exists()

        conn = db_utils.get_db_connection()
        rows = conn.execute(
            "SELECT paper_id, decision, resolved_at FROM review_queue ORDER BY paper_id"
        ).fetchall()
        row_a = conn.execute("SELECT pdf_status, pdf_path FROM papers WHERE paper_id='p_a'").fetchone()
        row_b = conn.execute("SELECT pdf_status, pdf_path FROM papers WHERE paper_id='p_b'").fetchone()
        conn.close()

        assert len(rows) == 2
        assert rows[0]["paper_id"] == "p_a"
        assert rows[0]["decision"] == "NEEDS_PDF_MATCH"
        assert rows[0]["resolved_at"] is None
        assert rows[1]["paper_id"] == "p_b"
        assert rows[1]["decision"] == "NEEDS_PDF_MATCH"
        assert row_a["pdf_status"] == "manual_required"
        assert row_a["pdf_path"] is None
        assert row_b["pdf_status"] == "manual_required"
        assert row_b["pdf_path"] is None
    finally:
        db_utils.DB_PATH = original_db_path


def test_downloads_watcher_matches_doi_from_pdf_content(tmp_path):
    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        conn = db_utils.get_db_connection()
        _create_tables(conn)
        conn.execute(
            "INSERT INTO papers (paper_id, doi, title, pdf_status) VALUES (?, ?, ?, ?)",
            ("paper_content_doi", "10.7777/content-123", "Content DOI paper", "manual_required"),
        )
        conn.commit()
        conn.close()

        downloads_dir = tmp_path / "Downloads"
        storage_dir = tmp_path / "storage" / "pdfs"
        downloads_dir.mkdir(parents=True, exist_ok=True)
        source_pdf = downloads_dir / "content_doi_paper.pdf"
        source_pdf.write_bytes(b"%PDF-1.4\n1 0 obj << /Producer (doi:10.7777/content-123) >>\n")

        result = process_downloaded_pdf(source_pdf, downloads_watch_dir=downloads_dir, pdf_storage_dir=storage_dir)
        assert result.status == "matched_doi"
        assert result.matched_paper_id == "paper_content_doi"
        assert result.destination is not None and result.destination.exists()

        conn = db_utils.get_db_connection()
        row = conn.execute(
            "SELECT pdf_status, pdf_path FROM papers WHERE paper_id = ?",
            ("paper_content_doi",),
        ).fetchone()
        conn.close()
        assert row["pdf_status"] == "downloaded"
        assert row["pdf_path"] == str(result.destination)
    finally:
        db_utils.DB_PATH = original_db_path


def test_downloads_watcher_rejects_untrusted_pdf_content_doi(tmp_path):
    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        conn = db_utils.get_db_connection()
        _create_tables(conn)
        conn.execute(
            "INSERT INTO papers (paper_id, doi, title, pdf_status) VALUES (?, ?, ?, ?)",
            ("paper_content_doi", "10.7777/content-123", "Rare Longitudinal Study on ABC", "manual_required"),
        )
        conn.commit()
        conn.close()

        downloads_dir = tmp_path / "Downloads"
        storage_dir = tmp_path / "storage" / "pdfs"
        downloads_dir.mkdir(parents=True, exist_ok=True)
        source_pdf = downloads_dir / "unrelated-download.pdf"
        source_pdf.write_bytes(b"%PDF-1.4\n1 0 obj << /Producer (doi:10.7777/content-123) >>\n")

        result = process_downloaded_pdf(source_pdf, downloads_watch_dir=downloads_dir, pdf_storage_dir=storage_dir)
        assert result.status == "unmatched"
        assert result.matched_paper_id is None
        assert result.destination is not None
        assert result.destination.exists()

        conn = db_utils.get_db_connection()
        rows = conn.execute(
            "SELECT paper_id, decision, resolved_at FROM review_queue ORDER BY id"
        ).fetchall()
        conn.close()

        assert len(rows) == 1
        assert rows[0]["paper_id"] == "paper_content_doi"
        assert rows[0]["decision"] == "NEEDS_PDF_MATCH"
        assert rows[0]["resolved_at"] is None
    finally:
        db_utils.DB_PATH = original_db_path


def test_downloads_watcher_unmatched_with_empty_queue_creates_review_entry(tmp_path):
    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        conn = db_utils.get_db_connection()
        _create_tables(conn)
        conn.commit()
        conn.close()

        downloads_dir = tmp_path / "Downloads"
        storage_dir = tmp_path / "storage" / "pdfs"
        downloads_dir.mkdir(parents=True, exist_ok=True)
        source_pdf = downloads_dir / "unknown-download.pdf"
        source_pdf.write_bytes(b"%PDF-1.4\n%fake\n")

        result = process_downloaded_pdf(source_pdf, downloads_watch_dir=downloads_dir, pdf_storage_dir=storage_dir)
        assert result.status == "unmatched"
        assert result.destination is not None
        assert "_unmatched" in str(result.destination)
        assert result.destination.exists()

        conn = db_utils.get_db_connection()
        rows = conn.execute(
            "SELECT paper_id, decision, reason FROM review_queue ORDER BY id"
        ).fetchall()
        conn.close()

        assert len(rows) == 1
        assert rows[0]["paper_id"] == "__UNMATCHED__"
        assert rows[0]["decision"] == "NEEDS_PDF_MATCH"
        assert "manual_required queue empty" in rows[0]["reason"]
    finally:
        db_utils.DB_PATH = original_db_path


def test_downloads_watcher_unmatched_with_canonical_fk_schema_creates_review_entry(tmp_path):
    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        conn = db_utils.get_db_connection()
        conn.execute(
            """
            CREATE TABLE papers (
                paper_id TEXT PRIMARY KEY,
                doi TEXT,
                title TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'NEW',
                pdf_status TEXT,
                summary TEXT,
                source TEXT,
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
                resolution TEXT,
                FOREIGN KEY(paper_id) REFERENCES papers(paper_id)
            )
            """
        )
        conn.commit()
        conn.close()

        downloads_dir = tmp_path / "Downloads"
        storage_dir = tmp_path / "storage" / "pdfs"
        downloads_dir.mkdir(parents=True, exist_ok=True)
        source_pdf = downloads_dir / "unknown-download.pdf"
        source_pdf.write_bytes(b"%PDF-1.4\n%fake\n")

        result = process_downloaded_pdf(source_pdf, downloads_watch_dir=downloads_dir, pdf_storage_dir=storage_dir)
        assert result.status == "unmatched"

        conn = db_utils.get_db_connection()
        paper = conn.execute(
            "SELECT paper_id, title, status FROM papers WHERE paper_id = ?",
            (downloads_watcher.UNMATCHED_SENTINEL_PAPER_ID,),
        ).fetchone()
        queued = conn.execute(
            "SELECT paper_id, decision, reason FROM review_queue ORDER BY id"
        ).fetchall()
        conn.close()

        assert paper is not None
        assert paper["title"] == "Unmatched downloaded PDFs"
        assert paper["status"] == "PENDING_REVIEW"
        assert len(queued) == 1
        assert queued[0]["paper_id"] == downloads_watcher.UNMATCHED_SENTINEL_PAPER_ID
        assert queued[0]["decision"] == "NEEDS_PDF_MATCH"
        assert "manual_required queue empty" in queued[0]["reason"]
    finally:
        db_utils.DB_PATH = original_db_path


def test_downloads_watcher_does_not_duplicate_unmatched_sentinel_open_rows(tmp_path):
    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        conn = db_utils.get_db_connection()
        _create_tables(conn)
        conn.commit()
        conn.close()

        downloads_dir = tmp_path / "Downloads"
        storage_dir = tmp_path / "storage" / "pdfs"
        downloads_dir.mkdir(parents=True, exist_ok=True)
        first_pdf = downloads_dir / "unknown-download-1.pdf"
        second_pdf = downloads_dir / "unknown-download-2.pdf"
        first_pdf.write_bytes(b"%PDF-1.4\n%fake\n")
        second_pdf.write_bytes(b"%PDF-1.4\n%fake\n")

        first = process_downloaded_pdf(first_pdf, downloads_watch_dir=downloads_dir, pdf_storage_dir=storage_dir)
        second = process_downloaded_pdf(second_pdf, downloads_watch_dir=downloads_dir, pdf_storage_dir=storage_dir)
        assert first.status == "unmatched"
        assert second.status == "unmatched"

        conn = db_utils.get_db_connection()
        rows = conn.execute(
            """
            SELECT paper_id, decision, resolved_at
            FROM review_queue
            WHERE paper_id = '__UNMATCHED__' AND decision = 'NEEDS_PDF_MATCH'
            ORDER BY id
            """
        ).fetchall()
        conn.close()

        assert len(rows) == 1
        assert rows[0]["resolved_at"] is None
    finally:
        db_utils.DB_PATH = original_db_path


def test_downloads_watcher_allows_metadata_doi_match_without_title_overlap(tmp_path, monkeypatch):
    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        conn = db_utils.get_db_connection()
        _create_tables(conn)
        conn.execute(
            "INSERT INTO papers (paper_id, doi, title, pdf_status) VALUES (?, ?, ?, ?)",
            ("meta_paper", "10.8888/meta-1", "Highly Specific Study Title", "manual_required"),
        )
        conn.commit()
        conn.close()

        monkeypatch.setattr(
            downloads_watcher,
            "_extract_doi_candidates_from_pdf_content",
            lambda _: [("10.8888/meta-1", "metadata")],
        )

        downloads_dir = tmp_path / "Downloads"
        storage_dir = tmp_path / "storage" / "pdfs"
        downloads_dir.mkdir(parents=True, exist_ok=True)
        source_pdf = downloads_dir / "totally-unrelated-filename.pdf"
        source_pdf.write_bytes(b"%PDF-1.4\n%fake\n")

        result = process_downloaded_pdf(source_pdf, downloads_watch_dir=downloads_dir, pdf_storage_dir=storage_dir)
        assert result.status == "matched_doi"
        assert result.matched_paper_id == "meta_paper"
        assert result.destination is not None and result.destination.exists()
    finally:
        db_utils.DB_PATH = original_db_path


def test_wait_for_stable_file_waits_through_growth(tmp_path, monkeypatch):
    source_pdf = tmp_path / "growing.pdf"
    source_pdf.write_bytes(b"%PDF-1.4\n")
    sleeps = {"count": 0}

    def fake_sleep(_seconds: float) -> None:
        if sleeps["count"] == 0:
            source_pdf.write_bytes(source_pdf.read_bytes() + b"%more\n")
        sleeps["count"] += 1

    monkeypatch.setattr(downloads_watcher.time, "sleep", fake_sleep)

    assert downloads_watcher._wait_for_stable_file(
        source_pdf,
        stable_checks=2,
        interval_seconds=0.01,
        max_wait_seconds=1.0,
    ) is True
    assert sleeps["count"] >= 2


def test_downloads_handler_skips_unstable_pdf(monkeypatch, tmp_path):
    source_pdf = tmp_path / "still-growing.pdf"
    source_pdf.write_bytes(b"%PDF-1.4\n")
    handler = downloads_watcher.DownloadsFileHandler(pdf_storage_dir=tmp_path / "pdfs")

    monkeypatch.setattr(downloads_watcher, "_wait_for_stable_file", lambda _path: False)

    def fail_if_called(*_args, **_kwargs):
        raise AssertionError("unstable PDF should not be processed")

    monkeypatch.setattr(downloads_watcher, "process_downloaded_pdf", fail_if_called)

    handler.on_created(SimpleNamespace(is_directory=False, src_path=str(source_pdf)))
    assert source_pdf.exists()


def test_downloads_handler_ignores_temporary_download_suffix(monkeypatch, tmp_path):
    temp_pdf = tmp_path / "paper.pdf.part"
    temp_pdf.write_bytes(b"%PDF-1.4\n")
    handler = downloads_watcher.DownloadsFileHandler(pdf_storage_dir=tmp_path / "pdfs")

    monkeypatch.setattr(
        downloads_watcher,
        "_wait_for_stable_file",
        lambda _path: (_ for _ in ()).throw(AssertionError("temporary downloads should be ignored")),
    )

    handler.on_created(SimpleNamespace(is_directory=False, src_path=str(temp_pdf)))
    assert temp_pdf.exists()


def test_downloads_handler_processes_pdf_after_temp_file_move(monkeypatch, tmp_path):
    temp_pdf = tmp_path / "paper.pdf.part"
    final_pdf = tmp_path / "paper.pdf"
    temp_pdf.write_bytes(b"%PDF-1.4\n")
    temp_pdf.rename(final_pdf)
    handler = downloads_watcher.DownloadsFileHandler(pdf_storage_dir=tmp_path / "pdfs")

    processed: list[Path] = []
    monkeypatch.setattr(downloads_watcher, "_wait_for_stable_file", lambda path: path == final_pdf)

    def fake_process(path, **_kwargs):
        processed.append(path)
        return SimpleNamespace(status="matched", destination=tmp_path / "pdfs" / path.name)

    monkeypatch.setattr(downloads_watcher, "process_downloaded_pdf", fake_process)

    handler.on_moved(SimpleNamespace(is_directory=False, src_path=str(temp_pdf), dest_path=str(final_pdf)))
    assert processed == [final_pdf]
