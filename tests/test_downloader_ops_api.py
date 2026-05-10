import json
import sqlite3
from pathlib import Path

from fastapi.testclient import TestClient

import src.db_utils as db_utils
from backend import main as api_main


def test_downloader_ops_metrics_endpoint_handles_missing_attempt_column(tmp_path: Path, monkeypatch):
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
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            INSERT INTO papers (paper_id, title, status, pdf_path, updated_at)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            ("p1", "Paper 1", "APPROVED", None),
        )
        conn.commit()
        conn.close()

        client = TestClient(api_main.app)
        res = client.get("/ops/downloader-metrics?hours=24")
        assert res.status_code == 200
        payload = res.json()

        assert payload["metrics"]["db_exists"] is True
        assert payload["metrics"]["paper_rows"] == 1
        assert payload["metrics"]["has_download_attempts_column"] is False
        assert payload["metrics"]["attempt_rows"] == 0
        assert payload["alerts"] == []
    finally:
        db_utils.DB_PATH = original_db_path


def test_downloader_ops_metrics_endpoint_counts_retry_and_alerts(tmp_path: Path, monkeypatch):
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
                download_attempts TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        attempts = [
            {"provider": "unpaywall", "status": "rate_limit", "retry_no": 0, "will_retry": True},
            {"provider": "unpaywall", "status": "rate_limit", "retry_no": 1, "will_retry": True},
            {"provider": "unpaywall", "status": "rate_limit", "retry_no": 2, "will_retry": False},
        ]
        conn.execute(
            """
            INSERT INTO papers (paper_id, title, status, pdf_path, download_attempts, updated_at)
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            ("p_rate", "Rate limited", "APPROVED", None, json.dumps(attempts)),
        )
        conn.commit()
        conn.close()

        client = TestClient(api_main.app)
        res = client.get("/ops/downloader-metrics?hours=24&rate_limit_warn=2")
        assert res.status_code == 200
        payload = res.json()
        metrics = payload["metrics"]

        assert metrics["has_download_attempts_column"] is True
        assert metrics["attempt_rows"] == 1
        assert metrics["status_counts"]["rate_limit"] == 3
        assert metrics["retry_attempts_total"] == 2
        assert metrics["rate_limit_retry_signals"] == 2
        assert metrics["rate_limit_exhausted"] == 1
        assert metrics["retry_attempts_by_provider"]["unpaywall"] == 2
        assert any("rate_limit count 3 >= warn threshold 2" in msg for msg in payload["alerts"])
    finally:
        db_utils.DB_PATH = original_db_path
