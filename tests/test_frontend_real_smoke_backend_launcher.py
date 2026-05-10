from __future__ import annotations

import json
import os
import re
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


def test_real_smoke_backend_launcher_check_only_passes_with_candidates(tmp_path):
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

    script_path = Path("scripts/run_backend_for_real_smoke.py").resolve()
    env = os.environ.copy()
    env["PAPERPIPE_CONFIG_PATH"] = str(config_path)
    env["PAPERPIPE_STORAGE_DIR"] = str(storage_dir)
    env["PAPERPIPE_REAL_SMOKE_REQUIRE_CANDIDATES"] = "1"
    env["E2E_BACKEND_PORT"] = "19090"

    result = subprocess.run(
        [sys.executable, str(script_path), "--check-only"],
        cwd=Path.cwd(),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["backend_port"] == "19090"
    assert payload["worker_enabled"] is True
    assert payload["preflight"]["candidate_count"] == 1


def test_real_smoke_backend_launcher_check_only_can_disable_worker(tmp_path):
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

    script_path = Path("scripts/run_backend_for_real_smoke.py").resolve()
    env = os.environ.copy()
    env["PAPERPIPE_CONFIG_PATH"] = str(config_path)
    env["PAPERPIPE_STORAGE_DIR"] = str(storage_dir)
    env["PAPERPIPE_REAL_SMOKE_REQUIRE_CANDIDATES"] = "1"
    env["PAPERPIPE_REAL_SMOKE_ENABLE_WORKER"] = "0"

    result = subprocess.run(
        [sys.executable, str(script_path), "--check-only"],
        cwd=Path.cwd(),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["worker_enabled"] is False


def test_real_smoke_backend_launcher_fails_for_missing_storage_override(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()
    config_path = tmp_path / "config.yaml"
    _write_config(config_path, vault)

    script_path = Path("scripts/run_backend_for_real_smoke.py").resolve()
    env = os.environ.copy()
    env["PAPERPIPE_CONFIG_PATH"] = str(config_path)
    env["PAPERPIPE_STORAGE_DIR"] = str(tmp_path / "missing-storage")

    result = subprocess.run(
        [sys.executable, str(script_path), "--check-only"],
        cwd=Path.cwd(),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 1
    assert "PAPERPIPE_STORAGE_DIR not found" in result.stderr


def test_frontend_e2e_backend_launcher_template_uses_specialty_trial_extraction() -> None:
    script_path = Path("frontend/scripts/run_backend_for_e2e.sh").resolve()

    content = script_path.read_text(encoding="utf-8")

    assert "specialty_trial_extraction:" in content
    legacy_key_pattern = re.compile(r"(?m)^\\s*trial" r"_extraction:")
    assert legacy_key_pattern.search(content) is None


def test_frontend_e2e_backend_launcher_anchors_runtime_paths_to_repo_root() -> None:
    script_path = Path("frontend/scripts/run_backend_for_e2e.sh").resolve()

    content = script_path.read_text(encoding="utf-8")

    assert 'E2E_RUNTIME_DIR="${REPO_ROOT}/frontend/.e2e-backend-runtime"' in content
    assert 'E2E_VAULT_PATH="${E2E_RUNTIME_DIR}/obsidian"' in content
    assert 'export PAPERPIPE_CONFIG_PATH="${E2E_CONFIG_PATH}"' in content
    assert 'export PAPERPIPE_DB_PATH="${E2E_DB_PATH}"' in content
    assert 'obsidian_vault: "${E2E_VAULT_PATH}"' in content
    assert 'pdf_storage_dir: "${E2E_PDF_STORAGE_PATH}"' in content
    assert "./frontend/.e2e-backend-runtime/" not in content


def test_frontend_e2e_backend_launcher_uses_repo_resolved_python() -> None:
    script_path = Path("frontend/scripts/run_backend_for_e2e.sh").resolve()

    content = script_path.read_text(encoding="utf-8")

    assert 'cd "${REPO_ROOT}"' in content
    assert 'scripts/resolve_verification_python.py" --require-module fastapi --require-module uvicorn' in content
    assert '"${REPO_ROOT}/.venv/bin/python"' not in content


def test_frontend_real_smoke_shell_wrapper_uses_repo_root_and_resolved_python() -> None:
    script_path = Path("frontend/scripts/run_backend_for_real_smoke.sh").resolve()

    content = script_path.read_text(encoding="utf-8")

    assert 'cd "${REPO_ROOT}"' in content
    assert 'scripts/resolve_verification_python.py" --require-module fastapi --require-module uvicorn' in content
    assert "./scripts/run_backend_for_real_smoke.py" in content
    assert "uvicorn backend.main:app" not in content
    assert '"${REPO_ROOT}/.venv/bin/python"' not in content


def test_frontend_real_smoke_preflight_wrapper_uses_repo_root_and_resolved_python() -> None:
    script_path = Path("frontend/scripts/run_real_smoke_preflight.sh").resolve()

    content = script_path.read_text(encoding="utf-8")

    assert 'cd "${REPO_ROOT}"' in content
    assert 'scripts/resolve_verification_python.py" --require-module yaml --require-module fastapi --require-module uvicorn' in content
    assert "./scripts/check_frontend_real_smoke_env.py --require-candidates" in content
    assert '"${REPO_ROOT}/.venv/bin/python"' not in content


def test_frontend_real_smoke_playwright_config_uses_python_launcher_and_same_origin_backend_url() -> None:
    config_path = Path("frontend/playwright.backend.real.config.ts").resolve()

    content = config_path.read_text(encoding="utf-8")

    assert 'resolve_verification_python.py' in content
    assert "./scripts/run_backend_for_real_smoke.py" in content
    assert "run_backend_for_real_smoke.sh" not in content
    assert 'LATTICE_UI_BACKEND_URL: backendBaseUrl' in content
    assert "PAPERPIPE_PYTHON_BIN" not in content


def test_frontend_backend_playwright_configs_use_seeded_wrapper_and_same_origin_backend_url() -> None:
    config_paths = [
        Path("frontend/playwright.backend.config.ts").resolve(),
        Path("frontend/playwright.backend.parser.config.ts").resolve(),
        Path("frontend/playwright.backend.gated.config.ts").resolve(),
        Path("frontend/playwright.workbench-debug.config.ts").resolve(),
    ]

    for config_path in config_paths:
        content = config_path.read_text(encoding="utf-8")
        assert 'command: "./frontend/scripts/run_backend_for_e2e.sh"' in content
        if config_path.name != "playwright.backend.gated.config.ts":
            assert 'LATTICE_UI_BACKEND_URL: backendBaseUrl' in content
