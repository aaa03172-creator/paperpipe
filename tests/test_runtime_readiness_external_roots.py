from __future__ import annotations

from pathlib import Path
import sqlite3
from types import SimpleNamespace

import src.services.stale_jobs as stale_jobs
import src.services.runtime_readiness as runtime_readiness
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
    monkeypatch.setattr(runtime_readiness, "select_meeting_pack_archive_candidates", lambda *args, **kwargs: [])

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
    monkeypatch.setattr(runtime_readiness, "select_meeting_pack_archive_candidates", lambda *args, **kwargs: [])

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
    monkeypatch.setattr(runtime_readiness, "select_meeting_pack_archive_candidates", lambda *args, **kwargs: [])

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


def test_collect_runtime_readiness_errors_for_watch_folder_output_overlap(tmp_path, monkeypatch):
    zotero_dir = tmp_path / "zotero"
    vault_dir = tmp_path / "vault"
    storage_dir = tmp_path / "storage" / "pdfs"
    watch_dir = storage_dir / "incoming"
    zotero_dir.mkdir()
    vault_dir.mkdir()
    storage_dir.mkdir(parents=True)
    config_path = tmp_path / "config.yaml"
    _write_config(config_path, zotero=str(zotero_dir), vault=str(vault_dir))
    config_text = config_path.read_text(encoding="utf-8").replace(
        f'watch_folder: "{config_path.parent / "watch-folder"}"',
        f'watch_folder: "{watch_dir}"',
    )
    config_path.write_text(config_text, encoding="utf-8")

    monkeypatch.setenv("PAPERPIPE_CONFIG_PATH", str(config_path))
    monkeypatch.setattr(runtime_readiness, "select_meeting_pack_archive_candidates", lambda *args, **kwargs: [])

    readiness = runtime_readiness.collect_runtime_readiness()
    checks = {check.name: check for check in readiness.checks}

    assert readiness.status == "error"
    assert checks["config_file"].status == "error"
    assert "paths.watch_folder overlaps managed output paths" in checks["config_file"].detail


def test_collect_runtime_readiness_errors_for_downloads_watch_output_overlap(tmp_path, monkeypatch):
    zotero_dir = tmp_path / "zotero"
    vault_dir = tmp_path / "vault"
    storage_dir = tmp_path / "storage" / "pdfs"
    zotero_dir.mkdir()
    vault_dir.mkdir()
    storage_dir.mkdir(parents=True)
    config_path = tmp_path / "config.yaml"
    _write_config(config_path, zotero=str(zotero_dir), vault=str(vault_dir))
    config_text = config_path.read_text(encoding="utf-8").replace(
        f'downloads_watch_dir: "{config_path.parent / "Downloads"}"',
        f'downloads_watch_dir: "{storage_dir / "incoming"}"',
    )
    config_path.write_text(config_text, encoding="utf-8")

    monkeypatch.setenv("PAPERPIPE_CONFIG_PATH", str(config_path))
    monkeypatch.setattr(runtime_readiness, "select_meeting_pack_archive_candidates", lambda *args, **kwargs: [])

    readiness = runtime_readiness.collect_runtime_readiness()
    checks = {check.name: check for check in readiness.checks}

    assert readiness.status == "error"
    assert checks["config_file"].status == "error"
    assert "paths.downloads_watch_dir overlaps paths.pdf_storage_dir" in checks["config_file"].detail


def test_collect_runtime_readiness_warns_for_hidden_fixture_structured_state(tmp_path, monkeypatch):
    zotero_dir = tmp_path / "zotero"
    vault_dir = tmp_path / "vault"
    zotero_dir.mkdir()
    vault_dir.mkdir()
    (vault_dir / ".pp" / "fixture-note").mkdir(parents=True)
    (vault_dir / ".pp" / "fixture-note" / "state.json").write_text(
        """
{
  "paper_slug": "fixture-note",
  "updated_at": "2026-03-10T09:00:00Z",
  "runs": [],
  "signals": {"has_claimset": true},
  "claimset": [
    {
      "id": "claim_c0ffee000001",
      "source_claim_id": "e2e-claim-1",
      "claim": "Fixture claim",
      "evidence_ids": ["evidence_deadbeef0001"],
      "evidence": [
        {
          "id": "evidence_deadbeef0001",
          "claim_id": "claim_c0ffee000001",
          "text": "Fixture evidence",
          "locator": {"chunk_id": "chunk-e2e-001", "source": "bbox"}
        }
      ]
    }
  ],
  "entities": [],
  "mesh": [],
  "outcomes": []
}
""".strip(),
        encoding="utf-8",
    )

    config_path = tmp_path / "config.yaml"
    _write_config(config_path, zotero=str(zotero_dir), vault=str(vault_dir))
    monkeypatch.setenv("PAPERPIPE_CONFIG_PATH", str(config_path))
    monkeypatch.setattr(runtime_readiness, "select_meeting_pack_archive_candidates", lambda *args, **kwargs: [])

    readiness = runtime_readiness.collect_runtime_readiness()
    checks = {check.name: check for check in readiness.checks}

    assert checks["structured_state_hygiene"].status == "warn"
    assert "hidden fixture structured states detected" in checks["structured_state_hygiene"].detail
    assert ".pp/fixture-note/state.json" in checks["structured_state_hygiene"].detail


