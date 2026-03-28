import asyncio
import uuid
import json
import logging
import traceback
import csv
import sqlite3
import hashlib
import shutil
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any, Callable, Awaitable, Optional, List

from src.config import load_config
from src.db_utils import get_db_connection
from src.agents.ingest_agent import IngestAgent
from src.agents.indexer_agent import IndexerAgent
from src.agents.reader_agent import ReaderAgent
from src.agents.stats_agent import StatsVerificationAgent
from src.profiles.profile_store import DEFAULT_PROFILE_PATH, load_profiles
from src.services.citation_grounding import resolve_claimset_grounding
from src.services.deepread_note_writer import (
    build_deepread_markdown,
    build_stats_markdown,
    upsert_deepread_section,
)
from src.services.deepread_state_projection import promote_deepread_structured_state_for_note
from src.services.reader_eval_sidecar import build_reader_eval_sidecar, write_reader_eval_sidecar
from src.agents.feedback_retriever import FeedbackRetriever
from src.quality.claimset_policy import enforce_claimset_evidence_policy
from src.timeout_policy import (
    default_reader_timeout_base_seconds,
    estimate_reader_timeout_seconds,
    is_timeout_exception,
    time_limit,
)
from src.verify import resolve_anchor_api_context

logger = logging.getLogger("paperpipe.backend")

# Global Job Queue Registry (In-Memory PubSub)
JOB_QUEUES: Dict[str, asyncio.Queue] = {}
FEEDBACK_FILE = Path("storage/feedback.jsonl")
REVIEW_NEEDS_READER = "NEEDS_READER"


def _resolve_pdf_path_from_db(paper_id: str) -> Optional[Path]:
    """
    Resolve pdf_path using DB first so canonical paper_id changes
    (e.g., zotero:/doi:) do not break local file discovery.
    """
    conn = None
    try:
        conn = get_db_connection()
        conn.row_factory = sqlite3.Row
        aliases = [paper_id]
        if ":" in paper_id:
            aliases.append(paper_id.split(":", 1)[1])
        seen: set[str] = set()
        for alias in aliases:
            alias = str(alias or "").strip()
            if not alias or alias in seen:
                continue
            seen.add(alias)
            row = conn.execute(
                "SELECT pdf_path FROM papers WHERE paper_id = ? LIMIT 1",
                (alias,),
            ).fetchone()
            if not row:
                continue
            raw = str(row["pdf_path"] or "").strip()
            if not raw:
                continue
            candidate = Path(raw).expanduser()
            if candidate.exists():
                return candidate

        if paper_id.startswith("doi:"):
            doi = paper_id.split(":", 1)[1]
            row = conn.execute(
                "SELECT pdf_path FROM papers WHERE lower(coalesce(doi, '')) = lower(?) LIMIT 1",
                (doi,),
            ).fetchone()
            if row:
                raw = str(row["pdf_path"] or "").strip()
                if raw:
                    candidate = Path(raw).expanduser()
                    if candidate.exists():
                        return candidate
    except Exception as exc:
        logger.debug("DB pdf_path lookup failed for %s: %s", paper_id, exc)
    finally:
        if conn is not None:
            conn.close()
    return None


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


def _resolve_ingest_parser_backend(config, override_backend: str | None = None) -> str:
    ingest = getattr(config, "ingest", None)
    configured_backend = str(
        getattr(ingest, "parser_backend", "fitz_pdfplumber") or "fitz_pdfplumber"
    ).strip().lower()
    enable_docling = bool(getattr(ingest, "enable_docling", False))
    allowed_backends = {"fitz_pdfplumber", "docling"}
    if configured_backend not in allowed_backends:
        logger.warning(
            "Unknown ingest parser backend in config: %s. Falling back to fitz_pdfplumber.",
            configured_backend,
        )
        configured_backend = "fitz_pdfplumber"
    requested_backend = str(override_backend or "").strip().lower() or configured_backend
    if requested_backend not in allowed_backends:
        logger.warning(
            "Unknown ingest parser backend override: %s. Falling back to configured backend %s.",
            requested_backend,
            configured_backend,
        )
        requested_backend = configured_backend
    if requested_backend == "docling" and not enable_docling:
        logger.info("Docling parser backend requested but enable_docling=false. Falling back to fitz_pdfplumber.")
        return "fitz_pdfplumber"
    return requested_backend


