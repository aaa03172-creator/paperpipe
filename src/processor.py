import logging
from typing import Dict, Any, List, Optional
import argparse
from pathlib import Path

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
from src.pdf import extract_text_from_pdf
from src.downloader import download_paper
from src.obsidian import save_paper_to_obsidian
from src.zotero import export_to_ris
from src.processor_legacy import (
    process_daily_slots_legacy_with_deps,
    process_local_pdf_legacy,
    process_paper_legacy,
)

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


def consume_budget(remaining_budget: int, success_count: int, failure_count: int) -> int:
    """Consume run budget by attempted actions (success + failure)."""
    attempted = max(0, success_count + failure_count)
    return max(0, remaining_budget - attempted)

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
                remaining_budget = consume_budget(remaining_budget, processed, failed)
                consecutive_failures = last_consecutive_failures(consecutive_failures, processed, failed)
                if processed > 0 or failed > 0:
                    progress_made = True
                if consecutive_failures >= MAX_CONSECUTIVE_FAILURES: break
                
            # Step 3: Gate (GATED -> APPROVED/...)
            if remaining_budget > 0:
                candidates = get_papers_by_status([STATE_GATED], limit=remaining_budget)
                processed, failed = self._process_step(candidates, self._step_gate)
                remaining_budget = consume_budget(remaining_budget, processed, failed)
                consecutive_failures = last_consecutive_failures(consecutive_failures, processed, failed)
                if processed > 0 or failed > 0:
                    progress_made = True
                if consecutive_failures >= MAX_CONSECUTIVE_FAILURES: break

            # Step 2: Analyze (FETCHED -> GATED)
            if remaining_budget > 0:
                candidates = get_papers_by_status([STATE_FETCHED], limit=remaining_budget)
                processed, failed = self._process_step(candidates, self._step_analyze)
                remaining_budget = consume_budget(remaining_budget, processed, failed)
                consecutive_failures = last_consecutive_failures(consecutive_failures, processed, failed)
                if processed > 0 or failed > 0:
                    progress_made = True
                if consecutive_failures >= MAX_CONSECUTIVE_FAILURES: break
                
            # Step 1: Fetch (NEW -> FETCHED)
            if remaining_budget > 0:
                candidates = get_papers_by_status([STATE_NEW], limit=remaining_budget)
                processed, failed = self._process_step(candidates, self._step_fetch)
                remaining_budget = consume_budget(remaining_budget, processed, failed)
                consecutive_failures = last_consecutive_failures(consecutive_failures, processed, failed)
                if processed > 0 or failed > 0:
                    progress_made = True
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
    return process_paper_legacy(
        paper_data=paper_data,
        config=config,
        llm_provider=llm_provider,
        is_deep_target=is_deep_target,
    )


def process_local_pdf(file_path: Path, config: Optional[AppConfig] = None):
    return process_local_pdf_legacy(file_path=file_path, config=config)


def process_daily_slots(ignore_db: bool = False) -> List[Dict[str, Any]]:
    return process_daily_slots_legacy_with_deps(
        ignore_db=ignore_db,
        load_config_fn=load_config,
        get_llm_provider_fn=get_llm_provider,
        get_fetchers_fn=get_fetchers,
        is_paper_processed_fn=is_paper_processed,
        download_paper_fn=download_paper,
        save_paper_to_obsidian_fn=save_paper_to_obsidian,
        export_to_ris_fn=export_to_ris,
        save_paper_state_fn=save_paper_state,
    )

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="PaperPipe Processor")
    parser.add_argument("--batch-size", type=int, default=5, help="Batch size limit")
    args = parser.parse_args()
    
    logging.basicConfig(level=logging.INFO)
    processor = PaperProcessor()
    processor.run(batch_size=args.batch_size)