def test_collect_runtime_readiness_warns_for_meeting_pack_archive_candidates(tmp_path, monkeypatch):
    zotero_dir = tmp_path / "zotero"
    vault_dir = tmp_path / "vault"
    zotero_dir.mkdir()
    vault_dir.mkdir()
    config_path = tmp_path / "config.yaml"
    _write_config(config_path, zotero=str(zotero_dir), vault=str(vault_dir))
    monkeypatch.setenv("PAPERPIPE_CONFIG_PATH", str(config_path))
    monkeypatch.setattr(
        runtime_readiness,
        "select_meeting_pack_archive_candidates",
        lambda *args, **kwargs: [
            SimpleNamespace(
                pack_id="meetingpack_20260410T000000000000Z_journal_club_alpha",
                reason="superseded_by_recent_healthy_pack",
            ),
            SimpleNamespace(
                pack_id="meetingpack_20260410T000100000000Z_project_progress_update_fixture",
                reason="fixture_like_pack",
            ),
        ],
    )

    readiness = runtime_readiness.collect_runtime_readiness()
    checks = {check.name: check for check in readiness.checks}

    assert checks["meeting_pack_storage_hygiene"].status == "warn"
    assert "Meeting Pack archive candidates detected (2;" in checks["meeting_pack_storage_hygiene"].detail
    assert "fixture_like_pack=1" in checks["meeting_pack_storage_hygiene"].detail
    assert "superseded_by_recent_healthy_pack=1" in checks["meeting_pack_storage_hygiene"].detail
    assert "paperpipe archive-meeting-pack-noise" in checks["meeting_pack_storage_hygiene"].detail


def test_collect_runtime_readiness_warns_for_fixture_paper_cleanup_candidates(tmp_path, monkeypatch):
    zotero_dir = tmp_path / "zotero"
    vault_dir = tmp_path / "vault"
    db_path = tmp_path / "state.db"
    zotero_dir.mkdir()
    vault_dir.mkdir()
    sqlite3.connect(db_path).close()
    config_path = tmp_path / "config.yaml"
    _write_config(config_path, zotero=str(zotero_dir), vault=str(vault_dir))
    monkeypatch.setenv("PAPERPIPE_CONFIG_PATH", str(config_path))
    monkeypatch.setattr(runtime_readiness, "select_meeting_pack_archive_candidates", lambda *args, **kwargs: [])
    monkeypatch.setattr(runtime_readiness, "get_db_path", lambda: db_path)
    monkeypatch.setattr(
        runtime_readiness,
        "select_fixture_paper_archive_candidates",
        lambda conn: [
            SimpleNamespace(paper_id="paper-e2e-001", fixture_reason="fixture_visibility_rule"),
            SimpleNamespace(paper_id="test_local_id", fixture_reason="paper_id_test_prefix"),
        ],
    )

    readiness = runtime_readiness.collect_runtime_readiness()
    checks = {check.name: check for check in readiness.checks}

    assert checks["fixture_paper_hygiene"].status == "warn"
    assert "fixture paper cleanup candidates detected (2;" in checks["fixture_paper_hygiene"].detail
    assert "fixture_visibility_rule=1" in checks["fixture_paper_hygiene"].detail
    assert "paper_id_test_prefix=1" in checks["fixture_paper_hygiene"].detail
    assert "paperpipe archive-fixture-no-feedback-papers" in checks["fixture_paper_hygiene"].detail


def test_collect_runtime_readiness_escalates_fixture_paper_cleanup_at_threshold(tmp_path, monkeypatch):
    zotero_dir = tmp_path / "zotero"
    vault_dir = tmp_path / "vault"
    db_path = tmp_path / "state.db"
    zotero_dir.mkdir()
    vault_dir.mkdir()
    sqlite3.connect(db_path).close()
    config_path = tmp_path / "config.yaml"
    _write_config(config_path, zotero=str(zotero_dir), vault=str(vault_dir))
    monkeypatch.setenv("PAPERPIPE_CONFIG_PATH", str(config_path))
    monkeypatch.setattr(runtime_readiness, "select_meeting_pack_archive_candidates", lambda *args, **kwargs: [])
    monkeypatch.setattr(runtime_readiness, "get_db_path", lambda: db_path)
    monkeypatch.setattr(
        runtime_readiness,
        "select_fixture_paper_archive_candidates",
        lambda conn: [
            SimpleNamespace(
                paper_id=f"paper-e2e-{idx:03d}",
                fixture_reason="fixture_visibility_rule",
            )
            for idx in range(runtime_readiness.FIXTURE_PAPER_HYGIENE_ERROR_THRESHOLD)
        ],
    )

    readiness = runtime_readiness.collect_runtime_readiness()
    checks = {check.name: check for check in readiness.checks}

    assert readiness.status == "error"
    assert checks["fixture_paper_hygiene"].status == "error"
    assert "too many fixture rows are distorting local classification-audit counts" in checks["fixture_paper_hygiene"].detail


