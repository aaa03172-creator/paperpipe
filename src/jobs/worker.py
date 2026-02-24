import time
import asyncio
import logging
import traceback
import json
from datetime import datetime, timezone
from pathlib import Path
from src.jobs.queue import JobQueue
from backend.services.job_runner import run_deepread_job

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
        
        # Setup Logs
        log_dir = Path("logs/jobs")
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / f"{job.job_id}.jsonl"
        
        try:
            # Update log path
            self.queue.update_job(job.job_id, {"log_path": str(log_file)})

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

                with open(log_file, "a") as f:
                    f.write(json.dumps(event) + "\n")

            run_kwargs = {
                "job_id": job.job_id,
                "paper_id": job.paper_id,
                "persona_id": job.persona_id or "default",
                "run_verify": bool(job.run_verify),
                "clean_reindex": bool(getattr(job, "clean_reindex", 0)),
                "run_id": job.run_id,
                "progress_callback": on_progress,
                "cancel_check": is_cancelled,
            }
            try:
                result = asyncio.run(run_deepread_job(**run_kwargs))
            except TypeError:
                # Compatibility for patched test doubles that still use the old signature.
                run_kwargs.pop("clean_reindex", None)
                result = asyncio.run(run_deepread_job(**run_kwargs))

            if result and result.get("status") == "cancelled":
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
                logger.info(f"✅ Job {job.job_id} completed.")
            else:
                error_message = (result or {}).get("error", "Deep Read pipeline failed")
                self.queue.update_job(job.job_id, {
                    "status": "failed",
                    "error_message": error_message,
                    "finished_at": datetime.now(timezone.utc).isoformat(),
                })
                logger.error(f"❌ Job {job.job_id} failed: {error_message}")

        except KeyboardInterrupt:
            state = self.queue.get_job(job.job_id)
            updates = {
                "finished_at": datetime.now(timezone.utc).isoformat(),
            }
            # If progress callback already wrote a terminal completed marker,
            # keep completed status instead of leaving a stale running row.
            if state and state.stage == "completed" and int(state.progress or 0) >= 100:
                updates["status"] = "completed"
            else:
                updates["status"] = "cancelled"
                updates["stage"] = "cancelled"
                updates["error_message"] = "worker interrupted"
            self.queue.update_job(job.job_id, updates)
            raise
            
        except Exception as e:
            logger.error(f"Job failed: {e}")
            traceback.print_exc()
            self.queue.update_job(job.job_id, {
                "status": "failed",
                "error_message": str(e),
                "finished_at": datetime.now(timezone.utc).isoformat()
            })

if __name__ == "__main__":
    worker = Worker()
    worker.start()
