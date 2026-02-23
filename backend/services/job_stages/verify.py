from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Awaitable, Callable

from backend.services.stats_runtime import (
    build_stats_cache_key,
    load_cached_stats_report,
    save_cached_stats_report,
)


logger = logging.getLogger("paperpipe.backend")


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
