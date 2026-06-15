import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime
import json
import argparse
from pypdf import PdfReader

from src.config import load_config, AppConfig, resolve_clinical_extraction_feature
from src.llm_provider import get_llm_provider, LLMProvider
from src.fetch import get_fetchers
from src.gates import GateEngine
from src.schemas.gates import GateDecision, ReasonCode
from src.db_utils import (
    sync_zotero_to_db, 
    get_papers_by_status, 
    update_paper_status,
    is_paper_processed,
    save_paper_state,
    mark_as_retracted,
)
from src.schemas import BiomedicalClinicalExtraction, Paper, PaperStatus, PaperTagging
from src.obsidian import save_paper_to_obsidian
from src.pdf import extract_text_from_pdf
from src.downloader import download_paper
from src.services.intake_override_log import build_intake_override_log, merge_feedback_json_with_intake_override
from src.services.runtime_paths import zotero_export_path
from src.zotero import export_to_ris
from src.retraction import check_retraction

logger = logging.getLogger(__name__)

# --- State Constants ---
STATE_NEW = "NEW"
STATE_FETCHED = "FETCHED"
STATE_PDF_MISSING = "PDF_MISSING"
STATE_GATED = "GATED"
STATE_APPROVED = "APPROVED"
STATE_QUARANTINED = "QUARANTINED"
STATE_PENDING = "PENDING_REVIEW"
STATE_INDEXED = "INDEXED"
STATE_FAILED = "FAILED"


@dataclass
class GatePersistenceOutcome:
    status: str
    updates: Dict[str, Any]
    analysis_available: bool


def derive_saved_issues_state(processing_status: PaperStatus | str, *, analysis_available: bool) -> str:
    """Map producer-owned processing results to content-review state for persisted paper rows."""
    if not analysis_available:
        return "unavailable"

    status_value = processing_status.value if isinstance(processing_status, PaperStatus) else str(processing_status)
    normalized = status_value.strip().upper()
    if normalized in {PaperStatus.APPROVED.value, PaperStatus.INDEXED.value}:
        return "clear"
    if normalized in {
        PaperStatus.PENDING_REVIEW.value,
        PaperStatus.QUARANTINED.value,
        PaperStatus.FAILED.value,
    }:
        return "flagged"
    return "unavailable"


def last_consecutive_failures(current_streak, success_count, failure_count):
    """Updates the consecutive failure streak"""
    if success_count > 0:
        return 0 
    return current_streak + failure_count


def _warn_failure_threshold_once(step_name: str, consecutive_failures: int, threshold: int) -> None:
    if consecutive_failures == threshold:
        logger.warning(
            "Consecutive failure threshold reached after %s (%s/%s); "
            "failed rows were isolated as FAILED and processor is continuing remaining eligible stages.",
            step_name,
            consecutive_failures,
            threshold,
        )


def _merge_feedback_json_payload(feedback_json: str | None, extra_payload: Dict[str, Any]) -> str:
    if feedback_json:
        try:
            parsed = json.loads(feedback_json)
        except Exception as exc:
            logger.warning(
                "Failed to parse feedback_json payload during merge; preserving raw payload: %s",
                exc,
                exc_info=True,
            )
            payload: Dict[str, Any] = {"raw_feedback_json": str(feedback_json)}
        else:
            payload = parsed if isinstance(parsed, dict) else {"raw_feedback_json": feedback_json}
    else:
        payload = {}
    payload.update(extra_payload)
    return json.dumps(payload, ensure_ascii=False)


def _feedback_json_from_tagging(tag_payload: Dict[str, Any] | None, *, confidence: float, soft_tags: list[str]) -> str:
    payload: Dict[str, Any] = dict(tag_payload) if isinstance(tag_payload, dict) else {}

    raw_soft_tags = payload.get("soft_tags", soft_tags)
    if isinstance(raw_soft_tags, list):
        payload["soft_tags"] = [str(tag) for tag in raw_soft_tags if str(tag).strip()]
    else:
        payload["soft_tags"] = []

    if not isinstance(payload.get("hard_tags"), dict):
        payload["hard_tags"] = {}

    try:
        payload["confidence"] = float(payload.get("confidence", confidence) or 0.0)
    except (TypeError, ValueError):
        payload["confidence"] = float(confidence or 0.0)

    return json.dumps(payload, ensure_ascii=False)


def _normalized_reason_codes(raw_codes: Any) -> list[str]:
    if not isinstance(raw_codes, list):
        return []
    out: list[str] = []
    for code in raw_codes:
        text = str(code or "").strip()
        if not text:
            continue
        out.append(text)
    return out


def _build_escalation_sidecar(result: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "approved": bool(result.get("approved", False)),
        "reason": str(result.get("reason") or ""),
        "final_route": str(result.get("final_route") or ""),
        "in_biomedical_scope": result.get("in_biomedical_scope")
        if isinstance(result.get("in_biomedical_scope"), bool)
        else None,
        "reason_codes": _normalized_reason_codes(result.get("reason_codes")),
    }


def _merge_reason_code_lists(*groups: list[str]) -> list[str]:
    merged: list[str] = []
    for group in groups:
        for code in group:
            text = str(code or "").strip()
            if not text or text in merged:
                continue
            merged.append(text)
    return merged


def _coerce_optional_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _coerce_optional_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        text = value.strip()
        if text and text.lstrip("-").isdigit():
            return int(text)
    return None


