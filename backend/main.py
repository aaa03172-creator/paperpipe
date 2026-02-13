from fastapi import FastAPI, APIRouter
from fastapi.middleware.cors import CORSMiddleware
import uuid
import asyncio
import json
from sse_starlette.sse import EventSourceResponse

app = FastAPI(title="PaperPipe API", version="3.0.0")

# CORS (Frontend origin only - strictly enforcing for now, assuming localhost:3000)
origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Health Check
@app.get("/health")
async def health_check():
    return {"status": "OK"}

# Job Endpoints (Mock for Phase 1)
jobs_router = APIRouter(prefix="/jobs", tags=["jobs"])

from .services.job_runner import run_deepread_job, JOB_QUEUES

@jobs_router.post("/deepread")
async def create_deepread_job(paper_id: str, persona_id: str = "default", verify: bool = False):
    job_id = str(uuid.uuid4())
    run_id = str(uuid.uuid4())
    JOB_QUEUES[job_id] = asyncio.Queue()
    
    # Run in background
    asyncio.create_task(run_deepread_job(job_id, paper_id, persona_id, verify, run_id))
    
    return {"job_id": job_id, "run_id": run_id, "status": "queued", "message": f"Deep read job started for {paper_id}"}

@jobs_router.get("/{job_id}/events")
async def job_events(job_id: str):
    """
    Real SSE endpoint consuming from JOB_QUEUES.
    """
    queue = JOB_QUEUES.get(job_id)
    if not queue:
        # If queue not found, maybe job is already done or invalid key?
        # For now, return a 404 or empty stream. 
        # Better to yield a "job not found" error event and close.
        async def not_found():
            yield {"event": "error", "data": json.dumps({"error": "Job not found or expired"})}
        return EventSourceResponse(not_found())

    async def event_generator():
        try:
            while True:
                # Wait for event
                event = await queue.get()
                yield event
                
                # Check for completion
                if event.get("event") == "completed":
                    break
        except asyncio.CancelledError:
            pass

    return EventSourceResponse(event_generator())

app.include_router(jobs_router)

# Import and include papers router (to be implemented next)
from .routers import papers, obsidian, feedback
app.include_router(papers.router)
app.include_router(obsidian.router)
app.include_router(feedback.router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
