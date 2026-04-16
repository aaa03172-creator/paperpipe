from __future__ import annotations

from pathlib import Path

from src.config import load_config
import src.services.runtime_paths as runtime_paths


def _write_config(path: Path, *, extra_paths: str = "") -> None:
    path.write_text(
        f"""
system:
  backfill_limit_days: 3
  log_level: "INFO"

paths:
  zotero_base_dir: "./zotero"
  obsidian_vault: "./vault"
  export_dir: "export"
  watch_folder: "Download/PaperPipe_Watch"
  library_dir: "Library"
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


def test_install_layout_normalizes_app_owned_legacy_path_literals(tmp_path, monkeypatch):
    config_path = tmp_path / "config.yaml"
    _write_config(config_path)

    monkeypatch.setenv("PAPERPIPE_INSTALL_LAYOUT", "1")
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("PAPERPIPE_CONFIG_PATH", str(config_path))
    monkeypatch.setattr(runtime_paths.sys, "platform", "darwin")

    config = load_config(str(config_path))
    install_root = tmp_path / "Library" / "Application Support" / "Lattice"

    assert config.paths.export_dir == (install_root / "storage" / "exports").resolve()
    assert config.paths.watch_folder == (install_root / "storage" / "watch_folder").resolve()
    assert config.paths.library_dir == (install_root / "storage" / "library").resolve()
    assert config.paths.pdf_storage_dir == (install_root / "storage" / "pdfs").resolve()


def test_install_layout_keeps_custom_and_external_paths_unchanged(tmp_path, monkeypatch):
    config_path = tmp_path / "config.yaml"
    _write_config(
        config_path,
        extra_paths="""
  upload_dir: "~/Documents/NotebookLM_Upload"
  downloads_watch_dir: "~/Downloads"
  pdf_storage_dir: "/tmp/custom-pdfs"
""",
    )

    monkeypatch.setenv("PAPERPIPE_INSTALL_LAYOUT", "1")
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("PAPERPIPE_CONFIG_PATH", str(config_path))
    monkeypatch.setattr(runtime_paths.sys, "platform", "darwin")

    config = load_config(str(config_path))

    assert config.paths.upload_dir == (tmp_path / "Documents" / "NotebookLM_Upload").expanduser()
    assert config.paths.downloads_watch_dir == (tmp_path / "Downloads").expanduser()
    assert config.paths.pdf_storage_dir == Path("/tmp/custom-pdfs")


def test_default_downloads_watch_dir_expands_user_home(tmp_path, monkeypatch):
    config_path = tmp_path / "config.yaml"
    _write_config(config_path)

    monkeypatch.delenv("PAPERPIPE_INSTALL_LAYOUT", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("PAPERPIPE_CONFIG_PATH", str(config_path))

    config = load_config(str(config_path))

    assert config.paths.downloads_watch_dir == (tmp_path / "Downloads").expanduser()
