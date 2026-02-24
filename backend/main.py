from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sse_starlette.sse import EventSourceResponse
import asyncio
import json
import os
from pathlib import Path
from typing import Any

import src.db_utils as db_utils
from src.db_utils import get_db_connection, init_db
from src.jobs.queue import JobQueue
from src.jobs.schemas import JobBootstrapMeta, JobCreate, JobEnqueueResponse, JobStatus
from src.schemas.ops import (
    ArtifactBundleResponse,
    ArtifactFileEntry,
    DownloaderOpsMetricsResponse,
    PersonaListResponse,
    PersonaOption,
    RunTimelineEvent,
    RunTimelineResponse,
)
from src.profiles.profile_store import load_profiles
from src.services.downloader_ops_metrics import Thresholds, collect_metrics, evaluate_alerts
from .routers import obsidian, feedback

app = FastAPI(title="Lattice API", version="3.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

queue = JobQueue()
FRONTEND_DIR = Path(__file__).resolve().parents[1] / "frontend"
FRONTEND_INDEX_PATH = FRONTEND_DIR / "index.html"

if FRONTEND_DIR.exists():
    app.mount("/ui-assets", StaticFiles(directory=str(FRONTEND_DIR)), name="ui-assets")

ARTIFACT_FILE_MAP: dict[str, str] = {
    "document_artifact": "document_artifact.json",
    "index_artifact": "index_artifact.json",
    "claimset": "claimset.json",
    "claimset_resolved": "claimset.resolved.json",
    "stats_report": "stats_report.json",
    "bootstrap_meta": "bootstrap_meta.json",
    "run_meta": "run_meta.json",
    "chunks": "chunks.jsonl",
}

ARTIFACT_ALIAS_MAP: dict[str, str] = {
    "document": "document_artifact",
    "document_artifact": "document_artifact",
    "index": "index_artifact",
    "index_artifact": "index_artifact",
    "claimset": "claimset",
    "claimset_resolved": "claimset_resolved",
    "claimset-resolved": "claimset_resolved",
    "stats": "stats_report",
    "stats_report": "stats_report",
    "bootstrap": "bootstrap_meta",
    "bootstrap_meta": "bootstrap_meta",
    "meta": "run_meta",
    "run_meta": "run_meta",
    "chunks": "chunks",
}

TERMINAL_JOB_STATUSES = {"completed", "failed", "cancelled"}


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


def _artifact_run_dir(paper_id: str, run_id: str) -> Path:
    return Path("storage/artifacts") / paper_id / run_id


def _safe_read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"_parse_error": str(exc)}


def _build_artifact_bundle(paper_id: str, run_id: str) -> ArtifactBundleResponse:
    run_dir = _artifact_run_dir(paper_id, run_id)
    if not run_dir.exists():
        raise HTTPException(status_code=404, detail=f"Artifacts not found for paper_id={paper_id}, run_id={run_id}")

    files: dict[str, ArtifactFileEntry] = {}
    for key, filename in ARTIFACT_FILE_MAP.items():
        path = run_dir / filename
        entry = ArtifactFileEntry(exists=path.exists(), path=str(path) if path.exists() else None)
        if path.exists() and path.suffix == ".json":
            entry.data = _safe_read_json(path)
        files[key] = entry

    return ArtifactBundleResponse(paper_id=paper_id, run_id=run_id, files=files)


def _resolve_artifact_key(artifact_name: str) -> str | None:
    normalized = artifact_name.strip().lower()
    return ARTIFACT_ALIAS_MAP.get(normalized)


