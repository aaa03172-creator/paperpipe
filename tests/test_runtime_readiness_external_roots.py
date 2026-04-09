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
  watch_folder: "{path.parent / 'watch-folder'}"
  downloads_watch_dir: "{path.parent / 'Downloads'}"
  pdf_storage_dir: "{path.parent / 'storage' / 'pdfs'}"

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


def test_collect_runtime_readiness_surfaces_missing_watchdog_for_pickup_paths(tmp_path, monkeypatch):
    zotero_dir = tmp_path / "zotero"
    vault_dir = tmp_path / "vault"
    watch_dir = tmp_path / "watch-folder"
    downloads_dir = tmp_path / "Downloads"
    pdf_storage_dir = tmp_path / "storage" / "pdfs"
    zotero_dir.mkdir()
    vault_dir.mkdir()
    watch_dir.mkdir()
    downloads_dir.mkdir()
    pdf_storage_dir.mkdir(parents=True)
    config_path = tmp_path / "config.yaml"
    _write_config(config_path, zotero=str(zotero_dir), vault=str(vault_dir))

    monkeypatch.setenv("PAPERPIPE_CONFIG_PATH", str(config_path))

    real_import_module = runtime_readiness.importlib.import_module

    def _fake_import_module(module_name: str):
        if module_name == "watchdog":
            raise ModuleNotFoundError("No module named 'watchdog'", name="watchdog")
        return real_import_module(module_name)

    monkeypatch.setattr(runtime_readiness.importlib, "import_module", _fake_import_module)

    readiness = runtime_readiness.collect_runtime_readiness()
    checks = {check.name: check for check in readiness.checks}

    assert checks["watchdog_dependency"].status == "error"
    assert "watchdog" in checks["watchdog_dependency"].detail
    assert checks["watch_folder"].status == "error"
    assert "watchdog" in checks["watch_folder"].detail
    assert checks["downloads_watch_dir"].status == "error"
    assert "watchdog" in checks["downloads_watch_dir"].detail
