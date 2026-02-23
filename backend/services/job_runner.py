import asyncio
import uuid
import json
import logging
import traceback
import csv
import sqlite3
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any, Callable, Awaitable, Optional, List

from src.config import load_config
from src.db_utils import get_db_connection
from src.agents.ingest_agent import IngestAgent
from src.agents.indexer_agent import IndexerAgent
from src.agents.reader_agent import ReaderAgent
from src.agents.stats_agent import StatsVerificationAgent
from src.profiles.profile_store import load_profiles
from src.services.deepread_note_writer import (
    build_deepread_markdown,
    build_stats_markdown,
    upsert_deepread_section,
)
from src.agents.feedback_retriever import FeedbackRetriever
from src.core.paper_identity import make_paper_key
from src.core.artifact_paths import build_artifact_dir
from src.core.evidence_resolver import resolve_claimset_evidence
from backend.services.stats_runtime import resolve_stats_trigger_for_paper
from backend.services.job_runner_stages import (
    run_ingest_stage,
    run_index_stage,
    run_read_stage,
    run_verify_stage,
)

logger = logging.getLogger("paperpipe.backend")

# Global Job Queue Registry (In-Memory PubSub)
JOB_QUEUES: Dict[str, asyncio.Queue] = {}
FEEDBACK_FILE = Path("storage/feedback.jsonl")
REVIEW_NEEDS_READER = "NEEDS_READER"


def _resolve_note_path_for_paper(config, paper_id: str) -> Optional[Path]:
    vault_path = config.paths.obsidian_vault
    idx_files = [config.paths.index_all, Path("00_Index/on_demand.csv")]
    for rel_idx in idx_files:
        index_path = vault_path / rel_idx
        if not index_path.exists():
            continue
        try:
            with open(index_path, "r", encoding="utf-8") as f:
                for row in csv.DictReader(f):
                    if row.get("Paper_ID") == paper_id or row.get("DOI") == paper_id:
                        note_rel = row.get("Note_Path")
                        if note_rel:
                            note_path = vault_path / note_rel
                            if note_path.exists():
                                return note_path
        except Exception:
            continue
    return None


def _resolve_persona_hint(persona_id: str) -> Optional[str]:
    pid = (persona_id or "default").strip()
    if not pid or pid == "default":
        return None
    try:
        conf = load_profiles()
    except Exception as exc:
        logger.warning("Persona profile load failed for '%s': %s", pid, exc)
        return None
    for profile in conf.profiles:
        if profile.id == pid and profile.enabled:
            hint_parts = [f"profile_id={profile.id}", f"title={profile.title}"]
            if profile.notes:
                hint_parts.append(f"notes={profile.notes}")
            q = profile.query.to_boolean_string()
            if q:
                hint_parts.append(f"query_focus={q}")
            return "\n".join(hint_parts)
    return None


def _load_similar_feedback_top3(query_text: str, limit: int = 3) -> List[Dict[str, str]]:
    """
    Uses FeedbackRetriever to find top-K approved feedback cases relevant to the query.
    """
    try:
        retriever = FeedbackRetriever()
        cases = retriever.query_relevant_feedback(query_text, limit=limit)
        if cases:
            return cases
    except Exception as e:
        logger.warning(f"Failed to load similar feedback: {e}")
    if not FEEDBACK_FILE.exists():
        return []

    # Fallback: JSONL recent accepted feedback scan.
    lines = FEEDBACK_FILE.read_text(encoding="utf-8").splitlines()
    items: List[Dict[str, str]] = []
    seen_papers: set[str] = set()
    for raw in reversed(lines):
        raw = raw.strip()
        if not raw:
            continue
        try:
            rec = json.loads(raw)
        except Exception:
            continue
        if rec.get("accepted") is not True:
            continue
        rec_paper = str(rec.get("paper_id") or "")
        if not rec_paper or rec_paper == query_text or rec_paper in seen_papers:
            continue
        corr = str(rec.get("user_correction") or "").strip()
        if not corr:
            continue
        preview = corr.replace("\n", " ")[:180]
        items.append({"paper_id": rec_paper, "preview": preview})
        seen_papers.add(rec_paper)
        if len(items) >= limit:
            break
    return items


def _resolve_main_model(config) -> str:
    agents = getattr(config, "agents", None)
    model_name = getattr(agents, "main_model", None) if agents is not None else None
    return model_name or "llama3:latest"