def test_collect_runtime_readiness_warns_for_queue_health_signals(tmp_path, monkeypatch):
    zotero_dir = tmp_path / "zotero"
    vault_dir = tmp_path / "vault"
    db_path = tmp_path / "state.db"
    zotero_dir.mkdir()
    vault_dir.mkdir()
    config_path = tmp_path / "config.yaml"
    _write_config(config_path, zotero=str(zotero_dir), vault=str(vault_dir))

    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            """
            CREATE TABLE jobs (
                job_id TEXT PRIMARY KEY,
                run_id TEXT,
                paper_id TEXT,
                status TEXT,
                progress INTEGER,
                stage TEXT,
                created_at TEXT,
                started_at TEXT,
                artifact_dir TEXT,
                log_path TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE job_events (
                event_id TEXT PRIMARY KEY,
                job_id TEXT NOT NULL,
                run_id TEXT,
                ts TEXT NOT NULL,
                level TEXT NOT NULL,
                event_type TEXT NOT NULL,
                message TEXT,
                payload_json TEXT
            )
            """
        )
        conn.execute(
            """
            INSERT INTO jobs (
                job_id, run_id, paper_id, status, progress, stage, created_at, started_at, artifact_dir, log_path
            )
            VALUES (?, ?, ?, 'queued', ?, ?, ?, ?, ?, ?)
            """,
            (
                "job-queued",
                "run-queued",
                "paper-queued",
                0,
                "queued",
                "2026-04-22T11:30:00+00:00",
                None,
                None,
                None,
            ),
        )
        conn.execute(
            """
            INSERT INTO jobs (
                job_id, run_id, paper_id, status, progress, stage, created_at, started_at, artifact_dir, log_path
            )
            VALUES (?, ?, ?, 'running', ?, ?, ?, ?, ?, ?)
            """,
            (
                "job-running",
                "run-running",
                "paper-running",
                45,
                "extracting",
                "2026-04-22T11:15:00+00:00",
                "2026-04-22T11:20:00+00:00",
                None,
                None,
            ),
        )
        conn.execute(
            """
            INSERT INTO job_events (
                event_id, job_id, run_id, ts, level, event_type, message, payload_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "event-reclaim-001",
                "job-running",
                "run-running",
                "2026-04-22T11:55:00+00:00",
                "ERROR",
                "job_reclaimed_stale_running",
                "reclaimed once",
                '{"status":"failed","error_code":"STALE_RUNNING_RECLAIMED"}',
            ),
        )
        conn.execute(
            """
            INSERT INTO job_events (
                event_id, job_id, run_id, ts, level, event_type, message, payload_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "event-requeue-001",
                "job-running",
                "run-running",
                "2026-04-22T11:57:00+00:00",
                "INFO",
                "job_requeued_replacement",
                "replacement queued",
                '{"replacement_job_id":"job-replacement","replacement_run_id":"run-replacement"}',
            ),
        )
        conn.commit()
    finally:
        conn.close()

    monkeypatch.setenv("PAPERPIPE_CONFIG_PATH", str(config_path))
    monkeypatch.setattr(runtime_readiness, "select_meeting_pack_archive_candidates", lambda *args, **kwargs: [])
    monkeypatch.setattr(runtime_readiness, "get_db_path", lambda: db_path)
    monkeypatch.setattr(
        stale_jobs,
        "utc_now",
        lambda: stale_jobs.datetime(2026, 4, 22, 12, 0, 0, tzinfo=stale_jobs.timezone.utc),
    )

    readiness = runtime_readiness.collect_runtime_readiness()
    checks = {check.name: check for check in readiness.checks}

    assert checks["queue_health"].status == "warn"
    assert "queue health needs attention" in checks["queue_health"].detail
    assert checks["queue_health"].metadata["available"] is True
    assert checks["queue_health"].metadata["queued_jobs_total"] == 1
    assert checks["queue_health"].metadata["running_jobs_total"] == 1
    assert checks["queue_health"].metadata["oldest_queued_age_seconds"] == 1800
    assert checks["queue_health"].metadata["stale_running_suspected_total"] == 1
    assert checks["queue_health"].metadata["stale_running_reclaimed_total"] == 1
    assert checks["queue_health"].metadata["last_stale_running_reclaimed_at"] == "2026-04-22T11:55:00+00:00"
    assert checks["queue_health"].metadata["stale_running_requeued_total"] == 1
    assert checks["queue_health"].metadata["last_stale_running_requeued_at"] == "2026-04-22T11:57:00+00:00"
    assert checks["queue_health"].metadata["recent_stale_running_reclaims"] == [
        {
            "job_id": "job-running",
            "run_id": "run-running",
            "paper_id": None,
            "reclaimed_at": "2026-04-22T11:55:00+00:00",
            "error_code": "STALE_RUNNING_RECLAIMED",
            "replacement_job_id": "job-replacement",
            "replacement_run_id": "run-replacement",
            "requeued_at": "2026-04-22T11:57:00+00:00",
        }
    ]
    assert checks["queue_health"].metadata["queue_age_warn_triggered"] is True
    assert checks["queue_health"].metadata["stale_running_warn_triggered"] is True
    assert "stale_running_reclaimed_total=1" in checks["queue_health"].detail
    assert "stale_running_requeued_total=1" in checks["queue_health"].detail


def test_browser_summary_surfaces_watch_boundary_warning() -> None:
    readiness = RuntimeReadinessResponse(
        status="degraded",
        checks=[
            RuntimeReadinessCheck(
                name="watch_folder",
                status="ok",
                detail="watched folder exists for automatic PDF pickup",
            ),
            RuntimeReadinessCheck(
                name="watch_folder_boundary",
                status="warn",
                detail="watch folder overlaps managed output paths",
            ),
            RuntimeReadinessCheck(
                name="downloads_watch_dir",
                status="ok",
                detail="downloads pickup folder exists on this machine",
            ),
            RuntimeReadinessCheck(
                name="downloads_watch_dir_boundary",
                status="warn",
                detail="downloads watch folder overlaps PDF storage",
            ),
        ],
    )

    summarized = runtime_readiness.summarize_browser_runtime_readiness(readiness)
    checks = {check.name: check for check in summarized.checks}

    assert checks["watch_folder"].status == "warn"
    assert checks["downloads_watch_dir"].status == "warn"


def test_browser_summary_preserves_queue_health_metadata() -> None:
    readiness = RuntimeReadinessResponse(
        status="degraded",
        checks=[
            RuntimeReadinessCheck(
                name="queue_health",
                status="warn",
                detail=(
                    "queue health needs attention: queued=2, running=1, oldest_queued_age_seconds=1800, "
                    "stale_running_suspected_total=1, stale_running_reclaimed_total=1, "
                    "last_stale_running_reclaimed_at=2026-04-22T11:55:00+00:00"
                ),
                path="/Users/example/repo/runtime/state.db",
                metadata={
                    "available": True,
                    "generated_at": "2026-04-22T12:00:00+00:00",
                    "stale_after_seconds": 900,
                    "queued_age_warn_after_seconds": 900,
                    "queued_jobs_total": 2,
                    "running_jobs_total": 1,
                    "oldest_queued_age_seconds": 1800,
                    "stale_running_suspected_total": 1,
                    "stale_running_reclaimed_total": 1,
                    "last_stale_running_reclaimed_at": "2026-04-22T11:55:00+00:00",
                    "stale_running_requeued_total": 1,
                    "last_stale_running_requeued_at": "2026-04-22T11:57:00+00:00",
                    "recent_stale_running_reclaims": [
                        {
                            "job_id": "job-running",
                            "run_id": "run-running",
                            "paper_id": None,
                            "reclaimed_at": "2026-04-22T11:55:00+00:00",
                            "error_code": "STALE_RUNNING_RECLAIMED",
                            "replacement_job_id": "job-replacement",
                            "replacement_run_id": "run-replacement",
                            "requeued_at": "2026-04-22T11:57:00+00:00",
                        }
                    ],
                    "queue_age_warn_triggered": True,
                    "stale_running_warn_triggered": True,
                },
            )
        ],
    )

    summarized = runtime_readiness.summarize_browser_runtime_readiness(readiness)
    checks = {check.name: check for check in summarized.checks}

    assert summarized.status == "degraded"
    assert checks["queue_health"].status == "warn"
    assert checks["queue_health"].detail == (
        "queue health needs attention: queued=2, running=1, oldest_queued_age_seconds=1800, "
        "stale_running_suspected_total=1, stale_running_reclaimed_total=1, "
        "last_stale_running_reclaimed_at=2026-04-22T11:55:00+00:00"
    )
    assert checks["queue_health"].path is None
    assert checks["queue_health"].metadata == {
        "available": True,
        "generated_at": "2026-04-22T12:00:00+00:00",
        "stale_after_seconds": 900,
        "queued_age_warn_after_seconds": 900,
        "queued_jobs_total": 2,
        "running_jobs_total": 1,
        "oldest_queued_age_seconds": 1800,
        "stale_running_suspected_total": 1,
        "stale_running_reclaimed_total": 1,
        "last_stale_running_reclaimed_at": "2026-04-22T11:55:00+00:00",
        "stale_running_requeued_total": 1,
        "last_stale_running_requeued_at": "2026-04-22T11:57:00+00:00",
        "queue_age_warn_triggered": True,
        "stale_running_warn_triggered": True,
    }


