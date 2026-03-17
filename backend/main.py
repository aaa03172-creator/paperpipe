from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sse_starlette.sse import EventSourceResponse
import asyncio
import json
import os
import re
from pathlib import Path
from typing import Any

import src.db_utils as db_utils
from src.db_utils import get_db_connection, init_db
from src.jobs.queue import DuplicateOpenJobError, JobQueue, QueueBackpressureError
from src.jobs.schemas import JobBootstrapMeta, JobCreate, JobEnqueueResponse, JobStatus
from src.schemas.chat import ChatRequest, ChatStubResponse
from src.output_modes import resolve_chat_output_mode_family
from src.schemas.papers import PaperDetailResponse, PaperSummaryResponse
from src.schemas.research_dna import (
    ResearchDNAActorRequest,
    ResearchDNACreateRequest,
    ResearchDNAEnvelope,
    ResearchDNAInterviewEnvelope,
    ResearchDNAInterviewRequest,
    ResearchDNAProjectedProfileEnvelope,
    ResearchDNAProjectProfileRequest,
    ResearchDNAPilotRunEnvelope,
    ResearchDNAPilotRunRequest,
    ResearchDNARefineRequest,
    ResearchDNAScreeningRequest,
    ResearchDNAUpdateRequest,
)
from src.profiles.research_dna_service import (
    ResearchDNAStateError,
    approve_pilot,
    create_research_dna,
    lock_research_dna,
    log_interview_response,
    refine_query_version,
    run_pilot,
    submit_screening_decision,
    unlock_research_dna,
    update_research_dna,
)
from src.profiles.research_dna_projection import sync_research_dna_profile
from src.profiles.research_dna_store import ResearchDNARevisionConflictError, load_research_dna
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
from src.services.path_masking import is_path_masking_enabled, mask_local_path
from src.services.paper_ops_summary import ArtifactSnapshotCache, build_ops_summary_for_paper_id
from src.services.runtime_paths import artifact_paper_dir, artifact_run_dir, artifacts_root
from .routers import feedback, meeting_packs, obsidian, paper_notes

def _resolve_cors_allow_origins() -> list[str]:
    raw = (
        os.getenv("LATTICE_CORS_ALLOW_ORIGINS")
        or os.getenv("PAPERPIPE_CORS_ALLOW_ORIGINS")
        or ""
    ).strip()
    if not raw:
        return ["http://127.0.0.1:8000", "http://localhost:8000"]
    origins = [item.strip() for item in raw.split(",") if item.strip()]
    return origins or ["http://127.0.0.1:8000", "http://localhost:8000"]


def _resolve_api_key() -> str:
    return (
        os.getenv("LATTICE_API_KEY")
        or os.getenv("PAPERPIPE_API_KEY")
        or ""
    ).strip()


def _is_chat_enabled() -> bool:
    raw = (
        os.getenv("CHAT_ENABLED")
        or os.getenv("LATTICE_CHAT_ENABLED")
        or os.getenv("PAPERPIPE_CHAT_ENABLED")
        or "false"
    ).strip().lower()
    return raw in {"1", "true", "yes", "on"}


def _requires_api_key(method: str, path: str) -> bool:
    if method.upper() != "POST":
        return False

    normalized = path.rstrip("/") or "/"
    if normalized in {"/jobs/deepread", "/feedback", "/obsidian/sync"}:
        return True
    return bool(re.match(r"^/jobs/[^/]+/cancel$", normalized))


