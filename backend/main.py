from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse
import asyncio
import json
import os
import sqlite3
from pathlib import Path
from contextlib import asynccontextmanager

from src.db_utils import get_db_connection, init_db
from src.jobs.queue import JobQueue
from src.jobs.schemas import JobCreate, JobStatus, JobBootstrapMeta
from .routers import obsidian, feedback, discover


@asynccontextmanager
async def _lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="PaperPipe API", version="3.1.0", lifespan=_lifespan)

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
            "stats_trigger_reason": meta.get("stats_trigger_reason"),
            "stats_cache_hit": meta.get("stats_cache_hit"),
            "stats_cache_key": meta.get("stats_cache_key"),
            "stats_cache_path": meta.get("stats_cache_path"),
            "evidence_spans_total": meta.get("evidence_spans_total"),
            "evidence_spans_grounded": meta.get("evidence_spans_grounded"),
            "evidence_grounded_ratio": meta.get("evidence_grounded_ratio"),
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


def _enrich_pdf_flags(item: dict) -> dict:
    pdf_path = item.get("pdf_path")
    pdf_exists = bool(pdf_path and os.path.exists(pdf_path))
    item["pdf_exists"] = pdf_exists
    if not pdf_exists and pdf_path:
        item["pdf_status"] = "missing"
    return item

@app.get("/health")
def health_check():
    return {"status": "ok", "version": "3.1.0"}

@app.get("/papers")
def list_papers():
    conn = get_db_connection()
    try:
        papers = conn.execute("SELECT * FROM papers ORDER BY updated_at DESC LIMIT 50").fetchall()
    except sqlite3.OperationalError as exc:
        if "no such table: papers" in str(exc):
            return []
        raise
    finally:
        conn.close()

    out = []
    for p in papers:
        out.append(_enrich_pdf_flags(dict(p)))
    return out


@app.get("/papers/{paper_id}")
def get_paper(paper_id: str):
    conn = get_db_connection()
    try:
        row = conn.execute("SELECT * FROM papers WHERE paper_id = ?", (paper_id,)).fetchone()
    except sqlite3.OperationalError as exc:
        if "no such table: papers" in str(exc):
            raise HTTPException(status_code=404, detail="Paper not found")
        raise
    finally:
        conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Paper not found")
    return _enrich_pdf_flags(dict(row))

@app.post("/jobs/deepread", response_model=dict)
def enqueue_job(job_req: JobCreate):
    job_id = queue.enqueue(
        job_req.paper_id,
        job_req.clean_reindex,
        job_req.run_verify,
        job_req.persona_id,
        job_req.run_profile,
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


@app.get("/metrics/quality")
def quality_metrics(limit: int = 100):
    conn = get_db_connection()
    try:
        rows = conn.execute(
            """
            SELECT job_id, artifact_dir
            FROM jobs
            WHERE status IN ('completed', 'failed', 'cancelled')
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (max(1, min(limit, 1000)),),
        ).fetchall()
    except sqlite3.OperationalError:
        return {
            "jobs_scanned": 0,
            "bootstrap_meta_found": 0,
            "evidence_grounded_ratio_count": 0,
            "evidence_grounded_ratio_avg": None,
            "stats_cache_total": 0,
            "stats_cache_hit_count": 0,
            "stats_cache_hit_rate": None,
        }
    finally:
        conn.close()

    ratios: list[float] = []
    stats_cache_total = 0
    stats_cache_hit_count = 0
    bootstrap_meta_found = 0

    for row in rows:
        artifact_dir = row["artifact_dir"]
        if not artifact_dir:
            continue
        meta = _read_bootstrap_meta(str(Path(artifact_dir) / "bootstrap_meta.json"))
        if not meta:
            continue
        bootstrap_meta_found += 1

        ratio = meta.get("evidence_grounded_ratio")
        if isinstance(ratio, (int, float)):
            ratios.append(float(ratio))

        cache_hit = meta.get("stats_cache_hit")
        if isinstance(cache_hit, bool):
            stats_cache_total += 1
            if cache_hit:
                stats_cache_hit_count += 1

    ratio_avg = round(sum(ratios) / len(ratios), 4) if ratios else None
    hit_rate = (
        round(stats_cache_hit_count / stats_cache_total, 4)
        if stats_cache_total > 0
        else None
    )
    return {
        "jobs_scanned": len(rows),
        "bootstrap_meta_found": bootstrap_meta_found,
        "evidence_grounded_ratio_count": len(ratios),
        "evidence_grounded_ratio_avg": ratio_avg,
        "stats_cache_total": stats_cache_total,
        "stats_cache_hit_count": stats_cache_hit_count,
        "stats_cache_hit_rate": hit_rate,
    }

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
app.include_router(discover.router)