def test_browser_summary_preserves_latest_intake_override_audit_advisory() -> None:
    readiness = RuntimeReadinessResponse(
        status="ok",
        checks=[
            RuntimeReadinessCheck(
                name="latest_intake_override_audit",
                status="ok",
                detail="latest intake override audit is available (intake_override_audit_20260420)",
                path="/Users/example/repo/snapshots/intake_override_audits/intake_override_audit_20260420/audit.md",
                metadata={
                    "available": True,
                    "run_id": "intake_override_audit_20260420",
                    "generated_at": "2026-04-20T05:00:00+00:00",
                    "source": "rows_jsonl",
                    "row_count": 7,
                    "audited_document_count": 3,
                    "triage_override_rate": 0.25,
                    "slot_disagreement_rate": 0.5,
                    "selection_fallback_count": 1,
                    "selection_fallback_rate": 0.333,
                    "slot_disagreement_count": 2,
                    "llm_slot_adjudication_rate": 0.5,
                    "llm_tagging_adjudication_rate": 0.25,
                    "analysis_unavailable_rate": 0.0,
                    "issues_state_unavailable_rate": 0.25,
                    "quality_signals": [
                        "slot_disagreement_present",
                        "selection_fallback_present",
                        "triage_override_present",
                        "slot_adjudication_present",
                        "tagging_adjudication_present",
                        "issues_state_unavailable_present",
                    ],
                },
            )
            ,
            RuntimeReadinessCheck(
                name="latest_intake_override_audit_quality",
                status="warn",
                detail="latest intake override audit quality needs attention: triage=25.0%, slot=50.0%",
                metadata={
                    "available": True,
                    "warn_threshold": 0.25,
                    "min_audited_docs": 3,
                    "audited_document_count": 3,
                    "sample_sufficient": True,
                    "quality_signals": [
                        "slot_disagreement_present",
                        "triage_override_present",
                    ],
                    "calibration": {
                        "total_runs": 2,
                        "eligible_runs": 1,
                        "warn_runs": 1,
                        "calibration_target_runs": 3,
                        "target_met": False,
                        "advice": "Keep the current 25% warning threshold for now.",
                    },
                },
            ),
        ],
    )

    summarized = runtime_readiness.summarize_browser_runtime_readiness(readiness)
    checks = {check.name: check for check in summarized.checks}

    assert checks["latest_intake_override_audit"].status == "ok"
    assert "latest intake override audit is available" in checks["latest_intake_override_audit"].detail
    assert checks["latest_intake_override_audit"].path is None
    assert checks["latest_intake_override_audit"].metadata == {
        "available": True,
        "run_id": "intake_override_audit_20260420",
        "generated_at": "2026-04-20T05:00:00+00:00",
        "source": "rows_jsonl",
        "row_count": 7,
        "audited_document_count": 3,
        "triage_override_rate": 0.25,
        "slot_disagreement_rate": 0.5,
        "selection_fallback_count": 1,
        "selection_fallback_rate": 0.333,
        "slot_disagreement_count": 2,
        "llm_slot_adjudication_rate": 0.5,
        "llm_tagging_adjudication_rate": 0.25,
        "analysis_unavailable_rate": 0.0,
        "issues_state_unavailable_rate": 0.25,
        "quality_signals": [
            "slot_disagreement_present",
            "selection_fallback_present",
            "triage_override_present",
            "slot_adjudication_present",
            "tagging_adjudication_present",
            "issues_state_unavailable_present",
        ],
    }
    assert checks["latest_intake_override_audit_quality"].status == "warn"
    assert "quality needs attention" in checks["latest_intake_override_audit_quality"].detail
    assert checks["latest_intake_override_audit_quality"].metadata == {
        "available": True,
        "warn_threshold": 0.25,
        "min_audited_docs": 3,
        "audited_document_count": 3,
        "sample_sufficient": True,
        "quality_signals": [
            "slot_disagreement_present",
            "triage_override_present",
        ],
        "calibration": {
            "total_runs": 2,
            "eligible_runs": 1,
            "warn_runs": 1,
            "calibration_target_runs": 3,
            "target_met": False,
            "advice": "Keep the current 25% warning threshold for now.",
        },
    }