app = FastAPI(title="Lattice API", version="3.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=_resolve_cors_allow_origins(),
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def api_key_guard(request: Request, call_next):
    expected_key = _resolve_api_key()
    if not expected_key:
        return await call_next(request)
    if not _requires_api_key(request.method, request.url.path):
        return await call_next(request)

    supplied_key = (request.headers.get("x-api-key") or "").strip()
    if supplied_key != expected_key:
        return JSONResponse(
            status_code=401,
            content={
                "error_code": "UNAUTHORIZED",
                "message": "Missing or invalid X-API-Key",
            },
        )
    return await call_next(request)

queue = JobQueue()
FRONTEND_DIR = Path(__file__).resolve().parents[1] / "frontend"
FRONTEND_INDEX_PATH = FRONTEND_DIR / "index.html"
UI_SHELL_PATH = FRONTEND_DIR / "ui-shell.html"

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


def _derive_paper_issues_state(item: dict[str, Any]) -> str:
    explicit_state = str(item.get("issues_state") or "").strip().lower()
    if explicit_state in {"flagged", "clear", "unavailable"}:
        return explicit_state
    issues_value = item.get("issues")
    issue_count = issues_value if isinstance(issues_value, int) else 0
    if issue_count > 0:
        return "flagged"
    issues_label = str(item.get("issues_label") or "").strip()
    if issues_label and re.search(r"not analy[sz]ed|unavailable|not available|pending|not reviewed|not run", issues_label, re.IGNORECASE):
        return "unavailable"
    status_value = str(item.get("status") or "").strip().upper()
    if status_value in {"NEW", "FETCHED", "PDF_MISSING", "GATED"}:
        return "unavailable"
    if status_value in {"PENDING_REVIEW", "QUARANTINED", "FAILED"}:
        return "flagged"
    if status_value in {"APPROVED", "INDEXED"}:
        return "clear"
    return "clear"


def _public_path(path_value: str | None) -> str | None:
    if path_value is None:
        return None
    if not is_path_masking_enabled():
        return path_value
    return mask_local_path(path_value)


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
            "artifact_dir": _public_path(getattr(job, "artifact_dir", None)),
            "log_path": _public_path(getattr(job, "log_path", None)),
            "bootstrap_meta_path": _public_path(meta_path),
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
    return artifact_run_dir(paper_id, run_id)


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
        entry = ArtifactFileEntry(
            exists=path.exists(),
            path=_public_path(str(path)) if path.exists() else None,
        )
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

    paper_dir = artifact_paper_dir(paper_id)
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


def _list_jobs(*, paper_id: str | None, status: str | None, limit: int) -> list[JobStatus]:
    conn = get_db_connection()
    try:
        where: list[str] = []
        params: list[Any] = []
        if paper_id:
            where.append("paper_id = ?")
            params.append(paper_id)
        if status:
            where.append("status = ?")
            params.append(status)

        query = "SELECT * FROM jobs"
        if where:
            query += " WHERE " + " AND ".join(where)
        query += " ORDER BY COALESCE(finished_at, started_at, created_at) DESC LIMIT ?"
        params.append(limit)

        rows = conn.execute(query, params).fetchall()
        return [_with_bootstrap_meta_path(JobStatus(**dict(row))) for row in rows]
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


@app.post("/api/chat", response_model=ChatStubResponse)
def chat_stub(req: ChatRequest):
    output_mode_family = resolve_chat_output_mode_family(req.output_mode_family)
    if not _is_chat_enabled():
        return JSONResponse(
            status_code=501,
            content=ChatStubResponse(
                chat_enabled=False,
                output_mode_family=output_mode_family,
                message=(
                    "CHAT_ENABLED=false. /api/chat is a stub only in this sprint; "
                    "no LLM provider, memory, or RAG call is executed."
                ),
            ).model_dump(),
        )
    return JSONResponse(
        status_code=501,
        content=ChatStubResponse(
            chat_enabled=True,
            output_mode_family=output_mode_family,
            message=(
                "/api/chat is intentionally stubbed. This sprint does not implement "
                "LLM execution, conversation storage, or retrieval."
            ),
        ).model_dump(),
    )


@app.post("/research-dna", response_model=ResearchDNAEnvelope)
def create_research_dna_endpoint(req: ResearchDNACreateRequest):
    try:
        dna = create_research_dna(
            topic=req.topic,
            intent=req.intent,
            actor_type=req.actor_type,
            actor_id=req.actor_id,
            reason=req.reason,
            dna_id=req.dna_id,
            title=req.title,
            recommended_databases=req.recommended_databases,
            available_databases=req.available_databases,
        )
    except ResearchDNAStateError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to create Research DNA: {exc}")
    return ResearchDNAEnvelope(dna=dna)


@app.get("/research-dna/{dna_id}", response_model=ResearchDNAEnvelope)
def get_research_dna_endpoint(dna_id: str):
    try:
        dna = load_research_dna(dna_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Research DNA not found")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to load Research DNA: {exc}")
    return ResearchDNAEnvelope(dna=dna)


@app.post("/research-dna/{dna_id}/approve-pilot", response_model=ResearchDNAEnvelope)
def approve_research_dna_pilot_endpoint(dna_id: str, req: ResearchDNAActorRequest):
    try:
        dna = approve_pilot(
            dna_id,
            actor_type=req.actor_type,
            actor_id=req.actor_id,
            reason=req.reason,
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Research DNA not found")
    except ResearchDNARevisionConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except ResearchDNAStateError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to approve pilot: {exc}")
    return ResearchDNAEnvelope(dna=dna)


@app.post("/research-dna/{dna_id}/update", response_model=ResearchDNAEnvelope)
def update_research_dna_endpoint(dna_id: str, req: ResearchDNAUpdateRequest):
    try:
        dna = update_research_dna(
            dna_id,
            patch=req.patch,
            actor_type=req.actor_type,
            actor_id=req.actor_id,
            reason=req.reason,
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Research DNA not found")
    except ResearchDNARevisionConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except ResearchDNAStateError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to update Research DNA: {exc}")
    return ResearchDNAEnvelope(dna=dna)


@app.post("/research-dna/{dna_id}/interview", response_model=ResearchDNAInterviewEnvelope)
def log_research_dna_interview_endpoint(dna_id: str, req: ResearchDNAInterviewRequest):
    try:
        dna, interview = log_interview_response(
            dna_id,
            round=req.round,
            question_id=req.question_id,
            question=req.question,
            answer=req.answer,
            actor_type=req.actor_type,
            actor_id=req.actor_id,
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Research DNA not found")
    except ResearchDNARevisionConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except ResearchDNAStateError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to log interview response: {exc}")
    return ResearchDNAInterviewEnvelope(dna=dna, interview=interview)


@app.post("/research-dna/{dna_id}/pilot", response_model=ResearchDNAPilotRunEnvelope)
def run_research_dna_pilot_endpoint(dna_id: str, req: ResearchDNAPilotRunRequest):
    try:
        pilot_run = run_pilot(
            dna_id,
            actor_type=req.actor_type,
            actor_id=req.actor_id,
            run_id=req.run_id,
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Research DNA not found")
    except ResearchDNARevisionConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except ResearchDNAStateError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to run pilot: {exc}")
    return ResearchDNAPilotRunEnvelope(pilot_run=pilot_run)


@app.post("/research-dna/{dna_id}/screening", response_model=ResearchDNAEnvelope)
def submit_research_dna_screening_endpoint(dna_id: str, req: ResearchDNAScreeningRequest):
    try:
        dna = submit_screening_decision(
            dna_id,
            run_id=req.run_id,
            candidate_id=req.candidate_id,
            decision=req.decision,
            reason_code=req.reason_code,
            note=req.note,
            actor_type=req.actor_type,
            actor_id=req.actor_id,
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Research DNA not found")
    except ResearchDNARevisionConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except ResearchDNAStateError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to submit screening decision: {exc}")
    return ResearchDNAEnvelope(dna=dna)


@app.post("/research-dna/{dna_id}/refine", response_model=ResearchDNAEnvelope)
def refine_research_dna_endpoint(dna_id: str, req: ResearchDNARefineRequest):
    try:
        dna = refine_query_version(
            dna_id,
            query_version=req.query_version,
            actor_type=req.actor_type,
            actor_id=req.actor_id,
            reason=req.reason,
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Research DNA not found")
    except ResearchDNARevisionConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except ResearchDNAStateError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to refine query version: {exc}")
    return ResearchDNAEnvelope(dna=dna)


@app.post("/research-dna/{dna_id}/lock", response_model=ResearchDNAEnvelope)
def lock_research_dna_endpoint(dna_id: str, req: ResearchDNAActorRequest):
    try:
        dna = lock_research_dna(
            dna_id,
            actor_type=req.actor_type,
            actor_id=req.actor_id,
            reason=req.reason,
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Research DNA not found")
    except ResearchDNARevisionConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except ResearchDNAStateError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to lock Research DNA: {exc}")
    return ResearchDNAEnvelope(dna=dna)


@app.post("/research-dna/{dna_id}/project-profile", response_model=ResearchDNAProjectedProfileEnvelope)
def project_research_dna_profile_endpoint(dna_id: str, req: ResearchDNAProjectProfileRequest):
    try:
        projection = sync_research_dna_profile(
            dna_id,
            actor_type=req.actor_type,
            actor_id=req.actor_id,
            reason=req.reason,
            query_version_name=req.query_version,
            database=req.database,
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Research DNA not found")
    except ResearchDNARevisionConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except ResearchDNAStateError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to project Research DNA profile: {exc}")
    return ResearchDNAProjectedProfileEnvelope(projection=projection)


@app.post("/research-dna/{dna_id}/unlock", response_model=ResearchDNAEnvelope)
def unlock_research_dna_endpoint(dna_id: str, req: ResearchDNAActorRequest):
    try:
        dna = unlock_research_dna(
            dna_id,
            actor_type=req.actor_type,
            actor_id=req.actor_id,
            reason=req.reason,
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Research DNA not found")
    except ResearchDNARevisionConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except ResearchDNAStateError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to unlock Research DNA: {exc}")
    return ResearchDNAEnvelope(dna=dna)


@app.get("/personas", response_model=PersonaListResponse)
def list_personas(include_disabled: bool = Query(default=False)):
    try:
        return PersonaListResponse(personas=_persona_options(include_disabled=include_disabled))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to load persona profiles: {exc}")


@app.get("/ui", include_in_schema=False)
def ui_shell():
    if UI_SHELL_PATH.exists():
        return FileResponse(UI_SHELL_PATH)
    if FRONTEND_INDEX_PATH.exists():
        return FileResponse(FRONTEND_INDEX_PATH)
    raise HTTPException(status_code=404, detail=f"UI shell not found: {UI_SHELL_PATH} or {FRONTEND_INDEX_PATH}")


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
def list_papers(
    limit: int = Query(default=50, ge=1, le=5000),
    offset: int = Query(default=0, ge=0),
) -> list[PaperSummaryResponse]:
    conn = get_db_connection()
    papers = conn.execute(
        "SELECT * FROM papers ORDER BY updated_at DESC LIMIT ? OFFSET ?",
        (limit, offset),
    ).fetchall()
    conn.close()
    artifacts_path = artifacts_root()
    artifact_cache: ArtifactSnapshotCache = {}
    out = []
    for p in papers:
        item = dict(p)
        pdf_path = item.get("pdf_path")
        pdf_exists = bool(pdf_path and os.path.exists(pdf_path))
        item["pdf_exists"] = pdf_exists
        item["pdf_path"] = _public_path(pdf_path)
        if not pdf_exists and pdf_path:
            item["pdf_status"] = "missing"
        item["issues_state"] = _derive_paper_issues_state(item)
        item["ops_summary"] = build_ops_summary_for_paper_id(artifacts_path, str(item.get("paper_id") or ""), artifact_cache)
        out.append(item)
    return out


@app.get("/papers/{paper_id}")
def get_paper(paper_id: str) -> PaperDetailResponse:
    conn = get_db_connection()
    row = conn.execute("SELECT * FROM papers WHERE paper_id = ?", (paper_id,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Paper not found")

    item = dict(row)
    pdf_path = item.get("pdf_path")
    pdf_exists = bool(pdf_path and os.path.exists(pdf_path))
    item["pdf_exists"] = pdf_exists
    item["pdf_path"] = _public_path(pdf_path)
    if not pdf_exists and pdf_path:
        item["pdf_status"] = "missing"
    item["issues_state"] = _derive_paper_issues_state(item)
    item["ops_summary"] = build_ops_summary_for_paper_id(artifacts_root(), paper_id, {})
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


@app.get("/artifacts/{paper_id:path}/latest", response_model=ArtifactBundleResponse)
def get_latest_artifacts(paper_id: str):
    run_id = _latest_run_id_for_paper(paper_id)
    if not run_id:
        raise HTTPException(status_code=404, detail=f"No artifact runs found for paper_id={paper_id}")
    return _build_artifact_bundle(paper_id, run_id)


@app.get("/artifacts", response_model=ArtifactBundleResponse)
def get_artifacts_for_run_query(paper_id: str, run_id: str):
    return _build_artifact_bundle(paper_id, run_id)


@app.get("/artifacts/{paper_id:path}/{run_id}/{artifact_name}", response_model=ArtifactFileEntry)
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


@app.get("/artifacts/{paper_id:path}/{run_id}", response_model=ArtifactBundleResponse)
def get_artifacts_for_run(paper_id: str, run_id: str):
    return _build_artifact_bundle(paper_id, run_id)

@app.post("/jobs/deepread", response_model=JobEnqueueResponse)
def enqueue_job(job_req: JobCreate):
    try:
        job_id = queue.enqueue(
            job_req.paper_id,
            job_req.clean_reindex,
            job_req.run_verify,
            job_req.persona_id,
        )
    except DuplicateOpenJobError as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "error_code": "JOB_ALREADY_OPEN",
                "message": f"Open job already exists for paper_id={exc.paper_id}",
                "paper_id": exc.paper_id,
                "job_id": exc.job_id,
                "run_id": exc.run_id,
                "status": exc.status,
            },
        )
    except QueueBackpressureError as exc:
        raise HTTPException(
            status_code=429,
            detail={
                "error_code": "QUEUE_FULL",
                "message": "Queued jobs limit reached",
                "queued_count": exc.queued_count,
                "limit": exc.limit,
            },
        )
    job = queue.get_job(job_id)
    return JobEnqueueResponse(job_id=job_id, run_id=job.run_id if job else None, status="queued")


@app.get("/jobs", response_model=list[JobStatus])
def list_jobs(
    paper_id: str | None = Query(default=None),
    status: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
):
    return _list_jobs(paper_id=paper_id, status=status, limit=limit)


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
                yield {"event": "error", "data": "Job not found", "retry": 2000}
                break
            
            # Send status update
            enriched = _with_bootstrap_meta_path(job)
            yield {"event": "status", "data": json.dumps(enriched.model_dump(), default=str), "retry": 2000}

            if not artifact_announced and job.artifact_dir and Path(job.artifact_dir).exists():
                yield {
                    "event": "artifact_ready",
                    "data": json.dumps(
                        {
                            "paper_id": job.paper_id,
                            "run_id": job.run_id,
                            "artifact_dir": _public_path(job.artifact_dir),
                        }
                    ),
                    "retry": 2000,
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
                    yield {"id": f"log-{idx}", "event": "log", "data": log_lines[idx - 1], "retry": 2000}
                replay_cursor = total_logs
                replay_kind = "log"

            if job.status in TERMINAL_JOB_STATUSES:
                terminal_seq = total_logs + 1
                if replay_cursor < terminal_seq:
                    yield {"id": f"done-{terminal_seq}", "event": "done", "data": job.status, "retry": 2000}
                    replay_cursor = terminal_seq
                    replay_kind = "done"
                break

            await asyncio.sleep(1)

    return EventSourceResponse(event_generator(), ping=20)

app.include_router(obsidian.router)
app.include_router(feedback.router)
app.include_router(paper_notes.router)
app.include_router(meeting_packs.router)
