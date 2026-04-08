import os
from pathlib import Path

from fastapi.testclient import TestClient

os.environ.setdefault(
    "PAPERPIPE_CONFIG_PATH",
    str(Path(__file__).resolve().parents[1] / "config.example.yaml"),
)

import src.db_utils as db_utils
from backend import main as api_main
from src.services.event_log import list_request_audits


def _init_temp_db(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    db_utils.init_db()
    return original_db_path


def test_browser_write_rate_limit_returns_429_and_logs_audit_rows(tmp_path, monkeypatch):
    monkeypatch.setenv("LATTICE_BROWSER_WRITE_RATE_LIMIT_COUNT", "2")
    monkeypatch.setenv("LATTICE_BROWSER_WRITE_RATE_LIMIT_WINDOW_SECONDS", "60")
    monkeypatch.delenv("LATTICE_BROWSER_AUDIT_LOGGING", raising=False)
    original_db_path = _init_temp_db(tmp_path, monkeypatch)
    try:
        client = TestClient(api_main.app)
        headers = {"x-forwarded-for": "10.0.0.8"}

        first = client.post("/api/jobs/deepread", json={"paper_id": "paper_throttle_001"}, headers=headers)
        second = client.post("/api/jobs/deepread", json={"paper_id": "paper_throttle_002"}, headers=headers)
        third = client.post("/api/jobs/deepread", json={"paper_id": "paper_throttle_003"}, headers=headers)

        assert first.status_code == 200
        assert second.status_code == 200
        assert third.status_code == 429
        payload = third.json()
        assert payload["error_code"] == "BROWSER_WRITE_RATE_LIMITED"
        assert payload["retry_after_seconds"] >= 1
        assert third.headers["retry-after"] == str(payload["retry_after_seconds"])

        audits = list_request_audits(path="/api/jobs/deepread", source="browser_api", limit=10)
        assert len(audits) == 3
        outcomes = [item["outcome"] for item in audits]
        assert outcomes.count("allowed") == 2
        assert outcomes.count("rate_limited") == 1
        assert any(item["client_ip"] == "10.0.0.8" for item in audits)
    finally:
        db_utils.DB_PATH = original_db_path


def test_beta_auth_denied_requests_are_logged_to_request_audit(tmp_path, monkeypatch):
    monkeypatch.setenv("LATTICE_BETA_PASSWORD", "beta-pass")
    monkeypatch.delenv("LATTICE_BROWSER_AUDIT_LOGGING", raising=False)
    original_db_path = _init_temp_db(tmp_path, monkeypatch)
    try:
        client = TestClient(api_main.app)

        blocked = client.get("/ui")
        assert blocked.status_code == 401

        audits = list_request_audits(path="/ui", source="browser_security", limit=10)
        assert len(audits) == 1
        assert audits[0]["outcome"] == "beta_auth_denied"
        assert audits[0]["status_code"] == 401
        assert audits[0]["payload"]["scope"] == "beta_gate"
    finally:
        db_utils.DB_PATH = original_db_path
