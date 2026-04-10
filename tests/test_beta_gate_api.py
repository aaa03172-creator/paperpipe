import base64
import importlib

from fastapi.testclient import TestClient

import src.db_utils as db_utils
from backend import main as api_main


def _basic_auth_headers(password: str, username: str = "beta") -> dict[str, str]:
    token = base64.b64encode(f"{username}:{password}".encode("utf-8")).decode("ascii")
    return {"Authorization": f"Basic {token}"}


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


def test_beta_gate_requires_basic_auth_for_browser_surfaces(monkeypatch):
    monkeypatch.setenv("LATTICE_BETA_PASSWORD", "beta-pass")
    monkeypatch.delenv("PAPERPIPE_BETA_PASSWORD", raising=False)

    client = TestClient(api_main.app)

    blocked_ui = client.get("/ui")
    assert blocked_ui.status_code == 401
    assert blocked_ui.headers["www-authenticate"].startswith("Basic ")

    blocked_readiness = client.get("/health/ready")
    assert blocked_readiness.status_code == 401

    blocked_api_readiness = client.get("/api/health/ready")
    assert blocked_api_readiness.status_code == 401

    blocked_root_papers = client.get("/papers")
    assert blocked_root_papers.status_code == 401

    blocked_root_notes = client.get("/paper-notes")
    assert blocked_root_notes.status_code == 401

    public_health = client.get("/health")
    assert public_health.status_code == 200

    headers = _basic_auth_headers("beta-pass")
    allowed_ui = client.get("/ui", headers=headers)
    assert allowed_ui.status_code == 200
    assert "Lattice Analysis Workbench" in allowed_ui.text

    allowed_asset = client.get("/ui-assets/styles/pp-theme.css", headers=headers)
    assert allowed_asset.status_code == 200

    allowed_api_readiness = client.get("/api/health/ready", headers=headers)
    assert allowed_api_readiness.status_code == 200

    allowed_root_papers = client.get("/papers", headers=headers)
    assert allowed_root_papers.status_code == 200


def test_beta_gate_and_api_key_bridge_stack_cleanly(tmp_path, monkeypatch):
    monkeypatch.setenv("LATTICE_BETA_PASSWORD", "beta-pass")
    monkeypatch.setenv("LATTICE_API_KEY", "secret-key")
    original_db_path = _init_temp_db(tmp_path, monkeypatch)
    try:
        client = TestClient(api_main.app)

        blocked_browser = client.get("/api/jobs")
        assert blocked_browser.status_code == 401
        assert blocked_browser.headers["www-authenticate"].startswith("Basic ")

        allowed_browser = client.get("/api/jobs", headers=_basic_auth_headers("beta-pass"))
        assert allowed_browser.status_code == 200
        assert allowed_browser.json() == []

        blocked_root = client.get("/jobs")
        assert blocked_root.status_code == 401
        assert blocked_root.headers["www-authenticate"].startswith("Basic ")

        blocked_root_after_basic = client.get("/jobs", headers=_basic_auth_headers("beta-pass"))
        assert blocked_root_after_basic.status_code == 401
        assert blocked_root_after_basic.json()["error_code"] == "UNAUTHORIZED"
    finally:
        db_utils.DB_PATH = original_db_path


def test_beta_ip_allowlist_blocks_non_allowlisted_clients(tmp_path, monkeypatch):
    monkeypatch.setenv("LATTICE_BETA_PASSWORD", "beta-pass")
    monkeypatch.setenv("LATTICE_API_KEY", "secret-key")
    monkeypatch.setenv("LATTICE_BETA_ALLOWED_IPS", "10.0.0.0/24")
    monkeypatch.setenv("LATTICE_TRUSTED_PROXY_IPS", "testclient")
    original_db_path = _init_temp_db(tmp_path, monkeypatch)
    try:
        client = TestClient(api_main.app)

        blocked_ui = client.get("/ui", headers={"x-forwarded-for": "203.0.113.25"})
        assert blocked_ui.status_code == 403
        assert blocked_ui.json()["error_code"] == "IP_NOT_ALLOWED"

        blocked_root = client.get(
            "/papers",
            headers={
                **_basic_auth_headers("beta-pass"),
                "X-API-Key": "secret-key",
                "x-forwarded-for": "203.0.113.25",
            },
        )
        assert blocked_root.status_code == 403
        assert blocked_root.json()["error_code"] == "IP_NOT_ALLOWED"

        allowed_ui = client.get("/ui", headers={"x-forwarded-for": "10.0.0.8", **_basic_auth_headers("beta-pass")})
        assert allowed_ui.status_code == 200

        allowed_root = client.get(
            "/papers",
            headers={
                **_basic_auth_headers("beta-pass"),
                "X-API-Key": "secret-key",
                "x-forwarded-for": "10.0.0.8",
            },
        )
        assert allowed_root.status_code == 200
    finally:
        db_utils.DB_PATH = original_db_path


def test_api_docs_remain_available_without_beta_gate(monkeypatch):
    monkeypatch.delenv("LATTICE_BETA_PASSWORD", raising=False)
    monkeypatch.delenv("PAPERPIPE_BETA_PASSWORD", raising=False)
    monkeypatch.delenv("LATTICE_ENABLE_API_DOCS", raising=False)
    monkeypatch.delenv("PAPERPIPE_ENABLE_API_DOCS", raising=False)

    reloaded_main = importlib.reload(api_main)
    try:
        client = TestClient(reloaded_main.app)
        assert client.get("/docs").status_code == 200
        assert client.get("/openapi.json").status_code == 200
    finally:
        importlib.reload(api_main)


def test_api_docs_default_off_with_beta_gate_and_can_be_opted_back_in(monkeypatch):
    monkeypatch.setenv("LATTICE_BETA_PASSWORD", "beta-pass")
    monkeypatch.delenv("PAPERPIPE_BETA_PASSWORD", raising=False)
    monkeypatch.delenv("LATTICE_ENABLE_API_DOCS", raising=False)
    monkeypatch.delenv("PAPERPIPE_ENABLE_API_DOCS", raising=False)

    reloaded_main = importlib.reload(api_main)
    try:
        client = TestClient(reloaded_main.app)
        assert client.get("/docs").status_code == 404
        assert client.get("/redoc").status_code == 404
        assert client.get("/openapi.json").status_code == 404

        monkeypatch.setenv("LATTICE_ENABLE_API_DOCS", "true")
        reloaded_main = importlib.reload(api_main)
        client = TestClient(reloaded_main.app)

        blocked_docs = client.get("/docs")
        assert blocked_docs.status_code == 401
        assert blocked_docs.headers["www-authenticate"].startswith("Basic ")

        headers = _basic_auth_headers("beta-pass")
        allowed_docs = client.get("/docs", headers=headers)
        assert allowed_docs.status_code == 200
        allowed_openapi = client.get("/openapi.json", headers=headers)
        assert allowed_openapi.status_code == 200
    finally:
        monkeypatch.delenv("LATTICE_BETA_PASSWORD", raising=False)
        monkeypatch.delenv("PAPERPIPE_BETA_PASSWORD", raising=False)
        monkeypatch.delenv("LATTICE_ENABLE_API_DOCS", raising=False)
        monkeypatch.delenv("PAPERPIPE_ENABLE_API_DOCS", raising=False)
        importlib.reload(api_main)
