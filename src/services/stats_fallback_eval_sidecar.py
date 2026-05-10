from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.schemas.agent_artifacts import StatsReport
from src.schemas.stats_fallback_eval import (
    StatsFallbackEvalCheckEntry,
    StatsFallbackEvalMetrics,
    StatsFallbackEvalSidecar,
)
from src.skills.storage import atomic_write_text

_AUTO_FALLBACK_PREFIX = "auto_fallback_"


def build_stats_fallback_eval_sidecar(
    *,
    paper_id: str,
    stats_report: StatsReport,
    bootstrap_meta: dict[str, Any] | None = None,
) -> StatsFallbackEvalSidecar:
    meta = bootstrap_meta or {}
    check_entries = [_build_check_entry(check, meta=meta) for check in stats_report.checks]
    metrics = StatsFallbackEvalMetrics(
        check_count=len(check_entries),
        verified_count=sum(1 for entry in check_entries if entry.verdict == "verified"),
        partially_verified_count=sum(1 for entry in check_entries if entry.verdict == "partially_verified"),
        inconsistent_count=sum(1 for entry in check_entries if entry.verdict == "inconsistent"),
        unverifiable_count=sum(1 for entry in check_entries if entry.verdict == "unverifiable"),
        auto_fallback_count=sum(1 for entry in check_entries if entry.auto_fallback),
        no_table_count=sum(1 for entry in check_entries if entry.fallback_reason == "no_table_data"),
        no_api_context_count=sum(1 for entry in check_entries if entry.fallback_reason == "NO_API_CONTEXT"),
        degenerate_table_shape_count=sum(
            1 for entry in check_entries if entry.fallback_reason == "degenerate_table_shape"
        ),
        no_extractable_stats_count=sum(
            1 for entry in check_entries if entry.fallback_reason == "no_extractable_stats"
        ),
        no_executable_verification_count=sum(
            1 for entry in check_entries if entry.fallback_reason == "no_executable_verification"
        ),
        unspecified_unverifiable_count=sum(
            1 for entry in check_entries if entry.fallback_reason == "UNSPECIFIED_UNVERIFIABLE"
        ),
    )
    return StatsFallbackEvalSidecar(
        generated_at=datetime.now(timezone.utc),
        paper_id=paper_id,
        doc_id=stats_report.doc_id,
        run_id=stats_report.run_id,
        table_extraction_pass=str(meta.get("table_extraction_pass") or "pass1"),
        table_failure_taxonomy=[str(code) for code in (meta.get("table_failure_taxonomy") or [])],
        fallback_used=bool(meta.get("fallback_used", False)),
        fallback_pages=[int(p) for p in (meta.get("fallback_pages") or []) if str(p).strip()],
        checks=check_entries,
        metrics=metrics,
    )


def write_stats_fallback_eval_sidecar(sidecar: StatsFallbackEvalSidecar, artifact_dir: Path) -> Path:
    path = artifact_dir / "stats_fallback_eval.json"
    atomic_write_text(path, sidecar.model_dump_json(indent=2))
    return path


def _build_check_entry(check: Any, *, meta: dict[str, Any]) -> StatsFallbackEvalCheckEntry:
    raw_verdict = getattr(check, "verdict", "")
    verdict = str(getattr(raw_verdict, "value", raw_verdict) or "").strip().lower()
    method = str(getattr(check, "method", "") or "").strip() or None
    notes = str(getattr(check, "notes", "") or "").strip() or None
    fallback_reason = _infer_fallback_reason(verdict=verdict, method=method, notes=notes, meta=meta)
    return StatsFallbackEvalCheckEntry(
        check_id=str(getattr(check, "check_id", "") or "unknown_check"),
        verdict=verdict or "unknown",
        method=method,
        notes=notes,
        auto_fallback=bool(method == "auto_fallback" or (notes or "").startswith(_AUTO_FALLBACK_PREFIX)),
        fallback_reason=fallback_reason,
    )


def _infer_fallback_reason(*, verdict: str, method: str | None, notes: str | None, meta: dict[str, Any]) -> str | None:
    if notes == "no_table_data" or method == "no_table_data":
        return "no_table_data"
    if notes and notes.startswith(_AUTO_FALLBACK_PREFIX):
        return notes[len(_AUTO_FALLBACK_PREFIX) :] or "auto_fallback_unspecified"
    if verdict == "unverifiable":
        anchor_verify_api = meta.get("anchor_verify_api") if isinstance(meta.get("anchor_verify_api"), dict) else {}
        reason_codes = {
            str(code).strip().upper()
            for code in (anchor_verify_api.get("reason_codes") or [])
            if str(code).strip()
        }
        anchor_verify_summary = meta.get("anchor_verify_summary") if isinstance(meta.get("anchor_verify_summary"), dict) else {}
        no_api_count = int(anchor_verify_summary.get("no_api") or 0)
        if "NO_API" in reason_codes or no_api_count > 0:
            return "NO_API_CONTEXT"
        if notes:
            return notes
        return "UNSPECIFIED_UNVERIFIABLE"
    return None
