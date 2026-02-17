from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse
import asyncio
import json
from pathlib import Path

from src.db_utils import get_db_connection, init_db
from src.jobs.queue import JobQueue
from src.jobs.schemas import JobCreate, JobStatus
from src.db_utils import get_db_connection, init_db
from src.jobs.queue import JobQueue
from src.jobs.schemas import JobCreate, JobStatus
from .routers import obsidian, feedback

app = FastAPI(title="PaperPipe API", version="3.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

queue = JobQueue()

@app.get("/health")
def health_check():
    return {"status": "ok", "version": "3.1.0"}

@app.get("/papers")
def list_papers():
    conn = get_db_connection()
    papers = conn.execute("SELECT * FROM papers ORDER BY updated_at DESC LIMIT 50").fetchall()
    conn.close()
    return [dict(p) for p in papers]

@app.post("/jobs/deepread", response_model=dict)
def enqueue_job(job_req: JobCreate):
    job_id = queue.enqueue(job_req.paper_id, job_req.clean_reindex)
    return {"job_id": job_id, "status": "queued"}

@app.get("/jobs/{job_id}", response_model=JobStatus)
def get_job_status(job_id: str):
    job = queue.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job

@app.post("/jobs/{job_id}/cancel")
def cancel_job(job_id: str):
    queue.cancel_job(job_id)
    return {"status": "cancelled"}

@app.get("/jobs/{job_id}/events")
async def job_events(job_id: str, request: Request):
    """SSE endpoint for job logs/status"""
    async def event_generator():
        last_pos = 0
        while True:
            if await request.is_disconnected():
                break
                
            job = queue.get_job(job_id)
            if not job:
                yield {"event": "error", "data": "Job not found"}
                break
            
            # Send status update
            yield {"event": "status", "data": json.dumps(job.dict(), default=str)}
            
            # Send new log lines
            if job.log_path and Path(job.log_path).exists():
                with open(job.log_path, "r") as f:
                    f.seek(last_pos)
                    lines = f.readlines()
                    last_pos = f.tell()
                    for line in lines:
                        yield {"event": "log", "data": line.strip()}
            
            if job.status in ["completed", "failed", "cancelled"]:
                yield {"event": "done", "data": job.status}
                break
            
            await asyncio.sleep(1)

    return EventSourceResponse(event_generator())

app.include_router(obsidian.router)
app.include_router(feedback.router)
