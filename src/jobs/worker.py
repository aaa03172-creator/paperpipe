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
        
        # Placeholder processing logic for MVP verification
        try:
            # Update log path
            self.queue.update_job(job.job_id, {"log_path": str(log_file)})
            
            # Simulate steps
            steps = ["Initializing", "Parsing PDF", "Generating Summary", "Gatekeeper Check", "Finalizing"]
            total_steps = len(steps)
            
            for i, step in enumerate(steps):
                # Check for cancellation
                current_job_state = self.queue.get_job(job.job_id)
                if current_job_state.status == 'cancelled':
                    logger.info(f"🛑 Job {job.job_id} cancelled.")
                    return

                # Log step
                msg = f"Step {i+1}/{total_steps}: {step}"
                logger.info(msg)
                with open(log_file, "a") as f:
                    f.write(json.dumps({"ts": time.time(), "level": "INFO", "msg": msg}) + "\n")
                
                # Update progress
                progress = int(((i + 1) / total_steps) * 100)
                self.queue.update_job(job.job_id, {"progress": progress, "stage": step})
                
                time.sleep(1) # Simulate work
                
            # Finish
            self.queue.update_job(job.job_id, {
                "status": "completed", 
                "finished_at": datetime.now(timezone.utc).isoformat(),
                "progress": 100,
                "stage": "Done"
            })
            logger.info(f"✅ Job {job.job_id} completed.")
            
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
