import base64

from fastapi.testclient import TestClient

import src.db_utils as db_utils
from backend import main as api_main
from src.services.event_log import list_request_audits


def _init_temp_db(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    db_utils.init_db()
    conn = db_utils.get_db_connection()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS papers (
            paper_id TEXT PRIMARY KEY,
            doi TEXT,
            title TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'NEW',
            pdf_path TEXT,
            summary TEXT,
            feedback_json TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.commit()
    conn.close()
    return original_db_path


def _browser_headers(*, forwarded_for: str | None = None, origin: str = "http://testserver") -> dict[str, str]:
    headers = {"origin": origin}
    if forwarded_for:
        headers["x-forwarded-for"] = forwarded_for
    return headers


def _basic_auth_headers(password: str, username: str = "beta") -> dict[str, str]:
    token = base64.b64encode(f"{username}:{password}".encode("utf-8")).decode("ascii")
    return {"Authorization": f"Basic {token}"}


def test_browser_write_rate_limit_returns_429_and_logs_audit_rows(tmp_path, monkeypatch):
    monkeypatch.setenv("LATTICE_BROWSER_WRITE_RATE_LIMIT_COUNT", "2")
    monkeypatch.setenv("LATTICE_BROWSER_WRITE_RATE_LIMIT_WINDOW_SECONDS", "60")
    monkeypatch.setenv("LATTICE_TRUSTED_PROXY_IPS", "testclient")
    monkeypatch.delenv("LATTICE_BROWSER_AUDIT_LOGGING", raising=False)
    original_db_path = _init_temp_db(tmp_path, monkeypatch)
    try:
        client = TestClient(api_main.app)
        headers = _browser_headers(forwarded_for="10.0.0.8")

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


def test_browser_read_rate_limit_returns_429_and_logs_audit_rows(tmp_path, monkeypatch):
    monkeypatch.setenv("LATTICE_BETA_PASSWORD", "beta-pass")
    monkeypatch.setenv("LATTICE_BROWSER_READ_RATE_LIMIT_COUNT", "2")
    monkeypatch.setenv("LATTICE_BROWSER_READ_RATE_LIMIT_WINDOW_SECONDS", "60")
    monkeypatch.delenv("LATTICE_BROWSER_AUDIT_LOGGING", raising=False)
    original_db_path = _init_temp_db(tmp_path, monkeypatch)
    try:
        client = TestClient(api_main.app)
        headers = _basic_auth_headers("beta-pass")

        first = client.get("/api/papers", headers=headers)
        second = client.get("/api/papers", headers=headers)
        third = client.get("/api/papers", headers=headers)

        assert first.status_code == 200
        assert second.status_code == 200
        assert third.status_code == 429
        payload = third.json()
        assert payload["error_code"] == "BROWSER_READ_RATE_LIMITED"
        assert payload["retry_after_seconds"] >= 1
        assert third.headers["retry-after"] == str(payload["retry_after_seconds"])

        audits = list_request_audits(path="/api/papers", source="browser_api", limit=10)
        assert len(audits) == 1
        assert audits[0]["outcome"] == "rate_limited"
        assert audits[0]["payload"]["scope"] == "browser_read"
    finally:
        db_utils.DB_PATH = original_db_path


def test_direct_protected_read_rate_limit_returns_429_and_logs_audit_rows(tmp_path, monkeypatch):
    monkeypatch.setenv("LATTICE_BETA_PASSWORD", "beta-pass")
    monkeypatch.setenv("LATTICE_API_KEY", "secret-key")
    monkeypatch.setenv("LATTICE_BROWSER_READ_RATE_LIMIT_COUNT", "2")
    monkeypatch.setenv("LATTICE_BROWSER_READ_RATE_LIMIT_WINDOW_SECONDS", "60")
    monkeypatch.delenv("LATTICE_BROWSER_AUDIT_LOGGING", raising=False)
    original_db_path = _init_temp_db(tmp_path, monkeypatch)
    try:
        client = TestClient(api_main.app)
        headers = {
            **_basic_auth_headers("beta-pass"),
            "X-API-Key": "secret-key",
        }

        first = client.get("/papers", headers=headers)
        second = client.get("/papers", headers=headers)
        third = client.get("/papers", headers=headers)

        assert first.status_code == 200
        assert second.status_code == 200
        assert third.status_code == 429
        payload = third.json()
        assert payload["error_code"] == "PROTECTED_READ_RATE_LIMITED"
        assert payload["retry_after_seconds"] >= 1
        assert third.headers["retry-after"] == str(payload["retry_after_seconds"])

        audits = list_request_audits(path="/papers", source="protected_api", limit=10)
        assert len(audits) == 1
        assert audits[0]["outcome"] == "rate_limited"
        assert audits[0]["payload"]["scope"] == "protected_read"
    finally:
        db_utils.DB_PATH = original_db_path


def test_direct_protected_write_rate_limit_returns_429_and_logs_audit_rows(tmp_path, monkeypatch):
    monkeypatch.setenv("LATTICE_BETA_PASSWORD", "beta-pass")
    monkeypatch.setenv("LATTICE_API_KEY", "secret-key")
    monkeypatch.setenv("LATTICE_BROWSER_WRITE_RATE_LIMIT_COUNT", "2")
    monkeypatch.setenv("LATTICE_BROWSER_WRITE_RATE_LIMIT_WINDOW_SECONDS", "60")
    monkeypatch.delenv("LATTICE_BROWSER_AUDIT_LOGGING", raising=False)
    original_db_path = _init_temp_db(tmp_path, monkeypatch)
    try:
        client = TestClient(api_main.app)
        headers = {
            **_basic_auth_headers("beta-pass"),
            "X-API-Key": "secret-key",
        }

        first = client.post("/jobs/deepread", json={"paper_id": "paper_direct_write_001"}, headers=headers)
        second = client.post("/jobs/deepread", json={"paper_id": "paper_direct_write_002"}, headers=headers)
        third = client.post("/jobs/deepread", json={"paper_id": "paper_direct_write_003"}, headers=headers)

        assert first.status_code == 200
        assert second.status_code == 200
        assert third.status_code == 429
        payload = third.json()
        assert payload["error_code"] == "PROTECTED_WRITE_RATE_LIMITED"
        assert payload["retry_after_seconds"] >= 1
        assert third.headers["retry-after"] == str(payload["retry_after_seconds"])

        audits = list_request_audits(path="/jobs/deepread", source="protected_api", limit=10)
        assert len(audits) == 1
        assert audits[0]["outcome"] == "rate_limited"
        assert audits[0]["payload"]["scope"] == "protected_write"
    finally:
        db_utils.DB_PATH = original_db_path


def test_beta_ip_allowlist_denials_are_logged_to_request_audit(tmp_path, monkeypatch):
    monkeypatch.setenv("LATTICE_BETA_PASSWORD", "beta-pass")
    monkeypatch.setenv("LATTICE_BETA_ALLOWED_IPS", "10.0.0.0/24")
    monkeypatch.setenv("LATTICE_TRUSTED_PROXY_IPS", "testclient")
    monkeypatch.delenv("LATTICE_BROWSER_AUDIT_LOGGING", raising=False)
    original_db_path = _init_temp_db(tmp_path, monkeypatch)
    try:
        client = TestClient(api_main.app)

        blocked = client.get("/ui", headers={"x-forwarded-for": "203.0.113.25"})
        assert blocked.status_code == 403
        assert blocked.json()["error_code"] == "IP_NOT_ALLOWED"

        audits = list_request_audits(path="/ui", source="access_policy", limit=10)
        assert len(audits) == 1
        assert audits[0]["outcome"] == "ip_denied"
        assert audits[0]["status_code"] == 403
        assert audits[0]["payload"]["scope"] == "ip_allowlist"
    finally:
        db_utils.DB_PATH = original_db_path


def test_forwarded_for_is_ignored_without_trusted_proxy_configuration(tmp_path, monkeypatch):
    monkeypatch.setenv("LATTICE_BROWSER_AUDIT_LOGGING", "true")
    monkeypatch.delenv("LATTICE_TRUSTED_PROXY_IPS", raising=False)
    original_db_path = _init_temp_db(tmp_path, monkeypatch)
    try:
        client = TestClient(api_main.app)

        response = client.post(
            "/api/jobs/deepread",
            json={"paper_id": "paper_forwarded_ignored_001"},
            headers=_browser_headers(forwarded_for="10.0.0.8"),
        )
        assert response.status_code == 200

        audits = list_request_audits(path="/api/jobs/deepread", source="browser_api", limit=10)
        assert len(audits) == 1
        assert audits[0]["client_ip"] == "testclient"
    finally:
        db_utils.DB_PATH = original_db_path


def test_cross_origin_browser_write_is_rejected_and_logged(tmp_path, monkeypatch):
    monkeypatch.setenv("LATTICE_BROWSER_AUDIT_LOGGING", "true")
    original_db_path = _init_temp_db(tmp_path, monkeypatch)
    try:
        client = TestClient(api_main.app)

        response = client.post(
            "/api/jobs/deepread",
            json={"paper_id": "paper_cross_origin_001"},
            headers=_browser_headers(origin="https://evil.example"),
        )
        assert response.status_code == 403
        assert response.json()["error_code"] == "FORBIDDEN"

        audits = list_request_audits(path="/api/jobs/deepread", source="browser_security", limit=10)
        assert len(audits) == 1
        assert audits[0]["outcome"] == "origin_denied"
        assert audits[0]["status_code"] == 403
        assert audits[0]["payload"]["scope"] == "browser_origin"
    finally:
        db_utils.DB_PATH = original_db_path


def test_loopback_dev_origin_is_allowed_for_browser_write(tmp_path, monkeypatch):
    monkeypatch.setenv("LATTICE_BROWSER_AUDIT_LOGGING", "true")
    original_db_path = _init_temp_db(tmp_path, monkeypatch)
    try:
        client = TestClient(api_main.app, base_url="http://127.0.0.1:18080")

        response = client.post(
            "/api/jobs/deepread",
            json={"paper_id": "paper_loopback_origin_001"},
            headers=_browser_headers(origin="http://127.0.0.1:43174"),
        )
        assert response.status_code == 200

        audits = list_request_audits(path="/api/jobs/deepread", source="browser_api", limit=10)
        assert len(audits) == 1
        assert audits[0]["outcome"] == "allowed"
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
