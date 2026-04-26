from __future__ import annotations

from pathlib import Path
from datetime import datetime, timezone

import src.db_utils as db_utils
import src.services.runtime_readiness as runtime_readiness
import src.services.stale_jobs as stale_jobs_service
from src.schemas.ops import RuntimeReadinessCheck, RuntimeReadinessResponse


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


def test_collect_runtime_readiness_warns_for_queue_health_signals(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()
        fixed_now = datetime(2026, 4, 22, 12, 0, 0, tzinfo=timezone.utc)
        monkeypatch.setattr(stale_jobs_service, "utc_now", lambda: fixed_now)

        conn = db_utils.get_db_connection()
        conn.execute(
            """
            INSERT INTO jobs (
                job_id, run_id, paper_id, status, progress, stage, created_at, started_at, heartbeat_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "job_runtime_stale_001",
                "run_runtime_stale_001",
                "paper_runtime_stale_001",
                "running",
                12,
                "read",
                "2026-04-22 10:00:00",
                "2026-04-22 10:15:00",
                "2026-04-22T10:20:00+00:00",
            ),
        )
        conn.execute(
            """
            INSERT INTO jobs (
                job_id, run_id, paper_id, status, progress, created_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                "job_runtime_queued_001",
                "run_runtime_queued_001",
                "paper_runtime_queued_001",
                "queued",
                0,
                "2026-04-22T11:30:00+00:00",
            ),
        )
        conn.execute(
            """
            INSERT INTO job_events (
                event_id, job_id, run_id, ts, level, event_type, message, payload_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "event_runtime_reclaim_001",
                "job_runtime_stale_001",
                "run_runtime_stale_001",
                "2026-04-22T11:55:00+00:00",
                "ERROR",
                "job_reclaimed_stale_running",
                "reclaimed",
                '{"paper_id":"paper_runtime_stale_001","error_code":"STALE_RUNNING_RECLAIMED"}',
            ),
        )
        conn.commit()
        conn.close()

        check = runtime_readiness.collect_queue_health_check(db_path=db_utils.get_db_path())

        assert check.status == "warn"
        assert "queue health needs attention" in check.detail
        assert check.metadata["available"] is True
        assert check.metadata["queued_jobs_total"] == 1
        assert check.metadata["running_jobs_total"] == 1
        assert check.metadata["oldest_queued_age_seconds"] == 1800
        assert check.metadata["stale_running_suspected_total"] == 1
        assert check.metadata["stale_running_reclaimed_total"] == 1
        assert check.metadata["recent_stale_running_reclaims"][0]["job_id"] == "job_runtime_stale_001"
    finally:
        db_utils.DB_PATH = original_db_path


def test_browser_summary_strips_specific_reclaim_identifiers() -> None:
    readiness = RuntimeReadinessResponse(
        status="degraded",
        checks=[
            RuntimeReadinessCheck(
                name="queue_health",
                status="warn",
                detail="queue health needs attention: stale_running_suspected_total=1",
                path="/Users/example/paperpipe/storage/state.db",
                metadata={
                    "available": True,
                    "queued_jobs_total": 0,
                    "running_jobs_total": 1,
                    "stale_running_suspected_total": 1,
                    "recent_stale_running_reclaims": [
                        {
                            "job_id": "job_sensitive",
                            "run_id": "run_sensitive",
                            "paper_id": "paper_sensitive",
                            "error_code": "STALE_RUNNING_RECLAIMED",
                        }
                    ],
                },
            )
        ],
    )

    summary = runtime_readiness.summarize_browser_runtime_readiness(readiness)
    checks = {check.name: check for check in summary.checks}

    assert checks["queue_health"].path is None
    assert checks["queue_health"].metadata == {
        "available": True,
        "queued_jobs_total": 0,
        "running_jobs_total": 1,
        "stale_running_suspected_total": 1,
    }