def build_gate_persistence_outcome(
    row: Dict[str, Any],
    *,
    gate_engine: GateEngine,
    llm_provider: Optional[LLMProvider] = None,
    producer: str = "processor_gate",
    allow_escalation: bool = True,
) -> GatePersistenceOutcome:
    confidence = row.get("confidence", 0.0)
    parse_ok = True
    schema_ok = True
    analysis: Dict[str, Any] = {}
    feedback_json = row.get("feedback_json")
    if feedback_json:
        try:
            parsed = json.loads(feedback_json)
            if isinstance(parsed, dict):
                analysis = parsed
            else:
                logger.warning(
                    "feedback_json for %s parsed as %s, expected object",
                    row.get("paper_id"),
                    type(parsed).__name__,
                )
                parse_ok = False
        except Exception as exc:
            logger.warning(
                "Failed to parse feedback_json for %s during gate evaluation: %s",
                row.get("paper_id"),
                exc,
                exc_info=True,
            )
            parse_ok = False

    analysis.setdefault("confidence", confidence)
    analysis.setdefault("soft_tags", [])
    analysis.setdefault("hard_tags", {})

    if parse_ok:
        try:
            PaperTagging.model_validate(analysis)
        except Exception as exc:
            logger.warning(
                "feedback_json schema validation failed for %s during gate evaluation: %s",
                row.get("paper_id"),
                exc,
                exc_info=True,
            )
            schema_ok = False

    gate_result = gate_engine.evaluate(analysis, parse_ok=parse_ok, schema_ok=schema_ok)
    base_reason_codes = [rc.value for rc in gate_result.reason_codes]

    status_map = {
        GateDecision.APPROVED: STATE_APPROVED,
        GateDecision.PENDING_REVIEW: STATE_PENDING,
        GateDecision.QUARANTINED: STATE_QUARANTINED,
        GateDecision.FAILED: STATE_FAILED,
    }
    status = status_map[gate_result.decision]
    decision = gate_result.decision.value
    merged_reason_codes = list(base_reason_codes)
    updates: Dict[str, Any] = {}

    if allow_escalation and gate_result.decision == GateDecision.PENDING_REVIEW:
        llm = llm_provider
        evaluate_escalation = getattr(llm, "evaluate_escalation", None) if llm else None
        if callable(evaluate_escalation):
            try:
                escalation_result = evaluate_escalation(
                    {
                        "paper_id": row.get("paper_id"),
                        "title": row.get("title"),
                        "summary": row.get("summary"),
                        "link": row.get("link"),
                        "doi": row.get("doi") or row.get("paper_id"),
                        "authors": row.get("authors"),
                        "published": row.get("published"),
                        "source": row.get("source"),
                        "slot": row.get("slot"),
                        "tags": analysis.get("soft_tags", []),
                    }
                )
                if isinstance(escalation_result, dict):
                    escalation_sidecar = _build_escalation_sidecar(escalation_result)
                    merged_reason_codes = _merge_reason_code_lists(
                        base_reason_codes,
                        escalation_sidecar["reason_codes"],
                    )
                    updates["feedback_json"] = _merge_feedback_json_payload(
                        feedback_json,
                        {"escalation": escalation_sidecar},
                    )
                    if escalation_sidecar["approved"]:
                        status = STATE_APPROVED
                        decision = GateDecision.APPROVED.value
            except Exception as exc:
                logger.warning("Escalation evaluation failed for %s: %s", row.get("paper_id"), exc, exc_info=True)

    analysis_available = parse_ok and schema_ok
    stored_tags = analysis.get("soft_tags", []) if isinstance(analysis.get("soft_tags"), list) else []
    issues_state = derive_saved_issues_state(
        status,
        analysis_available=analysis_available,
    )
    intake_override_log = build_intake_override_log(
        producer=producer,
        analysis_available=analysis_available,
        llm_tagging_used=bool(feedback_json),
        llm_slot_classification_used=False,
        input_slot=row.get("slot"),
        stored_slot=row.get("slot"),
        input_tags=stored_tags,
        stored_tags=stored_tags,
        processing_status=status,
        issues_state=issues_state,
        confidence=_coerce_optional_float(analysis.get("confidence", confidence)),
    )
    updates["feedback_json"] = merge_feedback_json_with_intake_override(
        updates.get("feedback_json", feedback_json),
        intake_override_log,
    )

    reason = ",".join(merged_reason_codes) or "NONE"
    updates.update(
        {
            "gate_decision": decision,
            "gate_reason": reason,
        }
    )
    return GatePersistenceOutcome(
        status=status,
        updates=updates,
        analysis_available=analysis_available,
    )


def _normalized_fetcher_source(fetcher: Any) -> str:
    raw_name = getattr(fetcher, "source_name", None)
    if callable(raw_name):
        try:
            raw_name = raw_name()
        except Exception as exc:
            logger.debug("Fetcher source_name() failed; using fallback source: %s", exc, exc_info=True)
            raw_name = None
    if raw_name is None:
        raw_name = getattr(fetcher, "source", None)
    text = str(raw_name or "").strip().lower()
    if "pubmed" in text:
        return "pubmed"
    if "arxiv" in text:
        return "arxiv"
    return text or "unknown"


def _normalized_slot_source(slot_cfg: Any) -> str:
    raw_source = getattr(slot_cfg, "source", "all")
    source = str(raw_source or "all").strip().lower()
    if source in {"pubmed", "arxiv", "all"}:
        return source
    return "all"


def _candidate_identity(paper: Any) -> tuple[str, str]:
    preferred = (
        getattr(paper, "doi", None),
        getattr(paper, "id", None),
        getattr(paper, "link", None),
    )
    for value in preferred:
        text = str(value or "").strip().lower()
        if text:
            return ("primary", text)

    title = str(getattr(paper, "title", "") or "").strip().lower()
    published = str(getattr(paper, "published", "") or "").strip().lower()
    return ("fallback", f"{title}::{published}")


