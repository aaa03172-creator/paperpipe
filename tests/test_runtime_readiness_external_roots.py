from __future__ import annotations

from pathlib import Path

import src.services.runtime_readiness as runtime_readiness


def _write_config(path: Path, *, zotero: str, vault: str) -> None:
    path.write_text(
        f"""
system:
  backfill_limit_days: 3
  log_level: "INFO"

paths:
  zotero_base_dir: "{zotero}"
  obsidian_vault: "{vault}"

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


def test_collect_runtime_readiness_warns_for_missing_external_roots(tmp_path, monkeypatch):
    config_path = tmp_path / "config.yaml"
    _write_config(
        config_path,
        zotero=str(tmp_path / "missing-zotero"),
        vault=str(tmp_path / "missing-vault"),
    )

    monkeypatch.setenv("PAPERPIPE_CONFIG_PATH", str(config_path))

    readiness = runtime_readiness.collect_runtime_readiness()
    checks = {check.name: check for check in readiness.checks}

    assert checks["obsidian_vault"].status == "warn"
    assert checks["obsidian_vault"].detail == "configured external root is missing"
    assert checks["zotero_base_dir"].status == "warn"
    assert checks["zotero_base_dir"].detail == "configured external root is missing"


def test_collect_runtime_readiness_marks_existing_external_roots_ok(tmp_path, monkeypatch):
    zotero_dir = tmp_path / "zotero"
    vault_dir = tmp_path / "vault"
    zotero_dir.mkdir()
    vault_dir.mkdir()
    config_path = tmp_path / "config.yaml"
    _write_config(config_path, zotero=str(zotero_dir), vault=str(vault_dir))

    monkeypatch.setenv("PAPERPIPE_CONFIG_PATH", str(config_path))

    readiness = runtime_readiness.collect_runtime_readiness()
    checks = {check.name: check for check in readiness.checks}

    assert checks["obsidian_vault"].status == "ok"
    assert checks["obsidian_vault"].detail == "configured external root exists"
    assert checks["zotero_base_dir"].status == "ok"
    assert checks["zotero_base_dir"].detail == "configured external root exists"
