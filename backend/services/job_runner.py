import asyncio
import json
import logging
import csv
import sqlite3
import hashlib
import shutil
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any, Callable, Awaitable, Optional, List
from urllib.parse import unquote, urlparse

from backend.routers import paper_notes
from src.config import load_config, resolve_clinical_extraction_feature
from src.db_utils import get_db_connection
from src.agents.ingest_agent import IngestAgent
from src.agents.indexer_agent import IndexerAgent
from src.agents.reader_agent import ReaderAgent
try:
    from src.agents.stats_agent import StatsVerificationAgent
    _STATS_AGENT_IMPORT_ERROR: Exception | None = None
except Exception as exc:  # pragma: no cover - exercised in import-smoke regression test
    StatsVerificationAgent = None  # type: ignore[assignment]
    _STATS_AGENT_IMPORT_ERROR = exc
from src.contracts.artifact_views import get_artifact_header, iter_text_sections
from src.contracts.output_bridge import claim_cards_from_claimset_payload, normalize_claimset_payload
from src.contracts.document_artifact_v2 import DocumentArtifactV2
from src.llm_provider import get_llm_provider
from src.persona_modes import normalize_persona_selection, resolve_reasoning_persona_hint
from src.profiles.profile_store import load_profiles
from src.schemas.core import BiomedicalClinicalExtraction
from src.schemas.skills import build_section_signal_summary
from src.services.event_log import log_job_event, sanitize_event_payload_for_log, sanitize_event_text_for_log
from src.services.identity import new_run_id
from src.services.citation_grounding import resolve_claimset_grounding
from src.services.deepread_note_writer import (
    build_clinical_extraction_markdown,
    build_deepread_markdown,
    build_stats_markdown,
    upsert_deepread_section,
)
from src.services.deepread_state_projection import promote_deepread_structured_state_for_note
from src.services.deepread_handoff_artifacts import write_deepread_handoff_artifacts
from src.services.evidence_extraction_sidecar import (
    build_evidence_extraction_bundle,
    write_evidence_extraction_bundle,
)
from src.services.figure_caption_sidecar import (
    build_figure_caption_sidecar,
    write_figure_caption_sidecar,
)
from src.services.visual_evidence_ledger import (
    build_visual_evidence_ledger,
    write_visual_evidence_ledger,
)
from src.services.claimset_coverage_sidecar import (
    build_claimset_coverage_sidecar,
    write_claimset_coverage_sidecar,
)
from src.services.claimset_coverage_focus_sidecar import (
    build_claimset_coverage_focus_sidecar,
    write_claimset_coverage_focus_sidecar,
)
from src.services.reader_eval_sidecar import build_reader_eval_sidecar, write_reader_eval_sidecar
from src.services.stats_fallback_eval_sidecar import (
    build_stats_fallback_eval_sidecar,
    write_stats_fallback_eval_sidecar,
)
from src.timeout_policy import (
    default_reader_timeout_base_seconds,
    estimate_reader_timeout_seconds,
    is_timeout_exception,
    time_limit,
)
from src.agents.feedback_retriever import FeedbackRetriever
from src.quality.claimset_policy import enforce_claimset_evidence_policy
from src.services.runtime_paths import artifact_run_dir, config_file_path, feedback_log_path, profiles_config_path
from src.services.performance_profile import StageTimer, summarize_stage_timings
from src.services.privacy_preflight import (
    build_privacy_preflight_response,
    privacy_preflight_should_block,
    public_external_link_or_none,
    resolve_privacy_preflight_mode,
)
from src.verify import resolve_anchor_api_context
from src.skills.storage import (
    atomic_write_text,
    resolve_note_path,
    resolve_note_slug_by_paper_id,
    resolve_vault_relative_path,
    split_frontmatter,
)

logger = logging.getLogger("paperpipe.backend")

FEEDBACK_FILE: Path | None = None
REVIEW_NEEDS_READER = "NEEDS_READER"
_INFERENCE_NONE = "none"
_INFERENCE_MIXED = "mixed"


def _feedback_file() -> Path:
    return FEEDBACK_FILE or feedback_log_path()


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


def _mark_paper_deepread_indexed(paper_id: str) -> bool:
    conn = None
    try:
        conn = get_db_connection()
        conn.row_factory = sqlite3.Row
        columns = {str(row[1]) for row in conn.execute("PRAGMA table_info(papers)").fetchall()}
        if "paper_id" not in columns or "status" not in columns:
            return False

        assignments = ["status = ?"]
        params: list[Any] = ["INDEXED"]
        now = datetime.now(timezone.utc).isoformat()
        if "processed_at" in columns:
            assignments.append("processed_at = ?")
            params.append(now)
        if "updated_at" in columns:
            assignments.append("updated_at = ?")
            params.append(now)
        params.append(paper_id)

        cursor = conn.execute(
            f"""
            UPDATE papers
            SET {', '.join(assignments)}
            WHERE paper_id = ?
              AND (status IS NULL OR status IN ('NEW', 'FETCHED', 'PDF_DOWNLOADED', 'APPROVED'))
            """,
            tuple(params),
        )
        conn.commit()
        return int(cursor.rowcount or 0) > 0
    except Exception as exc:
        logger.warning("Failed to mark paper %s as INDEXED after Deep Read: %s", paper_id, exc)
        if conn is not None:
            try:
                conn.rollback()
            except Exception:
                pass
        return False
    finally:
        if conn is not None:
            conn.close()


def _resolve_pdf_path_from_note_frontmatter(paper_id: str) -> Optional[Path]:
    try:
        vault_path = paper_notes._resolve_vault_path()
        index = paper_notes._build_index(vault_path)
        target = paper_notes._find_note_item_for_paper_id(index.items, paper_id)
        if target is None:
            return None

        note_path = vault_path / target.note_path
        if not note_path.exists():
            return None

        if target.has_runtime_source_metadata():
            frontmatter = target.build_runtime_source_frontmatter()
        else:
            content = paper_notes._safe_read_text(note_path)
            frontmatter, _ = paper_notes._parse_frontmatter(content)

        candidates: list[Path] = []
        for key in ("pdf_path", "local_pdf_path"):
            raw = str(frontmatter.get(key) or "").strip()
            if raw:
                candidates.append(Path(raw).expanduser())

        pdf_url = str(frontmatter.get("pdf_url") or "").strip()
        if pdf_url.lower().startswith("file://"):
            local_path = unquote(urlparse(pdf_url).path or "")
            if local_path:
                candidates.append(Path(local_path).expanduser())
        elif (
            pdf_url
            and not pdf_url.startswith("/papers/")
            and "://" not in pdf_url
        ):
            candidates.append(Path(pdf_url).expanduser())

        for candidate in candidates:
            if candidate.exists() and candidate.is_file():
                return candidate
    except Exception as exc:
        logger.debug("Note-backed pdf lookup failed for %s: %s", paper_id, exc)
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
                            note_path = resolve_vault_relative_path(vault_path, note_rel)
                            if note_path is not None and note_path.exists():
                                return note_path
        except Exception:
            continue
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
                "SELECT obsidian_path FROM papers WHERE paper_id = ? LIMIT 1",
                (alias,),
            ).fetchone()
            if not row:
                continue
            raw = str(row["obsidian_path"] or "").strip()
            if not raw:
                continue
            note_path = resolve_vault_relative_path(vault_path, raw)
            if note_path is None:
                continue
            if note_path.exists():
                return note_path
    except Exception as exc:
        logger.debug("DB note_path lookup failed for %s: %s", paper_id, exc)
    finally:
        if conn is not None:
            conn.close()

    try:
        note_slug = resolve_note_slug_by_paper_id(vault_path, paper_id)
        if note_slug:
            note_path = resolve_note_path(vault_path, note_slug)
            if note_path is not None and note_path.exists():
                return note_path
    except Exception as exc:
        logger.debug("Vault note_path lookup failed for %s: %s", paper_id, exc)
    return None


def _is_clinical_note(note_path: Optional[Path]) -> bool:
    if note_path is None or not note_path.exists():
        return False
    try:
        frontmatter, _body = split_frontmatter(note_path.read_text(encoding="utf-8"))
    except Exception:
        return False
    slot_value = str(frontmatter.get("slot") or "").strip().lower()
    type_value = str(frontmatter.get("type") or "").strip().lower()
    return slot_value == "clinical" or type_value in {"clinical_paper", "clinical_trial"}