def _dedupe_candidates(papers: List[Any]) -> List[Any]:
    deduped: List[Any] = []
    seen: set[tuple[str, str]] = set()
    for paper in papers:
        identity = _candidate_identity(paper)
        if identity in seen:
            continue
        seen.add(identity)
        deduped.append(paper)
    return deduped


def _select_slot_fetchers(fetchers: List[Any], slot_source: str) -> List[Any]:
    if slot_source == "all":
        return list(fetchers)
    return [fetcher for fetcher in fetchers if _normalized_fetcher_source(fetcher) == slot_source]


def _slot_candidate_budgets(config: AppConfig, slot_source: str) -> tuple[int | None, int | None]:
    constraints = getattr(getattr(config, "search", None), "constraints", None)
    if constraints is None:
        return None, None

    min_pubmed = _coerce_optional_int(getattr(constraints, "min_pubmed", None))
    if min_pubmed is not None:
        min_pubmed = max(0, min_pubmed)

    max_preprint = _coerce_optional_int(getattr(constraints, "max_preprint", None))
    if max_preprint is not None:
        max_preprint = max(0, max_preprint)

    if slot_source == "pubmed":
        return None, None
    if slot_source == "arxiv":
        return None, max_preprint
    return min_pubmed, max_preprint


def _fetch_slot_candidates(
    slot_cfg: Any,
    fetchers: List[Any],
    config: AppConfig,
) -> List[Any]:
    query = getattr(slot_cfg, "query", "")
    slot_source = _normalized_slot_source(slot_cfg)
    selected_fetchers = _select_slot_fetchers(fetchers, slot_source)
    pubmed_candidates: List[Any] = []
    preprint_candidates: List[Any] = []
    other_candidates: List[Any] = []

    for fetcher in selected_fetchers:
        try:
            fetched = fetcher.fetch(query, max_results=5)
        except TypeError:
            fetched = fetcher.fetch(query=query, max_results=5)

        normalized_source = _normalized_fetcher_source(fetcher)
        if normalized_source == "pubmed":
            pubmed_candidates.extend(fetched)
        elif normalized_source == "arxiv":
            preprint_candidates.extend(fetched)
        else:
            other_candidates.extend(fetched)

    pubmed_candidates = _dedupe_candidates(pubmed_candidates)
    preprint_candidates = _dedupe_candidates(preprint_candidates)
    other_candidates = _dedupe_candidates(other_candidates)
    pubmed_budget, preprint_budget = _slot_candidate_budgets(config, slot_source)

    selected: List[Any] = []
    if slot_source == "pubmed":
        selected.extend(pubmed_candidates[:pubmed_budget] if pubmed_budget is not None else pubmed_candidates)
    elif slot_source == "arxiv":
        selected.extend(preprint_candidates[:preprint_budget] if preprint_budget is not None else preprint_candidates)
    else:
        selected.extend(pubmed_candidates[:pubmed_budget] if pubmed_budget is not None else pubmed_candidates)
        selected.extend(preprint_candidates[:preprint_budget] if preprint_budget is not None else preprint_candidates)
        selected.extend(other_candidates)

    return _dedupe_candidates(selected)


def _published_timestamp(paper: Any) -> float:
    raw_value = str(getattr(paper, "published", "") or "").strip()
    if not raw_value:
        return 0.0
    for fmt in ("%Y-%m-%d", "%Y-%m", "%Y"):
        try:
            return datetime.strptime(raw_value, fmt).timestamp()
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(raw_value).timestamp()
    except ValueError:
        return 0.0


def _selection_source_bonus(slot_name: str, paper: Any) -> float:
    source = str(getattr(paper, "source", "") or "").strip().lower()
    normalized_slot = str(slot_name or "").strip().lower()
    if "pubmed" in source:
        return 0.25 if normalized_slot == "clinical" else 0.18
    if "arxiv" in source:
        return 0.04 if normalized_slot == "clinical" else 0.08
    return 0.06


def _selection_metadata_components(paper: Any) -> Dict[str, float]:
    doi_bonus = 0.08 if getattr(paper, "doi", None) else 0.0
    pdf_bonus = 0.07 if getattr(paper, "pdf_link", None) or getattr(paper, "local_pdf_path", None) else 0.0

    published_ts = _published_timestamp(paper)
    if published_ts <= 0:
        return {
            "doi_bonus": round(doi_bonus, 3),
            "pdf_bonus": round(pdf_bonus, 3),
            "recency_bonus": 0.0,
            "total": round(doi_bonus + pdf_bonus, 3),
        }

    age_days = max(0.0, (datetime.now().timestamp() - published_ts) / 86400.0)
    recency_bonus = 0.0
    if age_days <= 14:
        recency_bonus = 0.15
    elif age_days <= 60:
        recency_bonus = 0.10
    elif age_days <= 180:
        recency_bonus = 0.05

    total = doi_bonus + pdf_bonus + recency_bonus
    return {
        "doi_bonus": round(doi_bonus, 3),
        "pdf_bonus": round(pdf_bonus, 3),
        "recency_bonus": round(recency_bonus, 3),
        "total": round(total, 3),
    }


def _set_candidate_manual_score(paper: Any, score: float) -> None:
    try:
        setattr(paper, "manual_rank_score", round(float(score), 3))
    except Exception as exc:
        logger.debug("Failed to set candidate manual score on %r: %s", paper, exc, exc_info=True)


