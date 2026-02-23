from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Awaitable, Callable


logger = logging.getLogger("paperpipe.backend")


async def run_ingest_stage(
    *,
    pdf_path: Path,
    artifact_dir: Path,
    bootstrap_meta: dict[str, Any],
    emit: Callable[[str, int, str, str], Awaitable[Any]],
    is_cancelled: Callable[[], Awaitable[bool]],
    write_artifact_model: Callable[[Path, str, Any], None],
    write_bootstrap_meta: Callable[[Path, dict[str, Any]], None],
    ingest_agent_cls: Any,
) -> Any | None:
    if await is_cancelled():
        return None
    logger.info("Starting Ingest for %s", pdf_path.name)
    await emit("ingest", 10, f"Ingesting PDF: {pdf_path.name}", "INFO")
    ingest_agent = ingest_agent_cls()
    doc_artifact = ingest_agent.process_v2(str(pdf_path))
    if not doc_artifact:
        raise Exception("Ingestion failed to produce artifact")

    write_artifact_model(artifact_dir, "document_artifact.json", doc_artifact)
    bootstrap_meta["artifact_document_written"] = True
    write_bootstrap_meta(artifact_dir, bootstrap_meta)
    await emit("ingest", 25, f"Ingested {len(doc_artifact.pages)} pages", "INFO")
    return doc_artifact