def _latest_run_id_for_paper(paper_id: str) -> str | None:
    conn = get_db_connection()
    try:
        rows = conn.execute(
            """
            SELECT run_id, artifact_dir
            FROM jobs
            WHERE paper_id = ? AND run_id IS NOT NULL
            ORDER BY COALESCE(finished_at, started_at, created_at) DESC
            LIMIT 50
            """,
            (paper_id,),
        ).fetchall()
        for row in rows:
            run_id = str(row["run_id"] or "").strip()
            if not run_id:
                continue
            artifact_dir = str(row["artifact_dir"] or "").strip()
            if artifact_dir:
                if Path(artifact_dir).exists():
                    return run_id
            elif _artifact_run_dir(paper_id, run_id).exists():
                return run_id
    finally:
        conn.close()

    paper_dir = Path("storage/artifacts") / paper_id
    if not paper_dir.exists():
        return None
    candidates = [p for p in paper_dir.iterdir() if p.is_dir()]
    if not candidates:
        return None
    latest = sorted(candidates, key=lambda p: p.stat().st_mtime, reverse=True)[0]
    return latest.name


def _job_for_run_id(run_id: str) -> JobStatus | None:
    conn = get_db_connection()
    try:
        row = conn.execute(
            """
            SELECT *
            FROM jobs
            WHERE run_id = ?
            ORDER BY COALESCE(finished_at, started_at, created_at) DESC
            LIMIT 1
            """,
            (run_id,),
        ).fetchone()
        if not row:
            return None
        return JobStatus(**dict(row))
    finally:
        conn.close()