def _apply_optional_bibliometric_scores(candidates: List[Any], config: AppConfig) -> List[Any]:
    ranking = getattr(config, "ranking", None)
    bibliometrics = getattr(ranking, "bibliometrics", None)
    if not getattr(bibliometrics, "enabled", False):
        return candidates

    if not candidates or not all(isinstance(candidate, Paper) for candidate in candidates):
        return candidates

    try:
        from src.ranking import BibliometricScorer

        scorer = BibliometricScorer(config)
        return scorer.calculate_scores(list(candidates))
    except Exception as exc:
        logger.warning("Bibliometric scoring failed for daily slot candidates: %s", exc, exc_info=True)
        return candidates


def _rank_slot_candidates(slot_name: str, candidates: List[Any], config: AppConfig) -> List[Any]:
    ranked = list(_apply_optional_bibliometric_scores(candidates, config))

    for paper in ranked:
        base_score = _coerce_optional_float(getattr(paper, "manual_rank_score", None)) or 0.0
        metadata_components = _selection_metadata_components(paper)
        final_score = base_score + _selection_source_bonus(slot_name, paper) + metadata_components["total"]
        _set_candidate_manual_score(paper, final_score)

    indexed_ranked = list(enumerate(ranked))
    indexed_ranked.sort(
        key=lambda item: (
            -(_coerce_optional_float(getattr(item[1], "manual_rank_score", None)) or 0.0),
            -_published_timestamp(item[1]),
            item[0],
        ),
    )
    return [paper for _, paper in indexed_ranked]


def _select_slot_representative(slot_name: str, candidates: List[Any], config: AppConfig) -> List[Any]:
    if not candidates:
        return []
    ranked = _rank_slot_candidates(slot_name, candidates, config)
    return ranked


def _selection_constraints_summary(config: AppConfig, slot_source: str) -> Dict[str, Any]:
    constraints = getattr(getattr(config, "search", None), "constraints", None)
    pubmed_budget, preprint_budget = _slot_candidate_budgets(config, slot_source)
    return {
        "slot_source": slot_source,
        "min_pubmed": _coerce_optional_int(getattr(constraints, "min_pubmed", None)) if constraints is not None else None,
        "max_preprint": _coerce_optional_int(getattr(constraints, "max_preprint", None)) if constraints is not None else None,
        "applied_pubmed_budget": pubmed_budget,
        "applied_preprint_budget": preprint_budget,
    }


def _candidate_selection_breakdown(slot_name: str, paper: Any) -> Dict[str, Any]:
    source_bonus = round(_selection_source_bonus(slot_name, paper), 3)
    metadata_components = _selection_metadata_components(paper)
    final_score = round(_coerce_optional_float(getattr(paper, "manual_rank_score", None)) or 0.0, 3)
    base_score = round(final_score - source_bonus - float(metadata_components["total"]), 3)
    return {
        "base_score": base_score,
        "source_bonus": source_bonus,
        "metadata_bonus": metadata_components["total"],
        "metadata_components": metadata_components,
        "final_score": final_score,
    }


def _build_slot_selection_rationale(
    slot_name: str,
    slot_cfg: Any,
    ranked_candidates: List[Any],
    selected_paper: Any,
    config: AppConfig,
    skipped_processed_ids: List[str],
) -> Dict[str, Any]:
    slot_source = _normalized_slot_source(slot_cfg)
    selected_identity = _candidate_identity(selected_paper)
    selected_rank = 1
    source_counts: Dict[str, int] = {}
    top_candidates: List[Dict[str, Any]] = []

    for index, candidate in enumerate(ranked_candidates, start=1):
        normalized_source = _normalized_fetcher_source(candidate)
        source_counts[normalized_source] = source_counts.get(normalized_source, 0) + 1
        if index <= 3:
            top_candidates.append(
                {
                    "rank": index,
                    "paper_id": str(getattr(candidate, "id", "") or ""),
                    "title": str(getattr(candidate, "title", "") or ""),
                    "score": round(_coerce_optional_float(getattr(candidate, "manual_rank_score", None)) or 0.0, 3),
                    "score_breakdown": _candidate_selection_breakdown(slot_name, candidate),
                    "source": str(getattr(candidate, "source", "") or ""),
                    "published": str(getattr(candidate, "published", "") or ""),
                }
            )
        if _candidate_identity(candidate) == selected_identity:
            selected_rank = index

    return {
        "method": "daily_slot_rank_v1",
        "slot": slot_name,
        "candidate_count": len(ranked_candidates),
        "selected_rank": selected_rank,
        "selected_paper_id": str(getattr(selected_paper, "id", "") or ""),
        "selected_manual_rank_score": round(
            _coerce_optional_float(getattr(selected_paper, "manual_rank_score", None)) or 0.0,
            3,
        ),
        "selected_score_breakdown": _candidate_selection_breakdown(slot_name, selected_paper),
        "skipped_processed_candidates": skipped_processed_ids,
        "constraints": _selection_constraints_summary(config, slot_source),
        "source_counts": source_counts,
        "top_candidates": top_candidates,
    }