def _build_biomedical_clinical_extraction_inputs(doc, paper_id: str) -> tuple[dict[str, Any], str]:
    header = get_artifact_header(doc)
    sections = list(iter_text_sections(doc))

    summary_candidates: list[str] = []
    methods_candidates: list[str] = []
    for section in sections:
        lowered = (section.name or "").strip().lower()
        text = (section.text or "").strip()
        if not text:
            continue
        if any(token in lowered for token in ("abstract", "summary", "result", "discussion", "conclusion")):
            summary_candidates.append(text)
        if any(token in lowered for token in ("method", "design", "materials", "participant", "intervention", "protocol")):
            methods_candidates.append(text)

    if not summary_candidates:
        summary_candidates = [section.text for section in sections[:2] if (section.text or "").strip()]
    summary = "\n\n".join(summary_candidates)[:4000]
    methods_snippet = "\n\n".join(methods_candidates)[:3000]

    paper_payload = {
        "title": header.title or paper_id,
        "summary": summary,
        "link": public_external_link_or_none(header.source_ref),
        "doi": paper_id if str(paper_id).startswith("10.") or str(paper_id).startswith("doi:") else None,
        "authors": header.authors,
        "source": "deepread_job",
    }
    return paper_payload, methods_snippet


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


def _build_claimset_section_summary_payload(resolved_claimset: Any) -> list[Dict[str, Any]]:
    payload: Dict[str, Any] | None = None
    if hasattr(resolved_claimset, "model_dump"):
        try:
            dumped = resolved_claimset.model_dump(mode="json")
        except Exception:
            dumped = None
        if isinstance(dumped, dict):
            payload = dumped
    elif isinstance(resolved_claimset, dict):
        payload = resolved_claimset

    normalized = normalize_claimset_payload(payload)
    if normalized is None:
        return []
    try:
        return build_section_signal_summary(claim_cards_from_claimset_payload(normalized))
    except Exception as exc:
        logger.debug("Failed to derive claimset section summary: %s", exc)
        return []


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
    feedback_file = _feedback_file()
    if not feedback_file.exists():
        return []

    # Fallback: JSONL recent accepted feedback scan.
    lines = feedback_file.read_text(encoding="utf-8").splitlines()
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
        preview = (sanitize_event_text_for_log(corr) or "").replace("\n", " ")[:180]
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


def _ingest_runtime_options_for_run_meta(options: Dict[str, Any]) -> Dict[str, Any]:
    persisted = dict(options)
    api_key = persisted.pop("cloud_table_api_key", None)
    persisted["cloud_table_api_key_configured"] = bool(str(api_key or "").strip())
    return persisted


def _build_cloud_table_preflight_callback(
    *,
    run_meta: Dict[str, Any],
    bootstrap_meta: Dict[str, Any],
    artifact_dir: Path,
    paper_id: str,
    run_id: str,
    model: str,
):
    def _callback(page_text: str, page_number: int) -> bool:
        _record_inference_lane(
            run_meta,
            lane="cloud_table_fallback",
            selected_backend="openai",
            payload_class="external_allowed",
            redaction_applied=False,
            provider_name="CloudTableFallbackExtractor",
            provider_model=model,
        )
        try:
            preflight = build_privacy_preflight_response(
                mode=resolve_privacy_preflight_mode(),
                payload_class="external_allowed",
                scope="cloud_table_fallback_external_payload",
                payload_texts=[(f"pdf_page_{int(page_number)}_text", page_text)],
                input_refs=[f"paper:{paper_id}", f"run:{run_id}", f"page:{int(page_number)}"],
                redaction_applied=False,
            )
        except ValueError as exc:
            if "LATTICE_PRIVACY_PREFLIGHT_MODE" not in str(exc):
                raise
            bootstrap_meta["cloud_table_fallback_status"] = "failed:invalid_privacy_preflight_mode"
            run_meta["cloud_table_fallback_status"] = "failed:invalid_privacy_preflight_mode"
            run_meta["privacy_preflight_error"] = str(exc)
            _write_bootstrap_meta(artifact_dir, bootstrap_meta)
            _write_run_meta(artifact_dir, run_meta)
            return False
        if preflight.mode != "off":
            _record_privacy_preflight(
                run_meta,
                lane="cloud_table_fallback",
                payload=preflight.model_dump(mode="json"),
            )
        if privacy_preflight_should_block(preflight):
            bootstrap_meta["cloud_table_fallback_status"] = "privacy_preflight_blocked"
            run_meta["cloud_table_fallback_status"] = "privacy_preflight_blocked"
            _write_bootstrap_meta(artifact_dir, bootstrap_meta)
            _write_run_meta(artifact_dir, run_meta)
            return False
        bootstrap_meta["cloud_table_fallback_status"] = "privacy_preflight_passed"
        run_meta["cloud_table_fallback_status"] = "privacy_preflight_passed"
        _write_bootstrap_meta(artifact_dir, bootstrap_meta)
        _write_run_meta(artifact_dir, run_meta)
        return True

    return _callback


def _write_bootstrap_meta(artifact_dir: Path, payload: Dict[str, Any]) -> None:
    try:
        atomic_write_text(
            artifact_dir / "bootstrap_meta.json",
            json.dumps(payload, ensure_ascii=False, indent=2),
        )
    except Exception as exc:
        logger.warning("Failed to write bootstrap_meta.json: %s", exc)


def _write_run_meta(artifact_dir: Path, payload: Dict[str, Any]) -> None:
    try:
        atomic_write_text(
            artifact_dir / "run_meta.json",
            json.dumps(payload, ensure_ascii=False, indent=2),
        )
    except Exception as exc:
        logger.warning("Failed to write run_meta.json: %s", exc)