def _resolve_ingest_runtime_options(config) -> Dict[str, Any]:
    ingest = getattr(config, "ingest", None)
    return {
        "enable_ocr_fallback": bool(getattr(ingest, "enable_ocr_fallback", False)),
        "ocr_lang": str(getattr(ingest, "ocr_lang", "eng") or "eng"),
        "ocr_min_text_chars": int(getattr(ingest, "ocr_min_text_chars", 200)),
        "enable_table_pass2_ocr": bool(getattr(ingest, "enable_table_pass2_ocr", False)),
        "enable_cloud_table_fallback": bool(getattr(ingest, "enable_cloud_table_fallback", False)),
        "cloud_table_page_budget": int(getattr(ingest, "cloud_table_page_budget", 2)),
        "cloud_table_model": str(getattr(ingest, "cloud_table_model", "gpt-4o-mini") or "gpt-4o-mini"),
        "cloud_table_base_url": getattr(ingest, "cloud_table_base_url", None),
        "cloud_table_api_key": getattr(ingest, "cloud_table_api_key", None),
        "cloud_table_timeout_seconds": int(getattr(ingest, "cloud_table_timeout_seconds", 30)),
    }


def _write_bootstrap_meta(artifact_dir: Path, payload: Dict[str, Any]) -> None:
    try:
        with open(artifact_dir / "bootstrap_meta.json", "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
    except Exception as exc:
        logger.warning("Failed to write bootstrap_meta.json: %s", exc)


def _write_run_meta(artifact_dir: Path, payload: Dict[str, Any]) -> None:
    try:
        with open(artifact_dir / "run_meta.json", "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
    except Exception as exc:
        logger.warning("Failed to write run_meta.json: %s", exc)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _snapshot_copy(source: Path, target: Path) -> Optional[str]:
    if not source.exists():
        return None
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        return str(target)
    except Exception as exc:
        logger.warning("Snapshot copy failed (%s -> %s): %s", source, target, exc)
        return None


def _collect_llm_params(config: Any) -> Dict[str, Any]:
    llm = getattr(config, "llm", None)
    local = getattr(llm, "local", None) if llm is not None else None
    cloud = getattr(llm, "cloud", None) if llm is not None else None
    return {
        "mode": getattr(llm, "mode", None),
        "timeout_seconds": getattr(llm, "timeout_seconds", None),
        "max_retries": getattr(llm, "max_retries", None),
        "provider_local": getattr(local, "provider", None) if local is not None else None,
        "provider_cloud": getattr(cloud, "provider", None) if cloud is not None else None,
    }


def _collect_embed_params(config: Any) -> Dict[str, Any]:
    llm = getattr(config, "llm", None)
    local = getattr(llm, "local", None) if llm is not None else None
    models = getattr(local, "models", None) if local is not None else None
    embed_model = models.get("embedder") if isinstance(models, dict) else None
    return {
        "chunking": None,
        "embed_model": embed_model,
    }


def _extract_doc_doi_hint(doc: Any) -> Optional[str]:
    meta = getattr(doc, "meta", None)
    if meta is not None:
        doi = str(getattr(meta, "doi", "") or "").strip()
        if doi:
            return doi
    metadata = getattr(doc, "metadata", None)
    if metadata is not None:
        doi = str(getattr(metadata, "doi", "") or "").strip()
        if doi:
            return doi
    return None


def _extract_doc_source_ref(doc: Any) -> Optional[str]:
    meta = getattr(doc, "meta", None)
    if meta is not None:
        source_ref = str(getattr(meta, "source_ref", "") or "").strip()
        if source_ref:
            return source_ref
    source = getattr(doc, "source", None)
    if source is not None:
        ref = str(getattr(source, "ref", "") or "").strip()
        if ref:
            return ref
    return None


def _build_anchor_verify_summary(stats_report: Any) -> Dict[str, int]:
    summary = {"pass": 0, "warn": 0, "fail": 0, "no_api": 0}
    checks = getattr(stats_report, "checks", None)
    if not isinstance(checks, list):
        return summary

    for check in checks:
        verdict = _normalize_verdict(getattr(check, "verdict", ""))
        if verdict == "verified":
            summary["pass"] += 1
        elif verdict == "inconsistent":
            summary["fail"] += 1
        elif verdict == "unverifiable":
            summary["no_api"] += 1
        elif verdict:
            summary["warn"] += 1
    return summary


def _map_verdict_to_anchor_result(verdict: str) -> str:
    v = _normalize_verdict(verdict)
    if v == "verified":
        return "PASS"
    if v == "inconsistent":
        return "FAIL"
    if v == "unverifiable":
        return "NO_API"
    if v:
        return "WARN"
    return "WARN"


def _map_verdict_reason_codes(verdict: Any) -> List[str]:
    v = _normalize_verdict(verdict)
    if v == "verified":
        return ["VERDICT_VERIFIED"]
    if v == "partially_verified":
        return ["VERDICT_PARTIALLY_VERIFIED"]
    if v == "inconsistent":
        return ["VERDICT_INCONSISTENT"]
    if v == "unverifiable":
        return ["VERDICT_UNVERIFIABLE", "NO_API"]
    if v:
        return [f"VERDICT_{v.upper()}"]
    return ["VERDICT_UNKNOWN"]


def _normalize_verdict(verdict: Any) -> str:
    if verdict is None:
        return ""
    value = getattr(verdict, "value", verdict)
    return str(value or "").strip().lower()


def _resolve_verify_failure_api_context(error_text: str) -> Dict[str, Any]:
    msg = str(error_text or "").lower()
    reason_codes: List[str] = ["NO_API"]
    status = "unavailable"
    provider = "none"
    if "docker" in msg or "connection refused" in msg or "api version" in msg:
        reason_codes.insert(0, "DOCKER_UNAVAILABLE")
        status = "docker_unavailable"
    elif "timeout" in msg:
        reason_codes.insert(0, "VERIFY_TIMEOUT")
    else:
        reason_codes.insert(0, "VERIFY_ERROR")
    return {"provider": provider, "status": status, "reason_codes": reason_codes}


def _build_anchor_verify_log_entries(
    run_id: str,
    doc_id: str,
    stats_report: Any,
    api_provider: str = "stats_sandbox",
    api_reason_codes: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    entries: List[Dict[str, Any]] = []
    checks = getattr(stats_report, "checks", None)
    if not isinstance(checks, list):
        return entries

    for check in checks:
        verdict_raw = getattr(check, "verdict", "")
        verdict = _normalize_verdict(verdict_raw)
        evidence_list = getattr(check, "evidence", None)
        first_span = evidence_list[0] if isinstance(evidence_list, list) and evidence_list else None
        span_get = lambda key, default=None: getattr(first_span, key, default) if first_span is not None else default
        normalized_value = (
            getattr(check, "computed_p", None)
            if getattr(check, "computed_p", None) is not None
            else getattr(check, "reported_p", None)
        )
        if normalized_value is None:
            normalized_value = getattr(check, "reported_stat", None)

        bbox_ref = {
            "page": span_get("page", None),
            "bbox_pdf": span_get("bbox_pdf", None),
            "bbox_pct": span_get("bbox_pct", None),
            "table_id": span_get("table_id", None),
            "cell_id": span_get("cell_id", None),
            "source_span": span_get("source_span", None),
            "char_start": span_get("char_start", None),
            "char_end": span_get("char_end", None),
        }
        reason_codes = list(_map_verdict_reason_codes(verdict))
        for code in api_reason_codes or []:
            code_text = str(code or "").strip().upper()
            if code_text:
                reason_codes.append(code_text)

        entries.append(
            {
                "run_id": run_id,
                "doc_id": doc_id,
                "anchor_id": str(getattr(check, "check_id", "") or ""),
                "normalized_value": normalized_value,
                "bbox_ref": bbox_ref,
                "api_provider": str(api_provider or "stats_sandbox"),
                "result": _map_verdict_to_anchor_result(verdict),
                "reason_codes": sorted(set(reason_codes)),
            }
        )
    return entries


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

async def run_deepread_job(
    job_id: str,
    paper_id: str,
    persona_id: str = "default",
    reasoning_persona: str | None = None,
    profile_id: str | None = None,
    parser_backend: str | None = None,
    run_verify: bool = False,
    clean_reindex: bool = False,
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
    run_meta: Optional[Dict[str, Any]] = None

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

    def _mark_run_meta(status: str, **extra: Any) -> None:
        if artifact_dir is None or run_meta is None:
            return
        run_meta["status"] = status
        run_meta["updated_at"] = datetime.now(timezone.utc).isoformat()
        if status in {"succeeded", "failed", "cancelled"}:
            run_meta["finished_at"] = run_meta["updated_at"]
        run_meta.update(extra)
        _write_run_meta(artifact_dir, run_meta)

    try:
        if await is_cancelled():
            return {"status": "cancelled", "run_id": run_id}

        await emit("init", 0, f"Starting Deep Read for {paper_id}")
        
        config = load_config()
        
        # 1. Locate PDF
        # Try finding locally in Library first (Mocking DB lookup for now if needed, or using direct path if we have it)
        # For this MVP, let's assume paper_id is a citekey or we can find it in library
        await emit("init", 5, "Locating PDF...")
        
        pdf_path = _resolve_pdf_path_from_db(paper_id)
        if pdf_path:
            logger.info(f"✅ Found PDF from DB path: {pdf_path}")

        # Simple heuristic: Look in Library root or subdirs
        if not pdf_path:
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

        snapshots_dir = artifact_dir / "snapshots"
        snapshots_dir.mkdir(parents=True, exist_ok=True)
        run_meta = {
            "job_id": job_id,
            "run_id": run_id,
            "paper_id": paper_id,
            "persona_id": persona_id,
            "run_verify": bool(run_verify),
            "clean_reindex_requested": bool(clean_reindex),
            "pdf_path": str(pdf_path),
            "pdf_sha256": _sha256_file(pdf_path),
            "pdf_mtime": datetime.fromtimestamp(pdf_path.stat().st_mtime, timezone.utc).isoformat(),
            "config_snapshot": _snapshot_copy(Path("config.yaml"), snapshots_dir / "config.yaml"),
            "prompts_snapshot": _snapshot_copy(DEFAULT_PROFILE_PATH, snapshots_dir / "profiles.yaml"),
            "models_used": {"reader": None, "verifier": None},
            "parser_backend": None,
            "llm_params": _collect_llm_params(config),
            "embed_params": _collect_embed_params(config),
            "tool_policy_version": "v1",
            "anchor_verify_api": {"provider": "none", "status": "not_run", "reason_codes": []},
            "status": "running",
            "started_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        _write_run_meta(artifact_dir, run_meta)

        bootstrap_meta = {
            "job_id": job_id,
            "run_id": run_id,
            "paper_id": paper_id,
            "persona_id": persona_id,
            "persona_applied": False,
            "similar_feedback_count": 0,
            "similar_feedback_paper_ids": [],
            "run_verify": bool(run_verify),
            "clean_reindex_requested": bool(clean_reindex),
            "clean_reindex_applied": False,
            "clean_reindex_removed_chunks": 0,
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
            "parser_backend": None,
            "table_extraction_pass": "pass1",
            "table_failure_taxonomy": [],
            "fallback_used": False,
            "fallback_pages": [],
            "anchor_verify_summary": {"pass": 0, "warn": 0, "fail": 0, "no_api": 0},
            "anchor_verify_api": {"provider": "none", "status": "not_run", "reason_codes": []},
            "table_pass2_enabled": False,
            "table_pass3_enabled": False,
            "table_page_budget": 0,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        _write_bootstrap_meta(artifact_dir, bootstrap_meta)
        
        # 2. Ingest
        if await is_cancelled():
            _mark_run_meta("cancelled")
            return {"status": "cancelled", "run_id": run_id}
        logger.info(f"Starting Ingest for {pdf_path.name}")
        await emit("ingest", 10, f"Ingesting PDF: {pdf_path.name}")
        parser_backend = _resolve_ingest_parser_backend(config, override_backend=parser_backend)
        ingest_runtime_options = _resolve_ingest_runtime_options(config)
        bootstrap_meta["parser_backend"] = parser_backend
        bootstrap_meta["table_pass2_enabled"] = bool(ingest_runtime_options.get("enable_table_pass2_ocr", False))
        bootstrap_meta["table_pass3_enabled"] = bool(ingest_runtime_options.get("enable_cloud_table_fallback", False))
        bootstrap_meta["table_page_budget"] = int(ingest_runtime_options.get("cloud_table_page_budget", 0))
        _write_bootstrap_meta(artifact_dir, bootstrap_meta)
        if run_meta is not None:
            run_meta["parser_backend"] = parser_backend
            run_meta["ingest_options"] = dict(ingest_runtime_options)
            run_meta["updated_at"] = datetime.now(timezone.utc).isoformat()
            _write_run_meta(artifact_dir, run_meta)

        try:
            ingest_agent = IngestAgent(parser_backend=parser_backend, **ingest_runtime_options)
        except TypeError:
            # Test doubles may expose a simplified constructor.
            ingest_agent = IngestAgent()
        doc_artifact = ingest_agent.process_v2(str(pdf_path))
        
        if not doc_artifact:
             raise Exception("Ingestion failed to produce artifact")

        ingest_meta = getattr(ingest_agent, "last_table_extraction_meta", {}) or {}
        bootstrap_meta["table_extraction_pass"] = str(ingest_meta.get("table_extraction_pass") or "pass1")
        taxonomy = ingest_meta.get("table_failure_taxonomy")
        bootstrap_meta["table_failure_taxonomy"] = taxonomy if isinstance(taxonomy, list) else []
        bootstrap_meta["fallback_used"] = bool(ingest_meta.get("fallback_used", False))
        fallback_pages = ingest_meta.get("fallback_pages")
        bootstrap_meta["fallback_pages"] = fallback_pages if isinstance(fallback_pages, list) else []
        _write_bootstrap_meta(artifact_dir, bootstrap_meta)
        if run_meta is not None:
            run_meta["table_extraction"] = {
                "pass": bootstrap_meta["table_extraction_pass"],
                "failure_taxonomy": bootstrap_meta["table_failure_taxonomy"],
                "fallback_used": bootstrap_meta["fallback_used"],
                "fallback_pages": bootstrap_meta["fallback_pages"],
            }
            run_meta["updated_at"] = datetime.now(timezone.utc).isoformat()
            _write_run_meta(artifact_dir, run_meta)

        # Save Document Artifact
        with open(artifact_dir / "document_artifact.json", "w") as f:
            f.write(doc_artifact.model_dump_json(indent=2))
        bootstrap_meta["artifact_document_written"] = True
        _write_bootstrap_meta(artifact_dir, bootstrap_meta)
            
        await emit("ingest", 25, f"Ingested {len(doc_artifact.pages)} pages")

        # 3. Index
        if await is_cancelled():
            _mark_run_meta("cancelled")
            return {"status": "cancelled", "run_id": run_id}
        await emit("index", 30, "Indexing content...")
        indexer_agent = IndexerAgent()
        if clean_reindex:
            doc_id = str(getattr(doc_artifact, "document_id", "") or getattr(doc_artifact, "doc_id", "") or paper_id)
            if hasattr(indexer_agent, "reset_doc_index"):
                removed = int(indexer_agent.reset_doc_index(doc_id))
                bootstrap_meta["clean_reindex_applied"] = True
                bootstrap_meta["clean_reindex_removed_chunks"] = removed
                _write_bootstrap_meta(artifact_dir, bootstrap_meta)
                await emit("index", 33, f"Clean reindex applied: removed {removed} chunks")
            else:
                await emit("index", 33, "Clean reindex requested but index reset hook unavailable", level="WARNING")
        index_artifact = indexer_agent.process(doc_artifact)
        
        # Save Index Artifact
        with open(artifact_dir / "index_artifact.json", "w") as f:
             f.write(index_artifact.model_dump_json(indent=2))
        bootstrap_meta["artifact_index_written"] = True
        _write_bootstrap_meta(artifact_dir, bootstrap_meta)
             
        await emit("index", 45, f"Indexed {index_artifact.chunk_count} chunks")

        # 4. Read (Claim Extraction)
        if await is_cancelled():
            _mark_run_meta("cancelled")
            return {"status": "cancelled", "run_id": run_id}
        await emit("read", 50, "Reader Agent analyzing...")
        persona_hint = _resolve_persona_hint(persona_id)

        # Dynamic Few-Shot Injection based on persona
        feedback_query_text = persona_hint if persona_hint else paper_id
        similar_feedback = _load_similar_feedback_top3(query_text=feedback_query_text, limit=3)
        
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
        if run_meta is not None:
            run_meta["models_used"]["reader"] = main_model
            run_meta["updated_at"] = datetime.now(timezone.utc).isoformat()
            _write_run_meta(artifact_dir, run_meta)
        llm_conf = getattr(config, "llm", None)
        page_count = len(getattr(doc_artifact, "pages", []) or [])
        table_count = len(getattr(doc_artifact, "tables", []) or [])
        llm_timeout_default = max(15, int(getattr(llm_conf, "timeout_seconds", 15) or 15))
        reader_timeout_base = default_reader_timeout_base_seconds(llm_timeout_default)
        reader_timeout_budget = estimate_reader_timeout_seconds(
            reader_timeout_base,
            page_count=page_count,
            table_count=table_count,
            adaptive=True,
        )
        bootstrap_meta["reader_timeout_base_sec"] = reader_timeout_base
        bootstrap_meta["reader_timeout_budget_sec"] = reader_timeout_budget
        bootstrap_meta["reader_timeout_adaptive"] = True
        bootstrap_meta["reader_page_count"] = page_count
        bootstrap_meta["reader_table_count"] = table_count
        bootstrap_meta["reader_timeout_triggered"] = False
        bootstrap_meta["reader_timeout_error_type"] = None
        bootstrap_meta["reader_provider_timeout_override_applied"] = False
        _write_bootstrap_meta(artifact_dir, bootstrap_meta)
        if run_meta is not None:
            run_meta["reader_timeout_base_sec"] = reader_timeout_base
            run_meta["reader_timeout_budget_sec"] = reader_timeout_budget
            run_meta["reader_timeout_adaptive"] = True
            run_meta["reader_page_count"] = page_count
            run_meta["reader_table_count"] = table_count
            run_meta["reader_timeout_triggered"] = False
            run_meta["reader_timeout_error_type"] = None
            run_meta["reader_provider_timeout_override_applied"] = False
            run_meta["updated_at"] = datetime.now(timezone.utc).isoformat()
            _write_run_meta(artifact_dir, run_meta)
        try:
            reader_agent = ReaderAgent(
                model_name=main_model,
                persona_hint=persona_hint,
            )
        except TypeError:
            # Test doubles may expose a simplified constructor.
            reader_agent = ReaderAgent()
        try:
            with time_limit(int(reader_timeout_budget)):
                claim_set = reader_agent.analyze(doc_artifact)
        except Exception as exc:
            if not is_timeout_exception(exc):
                raise
            timeout_message = (
                f"Reader step timed out after {reader_timeout_budget}s "
                f"(pages={page_count}, tables={table_count})"
            )
            bootstrap_meta["reader_timeout_triggered"] = True
            bootstrap_meta["reader_timeout_error_type"] = type(exc).__name__
            _write_bootstrap_meta(artifact_dir, bootstrap_meta)
            if run_meta is not None:
                run_meta["reader_timeout_triggered"] = True
                run_meta["reader_timeout_error_type"] = type(exc).__name__
                run_meta["updated_at"] = datetime.now(timezone.utc).isoformat()
                _write_run_meta(artifact_dir, run_meta)
            await emit("read", 55, timeout_message, level="ERROR")
            raise TimeoutError(timeout_message) from exc
        
        if not claim_set:
             raise Exception("Reader Agent failed to produce claims")
        claim_set = enforce_claimset_evidence_policy(claim_set)
        resolved_claim_set = resolve_claimset_grounding(claim_set, index_artifact)
             
        # Save ClaimSet
        with open(artifact_dir / "claimset.json", "w") as f:
            f.write(claim_set.model_dump_json(indent=2))
        with open(artifact_dir / "claimset.resolved.json", "w") as f:
            f.write(resolved_claim_set.model_dump_json(indent=2))
        bootstrap_meta["artifact_claimset_written"] = True
        bootstrap_meta["artifact_claimset_resolved_written"] = True
        bootstrap_meta["artifact_reader_eval_written"] = False
        claim_count = len(claim_set.claims)
        bootstrap_meta["claimset_claim_count"] = claim_count
        bootstrap_meta["claimset_grounded_span_count"] = sum(
            1
            for claim in resolved_claim_set.claims
            for span in claim.evidence_spans
            if span.grounded is True
        )
        bootstrap_meta["claimset_unresolved_span_count"] = sum(
            1
            for claim in resolved_claim_set.claims
            for span in claim.evidence_spans
            if span.grounded is False
        )
        try:
            reader_eval = build_reader_eval_sidecar(
                paper_id=paper_id,
                run_id=run_id,
                claimset=claim_set,
                resolved_claimset=resolved_claim_set,
                index_artifact=index_artifact,
            )
            write_reader_eval_sidecar(reader_eval, artifact_dir)
            bootstrap_meta["artifact_reader_eval_written"] = True
            bootstrap_meta["reader_eval_claim_count"] = reader_eval.metrics.claim_count
            bootstrap_meta["reader_eval_supported_claim_count"] = reader_eval.metrics.supported_claim_count
            bootstrap_meta["reader_eval_unsupported_claim_count"] = reader_eval.metrics.unsupported_claim_count
            bootstrap_meta["reader_eval_heuristic_backfill_claim_count"] = (
                reader_eval.metrics.heuristic_backfill_claim_count
            )
        except Exception as exc:
            logger.warning("Failed to build reader_eval sidecar: %s", exc)
        if claim_count > 0:
            bootstrap_meta["claimset_readiness"] = "ready"
            bootstrap_meta["claimset_ready"] = True
            bootstrap_meta["claimset_readiness_reason"] = "claims_present"
            bootstrap_meta["claimset_readiness_badge"] = "READY"
            bootstrap_meta["claimset_ops_action"] = "none"
            bootstrap_meta["claimset_ops_alert"] = False
            bootstrap_meta["claimset_ops_note"] = "ready"
        else:
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
        _write_bootstrap_meta(artifact_dir, bootstrap_meta)
            
        await emit("read", 75, f"Extracted {len(claim_set.claims)} claims")

        # 5. Verify (Optional)
        if run_verify:
            if await is_cancelled():
                _mark_run_meta("cancelled")
                return {"status": "cancelled", "run_id": run_id}
            await emit("verify", 80, "Stats Verification Agent running...")
            try:
                stats_agent = StatsVerificationAgent()
                if run_meta is not None:
                    run_meta["models_used"]["verifier"] = stats_agent.__class__.__name__
                    run_meta["updated_at"] = datetime.now(timezone.utc).isoformat()
                    _write_run_meta(artifact_dir, run_meta)
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
                bootstrap_meta["anchor_verify_summary"] = _build_anchor_verify_summary(stats_report)
                anchor_api_context = resolve_anchor_api_context(
                    getattr(stats_report, "doc_id", None),
                    doi_hint=_extract_doc_doi_hint(doc_artifact),
                    source_ref=_extract_doc_source_ref(doc_artifact),
                    id_hint=paper_id,
                )
                bootstrap_meta["anchor_verify_api"] = anchor_api_context
                _write_bootstrap_meta(artifact_dir, bootstrap_meta)
                if run_meta is not None:
                    run_meta["verification_status"] = "completed"
                    run_meta["anchor_verify_summary"] = bootstrap_meta["anchor_verify_summary"]
                    run_meta["anchor_verify_api"] = anchor_api_context
                    run_meta["anchor_verify_log"] = _build_anchor_verify_log_entries(
                        run_id=run_id,
                        doc_id=str(getattr(stats_report, "doc_id", "") or paper_id),
                        stats_report=stats_report,
                        api_provider=str(anchor_api_context.get("provider") or "stats_sandbox"),
                        api_reason_codes=list(anchor_api_context.get("reason_codes") or []),
                    )
                    run_meta["updated_at"] = datetime.now(timezone.utc).isoformat()
                    _write_run_meta(artifact_dir, run_meta)
                    
                await emit("verify", 95, f"Verified {len(stats_report.checks)} checks")
                
            except Exception as e:
                logger.error(f"Verification Failed: {e}")
                bootstrap_meta["verifier_status"] = "failed"
                bootstrap_meta["anchor_verify_summary"] = {"pass": 0, "warn": 0, "fail": 0, "no_api": 0}
                bootstrap_meta["anchor_verify_api"] = _resolve_verify_failure_api_context(str(e))
                _write_bootstrap_meta(artifact_dir, bootstrap_meta)
                if run_meta is not None:
                    run_meta["verification_status"] = "failed"
                    run_meta["verification_error"] = str(e)
                    run_meta["anchor_verify_summary"] = {"pass": 0, "warn": 0, "fail": 0, "no_api": 0}
                    run_meta["anchor_verify_api"] = dict(bootstrap_meta["anchor_verify_api"])
                    run_meta["anchor_verify_log"] = []
                    run_meta["updated_at"] = datetime.now(timezone.utc).isoformat()
                    _write_run_meta(artifact_dir, run_meta)
                await emit("verify", 85, f"Verification failed: {str(e)}", level="WARNING")

        # 6. Complete
        _mark_run_meta("succeeded")

        # Best-effort note upsert (non-fatal): keep runtime fail-safe.
        try:
            note_path = _resolve_note_path_for_paper(config, paper_id)
            if note_path:
                promotion = promote_deepread_structured_state_for_note(
                    vault_path=Path(config.paths.obsidian_vault).expanduser(),
                    note_path=note_path,
                    artifact_dir=artifact_dir,
                )
                if promotion["status"] in {"created", "refreshed"}:
                    await emit("read", 76, f"Canonical state {promotion['status']}: {note_path.stem}")
                else:
                    await emit("read", 76, f"Canonical state skipped: {promotion['reason']}")
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
        _mark_run_meta("failed", error=str(e), error_type=type(e).__name__)
        if artifact_dir is not None and bootstrap_meta is not None:
            bootstrap_meta["claimset_readiness"] = "unknown"
            bootstrap_meta["claimset_ready"] = None
            bootstrap_meta["claimset_readiness_reason"] = "runtime_error"
            bootstrap_meta["claimset_readiness_badge"] = "UNKNOWN"
            bootstrap_meta["claimset_ops_action"] = "retry_suggested"
            bootstrap_meta["claimset_ops_alert"] = True
            bootstrap_meta["claimset_ops_note"] = f"runtime_error:{type(e).__name__}"
            _write_bootstrap_meta(artifact_dir, bootstrap_meta)
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
