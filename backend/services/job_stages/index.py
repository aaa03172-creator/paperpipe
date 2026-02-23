from __future__ import annotations

from pathlib import Path
from typing import Any, Awaitable, Callable

from src.contracts.output_contracts import build_chunkset_contract


async def run_index_stage(
    *,
    paper_id: str,
    run_id: str,
    doc_artifact: Any,
    artifact_dir: Path,
    bootstrap_meta: dict[str, Any],
    emit: Callable[[str, int, str, str], Awaitable[Any]],
    is_cancelled: Callable[[], Awaitable[bool]],
    write_artifact_model: Callable[[Path, str, Any], None],
    write_bootstrap_meta: Callable[[Path, dict[str, Any]], None],
    indexer_agent_cls: Any,
) -> Any | None:
    if await is_cancelled():
        return None
    await emit("index", 30, "Indexing content...", "INFO")
    indexer_agent = indexer_agent_cls()
    index_artifact = indexer_agent.process(doc_artifact)

    write_artifact_model(artifact_dir, "index_artifact.json", index_artifact)
    chunks_contract = build_chunkset_contract(
        paper_id=paper_id,
        run_id=run_id,
        index_artifact=index_artifact,
    )
    write_artifact_model(artifact_dir, "chunks.json", chunks_contract)
    bootstrap_meta["artifact_index_written"] = True
    bootstrap_meta["artifact_chunks_written"] = True
    write_bootstrap_meta(artifact_dir, bootstrap_meta)
    await emit("index", 45, f"Indexed {index_artifact.chunk_count} chunks", "INFO")
    return index_artifact