def _write_reader_timeout_sidecar(
    artifact_dir: Path,
    *,
    job_id: str,
    run_id: str,
    paper_id: str,
    timeout_message: str,
    timeout_budget_sec: int,
    page_count: int,
    table_count: int,
    error_type: str,
    bootstrap_meta: Dict[str, Any],
) -> Path | None:
    payload = {
        "schema_version": "reader_timeout.v1",
        "layer": "review_gate_artifact",
        "canonical_status": "non_canonical",
        "job_id": job_id,
        "run_id": run_id,
        "paper_id": paper_id,
        "status": "timeout",
        "message": timeout_message,
        "error_type": error_type,
        "timeout_budget_sec": int(timeout_budget_sec),
        "page_count": int(page_count),
        "table_count": int(table_count),
        "reader_model": bootstrap_meta.get("reader_model"),
        "reader_attempt_order": bootstrap_meta.get("reader_attempt_order"),
        "reader_provider_timeout_sec": bootstrap_meta.get("reader_provider_timeout_sec"),
        "reader_provider_timeout_override_applied": bootstrap_meta.get(
            "reader_provider_timeout_override_applied"
        ),
        "reader_analysis": bootstrap_meta.get("reader_analysis"),
        "recommended_action": "retry_with_larger_reader_timeout_or_focused_first_reader_context",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    path = artifact_dir / "reader_timeout.json"
    try:
        atomic_write_text(path, json.dumps(payload, ensure_ascii=False, indent=2))
        return path
    except Exception as exc:
        logger.warning("Failed to write reader_timeout.json: %s", exc)
        return None


def _class_name(obj: Any) -> str:
    return type(obj).__name__ if obj is not None else ""


def _resolve_task_backend_name(provider: Any, llm_mode: str | None, task: str) -> str:
    class_name = _class_name(provider)
    mode = str(llm_mode or "").strip().lower()
    normalized_task = str(task or "").strip().lower()

    if class_name == "HybridProvider":
        local = getattr(provider, "local", None)
        cloud = getattr(provider, "cloud", None)
        use_cloud_for_task = normalized_task in {"escalation", "evaluate_escalation"}
        if use_cloud_for_task and cloud is not None and callable(getattr(cloud, "is_available", None)) and cloud.is_available():
            return "commercial"
        if local is not None and callable(getattr(local, "is_available", None)) and local.is_available():
            return "local"
        if cloud is not None and callable(getattr(cloud, "is_available", None)) and cloud.is_available():
            return "commercial"
        return _INFERENCE_NONE
    if class_name == "OpenAIProvider":
        return "commercial"
    if class_name == "OllamaProvider":
        return "local"
    if mode == "local":
        return "local"
    if mode == "cloud":
        return "commercial"
    if mode == "hybrid":
        return _INFERENCE_MIXED
    return _INFERENCE_NONE


def _resolve_task_model_name(provider: Any, task: str) -> str | None:
    get_model = getattr(provider, "_get_model", None)
    if not callable(get_model):
        return None
    try:
        model = get_model(task)
    except Exception:
        return None
    text = str(model or "").strip()
    return text or None


def _refresh_inference_summary(run_meta: Dict[str, Any]) -> None:
    lanes = run_meta.get("inference_lanes")
    if not isinstance(lanes, dict) or not lanes:
        run_meta["selected_backend"] = _INFERENCE_NONE
        run_meta["payload_class"] = _INFERENCE_NONE
        run_meta["redaction_applied"] = False
        return

    backends = {
        str(lane.get("selected_backend") or "").strip()
        for lane in lanes.values()
        if isinstance(lane, dict) and str(lane.get("selected_backend") or "").strip() and str(lane.get("selected_backend") or "").strip() != _INFERENCE_NONE
    }
    payload_classes = {
        str(lane.get("payload_class") or "").strip()
        for lane in lanes.values()
        if isinstance(lane, dict) and str(lane.get("payload_class") or "").strip() and str(lane.get("payload_class") or "").strip() != _INFERENCE_NONE
    }
    run_meta["selected_backend"] = next(iter(backends)) if len(backends) == 1 else (_INFERENCE_MIXED if backends else _INFERENCE_NONE)
    run_meta["payload_class"] = next(iter(payload_classes)) if len(payload_classes) == 1 else (_INFERENCE_MIXED if payload_classes else _INFERENCE_NONE)
    run_meta["redaction_applied"] = any(
        bool(lane.get("redaction_applied"))
        for lane in lanes.values()
        if isinstance(lane, dict)
    )


def _record_inference_lane(
    run_meta: Dict[str, Any],
    *,
    lane: str,
    selected_backend: str,
    payload_class: str,
    redaction_applied: bool,
    provider_name: str | None = None,
    provider_model: str | None = None,
) -> None:
    lanes = run_meta.setdefault("inference_lanes", {})
    if not isinstance(lanes, dict):
        lanes = {}
        run_meta["inference_lanes"] = lanes
    lanes[lane] = {
        "selected_backend": str(selected_backend or _INFERENCE_NONE),
        "payload_class": str(payload_class or _INFERENCE_NONE),
        "redaction_applied": bool(redaction_applied),
        "provider_name": str(provider_name or "").strip() or None,
        "provider_model": str(provider_model or "").strip() or None,
    }
    _refresh_inference_summary(run_meta)


def _record_privacy_preflight(run_meta: Dict[str, Any], *, lane: str, payload: Dict[str, Any]) -> None:
    lanes = run_meta.setdefault("inference_lanes", {})
    if not isinstance(lanes, dict):
        lanes = {}
        run_meta["inference_lanes"] = lanes
    lane_payload = lanes.setdefault(lane, {})
    if isinstance(lane_payload, dict):
        lane_payload["privacy_preflight"] = payload


def _reader_inference_lane_from_metrics(reader_obj: Any) -> Dict[str, Any]:
    metrics = getattr(reader_obj, "last_analysis_metrics", None)
    attempts = metrics.get("attempts") if isinstance(metrics, dict) else None
    selected_attempt = metrics.get("selected_attempt") if isinstance(metrics, dict) else None
    if isinstance(attempts, list) and attempts:
        chosen: Dict[str, Any] | None = None
        if selected_attempt is not None:
            for attempt in attempts:
                if not isinstance(attempt, dict):
                    continue
                if attempt.get("attempt_idx") == selected_attempt:
                    chosen = attempt
                    break
        if chosen is None:
            for attempt in reversed(attempts):
                if isinstance(attempt, dict) and (
                    attempt.get("provider_name")
                    or attempt.get("provider_model")
                    or attempt.get("provider_status")
                ):
                    chosen = attempt
                    break
        if isinstance(chosen, dict):
            provider_name = str(chosen.get("provider_name") or "").strip() or "ollama"
            provider_model = str(chosen.get("provider_model") or "").strip() or None
            return {
                "selected_backend": "local",
                "payload_class": "local_only",
                "redaction_applied": False,
                "provider_name": provider_name,
                "provider_model": provider_model,
            }
    model_name = str(getattr(reader_obj, "model_name", "") or "").strip() or None
    return {
        "selected_backend": "local",
        "payload_class": "local_only",
        "redaction_applied": False,
        "provider_name": "ollama",
        "provider_model": model_name,
    }


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


def _apply_reader_timeout_budget(reader_agent: Any, timeout_budget_sec: int) -> Dict[str, Any]:
    """
    Best-effort local-provider timeout override for the current reader instance.
    Keeps the change scoped to this reader path without widening the global config contract.
    """
    budget = max(1, int(timeout_budget_sec))
    adapter = getattr(reader_agent, "adapter", None)
    provider = getattr(adapter, "provider", None)
    provider_config = getattr(provider, "config", None)
    current_timeout = int(getattr(provider_config, "timeout_seconds", 0) or 0)
    result: Dict[str, Any] = {
        "applied": False,
        "previous_timeout_sec": current_timeout,
        "effective_timeout_sec": current_timeout,
    }

    if provider is None or provider_config is None or current_timeout >= budget:
        return result

    try:
        provider_config.timeout_seconds = budget
        reinitializer = getattr(provider, "_initialize", None)
        if callable(reinitializer):
            reinitializer()
        result["applied"] = True
        result["effective_timeout_sec"] = int(getattr(provider_config, "timeout_seconds", budget) or budget)
        return result
    except Exception as exc:
        logger.warning("Reader timeout override failed: %s", exc)
        result["error"] = str(exc)
        result["effective_timeout_sec"] = int(getattr(provider_config, "timeout_seconds", current_timeout) or current_timeout)
        return result


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
    Emits structured events through log_job_event and the optional progress_callback.
    """
    if not run_id:
        run_id = new_run_id()

    artifact_dir: Optional[Path] = None
    bootstrap_meta: Optional[Dict[str, Any]] = None
    run_meta: Optional[Dict[str, Any]] = None
    stage_timings: list[dict[str, Any]] = []
    selection = normalize_persona_selection(
        persona_id=persona_id,
        reasoning_persona=reasoning_persona,
        profile_id=profile_id,
    )

    async def is_cancelled() -> bool:
        if not cancel_check:
            return False
        result = cancel_check()
        if asyncio.iscoroutine(result):
            return await result
        return bool(result)

    async def emit(stage: str, progress: int, message: str, level: str = "INFO"):
        safe_message = sanitize_event_text_for_log(message) or ""
        event = {
            "job_id": job_id,
            "run_id": run_id,
            "stage": stage,
            "progress": progress,
            "message": safe_message,
            "level": level,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        event = sanitize_event_payload_for_log(event)
        try:
            log_job_event(
                job_id=job_id,
                run_id=run_id,
                level=level,
                event_type="progress",
                message=safe_message,
                payload=event,
                ts=str(event["timestamp"]),
            )
        except Exception as exc:
            logger.debug("Structured job event logging failed for %s: %s", job_id, exc)
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

    def _job_result(status: str, **extra: Any) -> Dict[str, Any]:
        result: Dict[str, Any] = {"status": status, "run_id": run_id}
        if artifact_dir is not None:
            result["artifact_dir"] = str(artifact_dir)
        result.update(extra)
        return result

    def _persist_reader_analysis_metrics(reader_obj: Any) -> None:
        metrics = getattr(reader_obj, "last_analysis_metrics", None)
        if run_meta is not None:
            _record_inference_lane(
                run_meta,
                lane="reader",
                **_reader_inference_lane_from_metrics(reader_obj),
            )
        if not isinstance(metrics, dict) or not metrics:
            if run_meta is not None:
                run_meta["updated_at"] = datetime.now(timezone.utc).isoformat()
                _write_run_meta(artifact_dir, run_meta)
            return
        bootstrap_meta["reader_analysis"] = dict(metrics)
        _write_bootstrap_meta(artifact_dir, bootstrap_meta)
        if run_meta is not None:
            run_meta["reader_analysis"] = dict(metrics)
            run_meta["updated_at"] = datetime.now(timezone.utc).isoformat()
            _write_run_meta(artifact_dir, run_meta)

    def _write_performance_meta() -> None:
        if artifact_dir is None:
            return
        summary = summarize_stage_timings(stage_timings)
        if run_meta is not None:
            run_meta["performance"] = {
                "schema_version": "performance_profile.v1",
                "stage_timings": list(stage_timings),
                "summary": summary,
            }
            run_meta["updated_at"] = datetime.now(timezone.utc).isoformat()
            _write_run_meta(artifact_dir, run_meta)
        if bootstrap_meta is not None:
            bootstrap_meta["performance_summary"] = summary
            _write_bootstrap_meta(artifact_dir, bootstrap_meta)

    def _record_stage_timing(timer: StageTimer) -> None:
        timer.finish()
        stage_timings.append(timer.to_meta())
        _write_performance_meta()

    try:
        if await is_cancelled():
            return _job_result("cancelled")

        await emit("init", 0, f"Starting Deep Read for {paper_id}")
        
        config = load_config()
        
        # 1. Locate PDF
        # Try finding locally in Library first (Mocking DB lookup for now if needed, or using direct path if we have it)
        # For this MVP, let's assume paper_id is a citekey or we can find it in library
        await emit("init", 5, "Locating PDF...")
        
        pdf_path = _resolve_pdf_path_from_db(paper_id)
        if pdf_path:
            logger.info(f"✅ Found PDF from DB path: {pdf_path}")

        if not pdf_path:
            pdf_path = _resolve_pdf_path_from_note_frontmatter(paper_id)
            if pdf_path:
                logger.info(f"✅ Found PDF from note metadata: {pdf_path}")

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
            return _job_result("failed", error=f"PDF not found for {paper_id}")
            
        logger.info(f"✅ Found PDF: {pdf_path}")

        # Prepare Artifact Storage
        artifact_dir = artifact_run_dir(paper_id, run_id)
        artifact_dir.mkdir(parents=True, exist_ok=True)

        snapshots_dir = artifact_dir / "snapshots"
        snapshots_dir.mkdir(parents=True, exist_ok=True)
        run_meta = {
            "job_id": job_id,
            "run_id": run_id,
            "paper_id": paper_id,
            "persona_id": selection.persona_id,
            "reasoning_persona": selection.reasoning_persona,
            "profile_id": selection.profile_id,
            "run_verify": bool(run_verify),
            "clean_reindex_requested": bool(clean_reindex),
            "pdf_path": str(pdf_path),
            "pdf_sha256": _sha256_file(pdf_path),
            "pdf_mtime": datetime.fromtimestamp(pdf_path.stat().st_mtime, timezone.utc).isoformat(),
            "config_snapshot": _snapshot_copy(config_file_path(), snapshots_dir / "config.yaml"),
            "prompts_snapshot": _snapshot_copy(profiles_config_path(), snapshots_dir / "profiles.yaml"),
            "models_used": {"reader": None, "verifier": None},
            "requested_parser_backend": None,
            "parser_backend": None,
            "llm_params": _collect_llm_params(config),
            "embed_params": _collect_embed_params(config),
            "tool_policy_version": "v1",
            "selected_backend": _INFERENCE_NONE,
            "payload_class": _INFERENCE_NONE,
            "redaction_applied": False,
            "inference_lanes": {},
            "anchor_verify_api": {"provider": "none", "status": "not_run", "reason_codes": []},
            "status": "running",
            "section_count": 0,
            "performance": {
                "schema_version": "performance_profile.v1",
                "stage_timings": [],
                "summary": summarize_stage_timings([]),
            },
            "started_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        _write_run_meta(artifact_dir, run_meta)

        bootstrap_meta = {
            "job_id": job_id,
            "run_id": run_id,
            "paper_id": paper_id,
            "persona_id": selection.persona_id,
            "reasoning_persona": selection.reasoning_persona,
            "profile_id": selection.profile_id,
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
            "artifact_stats_fallback_eval_written": False,
            "artifact_document_written": False,
            "artifact_index_written": False,
            "artifact_claimset_written": False,
            "artifact_claimset_coverage_written": False,
            "artifact_claimset_coverage_focus_written": False,
            "artifact_figure_captions_written": False,
            "artifact_visual_evidence_ledger_written": False,
            "artifact_reader_timeout_written": False,
            "artifact_stats_written": False,
            "claimset_readiness": "unknown",
            "claimset_ready": None,
            "claimset_claim_count": 0,
            "claimset_section_count": 0,
            "claimset_readiness_reason": "not_evaluated",
            "claimset_readiness_badge": "UNKNOWN",
            "claimset_ops_action": "none",
            "claimset_ops_alert": False,
            "claimset_ops_note": "not_evaluated",
            "requested_parser_backend": None,
            "parser_backend": None,
            "parser_failure_code": None,
            "parser_failure_reason": None,
            "table_extraction_pass": "pass1",
            "table_failure_taxonomy": [],
            "fallback_used": False,
            "fallback_pages": [],
            "anchor_verify_summary": {"pass": 0, "warn": 0, "fail": 0, "no_api": 0},
            "anchor_verify_api": {"provider": "none", "status": "not_run", "reason_codes": []},
            "table_pass2_enabled": False,
            "table_pass3_enabled": False,
            "table_page_budget": 0,
            "cloud_table_fallback_status": "not_run",
            "artifact_clinical_extraction_written": False,
            "clinical_extraction_status": "not_run",
            "clinical_extraction_note_type": "unknown",
            "performance_summary": summarize_stage_timings([]),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        _write_bootstrap_meta(artifact_dir, bootstrap_meta)
        
        # 2. Ingest
        if await is_cancelled():
            _mark_run_meta("cancelled")
            return _job_result("cancelled")
        ingest_timer = StageTimer("ingest")
        ingest_timer.__enter__()
        logger.info(f"Starting Ingest for {pdf_path.name}")
        await emit("ingest", 10, f"Ingesting PDF: {pdf_path.name}")
        requested_parser_backend = str(parser_backend or "").strip().lower() or None
        parser_backend = _resolve_ingest_parser_backend(config, override_backend=parser_backend)
        ingest_runtime_options = _resolve_ingest_runtime_options(config)
        bootstrap_meta["requested_parser_backend"] = requested_parser_backend or parser_backend
        bootstrap_meta["parser_backend"] = parser_backend
        bootstrap_meta["table_pass2_enabled"] = bool(ingest_runtime_options.get("enable_table_pass2_ocr", False))
        bootstrap_meta["table_pass3_enabled"] = bool(ingest_runtime_options.get("enable_cloud_table_fallback", False))
        bootstrap_meta["table_page_budget"] = int(ingest_runtime_options.get("cloud_table_page_budget", 0))
        _write_bootstrap_meta(artifact_dir, bootstrap_meta)
        if run_meta is not None:
            run_meta["requested_parser_backend"] = requested_parser_backend or parser_backend
            run_meta["parser_backend"] = parser_backend
            run_meta["ingest_options"] = _ingest_runtime_options_for_run_meta(ingest_runtime_options)
            run_meta["updated_at"] = datetime.now(timezone.utc).isoformat()
            _write_run_meta(artifact_dir, run_meta)

        try:
            ingest_agent = IngestAgent(parser_backend=parser_backend, **ingest_runtime_options)
        except TypeError:
            # Test doubles may expose a simplified constructor.
            ingest_agent = IngestAgent()
        if run_meta is not None and bool(ingest_runtime_options.get("enable_cloud_table_fallback", False)):
            ingest_agent.cloud_table_preflight_callback = _build_cloud_table_preflight_callback(
                run_meta=run_meta,
                bootstrap_meta=bootstrap_meta,
                artifact_dir=artifact_dir,
                paper_id=paper_id,
                run_id=run_id,
                model=str(ingest_runtime_options.get("cloud_table_model") or "gpt-4o-mini"),
            )
        doc_artifact = ingest_agent.process_v2(str(pdf_path))
        
        if not doc_artifact:
            ingest_meta = getattr(ingest_agent, "last_table_extraction_meta", {}) or {}
            parser_failure_code = str(ingest_meta.get("parser_failure_code") or "").strip() or None
            parser_failure_reason = str(ingest_meta.get("parser_failure_reason") or "").strip() or None
            bootstrap_meta["parser_failure_code"] = parser_failure_code
            bootstrap_meta["parser_failure_reason"] = parser_failure_reason
            _write_bootstrap_meta(artifact_dir, bootstrap_meta)
            if run_meta is not None:
                run_meta["parser_failure_code"] = parser_failure_code
                run_meta["parser_failure_reason"] = parser_failure_reason
                run_meta["updated_at"] = datetime.now(timezone.utc).isoformat()
                _write_run_meta(artifact_dir, run_meta)
            suffix = f": {parser_failure_code}" if parser_failure_code else ""
            raise Exception(f"Ingestion failed to produce artifact{suffix}")

        ingest_meta = getattr(ingest_agent, "last_table_extraction_meta", {}) or {}
        effective_parser_backend = str(ingest_meta.get("parser_backend") or parser_backend).strip().lower()
        if effective_parser_backend not in {"fitz_pdfplumber", "docling"}:
            effective_parser_backend = parser_backend
        bootstrap_meta["parser_backend"] = effective_parser_backend
        bootstrap_meta["parser_backend_fallback_used"] = bool(ingest_meta.get("parser_backend_fallback_used", False))
        bootstrap_meta["parser_failure_code"] = ingest_meta.get("parser_failure_code")
        bootstrap_meta["parser_failure_reason"] = ingest_meta.get("parser_failure_reason")
        bootstrap_meta["table_extraction_pass"] = str(ingest_meta.get("table_extraction_pass") or "pass1")
        taxonomy = ingest_meta.get("table_failure_taxonomy")
        bootstrap_meta["table_failure_taxonomy"] = taxonomy if isinstance(taxonomy, list) else []
        bootstrap_meta["fallback_used"] = bool(ingest_meta.get("fallback_used", False))
        fallback_pages = ingest_meta.get("fallback_pages")
        bootstrap_meta["fallback_pages"] = fallback_pages if isinstance(fallback_pages, list) else []
        _write_bootstrap_meta(artifact_dir, bootstrap_meta)
        if run_meta is not None:
            run_meta["parser_backend"] = effective_parser_backend
            run_meta["parser_backend_fallback_used"] = bool(
                ingest_meta.get("parser_backend_fallback_used", False)
            )
            run_meta["parser_failure_code"] = ingest_meta.get("parser_failure_code")
            run_meta["parser_failure_reason"] = ingest_meta.get("parser_failure_reason")
            run_meta["updated_at"] = datetime.now(timezone.utc).isoformat()
            _write_run_meta(artifact_dir, run_meta)
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
        atomic_write_text(
            artifact_dir / "document_artifact.json",
            doc_artifact.model_dump_json(indent=2),
        )
        bootstrap_meta["artifact_document_written"] = True
        figure_caption_sidecar = None
        try:
            figure_caption_sidecar = build_figure_caption_sidecar(
                paper_id=paper_id,
                run_id=run_id,
                document_artifact=doc_artifact,
            )
            figure_caption_path = write_figure_caption_sidecar(figure_caption_sidecar, artifact_dir)
            bootstrap_meta["artifact_figure_captions_written"] = True
            bootstrap_meta["figure_caption_count"] = int(figure_caption_sidecar.metrics.figure_count)
            bootstrap_meta["figure_caption_artifact"] = str(figure_caption_path)
            if run_meta is not None:
                run_meta["figure_caption_artifact"] = str(figure_caption_path)
                run_meta["figure_caption_count"] = bootstrap_meta["figure_caption_count"]
                run_meta["updated_at"] = datetime.now(timezone.utc).isoformat()
                _write_run_meta(artifact_dir, run_meta)
        except Exception as exc:
            logger.warning("Failed to write figure_captions.json: %s", exc)
            bootstrap_meta["artifact_figure_captions_written"] = False
            bootstrap_meta["figure_caption_error"] = str(exc)
        _write_bootstrap_meta(artifact_dir, bootstrap_meta)

        note_path: Optional[Path] = _resolve_note_path_for_paper(config, paper_id)
        is_clinical_note = _is_clinical_note(note_path)
        bootstrap_meta["clinical_extraction_note_type"] = "clinical" if is_clinical_note else "non_clinical"
        run_meta["clinical_extraction_status"] = "skipped"
        run_meta["clinical_extraction_artifact"] = None
        _write_bootstrap_meta(artifact_dir, bootstrap_meta)
        _write_run_meta(artifact_dir, run_meta)

        llm_conf = getattr(config, "llm", None)
        clinical_extraction_feature = resolve_clinical_extraction_feature(
            getattr(llm_conf, "features", None)
        )
        clinical_extraction_enabled = bool(getattr(clinical_extraction_feature, "enabled", False))
        clinical_extraction: BiomedicalClinicalExtraction | None = None
        if is_clinical_note and clinical_extraction_enabled and llm_conf is not None:
            llm_provider = get_llm_provider(llm_conf, getattr(config, "entity_aliases", None))
            if llm_provider and llm_provider.is_available():
                _record_inference_lane(
                    run_meta,
                    lane="clinical_extraction",
                    selected_backend=_resolve_task_backend_name(
                        llm_provider,
                        getattr(llm_conf, "mode", None),
                        "clinical_extraction",
                    ),
                    payload_class="external_allowed",
                    redaction_applied=True,
                    provider_name=_class_name(llm_provider),
                    provider_model=_resolve_task_model_name(llm_provider, "clinical_extraction"),
                )
                _write_run_meta(artifact_dir, run_meta)
                extract_clinical = getattr(llm_provider, "extract_biomedical_clinical_data", None)
                if callable(extract_clinical):
                    try:
                        paper_payload, methods_snippet = _build_biomedical_clinical_extraction_inputs(doc_artifact, paper_id)
                        preflight_mode = resolve_privacy_preflight_mode()
                        preflight = build_privacy_preflight_response(
                            mode=preflight_mode,
                            payload_class="external_allowed",
                            scope="clinical_extraction_external_payload",
                            payload_texts=[
                                ("paper_metadata", json.dumps(paper_payload, ensure_ascii=False)),
                                ("methods_snippet", methods_snippet),
                            ],
                            input_refs=[f"paper:{paper_id}", f"run:{run_id}"],
                            redaction_applied=True,
                        )
                        if preflight.mode != "off":
                            _record_privacy_preflight(
                                run_meta,
                                lane="clinical_extraction",
                                payload=preflight.model_dump(mode="json"),
                            )
                            _write_run_meta(artifact_dir, run_meta)
                        if privacy_preflight_should_block(preflight):
                            bootstrap_meta["clinical_extraction_status"] = "privacy_preflight_blocked"
                            run_meta["clinical_extraction_status"] = "privacy_preflight_blocked"
                            _write_bootstrap_meta(artifact_dir, bootstrap_meta)
                            _write_run_meta(artifact_dir, run_meta)
                            await emit(
                                "ingest",
                                28,
                                "Biomedical clinical extraction blocked by privacy preflight",
                                level="WARNING",
                            )
                            extraction_candidate = None
                        else:
                            extraction_candidate = extract_clinical(paper_payload, methods_snippet)
                        if isinstance(extraction_candidate, BiomedicalClinicalExtraction):
                            clinical_extraction = extraction_candidate
                            clinical_path = artifact_dir / "clinical_extraction.json"
                            atomic_write_text(
                                clinical_path,
                                clinical_extraction.model_dump_json(indent=2),
                            )
                            bootstrap_meta["artifact_clinical_extraction_written"] = True
                            bootstrap_meta["clinical_extraction_status"] = "completed"
                            run_meta["clinical_extraction_status"] = "completed"
                            run_meta["clinical_extraction_artifact"] = str(clinical_path)
                            _write_bootstrap_meta(artifact_dir, bootstrap_meta)
                            _write_run_meta(artifact_dir, run_meta)
                            await emit("ingest", 28, "Biomedical clinical extraction artifact written")
                        elif privacy_preflight_should_block(preflight):
                            pass
                        else:
                            bootstrap_meta["clinical_extraction_status"] = "empty"
                            run_meta["clinical_extraction_status"] = "empty"
                            _write_bootstrap_meta(artifact_dir, bootstrap_meta)
                            _write_run_meta(artifact_dir, run_meta)
                    except ValueError as exc:
                        if "LATTICE_PRIVACY_PREFLIGHT_MODE" not in str(exc):
                            raise
                        bootstrap_meta["clinical_extraction_status"] = "failed:invalid_privacy_preflight_mode"
                        run_meta["clinical_extraction_status"] = "failed:invalid_privacy_preflight_mode"
                        run_meta["privacy_preflight_error"] = str(exc)
                        _write_bootstrap_meta(artifact_dir, bootstrap_meta)
                        _write_run_meta(artifact_dir, run_meta)
                        await emit("ingest", 28, "Biomedical clinical extraction skipped: invalid privacy preflight mode", level="WARNING")
                    except Exception as exc:
                        bootstrap_meta["clinical_extraction_status"] = f"failed:{type(exc).__name__}"
                        run_meta["clinical_extraction_status"] = f"failed:{type(exc).__name__}"
                        _write_bootstrap_meta(artifact_dir, bootstrap_meta)
                        _write_run_meta(artifact_dir, run_meta)
                        await emit("ingest", 28, f"Biomedical clinical extraction skipped: {type(exc).__name__}", level="WARNING")
            else:
                _record_inference_lane(
                    run_meta,
                    lane="clinical_extraction",
                    selected_backend=_INFERENCE_NONE,
                    payload_class="external_allowed",
                    redaction_applied=True,
                    provider_name=_class_name(llm_provider),
                    provider_model=None,
                )
                bootstrap_meta["clinical_extraction_status"] = "llm_unavailable"
                run_meta["clinical_extraction_status"] = "llm_unavailable"
                _write_bootstrap_meta(artifact_dir, bootstrap_meta)
                _write_run_meta(artifact_dir, run_meta)
        else:
            reason = "feature_disabled"
            if not is_clinical_note:
                reason = "not_clinical_note"
            bootstrap_meta["clinical_extraction_status"] = reason
            run_meta["clinical_extraction_status"] = reason
            _write_bootstrap_meta(artifact_dir, bootstrap_meta)
            _write_run_meta(artifact_dir, run_meta)
            
        await emit("ingest", 25, f"Ingested {len(doc_artifact.pages)} pages")
        _record_stage_timing(ingest_timer)

        # 3. Index
        if await is_cancelled():
            _mark_run_meta("cancelled")
            return _job_result("cancelled")
        index_timer = StageTimer("index")
        index_timer.__enter__()
        await emit("index", 30, "Indexing content...")
        indexer_agent = IndexerAgent()
        clean_reindex_doc_id: str | None = None
        if clean_reindex:
            clean_reindex_doc_id = str(getattr(doc_artifact, "document_id", "") or getattr(doc_artifact, "doc_id", "") or paper_id)
        index_artifact = indexer_agent.process(doc_artifact)
        if clean_reindex:
            if clean_reindex_doc_id and hasattr(indexer_agent, "prune_doc_index"):
                keep_ids = [str(chunk.vector_id) for chunk in index_artifact.chunks if str(chunk.vector_id or "").strip()]
                if not bool(getattr(indexer_agent, "last_index_complete", True)):
                    bootstrap_meta["clean_reindex_applied"] = False
                    bootstrap_meta["clean_reindex_skip_reason"] = "partial_replacement_vectors"
                    bootstrap_meta["clean_reindex_attempted_chunks"] = int(getattr(indexer_agent, "last_index_attempted_chunks", 0) or 0)
                    bootstrap_meta["clean_reindex_skipped_chunks"] = int(getattr(indexer_agent, "last_index_skipped_chunks", 0) or 0)
                    _write_bootstrap_meta(artifact_dir, bootstrap_meta)
                    await emit("index", 33, "Clean reindex skipped: partial replacement vectors", level="WARNING")
                elif keep_ids:
                    removed = int(indexer_agent.prune_doc_index(clean_reindex_doc_id, keep_ids=keep_ids))
                    bootstrap_meta["clean_reindex_applied"] = True
                    bootstrap_meta["clean_reindex_removed_chunks"] = removed
                    _write_bootstrap_meta(artifact_dir, bootstrap_meta)
                    await emit("index", 33, f"Clean reindex applied: pruned {removed} stale chunks")
                else:
                    bootstrap_meta["clean_reindex_applied"] = False
                    bootstrap_meta["clean_reindex_skip_reason"] = "no_replacement_vectors"
                    _write_bootstrap_meta(artifact_dir, bootstrap_meta)
                    await emit("index", 33, "Clean reindex skipped: no replacement vectors", level="WARNING")
            else:
                await emit("index", 33, "Clean reindex requested but index prune hook unavailable", level="WARNING")
        
        # Save Index Artifact
        atomic_write_text(
            artifact_dir / "index_artifact.json",
            index_artifact.model_dump_json(indent=2),
        )
        bootstrap_meta["artifact_index_written"] = True
        _write_bootstrap_meta(artifact_dir, bootstrap_meta)
             
        await emit("index", 45, f"Indexed {index_artifact.chunk_count} chunks")
        _record_stage_timing(index_timer)

        # 4. Read (Claim Extraction)
        if await is_cancelled():
            _mark_run_meta("cancelled")
            return _job_result("cancelled")
        reader_timer = StageTimer("reader")
        reader_timer.__enter__()
        await emit("read", 50, "Reader Agent analyzing...")
        hint_sections: list[str] = []
        reasoning_hint = resolve_reasoning_persona_hint(selection.reasoning_persona)
        if reasoning_hint:
            hint_sections.append(reasoning_hint)
        profile_hint = _resolve_persona_hint(selection.profile_id) if selection.profile_id else None
        if profile_hint:
            hint_sections.append(profile_hint)
        persona_hint = "\n\n".join(section for section in hint_sections if section) or None

        # Dynamic few-shot injection based on reasoning/profile context.
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
            if selection.reasoning_persona:
                await emit("read", 51, f"Reasoning persona applied: {selection.reasoning_persona}")
            if selection.profile_id:
                await emit("read", 52, f"Profile context applied: {selection.profile_id}")
            if not selection.reasoning_persona and not selection.profile_id:
                await emit("read", 52, f"Persona applied: {selection.persona_id}")
        _write_bootstrap_meta(artifact_dir, bootstrap_meta)
        main_model = _resolve_main_model(config)
        bootstrap_meta["reader_model"] = main_model
        _write_bootstrap_meta(artifact_dir, bootstrap_meta)
        if run_meta is not None:
            run_meta["models_used"]["reader"] = main_model
            run_meta["updated_at"] = datetime.now(timezone.utc).isoformat()
            _write_run_meta(artifact_dir, run_meta)
        page_count = len(getattr(doc_artifact, "pages", []) or [])
        table_count = len(getattr(doc_artifact, "tables", []) or [])
        llm_timeout_default = max(15, int(getattr(llm_conf, "timeout_seconds", 15) or 15))
        reader_attempt_order = str(getattr(llm_conf, "reader_attempt_order", "current") or "current")
        if reader_attempt_order not in {"current", "focused_first"}:
            reader_attempt_order = "current"
        bootstrap_meta["reader_attempt_order"] = reader_attempt_order
        _write_bootstrap_meta(artifact_dir, bootstrap_meta)
        if run_meta is not None:
            run_meta["reader_attempt_order"] = reader_attempt_order
            run_meta["updated_at"] = datetime.now(timezone.utc).isoformat()
            _write_run_meta(artifact_dir, run_meta)
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
        bootstrap_meta["artifact_reader_timeout_written"] = False
        bootstrap_meta["reader_timeout_artifact"] = None
        _write_bootstrap_meta(artifact_dir, bootstrap_meta)
        if run_meta is not None:
            run_meta["reader_timeout_base_sec"] = reader_timeout_base
            run_meta["reader_timeout_budget_sec"] = reader_timeout_budget
            run_meta["reader_timeout_adaptive"] = True
            run_meta["reader_page_count"] = page_count
            run_meta["reader_table_count"] = table_count
            run_meta["reader_timeout_triggered"] = False
            run_meta["reader_timeout_error_type"] = None
            run_meta["reader_timeout_artifact"] = None
            run_meta["updated_at"] = datetime.now(timezone.utc).isoformat()
            _write_run_meta(artifact_dir, run_meta)
        await emit("read", 54, f"Reader timeout budget: {reader_timeout_budget}s")
        performance_config = getattr(config, "performance", None)
        reader_max_context_chars = int(
            getattr(performance_config, "reader_max_context_chars", 16000) or 16000
        )
        bootstrap_meta["reader_max_context_chars"] = reader_max_context_chars
        _write_bootstrap_meta(artifact_dir, bootstrap_meta)
        if run_meta is not None:
            run_meta["reader_max_context_chars"] = reader_max_context_chars
            run_meta["updated_at"] = datetime.now(timezone.utc).isoformat()
            _write_run_meta(artifact_dir, run_meta)
        try:
            reader_agent = ReaderAgent(
                model_name=main_model,
                persona_hint=persona_hint,
                attempt_order=reader_attempt_order,
                max_context_chars=reader_max_context_chars,
            )
        except TypeError:
            try:
                # Test doubles may accept the legacy constructor without attempt_order.
                reader_agent = ReaderAgent(
                    model_name=main_model,
                    persona_hint=persona_hint,
                    max_context_chars=reader_max_context_chars,
                )
            except TypeError:
                # Final fallback for minimal test doubles.
                reader_agent = ReaderAgent()
        timeout_override = _apply_reader_timeout_budget(reader_agent, reader_timeout_budget)
        bootstrap_meta["reader_provider_timeout_sec"] = timeout_override["effective_timeout_sec"]
        bootstrap_meta["reader_provider_timeout_override_applied"] = bool(timeout_override["applied"])
        if timeout_override.get("error"):
            bootstrap_meta["reader_provider_timeout_override_error"] = str(timeout_override["error"])
        _write_bootstrap_meta(artifact_dir, bootstrap_meta)
        if run_meta is not None:
            run_meta["reader_provider_timeout_sec"] = timeout_override["effective_timeout_sec"]
            run_meta["reader_provider_timeout_override_applied"] = bool(timeout_override["applied"])
            if timeout_override.get("error"):
                run_meta["reader_provider_timeout_override_error"] = str(timeout_override["error"])
            run_meta["updated_at"] = datetime.now(timezone.utc).isoformat()
            _write_run_meta(artifact_dir, run_meta)
        try:
            with time_limit(int(reader_timeout_budget)):
                claim_set = reader_agent.analyze(doc_artifact)
        except Exception as exc:
            if not is_timeout_exception(exc):
                raise
            _persist_reader_analysis_metrics(reader_agent)
            timeout_message = (
                f"Reader step timed out after {reader_timeout_budget}s "
                f"(pages={page_count}, tables={table_count})"
            )
            bootstrap_meta["reader_timeout_triggered"] = True
            bootstrap_meta["reader_timeout_error_type"] = type(exc).__name__
            timeout_sidecar_path = _write_reader_timeout_sidecar(
                artifact_dir,
                job_id=job_id,
                run_id=run_id,
                paper_id=paper_id,
                timeout_message=timeout_message,
                timeout_budget_sec=reader_timeout_budget,
                page_count=page_count,
                table_count=table_count,
                error_type=type(exc).__name__,
                bootstrap_meta=bootstrap_meta,
            )
            bootstrap_meta["artifact_reader_timeout_written"] = timeout_sidecar_path is not None
            bootstrap_meta["reader_timeout_artifact"] = (
                str(timeout_sidecar_path) if timeout_sidecar_path is not None else None
            )
            _write_bootstrap_meta(artifact_dir, bootstrap_meta)
            if run_meta is not None:
                run_meta["reader_timeout_triggered"] = True
                run_meta["reader_timeout_error_type"] = type(exc).__name__
                run_meta["reader_timeout_artifact"] = (
                    str(timeout_sidecar_path) if timeout_sidecar_path is not None else None
                )
                run_meta["updated_at"] = datetime.now(timezone.utc).isoformat()
                _write_run_meta(artifact_dir, run_meta)
            await emit("read", 55, timeout_message, level="ERROR")
            raise TimeoutError(timeout_message) from exc
        _persist_reader_analysis_metrics(reader_agent)
        
        if not claim_set:
             raise Exception("Reader Agent failed to produce claims")
        claim_set = enforce_claimset_evidence_policy(claim_set)
        resolved_claim_set = resolve_claimset_grounding(
            claim_set,
            index_artifact,
            document_artifact=doc_artifact if isinstance(doc_artifact, DocumentArtifactV2) else None,
        )
             
        # Save ClaimSet
        atomic_write_text(
            artifact_dir / "claimset.json",
            claim_set.model_dump_json(indent=2),
        )
        atomic_write_text(
            artifact_dir / "claimset.resolved.json",
            resolved_claim_set.model_dump_json(indent=2),
        )
        bootstrap_meta["artifact_claimset_written"] = True
        bootstrap_meta["artifact_claimset_resolved_written"] = True
        bootstrap_meta["artifact_claimset_coverage_written"] = False
        bootstrap_meta["artifact_reader_eval_written"] = False
        bootstrap_meta["artifact_visual_evidence_ledger_written"] = False
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
        section_summary = _build_claimset_section_summary_payload(resolved_claim_set)
        bootstrap_meta["claimset_section_count"] = len(section_summary)
        if run_meta is not None:
            run_meta["section_count"] = len(section_summary)
            if section_summary:
                run_meta["section_summary"] = section_summary
            else:
                run_meta.pop("section_summary", None)
        visual_evidence_ledger = None
        try:
            visual_evidence_ledger = build_visual_evidence_ledger(
                paper_id=paper_id,
                run_id=run_id,
                document_artifact=doc_artifact,
                figure_captions=figure_caption_sidecar,
                resolved_claimset=resolved_claim_set,
            )
            visual_evidence_ledger_path = write_visual_evidence_ledger(visual_evidence_ledger, artifact_dir)
            bootstrap_meta["artifact_visual_evidence_ledger_written"] = True
            bootstrap_meta["visual_evidence_ledger_artifact"] = str(visual_evidence_ledger_path)
            bootstrap_meta["visual_evidence_entry_count"] = visual_evidence_ledger.metrics.entry_count
            bootstrap_meta["visual_evidence_unknown_count"] = visual_evidence_ledger.metrics.unknown_count
            bootstrap_meta["visual_evidence_partially_observed_count"] = (
                visual_evidence_ledger.metrics.partially_observed_count
            )
            if run_meta is not None:
                run_meta["visual_evidence_ledger"] = {
                    "artifact": str(visual_evidence_ledger_path),
                    "entry_count": visual_evidence_ledger.metrics.entry_count,
                    "unknown_count": visual_evidence_ledger.metrics.unknown_count,
                    "partially_observed_count": visual_evidence_ledger.metrics.partially_observed_count,
                    "generation_replay_required": visual_evidence_ledger.generation_replay_required,
                    "final_answer_validation_required": visual_evidence_ledger.final_answer_validation_required,
                }
        except Exception as exc:
            logger.warning("Failed to build visual_evidence_ledger sidecar: %s", exc)
            bootstrap_meta["artifact_visual_evidence_ledger_written"] = False
            bootstrap_meta["visual_evidence_ledger_error"] = str(exc)
        claimset_coverage = None
        try:
            claimset_coverage = build_claimset_coverage_sidecar(
                paper_id=paper_id,
                run_id=run_id,
                document_artifact=doc_artifact,
                index_artifact=index_artifact,
                resolved_claimset=resolved_claim_set,
                figure_captions=figure_caption_sidecar,
            )
            claimset_coverage_path = write_claimset_coverage_sidecar(claimset_coverage, artifact_dir)
            bootstrap_meta["artifact_claimset_coverage_written"] = True
            bootstrap_meta["claimset_coverage_status"] = claimset_coverage.coverage_status
            bootstrap_meta["claimset_coverage_artifact"] = str(claimset_coverage_path)
            bootstrap_meta["claimset_coverage_page_coverage_ratio"] = (
                claimset_coverage.metrics.page_coverage_ratio
            )
            bootstrap_meta["claimset_coverage_missing_topic_signal_count"] = (
                claimset_coverage.metrics.missing_topic_signal_count
            )
            if run_meta is not None:
                run_meta["claimset_coverage"] = {
                    "status": claimset_coverage.coverage_status,
                    "artifact": str(claimset_coverage_path),
                    "page_coverage_ratio": claimset_coverage.metrics.page_coverage_ratio,
                    "missing_topic_signal_count": claimset_coverage.metrics.missing_topic_signal_count,
                }
        except Exception as exc:
            logger.warning("Failed to build claimset_coverage sidecar: %s", exc)
            bootstrap_meta["artifact_claimset_coverage_written"] = False
            bootstrap_meta["claimset_coverage_error"] = str(exc)
        coverage_focus = None
        bootstrap_meta["artifact_claimset_coverage_focus_written"] = False
        if claimset_coverage is not None and claimset_coverage.coverage_status in {"warn", "fail"}:
            try:
                focus_claimset = reader_agent.analyze_coverage_focus(
                    doc_artifact,
                    coverage=claimset_coverage,
                    existing_claimset=resolved_claim_set,
                )
                resolved_focus_claimset = resolve_claimset_grounding(
                    focus_claimset,
                    index_artifact,
                    document_artifact=doc_artifact if isinstance(doc_artifact, DocumentArtifactV2) else None,
                )
                coverage_focus_metrics = dict(getattr(reader_agent, "last_coverage_focus_metrics", {}) or {})
                coverage_focus_metric_status = str(coverage_focus_metrics.get("status") or "").strip()
                coverage_focus_status = "generated"
                if coverage_focus_metric_status.startswith("skipped"):
                    coverage_focus_status = "skipped"
                elif coverage_focus_metric_status == "parse_failed":
                    coverage_focus_status = "error"
                coverage_focus = build_claimset_coverage_focus_sidecar(
                    paper_id=paper_id,
                    run_id=run_id,
                    coverage=claimset_coverage,
                    candidate_claimset=resolved_focus_claimset,
                    focus_status=coverage_focus_status,
                    reason=coverage_focus_metric_status or None,
                )
                coverage_focus_path = write_claimset_coverage_focus_sidecar(coverage_focus, artifact_dir)
                bootstrap_meta["artifact_claimset_coverage_focus_written"] = True
                bootstrap_meta["claimset_coverage_focus_artifact"] = str(coverage_focus_path)
                bootstrap_meta["claimset_coverage_focus_status"] = coverage_focus.focus_status
                bootstrap_meta["claimset_coverage_focus_claim_count"] = coverage_focus.metrics.generated_claim_count
                if run_meta is not None:
                    run_meta["claimset_coverage_focus"] = {
                        "status": coverage_focus.focus_status,
                        "artifact": str(coverage_focus_path),
                        "generated_claim_count": coverage_focus.metrics.generated_claim_count,
                        "target_count": coverage_focus.metrics.target_count,
                    }
                    run_meta["coverage_focus_analysis"] = coverage_focus_metrics
            except Exception as exc:
                logger.warning("Failed to build claimset_coverage_focus sidecar: %s", exc)
                bootstrap_meta["claimset_coverage_focus_status"] = "error"
                bootstrap_meta["claimset_coverage_focus_error"] = str(exc)
                try:
                    coverage_focus = build_claimset_coverage_focus_sidecar(
                        paper_id=paper_id,
                        run_id=run_id,
                        coverage=claimset_coverage,
                        focus_status="error",
                        reason=str(exc),
                    )
                    coverage_focus_path = write_claimset_coverage_focus_sidecar(coverage_focus, artifact_dir)
                    bootstrap_meta["artifact_claimset_coverage_focus_written"] = True
                    bootstrap_meta["claimset_coverage_focus_artifact"] = str(coverage_focus_path)
                    if run_meta is not None:
                        run_meta["claimset_coverage_focus"] = {
                            "status": coverage_focus.focus_status,
                            "artifact": str(coverage_focus_path),
                            "generated_claim_count": coverage_focus.metrics.generated_claim_count,
                            "target_count": coverage_focus.metrics.target_count,
                        }
                except Exception as sidecar_exc:
                    logger.warning("Failed to write claimset_coverage_focus error sidecar: %s", sidecar_exc)
                    bootstrap_meta["artifact_claimset_coverage_focus_written"] = False
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
            bootstrap_meta["reader_eval_bbox_span_count"] = reader_eval.metrics.bbox_span_count
            bootstrap_meta["reader_eval_text_match_span_count"] = reader_eval.metrics.text_match_span_count
            bootstrap_meta["reader_eval_approx_span_count"] = reader_eval.metrics.approx_span_count
            bootstrap_meta["reader_eval_unresolved_span_count"] = reader_eval.metrics.unresolved_span_count
            bootstrap_meta["reader_eval_ambiguous_span_count"] = reader_eval.metrics.ambiguous_span_count
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

        bootstrap_meta["artifact_evidence_extraction_bundle_written"] = False
        try:
            evidence_extraction_bundle = build_evidence_extraction_bundle(
                paper_id=paper_id,
                run_id=run_id,
                resolved_claimset=resolved_claim_set,
                clinical_extraction=clinical_extraction,
            )
            evidence_extraction_path = write_evidence_extraction_bundle(evidence_extraction_bundle, artifact_dir)
            bootstrap_meta["artifact_evidence_extraction_bundle_written"] = True
            bootstrap_meta["evidence_extraction_record_count"] = evidence_extraction_bundle.metrics.record_count
            bootstrap_meta["evidence_extraction_claim_record_count"] = (
                evidence_extraction_bundle.metrics.claim_record_count
            )
            bootstrap_meta["evidence_extraction_clinical_field_record_count"] = (
                evidence_extraction_bundle.metrics.clinical_field_record_count
            )
            bootstrap_meta["evidence_extraction_evidence_ref_count"] = (
                evidence_extraction_bundle.metrics.evidence_ref_count
            )
            if run_meta is not None:
                run_meta["evidence_extraction_bundle"] = {
                    "path": str(evidence_extraction_path),
                    "record_count": evidence_extraction_bundle.metrics.record_count,
                    "claim_record_count": evidence_extraction_bundle.metrics.claim_record_count,
                    "clinical_field_record_count": evidence_extraction_bundle.metrics.clinical_field_record_count,
                }
        except Exception as exc:
            logger.warning("Failed to build evidence_extraction bundle: %s", exc)
        _write_bootstrap_meta(artifact_dir, bootstrap_meta)
            
        await emit("read", 75, f"Extracted {len(claim_set.claims)} claims")
        _record_stage_timing(reader_timer)

        # 5. Verify (Optional)
        if run_verify:
            if await is_cancelled():
                _mark_run_meta("cancelled")
                return _job_result("cancelled")
            verify_timer = StageTimer("verify")
            verify_timer.__enter__()
            await emit("verify", 80, "Stats Verification Agent running...")
            try:
                if StatsVerificationAgent is None:
                    raise RuntimeError(
                        "Stats verification unavailable because optional verifier dependencies are missing: "
                        f"{_STATS_AGENT_IMPORT_ERROR}"
                    )
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
                atomic_write_text(
                    artifact_dir / "stats_report.json",
                    stats_report.model_dump_json(indent=2),
                )
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
                try:
                    stats_fallback_eval = build_stats_fallback_eval_sidecar(
                        paper_id=paper_id,
                        stats_report=stats_report,
                        bootstrap_meta=bootstrap_meta,
                    )
                    write_stats_fallback_eval_sidecar(stats_fallback_eval, artifact_dir)
                    bootstrap_meta["artifact_stats_fallback_eval_written"] = True
                    bootstrap_meta["stats_fallback_eval_check_count"] = stats_fallback_eval.metrics.check_count
                    bootstrap_meta["stats_fallback_eval_unverifiable_count"] = (
                        stats_fallback_eval.metrics.unverifiable_count
                    )
                    bootstrap_meta["stats_fallback_eval_auto_fallback_count"] = (
                        stats_fallback_eval.metrics.auto_fallback_count
                    )
                except Exception as exc:
                    logger.warning("Failed to build stats_fallback_eval sidecar: %s", exc)
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
            _record_stage_timing(verify_timer)

        # 6. Complete
        _mark_run_meta("succeeded")
        try:
            handoff_artifacts = write_deepread_handoff_artifacts(
                artifact_dir,
                paper_id=paper_id,
                run_id=run_id,
                run_meta=run_meta or {},
                bootstrap_meta=bootstrap_meta,
            )
            bootstrap_meta["artifact_acceptance_contract_written"] = True
            bootstrap_meta["artifact_quality_gate_written"] = True
            _write_bootstrap_meta(artifact_dir, bootstrap_meta)
            if run_meta is not None:
                run_meta["handoff_artifacts"] = handoff_artifacts
                run_meta["updated_at"] = datetime.now(timezone.utc).isoformat()
                _write_run_meta(artifact_dir, run_meta)
        except Exception as handoff_err:
            logger.warning("Failed to write deep-read handoff pilot artifacts: %s", handoff_err)

        # Best-effort note upsert (non-fatal): keep runtime fail-safe.
        try:
            if note_path is None:
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
                clinical_md = (
                    build_clinical_extraction_markdown(clinical_extraction)
                    if is_clinical_note and clinical_extraction is not None
                    else ""
                )
                deepread_md = build_deepread_markdown(
                    model_name=getattr(reader_agent, "model_name", "reader"),
                    claims_set=resolved_claim_set,
                    stats_md=stats_md,
                    clinical_md=clinical_md,
                    coverage=claimset_coverage,
                    visual_evidence=visual_evidence_ledger,
                    coverage_focus=coverage_focus,
                )
                note_content = note_path.read_text(encoding="utf-8")
                note_updated = upsert_deepread_section(note_content, deepread_md)
                atomic_write_text(note_path, note_updated)
                await emit("read", 78, f"Deep Read section upserted: {note_path.name}")
        except Exception as note_err:
            await emit("read", 78, f"Deep Read note upsert skipped: {note_err}", level="WARNING")

        if _mark_paper_deepread_indexed(paper_id):
            await emit("completed", 98, "Paper status updated: INDEXED")

        await emit("completed", 100, "Pipeline Completed Successfully")
        return _job_result("succeeded")

    except Exception as e:
        safe_error = sanitize_event_text_for_log(str(e)) or type(e).__name__
        logger.error("Job Failed: %s", safe_error)
        _mark_run_meta("failed", error=safe_error, error_type=type(e).__name__)
        if artifact_dir is not None and bootstrap_meta is not None:
            bootstrap_meta["claimset_readiness"] = "unknown"
            bootstrap_meta["claimset_ready"] = None
            bootstrap_meta["claimset_readiness_reason"] = "runtime_error"
            bootstrap_meta["claimset_readiness_badge"] = "UNKNOWN"
            bootstrap_meta["claimset_ops_action"] = "retry_suggested"
            bootstrap_meta["claimset_ops_alert"] = True
            bootstrap_meta["claimset_ops_note"] = f"runtime_error:{type(e).__name__}"
            bootstrap_meta["artifact_acceptance_contract_written"] = False
            bootstrap_meta["artifact_quality_gate_written"] = False
            _write_bootstrap_meta(artifact_dir, bootstrap_meta)
            if run_meta is not None:
                try:
                    handoff_artifacts = write_deepread_handoff_artifacts(
                        artifact_dir,
                        paper_id=paper_id,
                        run_id=run_id,
                        run_meta=run_meta,
                        bootstrap_meta=bootstrap_meta,
                    )
                    bootstrap_meta["artifact_acceptance_contract_written"] = True
                    bootstrap_meta["artifact_quality_gate_written"] = True
                    _write_bootstrap_meta(artifact_dir, bootstrap_meta)
                    run_meta["handoff_artifacts"] = handoff_artifacts
                    run_meta["updated_at"] = datetime.now(timezone.utc).isoformat()
                    _write_run_meta(artifact_dir, run_meta)
                except Exception as handoff_err:
                    safe_handoff_error = sanitize_event_text_for_log(str(handoff_err)) or type(handoff_err).__name__
                    logger.warning("Failed to write deep-read failure handoff artifacts: %s", safe_handoff_error)
                    try:
                        bootstrap_meta["handoff_write_error"] = safe_handoff_error
                        bootstrap_meta["artifact_acceptance_contract_written"] = False
                        bootstrap_meta["artifact_quality_gate_written"] = False
                        _write_bootstrap_meta(artifact_dir, bootstrap_meta)
                        run_meta["handoff_write_error"] = safe_handoff_error
                        run_meta["updated_at"] = datetime.now(timezone.utc).isoformat()
                        _write_run_meta(artifact_dir, run_meta)
                    except Exception as handoff_meta_err:
                        logger.warning(
                            "Failed to record deep-read failure handoff error metadata: %s",
                            sanitize_event_text_for_log(str(handoff_meta_err)) or type(handoff_meta_err).__name__,
                        )
        await emit("error", 0, safe_error, level="ERROR")
        return _job_result("failed", error=safe_error)
