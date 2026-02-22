import time
import asyncio
import logging
import traceback
import json
from datetime import datetime, timezone
from pathlib import Path
from src.jobs.queue import JobQueue
from backend.services.job_runner import run_deepread_job
from src.db_event_log import (
    create_run,
    finish_run,
    flush_event_buffer,
    log_event,
    log_event_buffered,
    update_job_status as update_job_status_eventlog,
)

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("Worker")

class Worker:
    def __init__(self):
        self.queue = JobQueue()
        self.running = True
        
    def start(self):
        logger.info("👷 Worker started. Polling for jobs...")
        while self.running:
            try:
                job = self.queue.claim_next_job()
                if job:
                    self.process_job(job)
                else:
                    time.sleep(2) # Poll interval
            except KeyboardInterrupt:
                logger.info("Worker stopping...")
                self.running = False
            except Exception as e:
                logger.error(f"Worker loop error: {e}")
                time.sleep(5)

    def process_job(self, job):
        logger.info(f"🚀 Starting Job {job.job_id} (Paper: {job.paper_id})")
        run_record_id = job.run_id or f"run_{job.job_id}"
        try:
            create_run(
                paper_id=job.paper_id or "",
                trigger_source="worker",
                pipeline_profile=job.run_profile or ("deep_verify" if bool(job.run_verify) else "grounded_read"),
                params={"job_id": job.job_id, "persona_id": job.persona_id or "default"},
                run_id=run_record_id,
            )
            log_event(job.job_id, "info", "job_start", f"job started for {job.paper_id}", {"run_id": run_record_id})
        except Exception as event_log_exc:
            logger.warning("Event-log start instrumentation skipped: %s", event_log_exc)
        
        # Setup Logs
        log_dir = Path("logs/jobs")
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / f"{job.job_id}.jsonl"
        
        try:
            # Update log path
            self.queue.update_job(job.job_id, {"log_path": str(log_file)})
            try:
                update_job_status_eventlog(job.job_id, "running")
            except Exception as event_log_exc:
                logger.warning("Event-log running status sync skipped: %s", event_log_exc)

            def is_cancelled() -> bool:
                state = self.queue.get_job(job.job_id)
                return bool(state and state.status == "cancelled")

            async def on_progress(event: dict):
                if is_cancelled():
                    return

                updates = {
                    "progress": int(event.get("progress", 0)),
                    "stage": event.get("stage", "running"),
                }
                if event.get("level") == "ERROR":
                    updates["error_message"] = event.get("message")
                self.queue.update_job(job.job_id, updates)
                try:
                    log_event_buffered(
                        job.job_id,
                        str(event.get("level", "INFO")).lower(),
                        "step_progress",
                        str(event.get("message") or ""),
                        {
                            "stage": event.get("stage"),
                            "progress": event.get("progress"),
                            "run_id": event.get("run_id"),
                        },
                    )
                except Exception as event_log_exc:
                    logger.warning("Event-log progress instrumentation skipped: %s", event_log_exc)

                with open(log_file, "a", encoding="utf-8") as f:
                    f.write(json.dumps(event) + "\n")

            result = asyncio.run(
                run_deepread_job(
                    job_id=job.job_id,
                    paper_id=job.paper_id,
                    persona_id=job.persona_id or "default",
                    run_verify=bool(job.run_verify),
                    run_profile=job.run_profile,
                    run_id=job.run_id,
                    progress_callback=on_progress,
                    cancel_check=is_cancelled,
                )
            )

            if result and result.get("status") == "cancelled":
                current = self.queue.get_job(job.job_id)
                if current and current.status != "cancelled":
                    self.queue.update_job(
                        job.job_id,
                        {
                            "status": "cancelled",
                            "stage": "cancelled",
                            "finished_at": datetime.now(timezone.utc).isoformat(),
                        },
                    )
                try:
                    update_job_status_eventlog(job.job_id, "cancelled")
                    log_event(job.job_id, "warning", "job_cancelled", "job cancelled during execution")
                    finish_run(run_record_id, "cancelled")
                    flush_event_buffer()
                except Exception as event_log_exc:
                    logger.warning("Event-log cancelled instrumentation skipped: %s", event_log_exc)
                logger.info(f"🛑 Job {job.job_id} cancelled during execution.")
                return
            elif result and result.get("status") == "succeeded":
                self.queue.update_job(job.job_id, {
                    "status": "completed",
                    "finished_at": datetime.now(timezone.utc).isoformat(),
                    "progress": 100,
                    "stage": "completed",
                    "artifact_dir": result.get("artifact_dir"),
                })
                try:
                    update_job_status_eventlog(
                        job.job_id,
                        "completed",
                        result_ref=result.get("artifact_dir"),
                    )
                    log_event(
                        job.job_id,
                        "info",
                        "job_completed",
                        "job completed",
                        {"artifact_dir": result.get("artifact_dir")},
                    )
                    finish_run(run_record_id, "succeeded")
                    flush_event_buffer()
                except Exception as event_log_exc:
                    logger.warning("Event-log completed instrumentation skipped: %s", event_log_exc)
                logger.info(f"✅ Job {job.job_id} completed.")
            else:
                error_message = (result or {}).get("error", "Deep Read pipeline failed")
                self.queue.update_job(job.job_id, {
                    "status": "failed",
                    "error_message": error_message,
                    "finished_at": datetime.now(timezone.utc).isoformat(),
                })
                try:
                    update_job_status_eventlog(
                        job.job_id,
                        "failed",
                        error_code="PIPELINE_FAILED",
                        error_detail=error_message,
                    )
                    log_event(
                        job.job_id,
                        "error",
                        "job_failed",
                        error_message,
                    )
                    finish_run(run_record_id, "failed", metrics={"error_message": error_message})
                    flush_event_buffer()
                except Exception as event_log_exc:
                    logger.warning("Event-log failed instrumentation skipped: %s", event_log_exc)
                logger.error(f"❌ Job {job.job_id} failed: {error_message}")
            
        except Exception as e:
            logger.error(f"Job failed: {e}")
            traceback.print_exc()
            self.queue.update_job(job.job_id, {
                "status": "failed",
                "error_message": str(e),
                "finished_at": datetime.now(timezone.utc).isoformat()
            })
            try:
                update_job_status_eventlog(
                    job.job_id,
                    "failed",
                    error_code="WORKER_EXCEPTION",
                    error_detail=str(e),
                )
                log_event(job.job_id, "error", "worker_exception", str(e))
                finish_run(run_record_id, "failed", metrics={"exception": str(e)})
                flush_event_buffer()
            except Exception as event_log_exc:
                logger.warning("Event-log exception instrumentation skipped: %s", event_log_exc)

if __name__ == "__main__":
    worker = Worker()
    worker.start()
