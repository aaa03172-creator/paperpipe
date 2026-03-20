from fastapi.testclient import TestClient

import src.db_utils as db_utils
from backend import main as api_main


def _init_temp_db(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    db_utils.init_db()
    return original_db_path


def test_chat_stub_defaults_to_disabled(tmp_path, monkeypatch):
    monkeypatch.delenv("CHAT_ENABLED", raising=False)
    monkeypatch.delenv("LATTICE_CHAT_ENABLED", raising=False)
    monkeypatch.delenv("PAPERPIPE_CHAT_ENABLED", raising=False)
    original_db_path = _init_temp_db(tmp_path, monkeypatch)
    try:
        client = TestClient(api_main.app)
        response = client.post("/api/chat", json={"paper_slug": "paper-001", "message": "hello"})
        assert response.status_code == 501
        payload = response.json()
        assert payload["error_code"] == "CHAT_NOT_IMPLEMENTED"
        assert payload["chat_enabled"] is False
        assert payload["output_mode_family"] == "learner"
        assert payload["external_calls"] is False
        assert "CHAT_ENABLED=false" in payload["message"]
    finally:
        db_utils.DB_PATH = original_db_path


def test_chat_stub_stays_not_implemented_when_flag_enabled(tmp_path, monkeypatch):
    monkeypatch.setenv("CHAT_ENABLED", "true")
    original_db_path = _init_temp_db(tmp_path, monkeypatch)
    try:
        client = TestClient(api_main.app)
        response = client.post("/api/chat", json={"paper_slug": "paper-001", "message": "hello"})
        assert response.status_code == 501
        payload = response.json()
        assert payload["error_code"] == "CHAT_NOT_IMPLEMENTED"
        assert payload["chat_enabled"] is True
        assert payload["output_mode_family"] == "learner"
        assert payload["external_calls"] is False
        assert "stubbed" in payload["message"]
    finally:
        db_utils.DB_PATH = original_db_path


def test_chat_stub_accepts_explicit_output_mode_family(tmp_path, monkeypatch):
    monkeypatch.delenv("CHAT_ENABLED", raising=False)
    original_db_path = _init_temp_db(tmp_path, monkeypatch)
    try:
        client = TestClient(api_main.app)
        response = client.post(
            "/api/chat",
            json={
                "paper_slug": "paper-001",
                "message": "hello",
                "output_mode_family": "builder_debug",
            },
        )
        assert response.status_code == 501
        payload = response.json()
        assert payload["error_code"] == "CHAT_NOT_IMPLEMENTED"
        assert payload["output_mode_family"] == "builder_debug"
        assert payload["chat_enabled"] is False
    finally:
        db_utils.DB_PATH = original_db_path
