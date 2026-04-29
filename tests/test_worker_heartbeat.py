from __future__ import annotations

import asyncio
import threading
import time
from datetime import datetime, timezone
from datetime import timedelta

import src.db_utils as db_utils
import src.jobs.worker as worker_mod
import src.services.stale_jobs as stale_jobs_service
from src.jobs.queue import JobQueue


def _utc_timestamp(value: datetime) -> float:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).timestamp()


def test_worker_updates_heartbeat_during_quiet_running_stage(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()

        async def fake_run_deepread_job(
            job_id: str,
            paper_id: str,
            persona_id: str = "default",
            run_verify: bool = False,
            run_id: str | None = None,
            progress_callback=None,
            cancel_check=None,
        ):
            await asyncio.sleep(0.05)
            return {
                "status": "succeeded",
                "artifact_dir": str(tmp_path / "storage" / "artifacts" / paper_id / (run_id or "run")),
            }

        monkeypatch.setattr(worker_mod, "run_deepread_job", fake_run_deepread_job)
        monkeypatch.setattr(worker_mod, "JOB_HEARTBEAT_INTERVAL_SECONDS", 0.01)

        queue = JobQueue()
        job_id = queue.enqueue("paper_worker_heartbeat_001")
        claimed = queue.claim_next_job()

        assert claimed is not None
        assert claimed.heartbeat_at is not None
        initial_heartbeat = claimed.heartbeat_at

        worker = worker_mod.Worker()
        worker.process_job(claimed)

        done = queue.get_job(job_id)
        assert done is not None
        assert done.status == "completed"
        assert done.started_at is not None
        assert done.heartbeat_at is not None
        assert initial_heartbeat is not None
        assert _utc_timestamp(done.heartbeat_at) > _utc_timestamp(initial_heartbeat)
    finally:
        db_utils.DB_PATH = original_db_path


def test_queue_update_job_ignores_late_writes_after_terminal_state(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()
        queue = JobQueue()
        job_id = queue.enqueue("paper_terminal_guard_001")

        queue.update_job(
            job_id,
            {
                "status": "failed",
                "error_code": "TERMINAL_GUARD_TEST",
                "error_message": "terminal write",
                "finished_at": "2026-04-22T03:00:00+00:00",
            },
        )
        queue.update_job(
            job_id,
            {
                "status": "completed",
                "progress": 100,
                "stage": "completed",
            },
        )
        queue.update_job(
            job_id,
            {
                "progress": 55,
                "stage": "read",
            },
        )

        done = queue.get_job(job_id)
        assert done is not None
        assert done.status == "failed"
        assert done.error_code == "TERMINAL_GUARD_TEST"
        assert done.error_message == "terminal write"
        assert done.progress == 0
        assert done.stage is None
    finally:
        db_utils.DB_PATH = original_db_path


def test_worker_preserves_reclaimed_failed_state_against_late_success(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()

        async def fake_run_deepread_job(
            job_id: str,
            paper_id: str,
            persona_id: str = "default",
            reasoning_persona: str | None = None,
            profile_id: str | None = None,
            parser_backend: str | None = None,
            run_verify: bool = False,
            clean_reindex: bool = False,
            run_id: str | None = None,
            progress_callback=None,
            cancel_check=None,
        ):
            while not (cancel_check and cancel_check()):
                await asyncio.sleep(0.01)
            return {
                "status": "succeeded",
                "artifact_dir": str(tmp_path / "storage" / "artifacts" / paper_id / (run_id or "run")),
            }

        monkeypatch.setattr(worker_mod, "run_deepread_job", fake_run_deepread_job)
        monkeypatch.setattr(worker_mod, "JOB_HEARTBEAT_INTERVAL_SECONDS", 1.0)
        monkeypatch.setattr(
            stale_jobs_service,
            "utc_now",
            lambda: datetime.now(timezone.utc) + timedelta(hours=1),
        )

        queue = JobQueue()
        job_id = queue.enqueue("paper_reclaim_race_001")
        claimed = queue.claim_next_job()

        assert claimed is not None

        worker = worker_mod.Worker()
        worker_thread = threading.Thread(target=worker.process_job, args=(claimed,), daemon=True)
        worker_thread.start()
        time.sleep(0.05)

        reclaim = stale_jobs_service.reclaim_stale_running_job(
            db_utils.get_db_path(),
            job_id=job_id,
            stale_after_seconds=60,
        )
        assert reclaim["outcome"] == "reclaimed"

        worker_thread.join(timeout=2.0)
        assert not worker_thread.is_alive()

        done = queue.get_job(job_id)
        assert done is not None
        assert done.status == "failed"
        assert done.error_code == "STALE_RUNNING_RECLAIMED"

        conn = db_utils.get_db_connection()
        event_types = [
            str(row["event_type"])
            for row in conn.execute(
                "SELECT event_type FROM job_events WHERE job_id = ? ORDER BY ts ASC",
                (job_id,),
            ).fetchall()
        ]
        conn.close()

        assert "job_reclaimed_stale_running" in event_types
        assert "job_completed" not in event_types
    finally:
        db_utils.DB_PATH = original_db_path
