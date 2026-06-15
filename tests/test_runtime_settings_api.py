import json
from pathlib import Path

import yaml
from fastapi.testclient import TestClient

from backend import main as api_main


def _browser_headers() -> dict[str, str]:
    return {"origin": "http://testserver"}


def _write_config(path: Path, *, api_key: str = "") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            [
                "system:",
                "  log_level: INFO",
                "paths:",
                f"  zotero_base_dir: {path.parent / 'zotero'}",
                f"  obsidian_vault: {path.parent / 'vault'}",
                "search:",
                "  constraints:",
                "    min_pubmed: 2",
                "    max_preprint: 1",
                "  slots:",
                "    primary:",
                '      query: "test"',
                "llm:",
                "  mode: local",
                "  local:",
                "    provider: ollama",
                "  cloud:",
                "    provider: openai",
                f"    api_key: {api_key}",
                "    model: gpt-4o-mini",
                "    embedding_model: text-embedding-3-small",
                "  features:",
                "    specialty_trial_extraction:",
                "      enabled: false",
                "    slot_classification:",
                "      enabled: false",
                "    one_liner:",
                "      enabled: false",
            ]
        ),
        encoding="utf-8",
    )


def test_llm_settings_status_masks_configured_key(tmp_path, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.setenv("LATTICE_API_KEY", "app-secret")
    config_path = tmp_path / "config.yaml"
    raw_key = "sk-test-secret-1234567890"
    _write_config(config_path, api_key=raw_key)
    monkeypatch.setenv("PAPERPIPE_CONFIG_PATH", str(config_path))

    response = TestClient(api_main.app).get("/api/runtime-settings/llm", headers=_browser_headers())

    assert response.status_code == 200
    payload = response.json()
    assert payload["mode"] == "local"
    assert payload["provider"] == "openai"
    assert payload["model"] == "gpt-4o-mini"
    assert payload["api_key_configured"] is True
    assert payload["api_key_source"] == "config"
    assert payload["api_key_masked"].endswith("7890")
    assert raw_key not in json.dumps(payload)


def test_llm_settings_direct_routes_require_api_key_when_configured(tmp_path, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.setenv("LATTICE_API_KEY", "app-secret")
    config_path = tmp_path / "config.yaml"
    _write_config(config_path)
    monkeypatch.setenv("PAPERPIPE_CONFIG_PATH", str(config_path))

    client = TestClient(api_main.app)
    blocked_read = client.get("/runtime-settings/llm")
    assert blocked_read.status_code == 401
    assert blocked_read.json()["error_code"] == "UNAUTHORIZED"

    blocked_write = client.put("/runtime-settings/llm", json={"mode": "cloud"})
    assert blocked_write.status_code == 401
    assert blocked_write.json()["error_code"] == "UNAUTHORIZED"

    allowed_read = client.get("/runtime-settings/llm", headers={"X-API-Key": "app-secret"})
    assert allowed_read.status_code == 200
    assert allowed_read.json()["api_key_configured"] is False


def test_llm_settings_env_override_masks_environment_key(tmp_path, monkeypatch):
    raw_env_key = "sk-env-secret-abcdef123456"
    monkeypatch.setenv("OPENAI_API_KEY", raw_env_key)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.setenv("LATTICE_API_KEY", "app-secret")
    config_path = tmp_path / "config.yaml"
    _write_config(config_path, api_key="sk-config-secret-should-not-win")
    monkeypatch.setenv("PAPERPIPE_CONFIG_PATH", str(config_path))

    response = TestClient(api_main.app).get("/api/runtime-settings/llm", headers=_browser_headers())

    assert response.status_code == 200
    payload = response.json()
    assert payload["api_key_configured"] is True
    assert payload["api_key_source"] == "env"
    assert payload["env_override_active"] is True
    assert payload["api_key_masked"].endswith("3456")
    assert raw_env_key not in json.dumps(payload)
    assert "sk-config-secret-should-not-win" not in json.dumps(payload)


def test_llm_settings_update_writes_cloud_config_without_echoing_key(tmp_path, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.setenv("LATTICE_API_KEY", "app-secret")
    config_path = tmp_path / "config.yaml"
    raw_key = "sk-ant-api03-test-secret-abcdefghijkl"
    _write_config(config_path)
    monkeypatch.setenv("PAPERPIPE_CONFIG_PATH", str(config_path))

    response = TestClient(api_main.app).put(
        "/api/runtime-settings/llm",
        headers=_browser_headers(),
        json={
            "mode": "cloud",
            "provider": "anthropic",
            "api_key": f"  {raw_key[:12]}  {raw_key[12:]}  ",
            "model": "claude-3-5-sonnet-latest",
            "embedding_model": "",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["mode"] == "cloud"
    assert payload["provider"] == "anthropic"
    assert payload["model"] == "claude-3-5-sonnet-latest"
    assert payload["api_key_configured"] is True
    assert payload["api_key_source"] == "config"
    assert raw_key not in json.dumps(payload)

    saved = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    assert saved["llm"]["mode"] == "cloud"
    assert saved["llm"]["cloud"]["provider"] == "anthropic"
    assert saved["llm"]["cloud"]["api_key"] == raw_key
    assert saved["llm"]["cloud"]["model"] == "claude-3-5-sonnet-latest"
    assert saved["llm"]["cloud"]["embedding_model"] is None


def test_llm_settings_update_supports_gemini_provider(tmp_path, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.setenv("LATTICE_API_KEY", "app-secret")
    config_path = tmp_path / "config.yaml"
    raw_key = "gemini-test-secret-abcdef9876"
    _write_config(config_path)
    monkeypatch.setenv("PAPERPIPE_CONFIG_PATH", str(config_path))

    response = TestClient(api_main.app).put(
        "/api/runtime-settings/llm",
        headers=_browser_headers(),
        json={
            "mode": "cloud",
            "provider": "gemini",
            "api_key": raw_key,
            "model": "gemini-2.5-flash",
            "embedding_model": "",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["provider"] == "gemini"
    assert payload["provider_env_var"] == "GEMINI_API_KEY"
    assert payload["model"] == "gemini-2.5-flash"
    assert payload["api_key_configured"] is True
    assert payload["api_key_source"] == "config"
    assert payload["api_key_masked"].endswith("9876")
    assert raw_key not in json.dumps(payload)

    saved = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    assert saved["llm"]["mode"] == "cloud"
    assert saved["llm"]["cloud"]["provider"] == "gemini"
    assert saved["llm"]["cloud"]["api_key"] == raw_key
    assert saved["llm"]["cloud"]["model"] == "gemini-2.5-flash"
    assert saved["llm"]["cloud"]["embedding_model"] is None


def test_llm_settings_gemini_env_override_prefers_gemini_key(tmp_path, monkeypatch):
    raw_env_key = "gemini-env-secret-abcdef9876"
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("GEMINI_API_KEY", raw_env_key)
    monkeypatch.setenv("GOOGLE_API_KEY", "google-env-secret-should-not-win")
    monkeypatch.setenv("LATTICE_API_KEY", "app-secret")
    config_path = tmp_path / "config.yaml"
    _write_config(config_path, api_key="gemini-config-secret-should-not-win")
    config_payload = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    config_payload["llm"]["cloud"]["provider"] = "gemini"
    config_payload["llm"]["cloud"]["model"] = "gemini-2.5-flash"
    config_path.write_text(yaml.safe_dump(config_payload, sort_keys=False), encoding="utf-8")
    monkeypatch.setenv("PAPERPIPE_CONFIG_PATH", str(config_path))

    response = TestClient(api_main.app).get("/api/runtime-settings/llm", headers=_browser_headers())

    assert response.status_code == 200
    payload = response.json()
    assert payload["provider"] == "gemini"
    assert payload["api_key_source"] == "env"
    assert payload["provider_env_var"] == "GEMINI_API_KEY"
    assert payload["api_key_masked"].endswith("9876")
    assert raw_env_key not in json.dumps(payload)
    assert "gemini-config-secret-should-not-win" not in json.dumps(payload)
    assert "google-env-secret-should-not-win" not in json.dumps(payload)


def test_llm_connection_test_uses_configured_provider_without_echoing_key(tmp_path, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.setenv("LATTICE_API_KEY", "app-secret")
    config_path = tmp_path / "config.yaml"
    raw_key = "gemini-live-test-secret-abcdef1357"
    _write_config(config_path, api_key=raw_key)
    config_payload = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    config_payload["llm"]["mode"] = "cloud"
    config_payload["llm"]["cloud"]["provider"] = "gemini"
    config_payload["llm"]["cloud"]["model"] = "gemini-2.5-flash"
    config_path.write_text(yaml.safe_dump(config_payload, sort_keys=False), encoding="utf-8")
    monkeypatch.setenv("PAPERPIPE_CONFIG_PATH", str(config_path))

    class FakeProvider:
        def is_available(self) -> bool:
            return True

        def _make_request(self, task, prompt, is_json=False, schema=None, system_prompt=None):
            assert task == "connection_test"
            assert "paper" not in prompt.lower()
            return "ok"

    monkeypatch.setattr("src.services.runtime_settings.get_llm_provider", lambda config, aliases=None: FakeProvider())

    response = TestClient(api_main.app).post("/api/runtime-settings/llm/test", headers=_browser_headers())

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["provider"] == "gemini"
    assert payload["model"] == "gemini-2.5-flash"
    assert payload["api_key_source"] == "config"
    assert payload["provider_env_var"] == "GEMINI_API_KEY"
    assert raw_key not in json.dumps(payload)


def test_llm_connection_test_reports_missing_key_without_calling_provider(tmp_path, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.setenv("LATTICE_API_KEY", "app-secret")
    config_path = tmp_path / "config.yaml"
    _write_config(config_path)
    config_payload = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    config_payload["llm"]["mode"] = "cloud"
    config_payload["llm"]["cloud"]["provider"] = "gemini"
    config_payload["llm"]["cloud"]["api_key"] = ""
    config_payload["llm"]["cloud"]["model"] = "gemini-2.5-flash"
    config_path.write_text(yaml.safe_dump(config_payload, sort_keys=False), encoding="utf-8")
    monkeypatch.setenv("PAPERPIPE_CONFIG_PATH", str(config_path))

    def fail_provider(*args, **kwargs):
        raise AssertionError("provider should not be initialized without an API key")

    monkeypatch.setattr("src.services.runtime_settings.get_llm_provider", fail_provider)

    response = TestClient(api_main.app).post("/api/runtime-settings/llm/test", headers=_browser_headers())

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "failed"
    assert payload["provider"] == "gemini"
    assert payload["api_key_source"] == "none"
    assert "API key is not configured" in payload["detail"]


def test_llm_settings_clear_key_preserves_provider_and_model(tmp_path, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.setenv("LATTICE_API_KEY", "app-secret")
    config_path = tmp_path / "config.yaml"
    _write_config(config_path, api_key="sk-test-secret-1234567890")
    monkeypatch.setenv("PAPERPIPE_CONFIG_PATH", str(config_path))

    response = TestClient(api_main.app).put(
        "/api/runtime-settings/llm",
        headers=_browser_headers(),
        json={"clear_api_key": True},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["provider"] == "openai"
    assert payload["api_key_configured"] is False
    assert payload["api_key_source"] == "none"
    saved = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    assert saved["llm"]["cloud"]["api_key"] == ""
