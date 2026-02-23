import asyncio
import uuid
import json
import logging
import traceback
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any, Callable, Awaitable, Optional

from src.config import load_config
from src.agents.ingest_agent import IngestAgent
from src.agents.indexer_agent import IndexerAgent
from src.agents.reader_agent import ReaderAgent
from src.agents.stats_agent import StatsVerificationAgent
from src.profiles.profile_store import load_profiles
from src.jobs.error_taxonomy import INPUT_PDF_NOT_FOUND, RUNTIME_EXCEPTION
from src.services.deepread_note_writer import (
    build_deepread_markdown,
    build_stats_markdown,
    upsert_deepread_section,
)
from src.core.evidence_resolver import resolve_claimset_evidence
from backend.services.job_runner_helpers import (
    create_artifact_context as _create_artifact_context,
    load_similar_feedback_top3 as _load_similar_feedback_top3_impl,
    locate_pdf_for_paper as _locate_pdf_for_paper,
    mark_runtime_failure as _mark_runtime_failure,
    resolve_main_model as _resolve_main_model,
    resolve_note_path_for_paper as _resolve_note_path_for_paper,
    resolve_persona_hint as _resolve_persona_hint_impl,
    update_claimset_readiness as _update_claimset_readiness,
    write_artifact_model as _write_artifact_model,
    write_bootstrap_meta as _write_bootstrap_meta,
)
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


def _resolve_persona_hint(persona_id: str):
    return _resolve_persona_hint_impl(persona_id, load_profiles_fn=load_profiles)


def _load_similar_feedback_top3(query_text: str, limit: int = 3):
    return _load_similar_feedback_top3_impl(
        query_text,
        limit=limit,
        feedback_file=FEEDBACK_FILE,
    )


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
            return {
                "status": "failed",
                "error": f"PDF not found for {paper_id}",
                "error_code": "PDF_NOT_FOUND",
                "error_taxonomy_code": INPUT_PDF_NOT_FOUND,
                "run_id": run_id,
            }
            
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
            paper_id=paper_id,
            run_id=run_id,
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
            run_id=run_id,
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
        return {
            "status": "failed",
            "error": str(e),
            "error_code": type(e).__name__,
            "error_taxonomy_code": RUNTIME_EXCEPTION,
            "run_id": run_id,
        }
    finally:
        pass
