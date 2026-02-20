import asyncio
import uuid
import json
import logging
import traceback
import csv
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any, Callable, Awaitable, Optional, List

from src.config import load_config
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

logger = logging.getLogger("paperpipe.backend")

# Global Job Queue Registry (In-Memory PubSub)
JOB_QUEUES: Dict[str, asyncio.Queue] = {}
FEEDBACK_FILE = Path("storage/feedback.jsonl")


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


def _load_similar_feedback_top3(paper_id: str, limit: int = 3) -> List[Dict[str, str]]:
    if not FEEDBACK_FILE.exists():
        return []
    lines = FEEDBACK_FILE.read_text(encoding="utf-8").splitlines()
    items: List[Dict[str, str]] = []
    for raw in reversed(lines):
        raw = raw.strip()
        if not raw:
            continue
        try:
            rec = json.loads(raw)
        except Exception:
            continue
        rec_paper = str(rec.get("paper_id") or "")
        if not rec_paper or rec_paper == paper_id:
            continue
        corr = str(rec.get("user_correction") or "").strip()
        if not corr:
            continue
        preview = corr.replace("\n", " ")[:180]
        items.append({"paper_id": rec_paper, "preview": preview})
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

async def run_deepread_job(
    job_id: str,
    paper_id: str,
    persona_id: str = "default",
    run_verify: bool = False,
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
        
        # 1. Locate PDF
        # Try finding locally in Library first (Mocking DB lookup for now if needed, or using direct path if we have it)
        # For this MVP, let's assume paper_id is a citekey or we can find it in library
        await emit("init", 5, "Locating PDF...")
        
        pdf_path = None
        # Simple heuristic: Look in Library root or subdirs
        results = list(config.paths.library_dir.rglob(f"*{paper_id}*.pdf"))
        # If ID is DOI, clean it
        if not results and "/" in paper_id:
             clean_id = paper_id.replace("/", "_")
             results = list(config.paths.library_dir.rglob(f"*{clean_id}*.pdf"))
        
        if results:
            pdf_path = results[0]
        
        if not pdf_path or not pdf_path.exists():
            logger.error(f"❌ PDF not found for {paper_id} in {config.paths.library_dir}")
            await emit("init", 0, f"PDF not found for {paper_id}", level="ERROR")
            return {"status": "failed", "error": f"PDF not found for {paper_id}", "run_id": run_id}
            
        logger.info(f"✅ Found PDF: {pdf_path}")

        # Prepare Artifact Storage
        artifact_dir = Path(f"storage/artifacts/{paper_id}/{run_id}")
        artifact_dir.mkdir(parents=True, exist_ok=True)
        bootstrap_meta: Dict[str, Any] = {
            "job_id": job_id,
            "run_id": run_id,
            "paper_id": paper_id,
            "persona_id": persona_id,
            "persona_applied": False,
            "similar_feedback_count": 0,
            "similar_feedback_paper_ids": [],
            "run_verify": bool(run_verify),
            "reader_model": None,
            "verifier_used": bool(run_verify),
            "verifier_status": "not_run",
            "stats_report_written": False,
            "artifact_document_written": False,
            "artifact_index_written": False,
            "artifact_claimset_written": False,
            "artifact_stats_written": False,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        _write_bootstrap_meta(artifact_dir, bootstrap_meta)
        
        # 2. Ingest
        if await is_cancelled():
            return {"status": "cancelled", "run_id": run_id}
        logger.info(f"Starting Ingest for {pdf_path.name}")
        await emit("ingest", 10, f"Ingesting PDF: {pdf_path.name}")
        ingest_agent = IngestAgent()
        doc_artifact = ingest_agent.process_v2(str(pdf_path))
        
        if not doc_artifact:
             raise Exception("Ingestion failed to produce artifact")

        # Save Document Artifact
        with open(artifact_dir / "document_artifact.json", "w") as f:
            f.write(doc_artifact.model_dump_json(indent=2))
        bootstrap_meta["artifact_document_written"] = True
        _write_bootstrap_meta(artifact_dir, bootstrap_meta)
            
        await emit("ingest", 25, f"Ingested {len(doc_artifact.pages)} pages")

        # 3. Index
        if await is_cancelled():
            return {"status": "cancelled", "run_id": run_id}
        await emit("index", 30, "Indexing content...")
        indexer_agent = IndexerAgent()
        index_artifact = indexer_agent.process(doc_artifact)
        
        # Save Index Artifact
        with open(artifact_dir / "index_artifact.json", "w") as f:
             f.write(index_artifact.model_dump_json(indent=2))
        bootstrap_meta["artifact_index_written"] = True
        _write_bootstrap_meta(artifact_dir, bootstrap_meta)
             
        await emit("index", 45, f"Indexed {index_artifact.chunk_count} chunks")

        # 4. Read (Claim Extraction)
        if await is_cancelled():
            return {"status": "cancelled", "run_id": run_id}
        await emit("read", 50, "Reader Agent analyzing...")
        persona_hint = _resolve_persona_hint(persona_id)
        similar_feedback = _load_similar_feedback_top3(paper_id=paper_id, limit=3)
        if similar_feedback:
            fb_lines = ["Similar feedback examples (Top-3):"]
            for idx, item in enumerate(similar_feedback, 1):
                fb_lines.append(f"{idx}) paper_id={item['paper_id']} preview={item['preview']}")
            feedback_hint = "\n".join(fb_lines)
            persona_hint = f"{persona_hint}\n\n{feedback_hint}" if persona_hint else feedback_hint
            bootstrap_meta["similar_feedback_count"] = len(similar_feedback)
            bootstrap_meta["similar_feedback_paper_ids"] = [item["paper_id"] for item in similar_feedback]
            await emit("read", 53, f"Similar feedback injected: {len(similar_feedback)}")
        if persona_hint:
            bootstrap_meta["persona_applied"] = True
            await emit("read", 52, f"Persona applied: {persona_id}")
        _write_bootstrap_meta(artifact_dir, bootstrap_meta)
        main_model = _resolve_main_model(config)
        bootstrap_meta["reader_model"] = main_model
        _write_bootstrap_meta(artifact_dir, bootstrap_meta)
        try:
            reader_agent = ReaderAgent(
                model_name=main_model,
                persona_hint=persona_hint,
            )
        except TypeError:
            # Test doubles may expose a simplified constructor.
            reader_agent = ReaderAgent()
        claim_set = reader_agent.analyze(doc_artifact)
        
        if not claim_set:
             raise Exception("Reader Agent failed to produce claims")
             
        # Save ClaimSet
        with open(artifact_dir / "claimset.json", "w") as f:
            f.write(claim_set.model_dump_json(indent=2))
        bootstrap_meta["artifact_claimset_written"] = True
        _write_bootstrap_meta(artifact_dir, bootstrap_meta)
            
        await emit("read", 75, f"Extracted {len(claim_set.claims)} claims")

        # 5. Verify (Optional)
        if run_verify:
            if await is_cancelled():
                return {"status": "cancelled", "run_id": run_id}
            await emit("verify", 80, "Stats Verification Agent running...")
            try:
                stats_agent = StatsVerificationAgent()
                # StatsVerificationAgent.run signature:
                # run(job_id: str, doc: DocumentArtifact|DocumentArtifactV2, claims: ClaimSet)
                stats_report = stats_agent.run(
                    job_id=job_id,
                    doc=doc_artifact,
                    claims=claim_set
                )
                
                # Save Report
                with open(artifact_dir / "stats_report.json", "w") as f:
                    f.write(stats_report.model_dump_json(indent=2))
                bootstrap_meta["verifier_status"] = "completed"
                bootstrap_meta["stats_report_written"] = True
                bootstrap_meta["artifact_stats_written"] = True
                _write_bootstrap_meta(artifact_dir, bootstrap_meta)
                    
                await emit("verify", 95, f"Verified {len(stats_report.checks)} checks")
                
            except Exception as e:
                logger.error(f"Verification Failed: {e}")
                bootstrap_meta["verifier_status"] = "failed"
                _write_bootstrap_meta(artifact_dir, bootstrap_meta)
                await emit("verify", 85, f"Verification failed: {str(e)}", level="WARNING")

        # 6. Complete
        # Best-effort note upsert (non-fatal): keep runtime fail-safe.
        try:
            note_path = _resolve_note_path_for_paper(config, paper_id)
            if note_path:
                stats_md = build_stats_markdown(stats_report) if run_verify and "stats_report" in locals() else ""
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
        await emit("error", 0, str(e), level="ERROR")
        if queue:
            await queue.put({"event": "completed", "data": json.dumps({"job_id": job_id, "status": "failed", "error": str(e)})})
        return {"status": "failed", "error": str(e), "run_id": run_id}
    finally:
        # Cleanup queue after short delay to allow client to disconnect?
        # Actually EventSourceResponse typically handles disconnect.
        # We might keep the queue for a bit or let it be garbage collected if we remove from dict.
        # For MVP, we leave it or remove it.
        # del JOB_QUEUES[job_id] # Keeping it might stream empty?
        pass