class PaperProcessor:
    def __init__(self):
        self.config = load_config()
        self.llm_provider = get_llm_provider(self.config.llm, self.config.entity_aliases)
        self.gate_engine = GateEngine(
            high_threshold=self.config.confidence_thresholds.high,
            low_threshold=self.config.confidence_thresholds.low,
            require_evidence=True,
        )
        self.upload_dir = Path(self.config.paths.upload_dir) if self.config.paths.upload_dir else None
        
        # Ensure directories
        if self.upload_dir:
            self.upload_dir.mkdir(parents=True, exist_ok=True)
            
    def run(self, batch_size: int = 5):
        """
        Main State Machine Loop.
        Processes papers through steps: Sync -> Fetch -> Analyze -> Gate -> Index.
        Safety: Limited batch size to prevent API cost explosions.
        Stops if too many consecutive failures occur.
        """
        logger.info(f"🚀 Starting PaperProcessor Run (Batch Limit: {batch_size})")
        
        # Step 0: Sync Zotero
        zotero_path = zotero_export_path()
        if zotero_path.exists():
            sync_zotero_to_db(zotero_path)
            
        remaining_budget = batch_size
        consecutive_failures = 0
        MAX_CONSECUTIVE_FAILURES = 3
        
        while remaining_budget > 0:
            progress_made = False
            
            # Step 4: Finalize (APPROVED -> INDEXED)
            if remaining_budget > 0:
                candidates = get_papers_by_status([STATE_APPROVED], limit=remaining_budget)
                processed, failed = self._process_step(candidates, self._step_finalize)
                remaining_budget -= processed
                consecutive_failures = last_consecutive_failures(consecutive_failures, processed, failed)
                if processed > 0:
                    progress_made = True
                if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                    _warn_failure_threshold_once("finalize", consecutive_failures, MAX_CONSECUTIVE_FAILURES)
                
            # Step 3: Gate (GATED -> APPROVED/...)
            if remaining_budget > 0:
                candidates = get_papers_by_status([STATE_GATED], limit=remaining_budget)
                processed, failed = self._process_step(candidates, self._step_gate)
                remaining_budget -= processed
                consecutive_failures = last_consecutive_failures(consecutive_failures, processed, failed)
                if processed > 0:
                    progress_made = True
                if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                    _warn_failure_threshold_once("gate", consecutive_failures, MAX_CONSECUTIVE_FAILURES)

            # Step 2: Analyze (FETCHED -> GATED)
            if remaining_budget > 0:
                candidates = get_papers_by_status([STATE_FETCHED], limit=remaining_budget)
                processed, failed = self._process_step(candidates, self._step_analyze)
                remaining_budget -= processed
                consecutive_failures = last_consecutive_failures(consecutive_failures, processed, failed)
                if processed > 0:
                    progress_made = True
                if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                    _warn_failure_threshold_once("analyze", consecutive_failures, MAX_CONSECUTIVE_FAILURES)
                
            # Step 1: Fetch (NEW -> FETCHED)
            if remaining_budget > 0:
                candidates = get_papers_by_status([STATE_NEW], limit=remaining_budget)
                processed, failed = self._process_step(candidates, self._step_fetch)
                remaining_budget -= processed
                consecutive_failures = last_consecutive_failures(consecutive_failures, processed, failed)
                if processed > 0:
                    progress_made = True
                if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                    _warn_failure_threshold_once("fetch", consecutive_failures, MAX_CONSECUTIVE_FAILURES)
            
            if not progress_made:
                break
                
            if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                logger.warning("Ending processor run after completing eligible stages with consecutive failures.")
                break
            
        logger.info(f"🏁 Run Complete. Actions consumed: {batch_size - remaining_budget}/{batch_size}")

    def _process_step(self, papers: List[Dict], handler) -> tuple[int, int]:
        """
        Helper to process a batch of papers with error isolation.
        Returns (success_count, failure_count)
        """
        success = 0
        failure = 0
        for paper_row in papers:
            if not paper_row:
                continue
            pid = paper_row['paper_id']
            try:
                handler(paper_row)
                success += 1
            except Exception as e:
                logger.error(f"❌ Error processing {pid} in {handler.__name__}: {e}", exc_info=True)
                update_paper_status(pid, STATE_FAILED, {"feedback_json": f"Error: {str(e)}"})
                failure += 1
        return success, failure

    # --- Step Handlers ---

    def _step_fetch(self, row: Dict):
        """Step 1: NEW -> FETCHED (Check PDF)"""
        pid = row['paper_id']
        pdf_path_str = row['pdf_path']
        logger.info(f"   [Step 1: Fetch] {pid}")
        
        final_pdf_path = None
        
        # 1. Check existing DB path
        if pdf_path_str:
            p = Path(pdf_path_str)
            if p.exists():
                final_pdf_path = p
        
        # 2. Check Library/ symlink standard
        if not final_pdf_path:
            lib_path = Path(f"Library/{pid}.pdf")
            if lib_path.exists():
                final_pdf_path = lib_path
                
        if final_pdf_path:
            # Update DB with verified path
            update_paper_status(pid, STATE_FETCHED, {"pdf_path": str(final_pdf_path)})
            logger.info(f"      -> Verified PDF at {final_pdf_path}")
        else:
            update_paper_status(pid, STATE_PDF_MISSING)
            logger.warning(f"      -> PDF Missing for {pid}")

    def _step_analyze(self, row: Dict):
        """Step 2: Analysis (FETCHED -> GATED)"""
        pid = row['paper_id']
        title = row['title']
        pdf_path = row['pdf_path']
        logger.info(f"   [Step 2: Analyze] {pid} ({title})")
        
        if not self.llm_provider or not self.llm_provider.is_available():
            raise RuntimeError("LLM Provider not available")
            
        # 1. Construct Paper object (minimal)
        summary = row.get('summary', '') or "Abstract not available."
        full_text = None

        if pdf_path:
            p = Path(pdf_path)
            if p.exists():
                logger.info(f"      -> Extracting text from PDF: {p.name}")
                full_text = extract_text_from_pdf(p, max_pages=5)
        
        paper_obj = {
            "title": title,
            "summary": summary,
            "full_text": full_text,
        }
        
        # 2. Run Hybrid Tagging (includes Confidence)
        logger.info("      -> Running Hybrid Tagging & Extraction...")
        tags_data = self.llm_provider.tag_paper(paper_obj)
        
        if not tags_data:
            raise ValueError("Tagging returned None")
            
        # 3. Save result to DB
        confidence = tags_data.get('confidence', 0.0)
        
        update_paper_status(pid, STATE_GATED, {
            "confidence": confidence,
            "feedback_json": json.dumps(tags_data) # Store analysis result here
        })
        logger.info(f"      -> Analysis Done. Confidence: {confidence}")

    def _step_gate(self, row: Dict):
        """Step 3: Gate (GATED -> APPROVED/QUARANTINED/PENDING)"""
        pid = row['paper_id']
        confidence = row.get('confidence', 0.0)
        logger.info(f"   [Step 3: Gate] {pid} (Conf: {confidence})")

        outcome = build_gate_persistence_outcome(
            row,
            gate_engine=self.gate_engine,
            llm_provider=self.llm_provider,
            producer="processor_gate",
            allow_escalation=True,
        )
        update_paper_status(pid, outcome.status, outcome.updates)
        logger.info(
            "      -> Gate Decision: %s (%s)",
            outcome.updates.get("gate_decision"),
            outcome.updates.get("gate_reason"),
        )

    def _step_finalize(self, row: Dict):
        """Step 4: Finalize (APPROVED -> INDEXED)"""
        pid = row['paper_id']
        logger.info(f"   [Step 4: Finalize] {pid}")
        
        # Placeholder for Embeddings / Vector DB
        
        # Also create Obsidian Note?
        feedback_json = row['feedback_json']
        if feedback_json:
            try:
                json.loads(feedback_json)
                # Construct result_dict for Obsidian (Mock)
                logger.info("      -> Prepared for Obsidian (Mock)")
            except Exception as e:
                logger.warning("      -> Failed to parse feedback_json for Obsidian: %s", e, exc_info=True)

        update_paper_status(pid, STATE_INDEXED)
        logger.info("      -> Status: INDEXED")