def _write_bootstrap_meta(artifact_dir: Path, payload: Dict[str, Any]) -> None:
    try:
        with open(artifact_dir / "bootstrap_meta.json", "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
    except Exception as exc:
        logger.warning("Failed to write bootstrap_meta.json: %s", exc)


def _enqueue_needs_reader_followup(paper_id: str, reason: str) -> str:
    """
    Best-effort operational follow-up for not-ready claimsets.
    Returns one of: queued | already_open | queue_unavailable | queue_error.
    """
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT 1 FROM review_queue
            WHERE paper_id = ? AND decision = ? AND resolved_at IS NULL
            LIMIT 1
            """,
            (paper_id, REVIEW_NEEDS_READER),
        )
        if cur.fetchone():
            return "already_open"
        cur.execute(
            """
            INSERT INTO review_queue (paper_id, decision, reason)
            VALUES (?, ?, ?)
            """,
            (paper_id, REVIEW_NEEDS_READER, reason),
        )
        conn.commit()
        return "queued"
    except sqlite3.OperationalError as exc:
        logger.warning("review_queue unavailable for paper_id=%s: %s", paper_id, exc)
        return "queue_unavailable"
    except Exception as exc:
        logger.warning("review_queue enqueue failed for paper_id=%s: %s", paper_id, exc)
        return "queue_error"
    finally:
        if conn is not None:
            conn.close()


def _locate_pdf_for_paper(config, paper_id: str) -> Optional[Path]:
    results = list(config.paths.library_dir.rglob(f"*{paper_id}*.pdf"))
    if not results and "/" in paper_id:
        clean_id = paper_id.replace("/", "_")
        results = list(config.paths.library_dir.rglob(f"*{clean_id}*.pdf"))
    if not results:
        return None
    return results[0]


def _build_bootstrap_meta(
    job_id: str,
    run_id: str,
    paper_id: str,
    persona_id: str,
    run_verify: bool,
) -> Dict[str, Any]:
    return {
        "job_id": job_id,
        "run_id": run_id,
        "paper_id": paper_id,
        "paper_key": make_paper_key(paper_id),
        "persona_id": persona_id,
        "persona_applied": False,
        "similar_feedback_count": 0,
        "similar_feedback_paper_ids": [],
        "run_verify": bool(run_verify),
        "stats_trigger_reason": "none",
        "stats_cache_hit": False,
        "stats_cache_key": None,
        "stats_cache_path": None,
        "reader_model": None,
        "verifier_used": bool(run_verify),
        "verifier_status": "not_run",
        "stats_report_written": False,
        "artifact_document_written": False,
        "artifact_index_written": False,
        "artifact_claimset_written": False,
        "artifact_stats_written": False,
        "claimset_readiness": "unknown",
        "claimset_ready": None,
        "claimset_claim_count": 0,
        "claimset_readiness_reason": "not_evaluated",
        "claimset_readiness_badge": "UNKNOWN",
        "claimset_ops_action": "none",
        "claimset_ops_alert": False,
        "claimset_ops_note": "not_evaluated",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def _create_artifact_context(
    job_id: str,
    run_id: str,
    paper_id: str,
    persona_id: str,
    run_verify: bool,
) -> tuple[Path, Dict[str, Any]]:
    paper_key = make_paper_key(paper_id)
    artifact_dir = build_artifact_dir(run_id=run_id, paper_id=paper_id, paper_key=paper_key)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    bootstrap_meta = _build_bootstrap_meta(job_id, run_id, paper_id, persona_id, run_verify)
    bootstrap_meta["artifact_paper_dir"] = str(artifact_dir.parent)
    _write_bootstrap_meta(artifact_dir, bootstrap_meta)
    return artifact_dir, bootstrap_meta


def _write_artifact_model(artifact_dir: Path, filename: str, model_obj: Any) -> None:
    with open(artifact_dir / filename, "w", encoding="utf-8") as f:
        f.write(model_obj.model_dump_json(indent=2))


def _update_claimset_readiness(bootstrap_meta: Dict[str, Any], paper_id: str, claim_count: int) -> None:
    bootstrap_meta["claimset_claim_count"] = claim_count
    if claim_count > 0:
        bootstrap_meta["claimset_readiness"] = "ready"
        bootstrap_meta["claimset_ready"] = True
        bootstrap_meta["claimset_readiness_reason"] = "claims_present"
        bootstrap_meta["claimset_readiness_badge"] = "READY"
        bootstrap_meta["claimset_ops_action"] = "none"
        bootstrap_meta["claimset_ops_alert"] = False
        bootstrap_meta["claimset_ops_note"] = "ready"
        return

    bootstrap_meta["claimset_readiness"] = "not_ready"
    bootstrap_meta["claimset_ready"] = False
    bootstrap_meta["claimset_readiness_reason"] = "empty_claims"
    bootstrap_meta["claimset_readiness_badge"] = "NOT_READY"
    followup = _enqueue_needs_reader_followup(
        paper_id=paper_id,
        reason="Runtime claimset empty (claims=0) after reader step",
    )
    if followup in {"queued", "already_open"}:
        bootstrap_meta["claimset_ops_action"] = "manual_review_queued"
        bootstrap_meta["claimset_ops_alert"] = False
    else:
        bootstrap_meta["claimset_ops_action"] = "manual_review_required"
        bootstrap_meta["claimset_ops_alert"] = True
    bootstrap_meta["claimset_ops_note"] = followup


def _mark_runtime_failure(bootstrap_meta: Dict[str, Any], exc: Exception) -> None:
    bootstrap_meta["claimset_readiness"] = "unknown"
    bootstrap_meta["claimset_ready"] = None
    bootstrap_meta["claimset_readiness_reason"] = "runtime_error"
    bootstrap_meta["claimset_readiness_badge"] = "UNKNOWN"
    bootstrap_meta["claimset_ops_action"] = "retry_suggested"
    bootstrap_meta["claimset_ops_alert"] = True
    bootstrap_meta["claimset_ops_note"] = f"runtime_error:{type(exc).__name__}"

async def run_deepread_job(
    job_id: str,
    paper_id: str,
    persona_id: str = "default",
    run_verify: bool = False,
    run_profile: str | None = None,
    run_id: str = None,
    progress_callback: Optional[Callable[[Dict[str, Any]], Awaitable[None]]] = None,
    cancel_check: Optional[Callable[[], bool | Awaitable[bool]]] = None,
):
    """
    Async Job Runner for Deep Read Pipeline.
    Orchestrates: Ingest -> Index -> Read -> Verify.
    Emits events to JOB_QUEUES[job_id].
    """
    if not run_id:
        run_id = str(uuid.uuid4())
    
    queue = JOB_QUEUES.get(job_id)
    artifact_dir: Optional[Path] = None
    bootstrap_meta: Optional[Dict[str, Any]] = None

    async def is_cancelled() -> bool:
        if not cancel_check:
            return False
        result = cancel_check()
        if asyncio.iscoroutine(result):
            return await result
        return bool(result)

    async def emit(stage: str, progress: int, message: str, level: str = "INFO"):
        event = {
            "job_id": job_id,
            "run_id": run_id,
            "stage": stage,
            "progress": progress,
            "message": message,
            "level": level,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        if queue:
            await queue.put({"event": "progress", "data": json.dumps(event)})
            if level == "ERROR":
                await queue.put({"event": "error", "data": json.dumps(event)})
        if progress_callback:
            await progress_callback(event)
        return event

    try:
        if await is_cancelled():
            return {"status": "cancelled", "run_id": run_id}

        await emit("init", 0, f"Starting Deep Read for {paper_id}")
        
        config = load_config()
        effective_profile = run_profile or ("deep_verify" if run_verify else "grounded_read")
        if effective_profile not in {"fast_ingest", "grounded_read", "deep_verify"}:
            effective_profile = "grounded_read"
        effective_run_verify, trigger_reason = resolve_stats_trigger_for_paper(
            paper_id,
            run_verify=bool(run_verify),
            run_profile=effective_profile,
        )
        
        # 1. Locate PDF
        await emit("init", 5, "Locating PDF...")

        pdf_path = _locate_pdf_for_paper(config, paper_id)
        
        if not pdf_path or not pdf_path.exists():
            logger.error(f"❌ PDF not found for {paper_id} in {config.paths.library_dir}")
            await emit("init", 0, f"PDF not found for {paper_id}", level="ERROR")
            return {"status": "failed", "error": f"PDF not found for {paper_id}", "run_id": run_id}
            
        logger.info(f"✅ Found PDF: {pdf_path}")

        # Prepare Artifact Storage
        artifact_dir, bootstrap_meta = _create_artifact_context(
            job_id=job_id,
            run_id=run_id,
            paper_id=paper_id,
            persona_id=persona_id,
            run_verify=effective_run_verify,
        )
        bootstrap_meta["run_profile"] = effective_profile
        bootstrap_meta["stats_trigger_reason"] = trigger_reason
        bootstrap_meta["verifier_used"] = bool(effective_run_verify)
        _write_bootstrap_meta(artifact_dir, bootstrap_meta)
        
        # 2. Ingest
        doc_artifact = await run_ingest_stage(
            pdf_path=pdf_path,
            artifact_dir=artifact_dir,
            bootstrap_meta=bootstrap_meta,
            emit=emit,
            is_cancelled=is_cancelled,
            write_artifact_model=_write_artifact_model,
            write_bootstrap_meta=_write_bootstrap_meta,
            ingest_agent_cls=IngestAgent,
        )
        if doc_artifact is None:
            return {"status": "cancelled", "run_id": run_id}

        # 3. Index
        index_artifact = await run_index_stage(
            doc_artifact=doc_artifact,
            artifact_dir=artifact_dir,
            bootstrap_meta=bootstrap_meta,
            emit=emit,
            is_cancelled=is_cancelled,
            write_artifact_model=_write_artifact_model,
            write_bootstrap_meta=_write_bootstrap_meta,
            indexer_agent_cls=IndexerAgent,
        )
        if index_artifact is None:
            return {"status": "cancelled", "run_id": run_id}

        if effective_profile == "fast_ingest":
            await emit("completed", 100, "Fast ingest completed successfully")
            if queue:
                await queue.put(
                    {"event": "completed", "data": json.dumps({"job_id": job_id, "status": "succeeded", "run_id": run_id})}
                )
            return {"status": "succeeded", "run_id": run_id, "artifact_dir": str(artifact_dir)}

        # 4. Read (Claim Extraction)
        read_result = await run_read_stage(
            paper_id=paper_id,
            persona_id=persona_id,
            config=config,
            doc_artifact=doc_artifact,
            index_artifact=index_artifact,
            artifact_dir=artifact_dir,
            bootstrap_meta=bootstrap_meta,
            emit=emit,
            is_cancelled=is_cancelled,
            write_artifact_model=_write_artifact_model,
            write_bootstrap_meta=_write_bootstrap_meta,
            resolve_persona_hint=_resolve_persona_hint,
            load_similar_feedback_top3=_load_similar_feedback_top3,
            resolve_main_model=_resolve_main_model,
            update_claimset_readiness=_update_claimset_readiness,
            resolve_claimset_evidence=resolve_claimset_evidence,
            reader_agent_cls=ReaderAgent,
        )
        if read_result is None:
            return {"status": "cancelled", "run_id": run_id}
        claim_set, reader_agent = read_result

        # 5. Verify (Optional)
        stats_report = None
        if effective_run_verify:
            verify_result = await run_verify_stage(
                job_id=job_id,
                doc_artifact=doc_artifact,
                claim_set=claim_set,
                artifact_dir=artifact_dir,
                bootstrap_meta=bootstrap_meta,
                emit=emit,
                is_cancelled=is_cancelled,
                write_artifact_model=_write_artifact_model,
                write_bootstrap_meta=_write_bootstrap_meta,
                stats_agent_cls=StatsVerificationAgent,
                stats_profile=effective_profile,
                stats_schema_version="1.0",
                stats_cache_dir=Path("storage/stats_cache"),
            )
            if verify_result.get("cancelled"):
                return {"status": "cancelled", "run_id": run_id}
            stats_report = verify_result.get("stats_report")

        # 6. Complete
        # Best-effort note upsert (non-fatal): keep runtime fail-safe.
        try:
            note_path = _resolve_note_path_for_paper(config, paper_id)
            if note_path:
                stats_md = build_stats_markdown(stats_report) if stats_report is not None else ""
                deepread_md = build_deepread_markdown(
                    model_name=getattr(reader_agent, "model_name", "reader"),
                    claims_set=claim_set,
                    stats_md=stats_md,
                )
                note_content = note_path.read_text(encoding="utf-8")
                note_updated = upsert_deepread_section(note_content, deepread_md)
                note_path.write_text(note_updated, encoding="utf-8")
                await emit("read", 78, f"Deep Read section upserted: {note_path.name}")
        except Exception as note_err:
            await emit("read", 78, f"Deep Read note upsert skipped: {note_err}", level="WARNING")

        await emit("completed", 100, "Pipeline Completed Successfully")
        if queue:
            await queue.put({"event": "completed", "data": json.dumps({"job_id": job_id, "status": "succeeded", "run_id": run_id})})
        return {"status": "succeeded", "run_id": run_id, "artifact_dir": str(artifact_dir)}

    except Exception as e:
        logger.error(f"Job Failed: {e}")
        traceback.print_exc() # Print trace to stdout for debugging
        if artifact_dir is not None and bootstrap_meta is not None:
            _mark_runtime_failure(bootstrap_meta, e)
            _write_bootstrap_meta(artifact_dir, bootstrap_meta)
        await emit("error", 0, str(e), level="ERROR")
        if queue:
            await queue.put({"event": "completed", "data": json.dumps({"job_id": job_id, "status": "failed", "error": str(e)})})
        return {"status": "failed", "error": str(e), "run_id": run_id}
    finally:
        pass