def test_browser_summary_preserves_latest_threshold_review_advisory() -> None:
    readiness = RuntimeReadinessResponse(
        status="ok",
        checks=[
            RuntimeReadinessCheck(
                name="latest_intake_override_threshold_review",
                status="ok",
                detail="latest intake override threshold review is available (threshold_review_20260421)",
                path="/Users/example/repo/snapshots/intake_override_threshold_review/threshold_review_20260421/summary.json",
                metadata={
                    "available": True,
                    "run_id": "threshold_review_20260421",
                    "provenance_kind": "operator",
                    "latest_eligible": True,
                    "generated_at": "2026-04-21T07:30:00+00:00",
                    "warn_threshold": 0.25,
                    "min_audited_docs": 3,
                    "calibration_target_runs": 3,
                    "recommended_action": "hold_current_threshold",
                    "review_ready": False,
                    "decision_reason": "only 1 sufficiently-audited run exists; persistent adjudication signals: slot_adjudication",
                    "next_step": "collect_more_audit_runs",
                    "latest_run_id": "audit_latest",
                    "latest_run_status": "warn",
                    "focus_signals": ["slot_adjudication", "slot", "triage"],
                    "latest_warn_signals": ["slot", "slot_adjudication"],
                    "blocking_summary": "1.collect_more_audit_runs: 1/3 sufficiently-audited runs currently meet the review floor, so threshold changes should stay blocked until more audit evidence accumulates.",
                    "blocking_action": {
                        "order": 1,
                        "action": "collect_more_audit_runs",
                        "target": None,
                        "blocking": True,
                        "signals": [],
                        "summary": "Gather more sufficiently-audited runs before promoting this threshold review into manual threshold changes.",
                        "evidence": "1/3 sufficiently-audited runs currently meet the review floor, so threshold changes should stay blocked until more audit evidence accumulates.",
                    },
                    "tuning_targets": ["slot_classification"],
                    "tuning_actions": [
                        {
                            "target": "slot_classification",
                            "action": "audit_slot_ambiguity_thresholds",
                            "summary": "Inspect ambiguity thresholds and evidence-bundle cues before policy changes.",
                        }
                    ],
                    "action_plan": [
                        {
                            "order": 1,
                            "action": "collect_more_audit_runs",
                            "target": None,
                            "blocking": True,
                            "signals": [],
                            "summary": "Gather more sufficiently-audited runs before promoting this threshold review into manual threshold changes.",
                            "evidence": "1/3 sufficiently-audited runs currently meet the review floor, so threshold changes should stay blocked until more audit evidence accumulates.",
                        },
                        {
                            "order": 2,
                            "action": "audit_slot_ambiguity_thresholds",
                            "target": "slot_classification",
                            "blocking": False,
                            "signals": ["slot_adjudication"],
                            "summary": "Inspect ambiguity thresholds and evidence-bundle cues before policy changes.",
                            "evidence": "Triggered because slot adjudication remains present in the threshold-review focus/latest-warn signals, which points to slot-classification ambiguity rather than a pure threshold-only issue.",
                        },
                    ],
                    "tuning_recommendations": [
                        "Audit slot-classification ambiguity thresholds and evidence-bundle cues before widening the warning-threshold review policy."
                    ],
                },
            )
        ],
    )

    summarized = runtime_readiness.summarize_browser_runtime_readiness(readiness)
    checks = {check.name: check for check in summarized.checks}

    assert checks["latest_intake_override_threshold_review"].status == "ok"
    assert "latest intake override threshold review is available" in checks["latest_intake_override_threshold_review"].detail
    assert checks["latest_intake_override_threshold_review"].path is None
    assert checks["latest_intake_override_threshold_review"].metadata == {
        "available": True,
        "run_id": "threshold_review_20260421",
        "provenance_kind": "operator",
        "latest_eligible": True,
        "generated_at": "2026-04-21T07:30:00+00:00",
        "warn_threshold": 0.25,
        "min_audited_docs": 3,
        "calibration_target_runs": 3,
        "recommended_action": "hold_current_threshold",
        "review_ready": False,
        "decision_reason": "only 1 sufficiently-audited run exists; persistent adjudication signals: slot_adjudication",
        "next_step": "collect_more_audit_runs",
        "latest_run_id": "audit_latest",
        "latest_run_status": "warn",
        "focus_signals": ["slot_adjudication", "slot", "triage"],
        "latest_warn_signals": ["slot", "slot_adjudication"],
        "blocking_summary": "1.collect_more_audit_runs: 1/3 sufficiently-audited runs currently meet the review floor, so threshold changes should stay blocked until more audit evidence accumulates.",
        "blocking_action": {
            "order": 1,
            "action": "collect_more_audit_runs",
            "target": None,
            "blocking": True,
            "signals": [],
            "summary": "Gather more sufficiently-audited runs before promoting this threshold review into manual threshold changes.",
            "evidence": "1/3 sufficiently-audited runs currently meet the review floor, so threshold changes should stay blocked until more audit evidence accumulates.",
        },
        "tuning_targets": ["slot_classification"],
        "tuning_actions": [
            {
                "target": "slot_classification",
                "action": "audit_slot_ambiguity_thresholds",
                "summary": "Inspect ambiguity thresholds and evidence-bundle cues before policy changes.",
            }
        ],
        "action_plan": [
            {
                "order": 1,
                "action": "collect_more_audit_runs",
                "target": None,
                "blocking": True,
                "signals": [],
                "summary": "Gather more sufficiently-audited runs before promoting this threshold review into manual threshold changes.",
                "evidence": "1/3 sufficiently-audited runs currently meet the review floor, so threshold changes should stay blocked until more audit evidence accumulates.",
            },
            {
                "order": 2,
                "action": "audit_slot_ambiguity_thresholds",
                "target": "slot_classification",
                "blocking": False,
                "signals": ["slot_adjudication"],
                "summary": "Inspect ambiguity thresholds and evidence-bundle cues before policy changes.",
                "evidence": "Triggered because slot adjudication remains present in the threshold-review focus/latest-warn signals, which points to slot-classification ambiguity rather than a pure threshold-only issue.",
            },
        ],
        "tuning_recommendations": [
            "Audit slot-classification ambiguity thresholds and evidence-bundle cues before widening the warning-threshold review policy."
        ],
    }