def _timeline_events_from_job(job: JobStatus, limit: int) -> list[RunTimelineEvent]:
    events: list[RunTimelineEvent] = []
    if job.log_path and Path(job.log_path).exists():
        lines = [
            line.strip()
            for line in Path(job.log_path).read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        for raw in lines[-limit:]:
            try:
                payload = json.loads(raw)
                level = str(payload.get("level") or "INFO")
                evt = "error" if level.upper() == "ERROR" else "log"
                events.append(
                    RunTimelineEvent(
                        event=evt,
                        source="job_log",
                        ts=str(payload.get("timestamp") or ""),
                        stage=payload.get("stage"),
                        progress=int(payload.get("progress")) if payload.get("progress") is not None else None,
                        level=level,
                        message=payload.get("message"),
                    )
                )
            except Exception:
                events.append(
                    RunTimelineEvent(
                        event="log",
                        source="job_log",
                        raw=raw,
                    )
                )

    terminal = (
        RunTimelineEvent(
            event="done",
            source="synthetic",
            ts=str(job.finished_at or job.started_at or job.created_at),
            stage=job.status,
            progress=job.progress,
            level="ERROR" if job.status == "failed" else "INFO",
            message=job.error_message or job.status,
        )
        if job.status in TERMINAL_JOB_STATUSES
        else RunTimelineEvent(
            event="status",
            source="synthetic",
            ts=str(job.started_at or job.created_at),
            stage=job.stage or job.status,
            progress=job.progress,
            level="INFO",
            message=job.status,
        )
    )
    events.append(terminal)

    if len(events) > limit:
        return events[-limit:]
    return events


def _read_log_lines(log_path: str | None) -> list[str]:
    if not log_path:
        return []
    path = Path(log_path)
    if not path.exists():
        return []
    return [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _parse_last_event_cursor(last_event_id: str | None) -> tuple[int, str]:
    """
    Parse Last-Event-ID into (sequence, kind).
    kind is one of: log | done | seq.
    """
    if not last_event_id:
        return (0, "seq")
    token = last_event_id.strip()
    if not token:
        return (0, "seq")
    if token.isdigit():
        return (max(0, int(token)), "seq")
    if "-" in token:
        prefix, tail = token.rsplit("-", 1)
        kind = prefix.strip().lower()
        if tail.isdigit():
            if kind not in {"log", "done"}:
                kind = "seq"
            return (max(0, int(tail)), kind)
    return (0, "seq")


def _normalize_replay_cursor(replay_cursor: int, replay_kind: str, total_logs: int, is_terminal: bool) -> tuple[int, str]:
    """
    Normalize replay cursor semantics for log rotations and terminal cursor handling.
    - stale cursor (out of range): replay from head
    - done cursor on terminal exact seq: no duplicate done replay
    - done cursor on non-terminal job: treat as stale
    """
    max_seq = total_logs + (1 if is_terminal else 0)
    if replay_kind == "done":
        if not is_terminal:
            return 0, "seq"
        if replay_cursor == max_seq:
            return replay_cursor, "done"
        if replay_cursor < max_seq:
            return replay_cursor, "seq"
    if replay_cursor > max_seq:
        return 0, "seq"
    return replay_cursor, replay_kind


def _persona_options(include_disabled: bool) -> list[PersonaOption]:
    options: list[PersonaOption] = [
        PersonaOption(
            id="default",
            title="Default (No Persona Override)",
            enabled=True,
            source="builtin",
        )
    ]
    conf = load_profiles()
    for profile in conf.profiles:
        if not include_disabled and not profile.enabled:
            continue
        options.append(
            PersonaOption(
                id=profile.id,
                title=profile.title,
                enabled=profile.enabled,
                notes=profile.notes,
                schedule=profile.schedule,
                query_focus=profile.query.to_boolean_string(),
                source="yaml",
            )
        )
    return options

@app.get("/health")
def health_check():
    return {"status": "ok", "version": "3.1.0"}


@app.get("/personas", response_model=PersonaListResponse)
def list_personas(include_disabled: bool = Query(default=False)):
    try:
        return PersonaListResponse(personas=_persona_options(include_disabled=include_disabled))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to load persona profiles: {exc}")


@app.get("/ui", include_in_schema=False)
def ui_shell():
    if not FRONTEND_INDEX_PATH.exists():
        raise HTTPException(status_code=404, detail=f"UI shell not found: {FRONTEND_INDEX_PATH}")
    return FileResponse(FRONTEND_INDEX_PATH)


@app.get("/ops/downloader-metrics", response_model=DownloaderOpsMetricsResponse)
def get_downloader_metrics(
    hours: int = Query(default=24, ge=1, le=24 * 30),
    rate_limit_warn: int = Query(default=3, ge=1),
    temp_fail_warn: int = Query(default=5, ge=1),
    bad_content_warn: int = Query(default=3, ge=1),
    policy_block_warn: int = Query(default=1, ge=1),
):
    thresholds = Thresholds(
        rate_limit_warn=rate_limit_warn,
        temp_fail_warn=temp_fail_warn,
        bad_content_warn=bad_content_warn,
        policy_block_warn=policy_block_warn,
    )
    metrics = collect_metrics(db_utils.DB_PATH, hours)
    alerts = evaluate_alerts(metrics, thresholds)
    return DownloaderOpsMetricsResponse(metrics=metrics, alerts=alerts)

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


@app.get("/papers/{paper_id}/pdf")
def get_paper_pdf(paper_id: str):
    conn = get_db_connection()
    row = conn.execute("SELECT paper_id, pdf_path FROM papers WHERE paper_id = ?", (paper_id,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Paper not found")

    raw_pdf_path = str(row["pdf_path"] or "").strip()
    if not raw_pdf_path:
        raise HTTPException(status_code=404, detail="PDF path not registered for this paper")

    pdf_path = Path(raw_pdf_path).expanduser()
    if not pdf_path.exists() or not pdf_path.is_file():
        raise HTTPException(status_code=404, detail="PDF file not found")

    return FileResponse(path=pdf_path, media_type="application/pdf", filename=pdf_path.name)


@app.get("/artifacts/{paper_id}/latest", response_model=ArtifactBundleResponse)
def get_latest_artifacts(paper_id: str):
    run_id = _latest_run_id_for_paper(paper_id)
    if not run_id:
        raise HTTPException(status_code=404, detail=f"No artifact runs found for paper_id={paper_id}")
    return _build_artifact_bundle(paper_id, run_id)


@app.get("/artifacts/{paper_id}/{run_id}", response_model=ArtifactBundleResponse)
def get_artifacts_for_run(paper_id: str, run_id: str):
    return _build_artifact_bundle(paper_id, run_id)


@app.get("/artifacts/{paper_id}/{run_id}/{artifact_name}", response_model=ArtifactFileEntry)
def get_artifact_file(paper_id: str, run_id: str, artifact_name: str):
    artifact_key = _resolve_artifact_key(artifact_name)
    if not artifact_key:
        raise HTTPException(status_code=404, detail=f"Unsupported artifact_name={artifact_name}")

    bundle = _build_artifact_bundle(paper_id, run_id)
    entry = bundle.files.get(artifact_key)
    if not entry or not entry.exists:
        raise HTTPException(
            status_code=404,
            detail=f"Artifact file not found for paper_id={paper_id}, run_id={run_id}, artifact_name={artifact_key}",
        )
    return entry

@app.post("/jobs/deepread", response_model=JobEnqueueResponse)
def enqueue_job(job_req: JobCreate):
    job_id = queue.enqueue(
        job_req.paper_id,
        job_req.clean_reindex,
        job_req.run_verify,
        job_req.persona_id,
    )
    job = queue.get_job(job_id)
    return JobEnqueueResponse(job_id=job_id, run_id=job.run_id if job else None, status="queued")

@app.get("/jobs/{job_id}", response_model=JobStatus)
def get_job_status(job_id: str):
    job = queue.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return _with_bootstrap_meta_path(job)


@app.get("/runs/{run_id}", response_model=JobStatus)
def get_run_status(run_id: str):
    job = _job_for_run_id(run_id)
    if not job:
        raise HTTPException(status_code=404, detail="Run not found")
    return _with_bootstrap_meta_path(job)


@app.get("/runs/{run_id}/timeline", response_model=RunTimelineResponse)
def get_run_timeline(run_id: str, limit: int = Query(default=500, ge=1, le=5000)):
    job = _job_for_run_id(run_id)
    if not job:
        raise HTTPException(status_code=404, detail="Run not found")
    events = _timeline_events_from_job(job, limit=limit)
    return RunTimelineResponse(run_id=run_id, job_id=job.job_id, paper_id=job.paper_id, events=events)


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
    """SSE endpoint for job logs/status with Last-Event-ID replay support."""
    replay_cursor, replay_kind = _parse_last_event_cursor(request.headers.get("last-event-id"))

    async def event_generator():
        nonlocal replay_cursor, replay_kind
        artifact_announced = False
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

            if not artifact_announced and job.artifact_dir and Path(job.artifact_dir).exists():
                yield {
                    "event": "artifact_ready",
                    "data": json.dumps(
                        {
                            "paper_id": job.paper_id,
                            "run_id": job.run_id,
                            "artifact_dir": job.artifact_dir,
                        }
                    ),
                }
                artifact_announced = True

            log_lines = _read_log_lines(job.log_path)
            total_logs = len(log_lines)
            replay_cursor, replay_kind = _normalize_replay_cursor(
                replay_cursor=replay_cursor,
                replay_kind=replay_kind,
                total_logs=total_logs,
                is_terminal=job.status in TERMINAL_JOB_STATUSES,
            )

            if replay_cursor < total_logs:
                for idx in range(replay_cursor + 1, total_logs + 1):
                    yield {"id": f"log-{idx}", "event": "log", "data": log_lines[idx - 1]}
                replay_cursor = total_logs
                replay_kind = "log"

            if job.status in TERMINAL_JOB_STATUSES:
                terminal_seq = total_logs + 1
                if replay_cursor < terminal_seq:
                    yield {"id": f"done-{terminal_seq}", "event": "done", "data": job.status}
                    replay_cursor = terminal_seq
                    replay_kind = "done"
                break

            await asyncio.sleep(1)

    return EventSourceResponse(event_generator())

app.include_router(obsidian.router)
app.include_router(feedback.router)
