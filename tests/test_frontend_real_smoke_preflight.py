from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path


def _write_config(path: Path, vault_path: Path) -> None:
    path.write_text(
        f"""
system:
  backfill_limit_days: 3
  log_level: "INFO"

paths:
  zotero_base_dir: "./zotero"
  obsidian_vault: "{vault_path}"

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


def _seed_db(path: Path, paper_id: str, pdf_path: Path) -> None:
    conn = sqlite3.connect(path)
    conn.execute(
        """
        CREATE TABLE papers (
            paper_id TEXT PRIMARY KEY,
            title TEXT,
            pdf_path TEXT,
            updated_at TEXT
        )
        """
    )
    conn.execute(
        """
        INSERT INTO papers (paper_id, title, pdf_path, updated_at)
        VALUES (?, ?, ?, datetime('now'))
        """,
        (paper_id, "Real Smoke Candidate", str(pdf_path)),
    )
    conn.commit()
    conn.close()


def _write_claimset(artifacts_dir: Path, paper_id: str) -> None:
    run_dir = artifacts_dir / paper_id / "run-001"
    run_dir.mkdir(parents=True, exist_ok=True)
    run_dir.joinpath("claimset.resolved.json").write_text(
        json.dumps(
            {
                "claims": [
                    {"evidence_spans": [{"page": 0}]},
                    {"evidence_spans": [{"page": 2}]},
                ]
            }
        ),
        encoding="utf-8",
    )


def test_real_smoke_preflight_finds_candidates(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()
    config_path = tmp_path / "config.yaml"
    _write_config(config_path, vault)

    storage_dir = tmp_path / "storage"
    artifacts_dir = storage_dir / "artifacts"
    artifacts_dir.mkdir(parents=True)
    db_path = storage_dir / "state.db"
    pdf_path = tmp_path / "sample.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n")
    _seed_db(db_path, "zotero:test-paper", pdf_path)
    _write_claimset(artifacts_dir, "zotero:test-paper")

    script_path = Path("scripts/check_frontend_real_smoke_env.py").resolve()
    env = os.environ.copy()
    env["PAPERPIPE_CONFIG_PATH"] = str(config_path)
    env["PAPERPIPE_STORAGE_DIR"] = str(storage_dir)

    result = subprocess.run(
        [sys.executable, str(script_path), "--require-candidates"],
        cwd=Path.cwd(),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["candidate_count"] == 1
    assert payload["candidates"][0]["paper_id"] == "zotero:test-paper"
    assert payload["errors"] == []


def test_real_smoke_preflight_fails_without_candidates(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()
    config_path = tmp_path / "config.yaml"
    _write_config(config_path, vault)

    storage_dir = tmp_path / "storage"
    artifacts_dir = storage_dir / "artifacts"
    artifacts_dir.mkdir(parents=True)
    db_path = storage_dir / "state.db"
    pdf_path = tmp_path / "sample.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n")
    _seed_db(db_path, "zotero:test-paper", pdf_path)

    script_path = Path("scripts/check_frontend_real_smoke_env.py").resolve()
    env = os.environ.copy()
    env["PAPERPIPE_CONFIG_PATH"] = str(config_path)
    env["PAPERPIPE_STORAGE_DIR"] = str(storage_dir)

    result = subprocess.run(
        [sys.executable, str(script_path), "--require-candidates"],
        cwd=Path.cwd(),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert payload["candidate_count"] == 0
    assert "no_real_smoke_candidates" in payload["errors"]