def test_browser_summary_preserves_latest_processor_gate_threshold_review_advisory() -> None:
    readiness = RuntimeReadinessResponse(
        status="ok",
        checks=[
            RuntimeReadinessCheck(
                name="latest_processor_gate_threshold_review",
                status="ok",
                detail="latest processor gate threshold review is available (processor_gate_threshold_review_20260421)",
                path="/Users/example/repo/snapshots/processor_gate_threshold_review/processor_gate_threshold_review_20260421/summary.json",
                metadata={
                    "available": True,
                    "run_id": "processor_gate_threshold_review_20260421",
                    "markdown_available": True,
                    "manual_review_rows_available": True,
                    "manual_review_markdown_available": True,
                    "manual_review_checklist_available": True,
                    "manual_review_basis_markdown_available": True,
                    "threshold_change_proposal_available": False,
                    "threshold_change_proposal_markdown_available": False,
                    "threshold_change_validation_replay_command_template": (
                        "python3 scripts/eval/audit_processor_gate_replay_drift.py "
                        "--threshold-change-proposal threshold_change_proposal.json "
                        "--reviewed-high-threshold '<REVIEWED_HIGH_THRESHOLD>'"
                    ),
                    "threshold_change_validation_replay_available": False,
                    "threshold_change_validation_replay_matches_proposal": False,
                    "threshold_change_validation_replay_needs_rerun": False,
                    "threshold_change_validation_replay_status": "not_applicable",
                    "threshold_replay_available": False,
                    "threshold_replay_markdown_available": False,
                    "threshold_replay_review_command_available": False,
                    "threshold_replay_review_command": (
                        "python3 scripts/eval/recommend_processor_gate_threshold_review.py "
                        "--drift-summary summary.json --run-id validation__threshold_review"
                    ),
                    "threshold_replay_text": None,
                    "threshold_replay_mode": None,
                    "threshold_replay_high_threshold": None,
                    "threshold_replay_low_threshold": None,
                    "threshold_replay_reviewed_high_threshold": None,
                    "threshold_replay_proposal_run_id": None,
                    "generated_at": "2026-04-21T07:30:00+00:00",
                    "drift_summary_available": True,
                    "drift_details_available": True,
                    "drift_markdown_available": True,
                    "high_threshold": 0.9,
                    "low_threshold": 0.7,
                    "min_candidate_rows": 20,
                    "drift_warn_threshold": 0.25,
                    "recommended_action": "manual_gate_threshold_review",
                    "review_ready": True,
                    "decision_reason": "latest drift run shows 26/54 drift row(s) (48.1%), above the 25% warning threshold",
                    "next_step": "review_gate_thresholds_and_mid_confidence_policy",
                    "latest_run_id": "processor_gate_replay_drift_preapply_20260421_r11",
                    "latest_run_status": "warn",
                    "threshold_change_ready": False,
                    "threshold_change_status": "blocked_policy_only",
                    "threshold_change_next_step": "review_mid_confidence_escalation_policy",
                    "threshold_change_blocker": "All 21 threshold-relevant row(s) are mid-confidence legacy approvals replaying to pending review; none support a high-threshold boundary change from this evidence alone.",
                    "threshold_change_text": "ready=no, status=blocked_policy_only, next=review_mid_confidence_escalation_policy",
                    "focus_areas": ["high_threshold", "mid_confidence_escalation"],
                    "tuning_targets": ["mid_confidence_escalation"],
                    "tuning_actions": [
                        {
                            "target": "mid_confidence_escalation",
                            "action": "review_mid_confidence_escalation_policy",
                            "summary": "Review whether historical mid-confidence approvals should now escalate to pending review before changing the high threshold.",
                        }
                    ],
                    "action_plan": [
                        {
                            "order": 1,
                            "action": "review_gate_thresholds_and_mid_confidence_policy",
                            "target": None,
                            "blocking": True,
                            "summary": "Use the threshold-relevant bucket as the primary manual-review basis before applying gate threshold changes.",
                        }
                    ],
                    "candidate_count": 54,
                    "promotable_count": 28,
                    "drift_count": 26,
                    "drift_rate": 0.481481,
                    "threshold_relevant_count": 21,
                    "policy_edge_case_count": 1,
                    "excluded_manual_override_count": 2,
                    "excluded_indexed_pending_count": 3,
                    "excluded_fixture_or_test_count": 4,
                    "excluded_other_count": 5,
                    "manual_review_scope_text": "relevant=21, policy=1, excluded.manual_override=2, excluded.indexed_pending=3, excluded.fixture_or_test=4, excluded.other=5",
                    "manual_review_scope_samples_text": "relevant=paper-a, paper-b, paper-c (+1 more) | excluded.manual_override=manual-1, manual-2 | excluded.indexed_pending=indexed-1, indexed-2, indexed-3 (+1 more) | excluded.fixture_or_test=fixture-1",
                    "threshold_relevant_sample_ids": ["paper-a", "paper-b", "paper-c"],
                    "excluded_manual_override_sample_ids": ["manual-1", "manual-2"],
                    "excluded_indexed_pending_sample_ids": ["indexed-1", "indexed-2", "indexed-3"],
                    "excluded_fixture_or_test_sample_ids": ["fixture-1"],
                    "manual_review_focus_recommendation": "Focus threshold tuning on threshold-relevant rows first.",
                    "worksheet_pending_count": 21,
                    "worksheet_primary_review_target": "mid_confidence_escalation_policy",
                    "worksheet_excluded_count": 9,
                    "worksheet_text": "pending=21, target=mid_confidence_escalation_policy, excluded=9",
                    "worksheet_summary": "21 threshold-relevant row(s) are queued for mid-confidence escalation policy review; exclude 9 non-threshold row(s) from raw threshold changes.",
                    "manual_review_basis_preliminary_call": "mid_confidence_policy_only",
                    "manual_review_basis_policy_support_count": 21,
                    "manual_review_basis_high_threshold_support_count": 0,
                    "manual_review_basis_text": "call=mid_confidence_policy_only, policy=21, high=0",
                    "manual_review_basis_summary": "All 21 threshold-relevant row(s) are mid-confidence legacy approvals replaying to pending review; none support a high-threshold boundary change from this evidence alone.",
                },
            )
        ],
    )

    summarized = runtime_readiness.summarize_browser_runtime_readiness(readiness)
    checks = {check.name: check for check in summarized.checks}

    assert checks["latest_processor_gate_threshold_review"].status == "ok"
    assert "latest processor gate threshold review is available" in checks["latest_processor_gate_threshold_review"].detail
    assert checks["latest_processor_gate_threshold_review"].path is None
    assert checks["latest_processor_gate_threshold_review"].metadata == {
        "available": True,
        "run_id": "processor_gate_threshold_review_20260421",
        "markdown_available": True,
        "manual_review_rows_available": True,
        "manual_review_markdown_available": True,
        "manual_review_checklist_available": True,
        "manual_review_basis_markdown_available": True,
        "threshold_change_proposal_available": False,
        "threshold_change_proposal_markdown_available": False,
        "threshold_change_validation_replay_command_available": True,
        "threshold_change_validation_replay_available": False,
        "threshold_change_validation_replay_matches_proposal": False,
        "threshold_change_validation_replay_needs_rerun": False,
        "threshold_change_validation_replay_status": "not_applicable",
        "threshold_replay_available": False,
        "threshold_replay_markdown_available": False,
        "threshold_replay_review_command_available": True,
        "threshold_replay_text": None,
        "threshold_replay_mode": None,
        "threshold_replay_high_threshold": None,
        "threshold_replay_low_threshold": None,
        "threshold_replay_reviewed_high_threshold": None,
        "threshold_replay_proposal_run_id": None,
        "generated_at": "2026-04-21T07:30:00+00:00",
        "drift_summary_available": True,
        "drift_details_available": True,
        "drift_markdown_available": True,
        "high_threshold": 0.9,
        "low_threshold": 0.7,
        "min_candidate_rows": 20,
        "drift_warn_threshold": 0.25,
        "recommended_action": "manual_gate_threshold_review",
        "review_ready": True,
        "decision_reason": "latest drift run shows 26/54 drift row(s) (48.1%), above the 25% warning threshold",
        "next_step": "review_gate_thresholds_and_mid_confidence_policy",
        "latest_run_id": "processor_gate_replay_drift_preapply_20260421_r11",
        "latest_run_status": "warn",
        "threshold_change_ready": False,
        "threshold_change_status": "blocked_policy_only",
        "threshold_change_next_step": "review_mid_confidence_escalation_policy",
        "threshold_change_blocker": "All 21 threshold-relevant row(s) are mid-confidence legacy approvals replaying to pending review; none support a high-threshold boundary change from this evidence alone.",
        "threshold_change_text": "ready=no, status=blocked_policy_only, next=review_mid_confidence_escalation_policy",
        "focus_areas": ["high_threshold", "mid_confidence_escalation"],
        "tuning_targets": ["mid_confidence_escalation"],
        "tuning_actions": [
            {
                "target": "mid_confidence_escalation",
                "action": "review_mid_confidence_escalation_policy",
                "summary": "Review whether historical mid-confidence approvals should now escalate to pending review before changing the high threshold.",
            }
        ],
        "action_plan": [
            {
                "order": 1,
                "action": "review_gate_thresholds_and_mid_confidence_policy",
                "target": None,
                "blocking": True,
                "summary": "Use the threshold-relevant bucket as the primary manual-review basis before applying gate threshold changes.",
            }
        ],
        "candidate_count": 54,
        "promotable_count": 28,
        "drift_count": 26,
        "drift_rate": 0.481481,
        "threshold_relevant_count": 21,
        "policy_edge_case_count": 1,
        "excluded_manual_override_count": 2,
        "excluded_indexed_pending_count": 3,
        "excluded_fixture_or_test_count": 4,
        "excluded_other_count": 5,
        "manual_review_scope_text": "relevant=21, policy=1, excluded.manual_override=2, excluded.indexed_pending=3, excluded.fixture_or_test=4, excluded.other=5",
        "manual_review_scope_samples_text": "relevant=paper-a, paper-b, paper-c (+1 more) | excluded.manual_override=manual-1, manual-2 | excluded.indexed_pending=indexed-1, indexed-2, indexed-3 (+1 more) | excluded.fixture_or_test=fixture-1",
        "threshold_relevant_sample_ids": ["paper-a", "paper-b", "paper-c"],
        "excluded_manual_override_sample_ids": ["manual-1", "manual-2"],
        "excluded_indexed_pending_sample_ids": ["indexed-1", "indexed-2", "indexed-3"],
        "excluded_fixture_or_test_sample_ids": ["fixture-1"],
        "manual_review_focus_recommendation": "Focus threshold tuning on threshold-relevant rows first.",
        "worksheet_pending_count": 21,
        "worksheet_primary_review_target": "mid_confidence_escalation_policy",
        "worksheet_excluded_count": 9,
        "worksheet_text": "pending=21, target=mid_confidence_escalation_policy, excluded=9",
        "worksheet_summary": "21 threshold-relevant row(s) are queued for mid-confidence escalation policy review; exclude 9 non-threshold row(s) from raw threshold changes.",
        "manual_review_basis_preliminary_call": "mid_confidence_policy_only",
        "manual_review_basis_policy_support_count": 21,
        "manual_review_basis_high_threshold_support_count": 0,
        "manual_review_basis_text": "call=mid_confidence_policy_only, policy=21, high=0",
        "manual_review_basis_summary": "All 21 threshold-relevant row(s) are mid-confidence legacy approvals replaying to pending review; none support a high-threshold boundary change from this evidence alone.",
    }


