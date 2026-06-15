from __future__ import annotations

from pathlib import Path
import sqlite3
import warnings

from pydantic import ValidationError
import pytest

import src.config as config_module
from src.config import (
    load_config,
    resolve_clinical_extraction_feature,
    resolve_specialty_trial_extraction_feature,
)
import src.db_utils as db_utils


@pytest.fixture(autouse=True)
def clear_default_config_path(monkeypatch):
    monkeypatch.delenv("PAPERPIPE_CONFIG_PATH", raising=False)


def _write_config(path: Path, *, vault_name: str, extra_paths: str = "") -> None:
    path.write_text(
        f"""
system:
  backfill_limit_days: 3
  log_level: "INFO"

paths:
  zotero_base_dir: "./{vault_name}/zotero"
  obsidian_vault: "./{vault_name}/vault"
{extra_paths}

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
    specialty_trial_extraction:
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


def test_load_config_prefers_openai_api_key_env_over_yaml_value(tmp_path, monkeypatch):
    config_path = tmp_path / "config.yaml"
    _write_config(config_path, vault_name="api-key")
    raw = config_path.read_text(encoding="utf-8")
    config_path.write_text(
        raw.replace('api_key: ""', 'api_key: "config-key-should-not-win"'),
        encoding="utf-8",
    )

    monkeypatch.setenv("OPENAI_API_KEY", " env-key-from-shell \n")

    config = load_config(str(config_path))

    assert config.llm.cloud.api_key == "env-key-from-shell"


def test_load_config_prefers_anthropic_api_key_env_when_provider_is_anthropic(tmp_path, monkeypatch):
    config_path = tmp_path / "anthropic-config.yaml"
    _write_config(config_path, vault_name="anthropic-api-key")
    raw = config_path.read_text(encoding="utf-8")
    raw = raw.replace('provider: "openai"', 'provider: "anthropic"', 1)
    raw = raw.replace('api_key: ""', 'api_key: "config-key-should-not-win"', 1)
    config_path.write_text(raw, encoding="utf-8")

    monkeypatch.setenv("OPENAI_API_KEY", "openai-key-should-be-ignored")
    monkeypatch.setenv("ANTHROPIC_API_KEY", " anthropic-env-key \n")

    config = load_config(str(config_path))

    assert config.llm.cloud.provider == "anthropic"
    assert config.llm.cloud.api_key == "anthropic-env-key"


def test_load_config_accepts_openai_responses_api_opt_in(tmp_path, monkeypatch):
    config_path = tmp_path / "responses-config.yaml"
    _write_config(config_path, vault_name="responses-api")
    raw = config_path.read_text(encoding="utf-8")
    raw = raw.replace('provider: "openai"', 'provider: "openai"\n    openai_api: "responses"', 1)
    config_path.write_text(raw, encoding="utf-8")

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    config = load_config(str(config_path))

    assert config.llm.cloud.provider == "openai"
    assert config.llm.cloud.openai_api == "responses"


def test_load_config_accepts_openai_json_schema_opt_in(tmp_path, monkeypatch):
    config_path = tmp_path / "responses-schema-config.yaml"
    _write_config(config_path, vault_name="responses-schema-api")
    raw = config_path.read_text(encoding="utf-8")
    raw = raw.replace(
        'provider: "openai"',
        'provider: "openai"\n    openai_api: "responses"\n    openai_json_mode: "json_schema"',
        1,
    )
    config_path.write_text(raw, encoding="utf-8")

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    config = load_config(str(config_path))

    assert config.llm.cloud.provider == "openai"
    assert config.llm.cloud.openai_api == "responses"
    assert config.llm.cloud.openai_json_mode == "json_schema"


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


def test_load_config_allows_omitting_legacy_trial_extraction_when_clinical_extraction_is_present(tmp_path):
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        """
system:
  backfill_limit_days: 3
  log_level: "INFO"

paths:
  zotero_base_dir: "./zotero"
  obsidian_vault: "./vault"

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
    clinical_extraction:
      enabled: true
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

    config = load_config(str(config_path))

    assert config.llm.features.clinical_extraction is not None
    assert config.llm.features.clinical_extraction.enabled is True
    assert config.llm.features.specialty_trial_extraction is None
    assert config.llm.features.trial_extraction is None


def test_resolve_clinical_extraction_feature_supports_dict_like_inputs() -> None:
    feature = resolve_clinical_extraction_feature(
        {
            "clinical_extraction": {"enabled": True, "model": "gpt-4.1-mini"},
            "specialty_trial_extraction": {"enabled": False, "model": "gpt-4.1"},
            "trial_extraction": {"enabled": False, "model": "gpt-4o-mini"},
        }
    )

    assert feature is not None
    assert feature.enabled is True
    assert feature.model == "gpt-4.1-mini"


def test_resolve_clinical_extraction_feature_falls_back_to_legacy_dict_payload() -> None:
    feature = resolve_clinical_extraction_feature(
        {
            "trial_extraction": {"enabled": False, "model": "gpt-4o-mini"},
        }
    )

    assert feature is not None
    assert feature.enabled is False
    assert feature.model == "gpt-4o-mini"


def test_resolve_clinical_extraction_feature_falls_back_to_explicit_specialty_payload() -> None:
    feature = resolve_clinical_extraction_feature(
        {
            "specialty_trial_extraction": {"enabled": False, "model": "gpt-4.1"},
            "trial_extraction": {"enabled": True, "model": "gpt-4o-mini"},
        }
    )

    assert feature is not None
    assert feature.enabled is False
    assert feature.model == "gpt-4.1"


def test_resolve_specialty_trial_extraction_feature_prefers_explicit_specialty_payload() -> None:
    feature = resolve_specialty_trial_extraction_feature(
        {
            "specialty_trial_extraction": {"enabled": False, "model": "gpt-4.1"},
            "trial_extraction": {"enabled": True, "model": "gpt-4o-mini"},
        }
    )

    assert feature is not None
    assert feature.enabled is False
    assert feature.model == "gpt-4.1"


def test_load_config_warns_once_for_legacy_trial_extraction_alias(tmp_path) -> None:
    config_path = tmp_path / "legacy-config.yaml"
    config_path.write_text(
        """
system:
  backfill_limit_days: 3
  log_level: "INFO"

paths:
  zotero_base_dir: "./zotero"
  obsidian_vault: "./vault"

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

    config_module._LEGACY_TRIAL_EXTRACTION_ALIAS_WARNED = False
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        load_config(str(config_path))
        load_config(str(config_path))

    legacy_warnings = [item for item in caught if "trial_extraction" in str(item.message)]
    assert len(legacy_warnings) == 1
    assert "2026-06-30" in str(legacy_warnings[0].message)


def test_load_config_with_specialty_trial_extraction_does_not_warn(tmp_path) -> None:
    config_path = tmp_path / "specialty-config.yaml"
    config_path.write_text(
        """
system:
  backfill_limit_days: 3
  log_level: "INFO"

paths:
  zotero_base_dir: "./zotero"
  obsidian_vault: "./vault"

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
    specialty_trial_extraction:
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

    config_module._LEGACY_TRIAL_EXTRACTION_ALIAS_WARNED = False
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        load_config(str(config_path))

    legacy_warnings = [item for item in caught if "trial_extraction" in str(item.message)]
    assert legacy_warnings == []


def test_load_config_warns_when_watch_folder_overlaps_upload_dir(tmp_path) -> None:
    config_path = tmp_path / "watch-overlap.yaml"
    _write_config(
        config_path,
        vault_name="watch-overlap",
        extra_paths="""
  watch_folder: "./watch-root"
  upload_dir: "./watch-root/uploads"
""",
    )

    with pytest.raises(ValidationError, match="paths.watch_folder overlaps managed output paths"):
        load_config(str(config_path))


def test_load_config_warns_when_downloads_watch_dir_overlaps_pdf_storage_dir(tmp_path) -> None:
    config_path = tmp_path / "downloads-overlap.yaml"
    _write_config(
        config_path,
        vault_name="downloads-overlap",
        extra_paths="""
  downloads_watch_dir: "./storage/pdfs/incoming"
  pdf_storage_dir: "./storage/pdfs"
""",
    )

    with pytest.raises(ValidationError, match="paths.downloads_watch_dir overlaps paths.pdf_storage_dir"):
        load_config(str(config_path))
