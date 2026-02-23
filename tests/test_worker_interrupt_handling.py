from __future__ import annotations

import pytest

import src.db_utils as db_utils
import src.jobs.worker as worker_mod
from src.jobs.queue import JobQueue


def test_worker_interrupt_keeps_terminal_completion_if_progress_already_completed(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()

        library_dir = tmp_path / "Library"
        library_dir.mkdir(parents=True, exist_ok=True)
        (library_dir / "paper_interrupt_001.pdf").write_bytes(b"%PDF-1.4\n%fake\n")

        async def fake_run_deepread_job(
            job_id: str,
            paper_id: str,
            persona_id: str = "default",
            run_verify: bool = False,
            run_id: str | None = None,
            progress_callback=None,
            cancel_check=None,
        ):
            if progress_callback:
                await progress_callback(
                    {
                        "job_id": job_id,
                        "run_id": run_id or "run_test",
                        "stage": "completed",
                        "progress": 100,
                        "message": "done",
                        "level": "INFO",
                    }
                )
            raise KeyboardInterrupt()

        monkeypatch.setattr(worker_mod, "run_deepread_job", fake_run_deepread_job)

        queue = JobQueue()
        job_id = queue.enqueue("paper_interrupt_001")
        claimed = queue.claim_next_job()
        assert claimed is not None

        worker = worker_mod.Worker()
        with pytest.raises(KeyboardInterrupt):
            worker.process_job(claimed)

        done = queue.get_job(job_id)
        assert done is not None
        assert done.status == "completed"
        assert done.progress == 100
        assert done.stage == "completed"
    finally:
        db_utils.DB_PATH = original_db_path
