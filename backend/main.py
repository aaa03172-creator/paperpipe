from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse
import asyncio
import json
import os
from pathlib import Path

from src.db_utils import get_db_connection, init_db
from src.jobs.queue import JobQueue
from src.jobs.schemas import JobCreate, JobStatus, JobBootstrapMeta
from src.db_utils import get_db_connection, init_db
from src.jobs.queue import JobQueue
from src.jobs.schemas import JobCreate, JobStatus, JobBootstrapMeta
from .routers import obsidian, feedback

app = FastAPI(title="PaperPipe API", version="3.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

queue = JobQueue()


def _resolve_bootstrap_meta_path(job: JobStatus) -> str | None:
    artifact_dir = getattr(job, "artifact_dir", None)
    if not artifact_dir:
        return None
    return str(Path(artifact_dir) / "bootstrap_meta.json")


def _read_bootstrap_meta(meta_path: str | None) -> dict:
    if not meta_path:
        return {}
    path = Path(meta_path)
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _with_bootstrap_meta_path(job: JobStatus) -> JobStatus:
    meta_path = _resolve_bootstrap_meta_path(job)
    meta = _read_bootstrap_meta(meta_path)
    readiness = meta.get("claimset_readiness")
    badge = meta.get("claimset_readiness_badge")
    if badge is None:
        if readiness == "ready":
            badge = "READY"
        elif readiness == "not_ready":
            badge = "NOT_READY"
        elif readiness == "unknown":
            badge = "UNKNOWN"
    return job.model_copy(
        update={
            "bootstrap_meta_path": meta_path,
            "similar_feedback_count": meta.get("similar_feedback_count"),
            "persona_applied": meta.get("persona_applied"),
            "artifact_document_written": meta.get("artifact_document_written"),
            "artifact_index_written": meta.get("artifact_index_written"),
            "artifact_claimset_written": meta.get("artifact_claimset_written"),
            "artifact_stats_written": meta.get("artifact_stats_written"),
            "claimset_readiness": meta.get("claimset_readiness"),
            "claimset_ready": meta.get("claimset_ready"),
            "claimset_claim_count": meta.get("claimset_claim_count"),
            "claimset_readiness_reason": meta.get("claimset_readiness_reason"),
            "claimset_readiness_badge": badge,
            "claimset_ops_action": meta.get("claimset_ops_action"),
            "claimset_ops_alert": meta.get("claimset_ops_alert"),
            "claimset_ops_note": meta.get("claimset_ops_note"),
        }
    )

@app.get("/health")
def health_check():
    return {"status": "ok", "version": "3.1.0"}

@app.get("/papers")
def list_papers():
    conn = get_db_connection()
    papers = conn.execute("SELECT * FROM papers ORDER BY updated_at DESC LIMIT 50").fetchall()
    conn.close()
    out = []
    for p in papers:
        item = dict(p)
        pdf_path = item.get("pdf_path")
        pdf_exists = bool(pdf_path and os.path.exists(pdf_path))
        item["pdf_exists"] = pdf_exists
        if not pdf_exists and pdf_path:
            item["pdf_status"] = "missing"
        out.append(item)
    return out


@app.get("/papers/{paper_id}")
def get_paper(paper_id: str):
    conn = get_db_connection()
    row = conn.execute("SELECT * FROM papers WHERE paper_id = ?", (paper_id,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Paper not found")

    item = dict(row)
    pdf_path = item.get("pdf_path")
    pdf_exists = bool(pdf_path and os.path.exists(pdf_path))
    item["pdf_exists"] = pdf_exists
    if not pdf_exists and pdf_path:
        item["pdf_status"] = "missing"
    return item

@app.post("/jobs/deepread", response_model=dict)
def enqueue_job(job_req: JobCreate):
    job_id = queue.enqueue(
        job_req.paper_id,
        job_req.clean_reindex,
        job_req.run_verify,
        job_req.persona_id,
    )
    return {"job_id": job_id, "status": "queued"}

@app.get("/jobs/{job_id}", response_model=JobStatus)
def get_job_status(job_id: str):
    job = queue.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return _with_bootstrap_meta_path(job)


@app.get("/jobs/{job_id}/bootstrap-meta", response_model=JobBootstrapMeta)
def get_job_bootstrap_meta(job_id: str):
    job = queue.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    meta_path = _resolve_bootstrap_meta_path(job)
    if not meta_path:
        raise HTTPException(status_code=404, detail="bootstrap_meta not available")
    path = Path(meta_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="bootstrap_meta file not found")
    try:
        return JobBootstrapMeta.model_validate(json.loads(path.read_text(encoding="utf-8")))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to parse bootstrap_meta: {exc}")

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
            enriched = _with_bootstrap_meta_path(job)
            yield {"event": "status", "data": json.dumps(enriched.model_dump(), default=str)}
            
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
