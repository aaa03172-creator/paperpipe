import logging
import time
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime
import json
import argparse
from pypdf import PdfReader

from src.config import load_config, AppConfig
from src.llm_provider import get_llm_provider, LLMProvider
from src.fetch import get_fetchers
from src.gates import GateEngine
from src.schemas.gates import GateDecision
from src.db_utils import (
    sync_zotero_to_db, 
    get_papers_by_status, 
    update_paper_status,
    is_paper_processed,
    save_paper_state,
)
from src.schemas import Paper, PaperStatus, PaperTagging
from src.obsidian import save_paper_to_obsidian
from src.pdf import extract_text_from_pdf
from src.downloader import download_paper
from src.services.intake_override_log import build_intake_override_log, merge_feedback_json_with_intake_override
from src.zotero import export_to_ris

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


def derive_saved_issues_state(processing_status: PaperStatus | str, *, analysis_available: bool) -> str:
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
        zotero_path = Path("storage/zotero_export.json")
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
                if processed > 0: progress_made = True
                if consecutive_failures >= MAX_CONSECUTIVE_FAILURES: break
                
            # Step 3: Gate (GATED -> APPROVED/...)
            if remaining_budget > 0:
                candidates = get_papers_by_status([STATE_GATED], limit=remaining_budget)
                processed, failed = self._process_step(candidates, self._step_gate)
                remaining_budget -= processed
                consecutive_failures = last_consecutive_failures(consecutive_failures, processed, failed)
                if processed > 0: progress_made = True
                if consecutive_failures >= MAX_CONSECUTIVE_FAILURES: break

            # Step 2: Analyze (FETCHED -> GATED)
            if remaining_budget > 0:
                candidates = get_papers_by_status([STATE_FETCHED], limit=remaining_budget)
                processed, failed = self._process_step(candidates, self._step_analyze)
                remaining_budget -= processed
                consecutive_failures = last_consecutive_failures(consecutive_failures, processed, failed)
                if processed > 0: progress_made = True
                if consecutive_failures >= MAX_CONSECUTIVE_FAILURES: break
                
            # Step 1: Fetch (NEW -> FETCHED)
            if remaining_budget > 0:
                candidates = get_papers_by_status([STATE_NEW], limit=remaining_budget)
                processed, failed = self._process_step(candidates, self._step_fetch)
                remaining_budget -= processed
                consecutive_failures = last_consecutive_failures(consecutive_failures, processed, failed)
                if processed > 0: progress_made = True
                if consecutive_failures >= MAX_CONSECUTIVE_FAILURES: break
            
            if not progress_made:
                break
                
            if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                logger.error("🛑 STOPPING due to consecutive failures limits.")
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
            if not paper_row: continue
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
                    parse_ok = False
            except Exception:
                parse_ok = False

        analysis.setdefault("confidence", confidence)
        analysis.setdefault("soft_tags", [])
        analysis.setdefault("hard_tags", {})

        if parse_ok:
            try:
                PaperTagging.model_validate(analysis)
            except Exception:
                schema_ok = False

        gate_result = self.gate_engine.evaluate(analysis, parse_ok=parse_ok, schema_ok=schema_ok)

        status_map = {
            GateDecision.APPROVED: STATE_APPROVED,
            GateDecision.PENDING_REVIEW: STATE_PENDING,
            GateDecision.QUARANTINED: STATE_QUARANTINED,
            GateDecision.FAILED: STATE_FAILED,
        }
        status = status_map[gate_result.decision]
        decision = gate_result.decision.value
        reason = ",".join([rc.value for rc in gate_result.reason_codes]) or "NONE"

        update_paper_status(pid, status, {
            "gate_decision": decision,
            "gate_reason": reason,
        })
        logger.info(f"      -> Gate Decision: {decision} ({reason})")

    def _step_finalize(self, row: Dict):
        """Step 4: Finalize (APPROVED -> INDEXED)"""
        pid = row['paper_id']
        logger.info(f"   [Step 4: Finalize] {pid}")
        
        # Placeholder for Embeddings / Vector DB
        
        # Also create Obsidian Note?
        feedback_json = row['feedback_json']
        if feedback_json:
            try:
                data = json.loads(feedback_json)
                # Construct result_dict for Obsidian (Mock)
                logger.info("      -> Prepared for Obsidian (Mock)")
            except Exception as e:
                logger.warning(f"      -> Failed to parse feedback_json for Obsidian: {e}")

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
    except Exception:
        pass

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
        query = getattr(slot_cfg, "query", "")
        for fetcher in fetchers:
            try:
                papers = fetcher.fetch(query, max_results=5)
            except TypeError:
                papers = fetcher.fetch(query=query, max_results=5)
            for paper in papers:
                if not ignore_db and is_paper_processed(paper.id):
                    continue

                paper = download_paper(paper, config)
                resolved_slot = slot_name
                if llm and llm.is_available() and getattr(config.llm.features.slot_classification, "enabled", False):
                    try:
                        resolved_slot = llm.classify_slot(
                            {"title": paper.title, "summary": paper.summary},
                            slot_name,
                        ) or slot_name
                    except Exception:
                        resolved_slot = slot_name

                tags: list[str] = []
                confidence = 0.0
                if analysis_available:
                    tag_payload = llm.tag_paper({"title": paper.title, "summary": paper.summary}) or {}
                    tags = tag_payload.get("soft_tags", []) or []
                    confidence = float(tag_payload.get("confidence", 0.0) or 0.0)

                if confidence >= config.confidence_thresholds.high:
                    status = PaperStatus.APPROVED
                elif confidence < config.confidence_thresholds.low:
                    status = PaperStatus.QUARANTINED
                else:
                    status = PaperStatus.PENDING_REVIEW

                issues_state = derive_saved_issues_state(
                    status,
                    analysis_available=analysis_available,
                )
                intake_override_log = build_intake_override_log(
                    producer="processor_daily_slots",
                    analysis_available=analysis_available,
                    llm_tagging_used=analysis_available,
                    llm_slot_classification_used=bool(
                        analysis_available and getattr(config.llm.features.slot_classification, "enabled", False)
                    ),
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
                    "doi": paper.doi or paper.id,
                    "title": paper.title,
                    "authors": paper.authors,
                    "published": paper.published,
                    "source": paper.source,
                    "summary": paper.summary,
                    "link": paper.link,
                    "slot": resolved_slot,
                    "tags": tags,
                    "processing_status": status,
                    "pdf_path": str(paper.local_pdf_path) if paper.local_pdf_path else None,
                    "local_pdf_path": str(paper.local_pdf_path) if paper.local_pdf_path else None,
                    "download_attempts": serialized_attempts,
                }
                
                if not row["pdf_path"]:
                    from src.institutional_access import generate_institutional_proxy_url, upsert_institutional_proxy_link
                    proxy_url = generate_institutional_proxy_url(doi=row["doi"], publisher_url=row["link"])
                    if proxy_url:
                        row["feedback_json"] = upsert_institutional_proxy_link("{}", proxy_url)
                row["feedback_json"] = merge_feedback_json_with_intake_override(
                    row.get("feedback_json"),
                    intake_override_log,
                )
                
                results.append(row)

                try:
                    save_paper_to_obsidian(row, config)
                except Exception:
                    pass
                try:
                    export_to_ris(row, Path(config.paths.export_dir))
                except Exception:
                    pass
                try:
                    save_paper_state(
                        row["doi"],
                        row["title"],
                        row["source"],
                        datetime.now().strftime("%Y-%m-%d"),
                        local_pdf_path=row.get("pdf_path"),
                        feedback_json=row.get("feedback_json"),
                        download_attempts=row.get("download_attempts"),
                        status=row["processing_status"].value if hasattr(row["processing_status"], "value") else str(row["processing_status"]),
                        issues_state=issues_state,
                    )
                except Exception:
                    pass

    return results

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="PaperPipe Processor")
    parser.add_argument("--batch-size", type=int, default=5, help="Batch size limit")
    args = parser.parse_args()
    
    logging.basicConfig(level=logging.INFO)
    processor = PaperProcessor()
    processor.run(batch_size=args.batch_size)
