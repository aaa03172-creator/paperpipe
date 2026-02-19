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

logger = logging.getLogger("paperpipe.backend")

# Global Job Queue Registry (In-Memory PubSub)
JOB_QUEUES: Dict[str, asyncio.Queue] = {}

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
             
        await emit("index", 45, f"Indexed {index_artifact.chunk_count} chunks")

        # 4. Read (Claim Extraction)
        if await is_cancelled():
            return {"status": "cancelled", "run_id": run_id}
        await emit("read", 50, "Reader Agent analyzing...")
        reader_agent = ReaderAgent()
        claim_set = reader_agent.analyze(doc_artifact)
        
        if not claim_set:
             raise Exception("Reader Agent failed to produce claims")
             
        # Save ClaimSet
        with open(artifact_dir / "claimset.json", "w") as f:
            f.write(claim_set.model_dump_json(indent=2))
            
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
                    
                await emit("verify", 95, f"Verified {len(stats_report.checks)} checks")
                
            except Exception as e:
                logger.error(f"Verification Failed: {e}")
                await emit("verify", 85, f"Verification failed: {str(e)}", level="WARNING")

        # 6. Complete
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
