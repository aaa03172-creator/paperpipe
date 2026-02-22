from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Awaitable, Callable, Optional

from backend.services.stats_runtime import (
    build_stats_cache_key,
    load_cached_stats_report,
    save_cached_stats_report,
)


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


async def run_index_stage(
    *,
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
    bootstrap_meta["artifact_index_written"] = True
    write_bootstrap_meta(artifact_dir, bootstrap_meta)
    await emit("index", 45, f"Indexed {index_artifact.chunk_count} chunks", "INFO")
    return index_artifact


async def run_read_stage(
    *,
    paper_id: str,
    persona_id: str,
    config: Any,
    doc_artifact: Any,
    index_artifact: Any,
    artifact_dir: Path,
    bootstrap_meta: dict[str, Any],
    emit: Callable[[str, int, str, str], Awaitable[Any]],
    is_cancelled: Callable[[], Awaitable[bool]],
    write_artifact_model: Callable[[Path, str, Any], None],
    write_bootstrap_meta: Callable[[Path, dict[str, Any]], None],
    resolve_persona_hint: Callable[[str], Optional[str]],
    load_similar_feedback_top3: Callable[[str, int], list[dict[str, str]]],
    resolve_main_model: Callable[[Any], str],
    update_claimset_readiness: Callable[[dict[str, Any], str, int], None],
    resolve_claimset_evidence: Callable[[Any, Any], Any],
    reader_agent_cls: Any,
) -> tuple[Any, Any] | None:
    if await is_cancelled():
        return None
    await emit("read", 50, "Reader Agent analyzing...", "INFO")
    persona_hint = resolve_persona_hint(persona_id)

    feedback_query_text = persona_hint if persona_hint else paper_id
    similar_feedback = load_similar_feedback_top3(feedback_query_text, limit=3)
    if similar_feedback:
        fb_lines = ["Similar feedback examples (Top-3):"]
        for idx, item in enumerate(similar_feedback, 1):
            fb_lines.append(f"{idx}) paper_id={item['paper_id']} preview={item['preview']}")
        feedback_hint = "\n".join(fb_lines)
        persona_hint = f"{persona_hint}\n\n{feedback_hint}" if persona_hint else feedback_hint
        bootstrap_meta["similar_feedback_count"] = len(similar_feedback)
        bootstrap_meta["similar_feedback_paper_ids"] = [item["paper_id"] for item in similar_feedback]
        await emit("read", 53, f"Similar feedback injected: {len(similar_feedback)}", "INFO")

    if persona_hint:
        bootstrap_meta["persona_applied"] = True
        await emit("read", 52, f"Persona applied: {persona_id}", "INFO")

    write_bootstrap_meta(artifact_dir, bootstrap_meta)
    main_model = resolve_main_model(config)
    bootstrap_meta["reader_model"] = main_model
    write_bootstrap_meta(artifact_dir, bootstrap_meta)

    try:
        reader_agent = reader_agent_cls(model_name=main_model, persona_hint=persona_hint)
    except TypeError:
        reader_agent = reader_agent_cls()

    claim_set = reader_agent.analyze(doc_artifact)
    if not claim_set:
        raise Exception("Reader Agent failed to produce claims")

    claim_set = resolve_claimset_evidence(claim_set, index_artifact)

    write_artifact_model(artifact_dir, "claimset.json", claim_set)
    bootstrap_meta["artifact_claimset_written"] = True
    update_claimset_readiness(bootstrap_meta, paper_id, len(claim_set.claims))
    write_bootstrap_meta(artifact_dir, bootstrap_meta)
    await emit("read", 75, f"Extracted {len(claim_set.claims)} claims", "INFO")
    return claim_set, reader_agent


async def run_verify_stage(
    *,
    job_id: str,
    doc_artifact: Any,
    claim_set: Any,
    artifact_dir: Path,
    bootstrap_meta: dict[str, Any],
    emit: Callable[[str, int, str, str], Awaitable[Any]],
    is_cancelled: Callable[[], Awaitable[bool]],
    write_artifact_model: Callable[[Path, str, Any], None],
    write_bootstrap_meta: Callable[[Path, dict[str, Any]], None],
    stats_agent_cls: Any,
    stats_profile: str = "default",
    stats_schema_version: str = "1.0",
    stats_cache_dir: Path | None = None,
) -> dict[str, Any]:
    if await is_cancelled():
        return {"cancelled": True, "stats_report": None}

    await emit("verify", 80, "Stats Verification Agent running...", "INFO")
    cache_key, paper_hash = build_stats_cache_key(
        doc_artifact=doc_artifact,
        claim_set=claim_set,
        stats_profile=stats_profile,
        schema_version=stats_schema_version,
    )
    cache_root = stats_cache_dir or Path("storage/stats_cache")
    cached_report, cache_path = load_cached_stats_report(cache_root, cache_key)
    bootstrap_meta["stats_cache_key"] = cache_key
    bootstrap_meta["stats_cache_path"] = str(cache_path)
    bootstrap_meta["stats_paper_hash"] = paper_hash

    if cached_report is not None:
        write_artifact_model(artifact_dir, "stats_report.json", cached_report)
        bootstrap_meta["verifier_status"] = "cache_hit"
        bootstrap_meta["stats_cache_hit"] = True
        bootstrap_meta["stats_report_written"] = True
        bootstrap_meta["artifact_stats_written"] = True
        write_bootstrap_meta(artifact_dir, bootstrap_meta)
        await emit("verify", 95, "Stats cache hit; reused previous report", "INFO")
        return {"cancelled": False, "stats_report": cached_report}

    try:
        stats_agent = stats_agent_cls()
        stats_report = stats_agent.run(job_id=job_id, doc=doc_artifact, claims=claim_set)
        save_cached_stats_report(cache_root, cache_key, stats_report)
        write_artifact_model(artifact_dir, "stats_report.json", stats_report)
        bootstrap_meta["verifier_status"] = "completed"
        bootstrap_meta["stats_cache_hit"] = False
        bootstrap_meta["stats_report_written"] = True
        bootstrap_meta["artifact_stats_written"] = True
        write_bootstrap_meta(artifact_dir, bootstrap_meta)
        await emit("verify", 95, f"Verified {len(stats_report.checks)} checks", "INFO")
        return {"cancelled": False, "stats_report": stats_report}
    except Exception as exc:
        logger.error("Verification Failed: %s", exc)
        bootstrap_meta["verifier_status"] = "failed"
        bootstrap_meta["stats_cache_hit"] = False
        write_bootstrap_meta(artifact_dir, bootstrap_meta)
        await emit("verify", 85, f"Verification failed: {str(exc)}", "WARNING")
        return {"cancelled": False, "stats_report": None}
