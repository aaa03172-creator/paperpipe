import logging
import time
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime
import argparse
from pypdf import PdfReader

from src.config import load_config, AppConfig
from src.llm_provider import get_llm_provider, LLMProvider
from src.fetch import get_fetchers
from src.gates import GateEngine
from src.schemas.gates import GateDecision
from src.processor_steps import (
    step_analyze,
    step_fetch,
    step_finalize,
    step_gate,
)
from src.db_utils import (
    sync_zotero_to_db, 
    get_papers_by_status, 
    update_paper_status,
    is_paper_processed,
    save_paper_state,
)
from src.schemas import Paper, PaperStatus
from src.obsidian import save_paper_to_obsidian
from src.pdf import extract_text_from_pdf
from src.downloader import download_paper
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
        step_fetch(
            row,
            state_fetched=STATE_FETCHED,
            state_pdf_missing=STATE_PDF_MISSING,
            update_status_fn=update_paper_status,
            logger=logger,
        )

    def _step_analyze(self, row: Dict):
        step_analyze(
            row,
            llm_provider=self.llm_provider,
            state_gated=STATE_GATED,
            extract_text_fn=extract_text_from_pdf,
            update_status_fn=update_paper_status,
            logger=logger,
        )

    def _step_gate(self, row: Dict):
        status_map = {
            GateDecision.APPROVED: STATE_APPROVED,
            GateDecision.PENDING_REVIEW: STATE_PENDING,
            GateDecision.QUARANTINED: STATE_QUARANTINED,
            GateDecision.FAILED: STATE_FAILED,
        }
        step_gate(
            row,
            gate_engine=self.gate_engine,
            status_map=status_map,
            update_status_fn=update_paper_status,
            logger=logger,
        )

    def _step_finalize(self, row: Dict):
        step_finalize(
            row,
            state_indexed=STATE_INDEXED,
            update_status_fn=update_paper_status,
            logger=logger,
        )


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
                if llm and llm.is_available():
                    tag_payload = llm.tag_paper({"title": paper.title, "summary": paper.summary}) or {}
                    tags = tag_payload.get("soft_tags", []) or []
                    confidence = float(tag_payload.get("confidence", 0.0) or 0.0)

                if confidence >= config.confidence_thresholds.high:
                    status = PaperStatus.APPROVED
                elif confidence < config.confidence_thresholds.low:
                    status = PaperStatus.QUARANTINED
                else:
                    status = PaperStatus.PENDING_REVIEW

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
                }
                
                if not row["pdf_path"]:
                    from src.institutional_access import generate_institutional_proxy_url, upsert_institutional_proxy_link
                    proxy_url = generate_institutional_proxy_url(doi=row["doi"], publisher_url=row["link"])
                    if proxy_url:
                        row["feedback_json"] = upsert_institutional_proxy_link("{}", proxy_url)
                
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