def process_paper(
    paper_data: Dict[str, Any],
    config: Optional[AppConfig] = None,
    llm_provider: Optional[LLMProvider] = None,
    is_deep_target: bool = False,
):
    """Compatibility shim used by legacy watcher/tests."""
    _ = is_deep_target
    _ = config
    _ = llm_provider
    return paper_data.get("paper")


def process_local_pdf(file_path: Path, config: Optional[AppConfig] = None):
    """Legacy entrypoint retained for backward compatibility."""
    cfg = config or load_config()
    title = file_path.stem
    try:
        reader = PdfReader(str(file_path))
        meta_title = (reader.metadata or {}).get("/Title")
        if meta_title:
            title = str(meta_title)
    except Exception as exc:
        logger.warning("Failed to read PDF metadata from %s: %s", file_path, exc, exc_info=True)

    paper = Paper(
        id=f"local--{int(time.time())}",
        title=title,
        authors=[],
        published=datetime.now().strftime("%Y-%m-%d"),
        source="local_pdf",
        summary="",
        link=f"file://{file_path.absolute()}",
        local_pdf_path=file_path,
    )
    return process_paper({"paper": paper}, config=cfg, llm_provider=None, is_deep_target=False)


def process_daily_slots(ignore_db: bool = False) -> List[Dict[str, Any]]:
    """Legacy batch pipeline used by older tests/scripts."""
    config = load_config()
    llm = get_llm_provider(config.llm, config.entity_aliases)
    analysis_available = bool(llm and llm.is_available())
    slots = getattr(config.search, "slots", {}) or {}
    fetchers = get_fetchers(config)
    results: List[Dict[str, Any]] = []

    for slot_name, slot_cfg in slots.items():
        slot_candidates = _fetch_slot_candidates(slot_cfg, fetchers, config)
        ranked_candidates = _select_slot_representative(slot_name, slot_candidates, config)
        selected_paper = None
        skipped_processed_ids: list[str] = []
        for candidate in ranked_candidates:
            if not ignore_db and is_paper_processed(candidate.id):
                skipped_processed_ids.append(str(candidate.id))
                continue
            selected_paper = candidate
            break

        if selected_paper is None:
            continue

        selection_rationale = _build_slot_selection_rationale(
            slot_name,
            slot_cfg,
            ranked_candidates,
            selected_paper,
            config,
            skipped_processed_ids,
        )

        paper = download_paper(selected_paper, config)
        canonical_doi = str(getattr(paper, "doi", "") or "").strip()
        resolved_slot = slot_name
        if llm and llm.is_available() and getattr(config.llm.features.slot_classification, "enabled", False):
            try:
                resolved_slot = llm.classify_slot(
                    {"title": paper.title, "summary": paper.summary},
                    slot_name,
                ) or slot_name
            except Exception as exc:
                logger.warning(
                    "Slot classification failed for %s; keeping slot %s: %s",
                    paper.id,
                    slot_name,
                    exc,
                    exc_info=True,
                )
                resolved_slot = slot_name

        tags: list[str] = []
        confidence = 0.0
        tagging_metrics: dict[str, Any] = {}
        tag_payload: dict[str, Any] = {}
        if analysis_available:
            tag_payload = llm.tag_paper({"title": paper.title, "summary": paper.summary}) or {}
            tags = tag_payload.get("soft_tags", []) or []
            confidence = float(tag_payload.get("confidence", 0.0) or 0.0)
            get_tagging_metrics = getattr(llm, "get_tagging_metrics", None)
            if callable(get_tagging_metrics):
                metrics_candidate = get_tagging_metrics()
                if isinstance(metrics_candidate, dict):
                    tagging_metrics = metrics_candidate

        feedback_json = _feedback_json_from_tagging(
            tag_payload,
            confidence=confidence,
            soft_tags=tags,
        )
        try:
            gate_analysis = json.loads(feedback_json)
        except Exception as exc:
            logger.warning(
                "Failed to parse feedback_json for daily slot gate evaluation on %s: %s",
                paper.id,
                exc,
                exc_info=True,
            )
            gate_analysis = {}
        gate_engine = GateEngine(
            high_threshold=config.confidence_thresholds.high,
            low_threshold=config.confidence_thresholds.low,
            require_evidence=True,
        )
        gate_result = gate_engine.evaluate(
            gate_analysis,
            parse_ok=analysis_available,
            schema_ok=analysis_available,
        )
        status = PaperStatus(gate_result.decision.value)
        gate_decision = gate_result.decision.value
        gate_reason_codes = [code.value for code in gate_result.reason_codes]

        clinical_extraction_feature = resolve_clinical_extraction_feature(
            getattr(config.llm, "features", None)
        )
        clinical_extraction_enabled = bool(getattr(clinical_extraction_feature, "enabled", False))
        clinical_extraction: Optional[BiomedicalClinicalExtraction] = None
        if analysis_available and resolved_slot.lower() == "clinical" and clinical_extraction_enabled:
            extract_clinical = getattr(llm, "extract_biomedical_clinical_data", None)
            if callable(extract_clinical):
                try:
                    extraction_candidate = extract_clinical(
                        {
                            "title": paper.title,
                            "summary": paper.summary,
                            "link": paper.link,
                            "doi": canonical_doi or paper.id,
                            "authors": paper.authors,
                            "published": paper.published,
                            "source": paper.source,
                        }
                    )
                    if isinstance(extraction_candidate, BiomedicalClinicalExtraction):
                        clinical_extraction = extraction_candidate
                except Exception as exc:
                    logger.warning("Clinical extraction failed for %s: %s", paper.id, exc, exc_info=True)

        if (
            clinical_extraction is None
            and status == PaperStatus.PENDING_REVIEW
            and ReasonCode.EVIDENCE_MISSING.value in gate_reason_codes
            and confidence >= config.confidence_thresholds.high
            and not tag_payload.get("evidence_snippets")
            and str(paper.summary or "").strip()
        ):
            tag_payload["evidence_snippets"] = [
                {
                    "snippet": str(paper.summary).strip(),
                    "location": "abstract",
                    "supports": "slot_decision",
                }
            ]
            feedback_json = _feedback_json_from_tagging(
                tag_payload,
                confidence=confidence,
                soft_tags=tags,
            )
            gate_result = gate_engine.evaluate(
                json.loads(feedback_json),
                parse_ok=analysis_available,
                schema_ok=analysis_available,
            )
            status = PaperStatus(gate_result.decision.value)
            gate_decision = gate_result.decision.value
            gate_reason_codes = [code.value for code in gate_result.reason_codes]

        escalation_sidecar: Optional[Dict[str, Any]] = None
        escalation_reason: Optional[str] = None
        escalation_final_route: Optional[str] = None
        escalation_in_biomedical_scope: Optional[bool] = None
        escalation_reason_codes: list[str] = []
        is_escalated = False

        if (
            analysis_available
            and status == PaperStatus.PENDING_REVIEW
            and hasattr(llm, "evaluate_escalation")
            and callable(getattr(llm, "evaluate_escalation"))
        ):
            try:
                escalation_result = llm.evaluate_escalation(
                    {
                        "title": paper.title,
                        "summary": paper.summary,
                        "link": paper.link,
                        "doi": canonical_doi or paper.id,
                        "authors": paper.authors,
                        "published": paper.published,
                        "source": paper.source,
                        "slot": resolved_slot,
                        "tags": tags,
                    }
                ) or {}
                escalation_sidecar = _build_escalation_sidecar(escalation_result)
                gate_reason_codes = _merge_reason_code_lists(
                    gate_reason_codes,
                    escalation_sidecar["reason_codes"],
                )
                escalation_reason = escalation_sidecar["reason"] or None
                escalation_final_route = escalation_sidecar["final_route"] or None
                escalation_in_biomedical_scope = escalation_sidecar["in_biomedical_scope"]
                escalation_reason_codes = escalation_sidecar["reason_codes"]
                if escalation_sidecar["approved"]:
                    status = PaperStatus.APPROVED
                    gate_decision = GateDecision.APPROVED.value
                    is_escalated = True
            except Exception as exc:
                logger.warning("Escalation evaluation failed for %s: %s", paper.id, exc, exc_info=True)

        retraction_check: Optional[Dict[str, Any]] = None
        system_config = getattr(config, "system", None)
        if bool(getattr(system_config, "check_retraction_on_ingest", False)) and canonical_doi:
            retraction_check = check_retraction(
                canonical_doi,
                email=getattr(system_config, "unpaywall_email", None),
            )
            if retraction_check.get("is_retracted"):
                status = PaperStatus.QUARANTINED
                gate_decision = GateDecision.QUARANTINED.value
                gate_reason_codes = _merge_reason_code_lists(gate_reason_codes, ["RETRACTED"])

        issues_state = derive_saved_issues_state(
            status,
            analysis_available=analysis_available,
        )
        slot_metrics: dict[str, Any] = {}
        get_slot_metrics = getattr(llm, "get_slot_classification_metrics", None) if llm else None
        if callable(get_slot_metrics):
            metrics_candidate = get_slot_metrics()
            if isinstance(metrics_candidate, dict):
                slot_metrics = metrics_candidate
        intake_override_log = build_intake_override_log(
            producer="processor_daily_slots",
            analysis_available=analysis_available,
            llm_tagging_used=analysis_available,
            llm_slot_classification_used=bool(
                llm and llm.is_available() and getattr(config.llm.features.slot_classification, "enabled", False)
            ),
            llm_tagging_adjudication_used=bool(tagging_metrics.get("adjudication_triggered")),
            llm_tagging_adjudication_reason=str(tagging_metrics.get("adjudication_reason") or "").strip() or None,
            llm_slot_adjudication_used=bool(slot_metrics.get("adjudication_triggered")),
            llm_slot_adjudication_reason=str(slot_metrics.get("adjudication_reason") or "").strip() or None,
            input_slot=slot_name,
            stored_slot=resolved_slot,
            input_tags=tags,
            stored_tags=tags,
            processing_status=status.value,
            issues_state=issues_state,
            confidence=confidence,
        )

        serialized_attempts: list[dict[str, Any]] = []
        for attempt in (paper.download_attempts or []):
            if hasattr(attempt, "model_dump"):
                serialized_attempts.append(attempt.model_dump(mode="json"))
            elif isinstance(attempt, dict):
                serialized_attempts.append(attempt)
            else:
                serialized_attempts.append({"message": str(attempt)})

        row = {
            "id": paper.id,
            "paper_id": paper.id,
            "doi": canonical_doi,
            "title": paper.title,
            "authors": paper.authors,
            "published": paper.published,
            "source": paper.source,
            "summary": paper.summary,
            "link": paper.link,
            "slot": resolved_slot,
            "tags": tags,
            "processing_status": status,
            "is_escalated": is_escalated,
            "escalation_reason": escalation_reason,
            "escalation_final_route": escalation_final_route,
            "escalation_in_biomedical_scope": escalation_in_biomedical_scope,
            "escalation_reason_codes": escalation_reason_codes,
            "pdf_path": str(paper.local_pdf_path) if paper.local_pdf_path else None,
            "local_pdf_path": str(paper.local_pdf_path) if paper.local_pdf_path else None,
            "download_attempts": serialized_attempts,
            "manual_rank_score": _coerce_optional_float(getattr(paper, "manual_rank_score", None)),
            "gate_decision": gate_decision,
            "gate_reason": ",".join(gate_reason_codes) or "NONE",
        }
        row["feedback_json"] = feedback_json
        row["feedback_json"] = _merge_feedback_json_payload(
            row["feedback_json"],
            {
                "gate_decision": row["gate_decision"],
                "gate_reason": row["gate_reason"],
            },
        )
        if retraction_check is not None:
            row["retraction_check"] = retraction_check
            row["feedback_json"] = _merge_feedback_json_payload(
                row["feedback_json"],
                {"retraction_check": retraction_check},
            )
        row["pdf_status"] = "downloaded" if row["pdf_path"] else "missing"

        if not row["pdf_path"]:
            from src.institutional_access import generate_institutional_proxy_url, upsert_institutional_proxy_link
            proxy_url = generate_institutional_proxy_url(
                doi=row["doi"] or None,
                publisher_url=row["link"],
                proxy_prefix=getattr(getattr(config, "system", None), "institutional_proxy_url", None),
            )
            if proxy_url:
                row["feedback_json"] = upsert_institutional_proxy_link(row.get("feedback_json"), proxy_url)
                row["pdf_status"] = "manual_required"
        row["feedback_json"] = merge_feedback_json_with_intake_override(
            row.get("feedback_json"),
            intake_override_log,
        )
        row["feedback_json"] = _merge_feedback_json_payload(
            row.get("feedback_json"),
            {"selection": selection_rationale},
        )
        if escalation_sidecar is not None:
            row["feedback_json"] = _merge_feedback_json_payload(
                row.get("feedback_json"),
                {"escalation": escalation_sidecar},
            )
        if clinical_extraction is not None:
            row["clinical_data"] = clinical_extraction.model_dump(mode="json")
            row["feedback_json"] = _merge_feedback_json_payload(
                row.get("feedback_json"),
                {"clinical_data": row["clinical_data"]},
            )

        results.append(row)

        try:
            save_paper_to_obsidian(row, config, extraction=clinical_extraction)
        except Exception as exc:
            logger.warning("Failed to save Obsidian note for %s: %s", row["paper_id"], exc, exc_info=True)
        ris_path = None
        try:
            ris_path = export_to_ris(row, Path(config.paths.export_dir))
        except Exception as exc:
            logger.warning("Failed to export RIS for %s: %s", row["paper_id"], exc, exc_info=True)
        try:
            save_paper_state(
                row["paper_id"],
                row["title"],
                row["source"],
                datetime.now().strftime("%Y-%m-%d"),
                doi=row.get("doi") or None,
                pdf_status=row.get("pdf_status"),
                local_pdf_path=row.get("pdf_path"),
                ris_path=ris_path,
                feedback_json=row.get("feedback_json"),
                download_attempts=row.get("download_attempts"),
                status=row["processing_status"].value if hasattr(row["processing_status"], "value") else str(row["processing_status"]),
                issues_state=issues_state,
            )
        except Exception as exc:
            logger.warning("Failed to save paper state for %s: %s", row["paper_id"], exc, exc_info=True)
        if retraction_check and retraction_check.get("is_retracted"):
            try:
                mark_as_retracted(row["paper_id"])
            except Exception as exc:
                logger.warning("Failed to mark retracted paper %s: %s", row["paper_id"], exc, exc_info=True)

    return results

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="PaperPipe Processor")
    parser.add_argument("--batch-size", type=int, default=5, help="Batch size limit")
    args = parser.parse_args()
    
    logging.basicConfig(level=logging.INFO)
    processor = PaperProcessor()
    processor.run(batch_size=args.batch_size)
