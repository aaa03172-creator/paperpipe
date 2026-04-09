from __future__ import annotations

from pathlib import Path
import sqlite3

from src.config import LocalLLMConfig, load_config
import src.db_utils as db_utils


def _write_config(path: Path, *, vault_name: str) -> None:
    path.write_text(
        f"""
system:
  backfill_limit_days: 3
  log_level: "INFO"

paths:
  zotero_base_dir: "./{vault_name}/zotero"
  obsidian_vault: "./{vault_name}/vault"

search:
  constraints:
    min_pubmed: 1
    max_preprint: 1
  slots:
    mechanism:
      query: "test"
      source: "pubmed"

llm:
  mode: "local"
  local:
    provider: "ollama"
    base_url: "http://127.0.0.1:11434"
    models:
      classifier: "llama3:8b"
      tagger: "biomistral:7b"
      embedder: "nomic-embed-text"
      judge: "llama3:latest"
      chat: "phi3"
  cloud:
    provider: "openai"
    api_key: ""
    model: "gpt-4o-mini"
  features:
    trial_extraction:
      enabled: false
      model: "gpt-4o-mini"
    slot_classification:
      enabled: false
      model: "gpt-4o-mini"
    one_liner:
      enabled: false
      model: "gpt-4o-mini"
  timeout_seconds: 15
  max_retries: 1
""".strip(),
        encoding="utf-8",
    )


def test_load_config_respects_env_override(tmp_path, monkeypatch):
    default_config = tmp_path / "config.default.yaml"
    override_config = tmp_path / "config.override.yaml"
    _write_config(default_config, vault_name="default")
    _write_config(override_config, vault_name="override")

    monkeypatch.setenv("PAPERPIPE_CONFIG_PATH", str(override_config))

    config = load_config(str(default_config))

    assert config.paths.obsidian_vault == Path("./override/vault").expanduser()
    assert config.paths.zotero_base_dir == Path("./override/zotero").expanduser()


def test_local_llm_defaults_align_judge_model() -> None:
    assert LocalLLMConfig().models["judge"] == "llama3:latest"


def test_db_utils_follows_db_env_override_after_import(tmp_path, monkeypatch):
    original_db_path = db_utils.DB_PATH
    env_db_path = tmp_path / "env-state.db"
    monkeypatch.setenv("PAPERPIPE_DB_PATH", str(env_db_path))
    try:
        db_utils.DB_PATH = original_db_path
        db_utils.init_db()

        assert db_utils.get_db_path() == env_db_path.resolve()
        assert env_db_path.exists()

        conn = db_utils.get_db_connection()
        actual_path = conn.execute("PRAGMA database_list").fetchone()[2]
        conn.close()
        assert Path(actual_path).resolve() == env_db_path.resolve()

        schema_conn = sqlite3.connect(env_db_path)
        tables = {
            row[0]
            for row in schema_conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        }
        schema_conn.close()
        assert "jobs" in tables
        assert "user_actions" in tables
    finally:
        db_utils.DB_PATH = original_db_path