def test_browser_summary_preserves_latest_slot_classification_tuning_review_advisory() -> None:
    readiness = RuntimeReadinessResponse(
        status="ok",
        checks=[
            RuntimeReadinessCheck(
                name="latest_slot_classification_tuning_review",
                status="ok",
                detail="latest slot classification tuning review is available (slot_classification_tuning_review_20260422_r1)",
                path="/Users/example/repo/snapshots/slot_classification_tuning_review/slot_classification_tuning_review_20260422_r1/summary.json",
                metadata={
                    "available": True,
                    "run_id": "slot_classification_tuning_review_20260422_r1",
                    "markdown_available": True,
                    "generated_at": "2026-04-22T01:49:08.825177Z",
                    "recommended_action": "hold_current_prompt_policy",
                    "review_ready": False,
                    "decision_reason": "Do not treat the candidate slot prompt or policy as an improvement while the paired benchmark shows a regression.",
                    "next_step": "hold_current_prompt_policy",
                    "latest_compare_run_id": "slot_classification_tie_breaker_compare_20260422_r1",
                    "paired_compare_status": "regressed",
                    "default_rerun_status": "warn",
                    "boundary_rerun_status": "warn",
                    "prompt_change_ready": False,
                    "prompt_change_status": "blocked_advisory",
                    "prompt_change_blocker": "paired compare shows failed_checks=['default_template_accuracy', 'default_template_mismatch_count'] and regressions=['default_template_accuracy', 'default_template_mismatch_count']",
                    "tuning_targets": ["slot_classification"],
                    "tuning_actions": [
                        {
                            "target": "slot_classification",
                            "action": "audit_slot_policy_with_paired_compare_and_rerun_drift",
                            "summary": "Evaluate any slot prompt or policy candidate with both paired benchmark comparison and rerun-drift evidence before treating it as durable.",
                        }
                    ],
                    "action_plan": [
                        {
                            "order": 1,
                            "action": "hold_current_prompt_policy",
                            "target": "slot_classification",
                            "blocking": True,
                            "summary": "Do not treat the candidate slot prompt or policy as an improvement while the paired benchmark shows a regression.",
                            "evidence": "paired compare shows failed_checks=['default_template_accuracy', 'default_template_mismatch_count'] and regressions=['default_template_accuracy', 'default_template_mismatch_count']",
                        },
                        {
                            "order": 2,
                            "action": "collect_default_rerun_stability_evidence",
                            "target": "slot_classification",
                            "blocking": True,
                            "summary": "Same-code reruns on the default benchmark are unstable above the allowed drift rate.",
                            "evidence": "default benchmark rerun drift is 1 row(s) / 0.0909, above the allowed 0.0000",
                        },
                    ],
                    "tuning_recommendations": [
                        "Do not treat the candidate slot prompt or policy as an improvement while the paired benchmark regresses.",
                        "Same-code reruns on the default benchmark are not yet stable enough for a durable prompt/policy conclusion.",
                    ],
                    "paired_compare_failed_checks": [
                        "default_template_accuracy",
                        "default_template_mismatch_count",
                    ],
                    "paired_compare_regressions": [
                        "default_template_accuracy",
                        "default_template_mismatch_count",
                    ],
                    "paired_compare_error_migration_detected": True,
                    "default_rerun_drift_rate": 0.09090909090909091,
                    "boundary_rerun_drift_rate": 0.25,
                    "default_rerun_drift_count": 1,
                    "boundary_rerun_drift_count": 1,
                },
            )
        ],
    )

    summarized = runtime_readiness.summarize_browser_runtime_readiness(readiness)
    checks = {check.name: check for check in summarized.checks}

    assert checks["latest_slot_classification_tuning_review"].status == "ok"
    assert "latest slot classification tuning review is available" in checks["latest_slot_classification_tuning_review"].detail
    assert checks["latest_slot_classification_tuning_review"].path is None
    assert checks["latest_slot_classification_tuning_review"].metadata == {
        "available": True,
        "run_id": "slot_classification_tuning_review_20260422_r1",
        "markdown_available": True,
        "generated_at": "2026-04-22T01:49:08.825177Z",
        "recommended_action": "hold_current_prompt_policy",
        "review_ready": False,
        "decision_reason": "Do not treat the candidate slot prompt or policy as an improvement while the paired benchmark shows a regression.",
        "next_step": "hold_current_prompt_policy",
        "latest_compare_run_id": "slot_classification_tie_breaker_compare_20260422_r1",
        "paired_compare_status": "regressed",
        "default_rerun_status": "warn",
        "boundary_rerun_status": "warn",
        "prompt_change_ready": False,
        "prompt_change_status": "blocked_advisory",
        "prompt_change_blocker": "paired compare shows failed_checks=['default_template_accuracy', 'default_template_mismatch_count'] and regressions=['default_template_accuracy', 'default_template_mismatch_count']",
        "tuning_targets": ["slot_classification"],
        "tuning_actions": [
            {
                "target": "slot_classification",
                "action": "audit_slot_policy_with_paired_compare_and_rerun_drift",
                "summary": "Evaluate any slot prompt or policy candidate with both paired benchmark comparison and rerun-drift evidence before treating it as durable.",
            }
        ],
        "action_plan": [
            {
                "order": 1,
                "action": "hold_current_prompt_policy",
                "target": "slot_classification",
                "blocking": True,
                "summary": "Do not treat the candidate slot prompt or policy as an improvement while the paired benchmark shows a regression.",
                "evidence": "paired compare shows failed_checks=['default_template_accuracy', 'default_template_mismatch_count'] and regressions=['default_template_accuracy', 'default_template_mismatch_count']",
            },
            {
                "order": 2,
                "action": "collect_default_rerun_stability_evidence",
                "target": "slot_classification",
                "blocking": True,
                "summary": "Same-code reruns on the default benchmark are unstable above the allowed drift rate.",
                "evidence": "default benchmark rerun drift is 1 row(s) / 0.0909, above the allowed 0.0000",
            },
        ],
        "tuning_recommendations": [
            "Do not treat the candidate slot prompt or policy as an improvement while the paired benchmark regresses.",
            "Same-code reruns on the default benchmark are not yet stable enough for a durable prompt/policy conclusion.",
        ],
        "paired_compare_failed_checks": [
            "default_template_accuracy",
            "default_template_mismatch_count",
        ],
        "paired_compare_regressions": [
            "default_template_accuracy",
            "default_template_mismatch_count",
        ],
        "paired_compare_error_migration_detected": True,
        "default_rerun_drift_rate": 0.09090909090909091,
        "boundary_rerun_drift_rate": 0.25,
        "default_rerun_drift_count": 1,
        "boundary_rerun_drift_count": 1,
    }
