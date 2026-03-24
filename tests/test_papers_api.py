import json
from pathlib import Path

from fastapi.testclient import TestClient

import src.db_utils as db_utils
from backend import main as api_main


def _write_artifact_run(path: Path, *, claimset: dict | None = None, stats_report: dict | None = None) -> None:
    path.mkdir(parents=True, exist_ok=True)
    if claimset is not None:
        (path / "claimset.resolved.json").write_text(json.dumps(claimset), encoding="utf-8")
    if stats_report is not None:
        (path / "stats_report.json").write_text(json.dumps(stats_report), encoding="utf-8")


def test_papers_detail_includes_pdf_exists_and_missing_status(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PAPERPIPE_ARTIFACTS_DIR", str(tmp_path / "storage" / "artifacts"))

    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()
        conn = db_utils.get_db_connection()
        conn.execute(
            """
            CREATE TABLE papers (
                paper_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                status TEXT NOT NULL,
                pdf_path TEXT,
                pdf_status TEXT,
                summary TEXT,
                created_at TIMESTAMP,
                updated_at TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            INSERT INTO papers (paper_id, title, status, pdf_path, summary, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            (
                "p_missing_pdf",
                "Missing PDF Paper",
                "INDEXED",
                str(tmp_path / "no_such_file.pdf"),
                "summary",
            ),
        )
        existing_pdf = tmp_path / "existing.pdf"
        existing_pdf.write_text("%PDF", encoding="utf-8")
        conn.execute(
            """
            INSERT INTO papers (paper_id, title, status, pdf_path, summary, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            (
                "p_has_pdf",
                "Has PDF Paper",
                "INDEXED",
                str(existing_pdf),
                "summary",
            ),
        )
        conn.commit()
        conn.close()

        client = TestClient(api_main.app)

        detail_missing = client.get("/papers/p_missing_pdf")
        assert detail_missing.status_code == 200
        payload_missing = detail_missing.json()
        assert payload_missing["paper_id"] == "p_missing_pdf"
        assert payload_missing["pdf_exists"] is False
        assert payload_missing["pdf_status"] == "missing"

        detail_ok = client.get("/papers/p_has_pdf")
        assert detail_ok.status_code == 200
        payload_ok = detail_ok.json()
        assert payload_ok["paper_id"] == "p_has_pdf"
        assert payload_ok["pdf_exists"] is True
        assert payload_ok["ops_summary"] is None

        missing = client.get("/papers/nope")
        assert missing.status_code == 404

        listing = client.get("/papers")
        assert listing.status_code == 200
        rows = listing.json()
        by_id = {row["paper_id"]: row for row in rows}
        assert by_id["p_missing_pdf"]["pdf_exists"] is False
        assert by_id["p_missing_pdf"]["pdf_status"] == "missing"
        assert by_id["p_has_pdf"]["pdf_exists"] is True
        assert by_id["p_has_pdf"]["pdf_status"] is None
        assert by_id["p_has_pdf"]["ops_summary"] is None
    finally:
        db_utils.DB_PATH = original_db_path


def test_papers_list_is_limited_and_sorted_by_updated_at(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PAPERPIPE_ARTIFACTS_DIR", str(tmp_path / "storage" / "artifacts"))

    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()
        conn = db_utils.get_db_connection()
        conn.execute(
            """
            CREATE TABLE papers (
                paper_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                status TEXT NOT NULL,
                pdf_path TEXT,
                pdf_status TEXT,
                summary TEXT,
                created_at TIMESTAMP,
                updated_at TIMESTAMP
            )
            """
        )
        for idx in range(60):
            conn.execute(
                """
                INSERT INTO papers (paper_id, title, status, pdf_path, summary, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    f"p_{idx:02d}",
                    f"Paper {idx:02d}",
                    "INDEXED",
                    None,
                    "summary",
                    f"2026-02-01 00:{idx % 60:02d}:00",
                    f"2026-02-01 00:{idx % 60:02d}:00",
                ),
            )
        conn.commit()
        conn.close()

        client = TestClient(api_main.app)
        listing = client.get("/papers")

        assert listing.status_code == 200
        rows = listing.json()
        assert len(rows) == 50
        assert rows[0]["paper_id"] == "p_59"
        assert rows[-1]["paper_id"] == "p_10"
        assert rows[0]["pdf_exists"] is False
        assert rows[0]["pdf_status"] is None
    finally:
        db_utils.DB_PATH = original_db_path


def test_papers_endpoints_include_operational_summary_from_artifacts(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    artifacts_dir = tmp_path / "storage" / "artifacts"
    monkeypatch.setenv("PAPERPIPE_ARTIFACTS_DIR", str(artifacts_dir))

    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()
        conn = db_utils.get_db_connection()
        conn.execute(
            """
            CREATE TABLE papers (
                paper_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                status TEXT NOT NULL,
                pdf_path TEXT,
                pdf_status TEXT,
                summary TEXT,
                created_at TIMESTAMP,
                updated_at TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            INSERT INTO papers (paper_id, title, status, summary, created_at, updated_at)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            ("paper_ops_healthy", "Healthy Paper", "INDEXED", "summary"),
        )
        conn.execute(
            """
            INSERT INTO papers (paper_id, title, status, summary, created_at, updated_at)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            ("paper_ops_missing", "Missing Stats Paper", "INDEXED", "summary"),
        )
        conn.commit()
        conn.close()

        _write_artifact_run(
            artifacts_dir / "paper_ops_healthy" / "run-healthy",
            claimset={"claims": [{"claim_id": "c1"}]},
            stats_report={"checks": [{"id": "check-1"}, {"id": "check-2"}]},
        )
        _write_artifact_run(
            artifacts_dir / "paper_ops_missing" / "run-missing",
            claimset={"claims": [{"claim_id": "c1"}]},
            stats_report={"checks": []},
        )

        client = TestClient(api_main.app)

        listing = client.get("/papers")
        assert listing.status_code == 200
        by_id = {row["paper_id"]: row for row in listing.json()}
        assert by_id["paper_ops_healthy"]["ops_summary"]["state"] == "healthy"
        assert by_id["paper_ops_healthy"]["ops_summary"]["stats_check_count"] == 2
        assert by_id["paper_ops_healthy"]["latest_run_id"] == "run-healthy"
        assert by_id["paper_ops_missing"]["ops_summary"]["state"] == "action_needed"
        assert by_id["paper_ops_missing"]["ops_summary"]["reason"] == "Stats report is missing or empty."
        assert by_id["paper_ops_missing"]["latest_run_id"] == "run-missing"

        detail = client.get("/papers/paper_ops_missing")
        assert detail.status_code == 200
        payload = detail.json()
        assert payload["ops_summary"]["recommended_action"] == "repair_stats"
        assert payload["ops_summary"]["latest_run_id"] == "run-missing"
        assert payload["latest_run_id"] == "run-missing"
    finally:
        db_utils.DB_PATH = original_db_path


def test_papers_endpoints_surface_latest_run_id_from_jobs_when_ops_summary_is_absent(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    artifacts_dir = tmp_path / "storage" / "artifacts"
    monkeypatch.setenv("PAPERPIPE_ARTIFACTS_DIR", str(artifacts_dir))

    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()
        conn = db_utils.get_db_connection()
        conn.execute(
            """
            CREATE TABLE papers (
                paper_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                status TEXT NOT NULL,
                pdf_path TEXT,
                pdf_status TEXT,
                summary TEXT,
                created_at TIMESTAMP,
                updated_at TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            INSERT INTO papers (paper_id, title, status, summary, created_at, updated_at)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            ("paper_job_only", "Job-backed Paper", "INDEXED", "summary"),
        )
        run_dir = artifacts_dir / "paper_job_only" / "run-job-only"
        run_dir.mkdir(parents=True, exist_ok=True)
        conn.execute(
            """
            INSERT INTO jobs (job_id, run_id, paper_id, status, artifact_dir, created_at)
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            ("job-001", "run-job-only", "paper_job_only", "completed", str(run_dir)),
        )
        conn.commit()
        conn.close()

        client = TestClient(api_main.app)

        listing = client.get("/papers")
        assert listing.status_code == 200
        by_id = {row["paper_id"]: row for row in listing.json()}
        assert by_id["paper_job_only"]["ops_summary"] is None
        assert by_id["paper_job_only"]["latest_run_id"] == "run-job-only"

        detail = client.get("/papers/paper_job_only")
        assert detail.status_code == 200
        payload = detail.json()
        assert payload["ops_summary"] is None
        assert payload["latest_run_id"] == "run-job-only"
    finally:
        db_utils.DB_PATH = original_db_path


def test_papers_endpoints_include_content_review_state(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PAPERPIPE_ARTIFACTS_DIR", str(tmp_path / "storage" / "artifacts"))

    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()
        conn = db_utils.get_db_connection()
        conn.execute(
            """
            CREATE TABLE papers (
                paper_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                status TEXT NOT NULL,
                pdf_path TEXT,
                pdf_status TEXT,
                summary TEXT,
                issues INTEGER,
                issues_label TEXT,
                issues_state TEXT,
                created_at TIMESTAMP,
                updated_at TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            INSERT INTO papers (paper_id, title, status, issues, issues_label, issues_state, summary, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            ("paper_flagged", "Flagged Paper", "INDEXED", 2, "2 mapping ambiguities", None, "summary"),
        )
        conn.execute(
            """
            INSERT INTO papers (paper_id, title, status, issues, issues_label, issues_state, summary, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            ("paper_clear", "Clear Paper", "INDEXED", 0, "No critical issues", None, "summary"),
        )
        conn.execute(
            """
            INSERT INTO papers (paper_id, title, status, issues, issues_label, issues_state, summary, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            ("paper_unavailable", "Unavailable Paper", "INDEXED", 0, "Not analyzed", None, "summary"),
        )
        conn.execute(
            """
            INSERT INTO papers (paper_id, title, status, issues, issues_label, issues_state, summary, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            ("paper_explicit", "Explicit State Paper", "INDEXED", 0, "No critical issues", "unavailable", "summary"),
        )
        conn.execute(
            """
            INSERT INTO papers (paper_id, title, status, summary, created_at, updated_at)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            ("paper_new", "New Paper", "NEW", "summary"),
        )
        conn.execute(
            """
            INSERT INTO papers (paper_id, title, status, summary, created_at, updated_at)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            ("paper_pending", "Pending Paper", "PENDING_REVIEW", "summary"),
        )
        conn.execute(
            """
            INSERT INTO papers (paper_id, title, status, summary, created_at, updated_at)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            ("paper_approved", "Approved Paper", "APPROVED", "summary"),
        )
        conn.commit()
        conn.close()

        client = TestClient(api_main.app)

        listing = client.get("/papers")
        assert listing.status_code == 200
        by_id = {row["paper_id"]: row for row in listing.json()}
        assert by_id["paper_flagged"]["issues_state"] == "flagged"
        assert by_id["paper_clear"]["issues_state"] == "clear"
        assert by_id["paper_unavailable"]["issues_state"] == "unavailable"
        assert by_id["paper_explicit"]["issues_state"] == "unavailable"
        assert by_id["paper_new"]["issues_state"] == "unavailable"
        assert by_id["paper_pending"]["issues_state"] == "flagged"
        assert by_id["paper_approved"]["issues_state"] == "clear"

        detail = client.get("/papers/paper_unavailable")
        assert detail.status_code == 200
        payload = detail.json()
        assert payload["issues_label"] == "Not analyzed"
        assert payload["issues_state"] == "unavailable"

        explicit_detail = client.get("/papers/paper_explicit")
        assert explicit_detail.status_code == 200
        explicit_payload = explicit_detail.json()
        assert explicit_payload["issues_label"] == "No critical issues"
        assert explicit_payload["issues_state"] == "unavailable"
    finally:
        db_utils.DB_PATH = original_db_path


def test_init_db_backfills_paper_issues_state_column(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        conn = db_utils.sqlite3.connect(db_utils.DB_PATH)
        conn.execute(
            """
            CREATE TABLE papers (
                paper_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                status TEXT NOT NULL,
                summary TEXT,
                created_at TIMESTAMP,
                updated_at TIMESTAMP
            )
            """
        )
        conn.commit()
        conn.close()

        db_utils.init_db()

        conn = db_utils.get_db_connection()
        columns = {row[1] for row in conn.execute("PRAGMA table_info(papers)").fetchall()}
        conn.close()

        assert "issues_state" in columns
    finally:
        db_utils.DB_PATH = original_db_path


def test_paper_pdf_endpoint_serves_existing_file_and_handles_missing(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()
        conn = db_utils.get_db_connection()
        conn.execute(
            """
            CREATE TABLE papers (
                paper_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                status TEXT NOT NULL,
                pdf_path TEXT,
                pdf_status TEXT,
                summary TEXT,
                created_at TIMESTAMP,
                updated_at TIMESTAMP
            )
            """
        )
        existing_pdf = tmp_path / "served.pdf"
        existing_pdf.write_bytes(b"%PDF-1.4\n%test\n")
        conn.execute(
            """
            INSERT INTO papers (paper_id, title, status, pdf_path, summary, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            ("p_served", "Served PDF", "INDEXED", str(existing_pdf), "summary"),
        )
        conn.execute(
            """
            INSERT INTO papers (paper_id, title, status, pdf_path, summary, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            ("p_missing_path", "Missing Path", "INDEXED", "", "summary"),
        )
        conn.execute(
            """
            INSERT INTO papers (paper_id, title, status, pdf_path, summary, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            ("p_missing_file", "Missing File", "INDEXED", str(tmp_path / "gone.pdf"), "summary"),
        )
        conn.commit()
        conn.close()

        client = TestClient(api_main.app)

        served = client.get("/papers/p_served/pdf")
        assert served.status_code == 200
        assert served.headers.get("content-type", "").startswith("application/pdf")
        assert served.content.startswith(b"%PDF")

        missing_path = client.get("/papers/p_missing_path/pdf")
        assert missing_path.status_code == 404
        assert "PDF path not registered" in missing_path.json()["detail"]

        missing_file = client.get("/papers/p_missing_file/pdf")
        assert missing_file.status_code == 404
        assert "PDF file not found" in missing_file.json()["detail"]

        missing_paper = client.get("/papers/nope/pdf")
        assert missing_paper.status_code == 404
        assert missing_paper.json()["detail"] == "Paper not found"
    finally:
        db_utils.DB_PATH = original_db_path
