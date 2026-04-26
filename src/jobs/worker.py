import time
import asyncio
import logging
import threading
import json
from datetime import datetime, timezone
from pathlib import Path
from src.jobs.queue import JobQueue
from backend.services.job_runner import run_deepread_job
from src.services.event_log import get_execution_run_params, log_job_event

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("Worker")
JOB_HEARTBEAT_INTERVAL_SECONDS = 30.0
TERMINAL_STOP_STATUSES = {"completed", "failed", "cancelled"}

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
        heartbeat_stop = threading.Event()
        heartbeat_thread: threading.Thread | None = None

        def current_state():
            return self.queue.get_job(job.job_id)
        
        try:
            # Update log path
            self.queue.update_job(job.job_id, {"log_path": str(log_file)})

            def has_left_running_state() -> bool:
                state = current_state()
                return bool(state and state.status in TERMINAL_STOP_STATUSES)

            def heartbeat_loop() -> None:
                while not heartbeat_stop.wait(JOB_HEARTBEAT_INTERVAL_SECONDS):
                    try:
                        state = current_state()
                        if not state or state.status != "running":
                            return
                        self.queue.update_job(
                            job.job_id,
                            {"heartbeat_at": datetime.now(timezone.utc).isoformat()},
                        )
                    except Exception as exc:
                        logger.warning(f"Heartbeat update failed for job {job.job_id}: {exc}")

            heartbeat_thread = threading.Thread(
                target=heartbeat_loop,
                name=f"job-heartbeat-{job.job_id}",
                daemon=True,
            )
            heartbeat_thread.start()

            def should_stop() -> bool:
                return has_left_running_state()

            async def on_progress(event: dict):
                if has_left_running_state():
                    return

                updates = {
                    "progress": int(event.get("progress", 0)),
                    "stage": event.get("stage", "running"),
                    "heartbeat_at": datetime.now(timezone.utc).isoformat(),
                }
                if event.get("level") == "ERROR":
                    updates["error_message"] = event.get("message")
                self.queue.update_job(job.job_id, updates)

                with open(log_file, "a") as f:
                    f.write(json.dumps(event) + "\n")

            run_params = get_execution_run_params(job.run_id)
            run_kwargs = {
                "job_id": job.job_id,
                "paper_id": job.paper_id,
                "persona_id": str(run_params.get("persona_id") or job.persona_id or "default"),
                "reasoning_persona": run_params.get("reasoning_persona"),
                "profile_id": run_params.get("profile_id"),
                "parser_backend": run_params.get("parser_backend"),
                "run_verify": bool(job.run_verify),
                "clean_reindex": bool(getattr(job, "clean_reindex", 0)),
                "run_id": job.run_id,
                "progress_callback": on_progress,
                "cancel_check": should_stop,
            }
            try:
                result = asyncio.run(run_deepread_job(**run_kwargs))
            except TypeError:
                # Compatibility for patched test doubles that still use the old signature.
                compatibility_kwargs = dict(run_kwargs)
                compatibility_kwargs.pop("reasoning_persona", None)
                compatibility_kwargs.pop("profile_id", None)
                compatibility_kwargs.pop("parser_backend", None)
                try:
                    result = asyncio.run(run_deepread_job(**compatibility_kwargs))
                except TypeError:
                    compatibility_kwargs.pop("clean_reindex", None)
                    result = asyncio.run(run_deepread_job(**compatibility_kwargs))

            state = current_state()
            if state and state.status in TERMINAL_STOP_STATUSES:
                logger.info(
                    "Job %s left running state as %s before final worker write; preserving terminal state.",
                    job.job_id,
                    state.status,
                )
                return

            if result and result.get("status") == "cancelled":
                log_job_event(
                    job_id=job.job_id,
                    run_id=job.run_id,
                    level="INFO",
                    event_type="job_cancelled",
                    message="cancelled during execution",
                    payload={"status": "cancelled"},
                )
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
                log_job_event(
                    job_id=job.job_id,
                    run_id=job.run_id,
                    level="INFO",
                    event_type="job_completed",
                    message="completed",
                    payload={"status": "completed", "artifact_dir": result.get("artifact_dir")},
                )
                logger.info(f"✅ Job {job.job_id} completed.")
            else:
                error_message = (result or {}).get("error", "Deep Read pipeline failed")
                self.queue.update_job(job.job_id, {
                    "status": "failed",
                    "error_message": error_message,
                    "finished_at": datetime.now(timezone.utc).isoformat(),
                })
                log_job_event(
                    job_id=job.job_id,
                    run_id=job.run_id,
                    level="ERROR",
                    event_type="job_failed",
                    message=error_message,
                    payload={"status": "failed", "error": error_message},
                )
                logger.error(f"❌ Job {job.job_id} failed: {error_message}")

        except KeyboardInterrupt:
            state = current_state()
            if state and state.status in TERMINAL_STOP_STATUSES:
                logger.info(
                    "Worker interrupt observed after terminal state %s for job %s; preserving current state.",
                    state.status,
                    job.job_id,
                )
                raise
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
            log_job_event(
                job_id=job.job_id,
                run_id=job.run_id,
                level="ERROR" if updates.get("status") != "completed" else "INFO",
                event_type="worker_interrupt",
                message=str(updates.get("error_message") or updates.get("status") or "interrupted"),
                payload=updates,
            )
            raise
            
        except Exception as e:
            logger.error(f"Job failed: {e}")
            state = current_state()
            if state and state.status in TERMINAL_STOP_STATUSES:
                logger.info(
                    "Worker exception observed after terminal state %s for job %s; preserving current state.",
                    state.status,
                    job.job_id,
                )
                return
            self.queue.update_job(job.job_id, {
                "status": "failed",
                "error_message": str(e),
                "finished_at": datetime.now(timezone.utc).isoformat()
            })
            log_job_event(
                job_id=job.job_id,
                run_id=job.run_id,
                level="ERROR",
                event_type="worker_exception",
                message=str(e),
                payload={"error": str(e)},
            )
        finally:
            heartbeat_stop.set()
            if heartbeat_thread is not None:
                heartbeat_thread.join(timeout=1.0)

if __name__ == "__main__":
    worker = Worker()
    worker.start()
