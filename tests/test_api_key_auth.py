from fastapi.testclient import TestClient

import src.db_utils as db_utils
from backend import main as api_main


def _init_temp_db(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    db_utils.init_db()
    return original_db_path


def test_write_endpoints_require_api_key_when_configured(tmp_path, monkeypatch):
    monkeypatch.setenv("LATTICE_API_KEY", "secret-key")
    original_db_path = _init_temp_db(tmp_path, monkeypatch)
    try:
        client = TestClient(api_main.app)

        deepread = client.post("/jobs/deepread", json={"paper_id": "paper_auth_001"})
        assert deepread.status_code == 401
        assert deepread.json()["error_code"] == "UNAUTHORIZED"

        cancel = client.post("/jobs/job_auth_001/cancel")
        assert cancel.status_code == 401

        feedback = client.post(
            "/feedback",
            json={
                "paper_id": "paper_auth_001",
                "run_id": "run_auth_001",
                "user_correction": "fix claim wording",
                "accepted": True,
            },
        )
        assert feedback.status_code == 401

        obsidian_sync = client.post("/obsidian/sync", json={"paper_id": "paper_auth_001", "run_id": "run_auth_001"})
        assert obsidian_sync.status_code == 401
    finally:
        db_utils.DB_PATH = original_db_path


def test_write_endpoints_accept_valid_api_key(tmp_path, monkeypatch):
    monkeypatch.setenv("LATTICE_API_KEY", "secret-key")
    original_db_path = _init_temp_db(tmp_path, monkeypatch)
    try:
        client = TestClient(api_main.app)
        headers = {"X-API-Key": "secret-key"}

        deepread = client.post("/jobs/deepread", json={"paper_id": "paper_auth_allow_001"}, headers=headers)
        assert deepread.status_code == 200

        cancel = client.post("/jobs/job_auth_allow_001/cancel", headers=headers)
        assert cancel.status_code == 200
        assert cancel.json()["status"] == "cancelled"

        feedback = client.post(
            "/feedback",
            json={
                "paper_id": "paper_auth_allow_001",
                "run_id": "run_auth_allow_001",
                "user_correction": "accepted correction",
                "accepted": True,
            },
            headers=headers,
        )
        assert feedback.status_code == 200
    finally:
        db_utils.DB_PATH = original_db_path


def test_read_endpoints_do_not_require_api_key(tmp_path, monkeypatch):
    monkeypatch.setenv("LATTICE_API_KEY", "secret-key")
    original_db_path = _init_temp_db(tmp_path, monkeypatch)
    try:
        client = TestClient(api_main.app)

        health = client.get("/health")
        assert health.status_code == 200
        assert health.json()["status"] == "ok"
    finally:
        db_utils.DB_PATH = original_db_path


def test_legacy_api_key_env_is_supported(tmp_path, monkeypatch):
    monkeypatch.delenv("LATTICE_API_KEY", raising=False)
    monkeypatch.setenv("PAPERPIPE_API_KEY", "legacy-key")
    original_db_path = _init_temp_db(tmp_path, monkeypatch)
    try:
        client = TestClient(api_main.app)

        blocked = client.post("/jobs/deepread", json={"paper_id": "paper_legacy_auth_001"})
        assert blocked.status_code == 401

        allowed = client.post(
            "/jobs/deepread",
            json={"paper_id": "paper_legacy_auth_001"},
            headers={"X-API-Key": "legacy-key"},
        )
        assert allowed.status_code == 200
    finally:
        db_utils.DB_PATH = original_db_path
