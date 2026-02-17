import time
import logging
import traceback
import json
from datetime import datetime, timezone
from pathlib import Path
from src.jobs.queue import JobQueue

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("Worker")


def _default_processor_factory():
    # Lazy import to keep worker unit tests decoupled from heavy runtime deps.
    from src.processor import PaperProcessor

    return PaperProcessor()


class Worker:
    def __init__(self, queue: JobQueue | None = None, processor=None, processor_factory=None):
        self.queue = queue or JobQueue()
        self.running = True
        if processor is not None:
            self.processor = processor
        else:
            factory = processor_factory or _default_processor_factory
            self.processor = factory()
        
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
        
        # Update log path tracking
        self.queue.update_job(job.job_id, {"log_path": str(log_file)})

        def on_progress(p: int, stage: str):
            """Callback from Processor to update Job UI"""
            # Check cancellation first
            current_job = self.queue.get_job(job.job_id)
            if current_job and current_job.status == 'cancelled':
                raise InterruptedError("Job Cancelled")
                
            # Log
            msg = f"[{p}%] {stage}"
            logger.info(f"Job {job.job_id}: {msg}")
            with open(log_file, "a") as f:
                f.write(json.dumps({"ts": time.time(), "level": "INFO", "msg": msg}) + "\n")
            
            # Update DB
            self.queue.update_job(job.job_id, {"progress": p, "stage": stage})

        try:
            self.queue.update_job(job.job_id, {"status": "running", "started_at": datetime.now(timezone.utc).isoformat()})
            
            # --- CORE LOGIC EXECUTION ---
            success = self.processor.process_single_paper(job.paper_id, on_progress=on_progress)
            
            if success:
                self.queue.update_job(job.job_id, {
                    "status": "completed", 
                    "finished_at": datetime.now(timezone.utc).isoformat(),
                    "progress": 100,
                    "stage": "Done"
                })
                logger.info(f"✅ Job {job.job_id} completed successfully.")
            else:
                 raise RuntimeError("Processor returned False")

        except InterruptedError:
            logger.info(f"🛑 Job {job.job_id} cancelled during processing.")
            self.queue.update_job(job.job_id, {
                "status": "cancelled",
                "finished_at": datetime.now(timezone.utc).isoformat()
            })
            
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
