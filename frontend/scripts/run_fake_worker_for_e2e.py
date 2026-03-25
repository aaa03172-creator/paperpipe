#!/usr/bin/env python3
from __future__ import annotations

import asyncio
import json
import logging
import shutil
import signal
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.services.job_runner import _resolve_ingest_parser_backend
from src.jobs.queue import JobQueue
import src.jobs.worker as worker_mod


logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("e2e_fake_worker")

POLL_INTERVAL_SECONDS = 0.2
SEED_ARTIFACT_FILES = (
    "claimset.json",
    "claimset.resolved.json",
    "document_artifact.json",
    "stats_report.json",
)

_stop_requested = False


def _request_stop(signum, _frame) -> None:
    global _stop_requested
    logger.info("received signal %s, stopping fake worker", signum)
    _stop_requested = True


for sig in (signal.SIGINT, signal.SIGTERM):
    signal.signal(sig, _request_stop)


def _latest_seed_artifact_dir(paper_id: str, run_id: str | None) -> Path | None:
    paper_root = Path("storage") / "artifacts" / paper_id
    if not paper_root.exists():
        return None
    candidates = [path for path in paper_root.iterdir() if path.is_dir() and path.name != str(run_id or "")]
    if not candidates:
        return None
    return max(candidates, key=lambda path: path.stat().st_mtime)


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
    del persona_id, reasoning_persona, profile_id, run_verify, clean_reindex
    if cancel_check and cancel_check():
        return {"status": "cancelled", "run_id": run_id}

    effective_backend = _resolve_ingest_parser_backend(
        SimpleNamespace(ingest=SimpleNamespace(parser_backend="fitz_pdfplumber", enable_docling=False)),
        override_backend=parser_backend,
    )
    artifact_dir = Path("storage") / "artifacts" / paper_id / str(run_id)
    artifact_dir.mkdir(parents=True, exist_ok=True)

    seed_dir = _latest_seed_artifact_dir(paper_id, run_id)
    if seed_dir is not None:
        for filename in SEED_ARTIFACT_FILES:
            source = seed_dir / filename
            if source.exists():
                shutil.copy2(source, artifact_dir / filename)

    def emit_timestamp() -> str:
        return datetime.now(timezone.utc).isoformat()

    if progress_callback:
        await progress_callback(
            {
                "job_id": job_id,
                "run_id": run_id,
                "stage": "ingest",
                "progress": 20,
                "message": "e2e fake worker started",
                "level": "INFO",
                "timestamp": emit_timestamp(),
            }
        )
        await asyncio.sleep(0.05)
        await progress_callback(
            {
                "job_id": job_id,
                "run_id": run_id,
                "stage": "read",
                "progress": 80,
                "message": f"e2e fake worker resolved parser backend: {effective_backend}",
                "level": "INFO",
                "timestamp": emit_timestamp(),
            }
        )

    bootstrap_meta = {
        "paper_id": paper_id,
        "run_id": run_id,
        "parser_backend": effective_backend,
        "artifact_document_written": (artifact_dir / "document_artifact.json").exists(),
        "artifact_claimset_written": (artifact_dir / "claimset.json").exists(),
        "artifact_claimset_resolved_written": (artifact_dir / "claimset.resolved.json").exists(),
        "artifact_stats_written": (artifact_dir / "stats_report.json").exists(),
    }
    (artifact_dir / "bootstrap_meta.json").write_text(json.dumps(bootstrap_meta, indent=2), encoding="utf-8")
    (artifact_dir / "run_meta.json").write_text(
        json.dumps({"paper_id": paper_id, "run_id": run_id, "status": "completed"}, indent=2),
        encoding="utf-8",
    )

    logger.info(
        "completed fake deepread job %s for %s: requested=%s resolved=%s",
        job_id,
        paper_id,
        parser_backend,
        effective_backend,
    )
    return {"status": "succeeded", "run_id": run_id, "artifact_dir": str(artifact_dir)}


def main() -> int:
    worker_mod.run_deepread_job = fake_run_deepread_job
    queue = JobQueue()
    worker = worker_mod.Worker()
    logger.info("e2e fake worker polling for queued jobs")
    while not _stop_requested:
        job = queue.claim_next_job()
        if job is None:
            time.sleep(POLL_INTERVAL_SECONDS)
            continue
        worker.process_job(job)
    logger.info("e2e fake worker stopped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
