import logging
import time
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime
import json

from src.config import load_config, AppConfig
from src.llm_provider import get_llm_provider, LLMProvider
from src.db_utils import (
    sync_zotero_to_db, 
    get_papers_by_status, 
    update_paper_status,
    DB_PATH
)
from src.schemas import Paper, PaperStatus
from src.obsidian import save_paper_to_obsidian

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

class PaperProcessor:
    def __init__(self):
        self.config = load_config()
        self.llm_provider = get_llm_provider(self.config.llm, self.config.entity_aliases)
        self.upload_dir = Path(self.config.paths.upload_dir) if self.config.paths.upload_dir else None
        
        # Ensure directories
        if self.upload_dir:
            self.upload_dir.mkdir(parents=True, exist_ok=True)
            
    def run(self, batch_size: int = 5):
        """
        Main State Machine Loop.
        Processes papers through steps: Sync -> Fetch -> Analyze -> Gate -> Index.
        Safety: Limited batch size to prevent API cost explosions.
        """
        logger.info(f"🚀 Starting PaperProcessor Run (Batch Limit: {batch_size})")
        
        # Step 0: Sync Zotero
        zotero_path = Path("storage/zotero_export.json")
        if zotero_path.exists():
            sync_zotero_to_db(zotero_path)
            
        processed_count = 0
        
        # We process in priority of states to push items forward
        # Order: APPROVED (to Index) -> GATED (to Gate) -> FETCHED (to Analyze) -> NEW (to Fetch)
        # But to respect batch_size as a global limit of "Actions Taken", we might want to iterate carefully.
        # User requested "Global Batch Size = 5".
        
        # Strategy: Fetch candidates for each stage, but only execute up to batch_size TOTAL actions.
        
        remaining_budget = batch_size
        
        # Step 4: Finalize (APPROVED -> INDEXED)
        if remaining_budget > 0:
            candidates = get_papers_by_status([STATE_APPROVED], limit=remaining_budget)
            processed = self._process_step(candidates, self._step_finalize)
            remaining_budget -= processed
            
        # Step 3: Gate (GATED -> APPROVED/...)
        if remaining_budget > 0:
            candidates = get_papers_by_status([STATE_GATED], limit=remaining_budget)
            processed = self._process_step(candidates, self._step_gate)
            remaining_budget -= processed

        # Step 2: Analyze (FETCHED -> GATED)
        if remaining_budget > 0:
            candidates = get_papers_by_status([STATE_FETCHED], limit=remaining_budget)
            processed = self._process_step(candidates, self._step_analyze)
            remaining_budget -= processed
            
        # Step 1: Fetch (NEW -> FETCHED)
        if remaining_budget > 0:
            candidates = get_papers_by_status([STATE_NEW], limit=remaining_budget)
            processed = self._process_step(candidates, self._step_fetch)
            remaining_budget -= processed
            
        logger.info(f"🏁 Run Complete. Actions consumed: {batch_size - remaining_budget}/{batch_size}")

    def _process_step(self, papers: List[Dict], handler) -> int:
        """Helper to process a batch of papers with error isolation."""
        count = 0
        for paper_row in papers:
            if not paper_row: continue
            pid = paper_row['paper_id']
            try:
                handler(paper_row)
                count += 1
            except Exception as e:
                logger.error(f"❌ Error processing {pid} in {handler.__name__}: {e}", exc_info=True)
                update_paper_status(pid, STATE_FAILED, {"feedback_json": f"Error: {str(e)}"})
        return count

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
        # Note: We rely on Zotero-synced data. Summary might be missing in DB?
        # Ideally we read from the text file or just use title.
        summary = row.get('summary', '') or "Abstract not available."
        
        paper_obj = {
            "title": title,
            "summary": summary
        }
        
        # 2. Run Hybrid Tagging (includes Confidence)
        logger.info("      -> Running Hybrid Tagging & Extraction...")
        tags_data = self.llm_provider.tag_paper(paper_obj)
        
        if not tags_data:
            raise ValueError("Tagging returned None")
            
        # 3. Save result to DB
        # We store the full tagging result in 'feedback_json' for now (or a specific column if we had one)
        # The DB schema has 'feedback_json', let's use that.
        # Also extract confidence for the column.
        
        confidence = tags_data.get('confidence', 0.0)
        
        update_paper_status(pid, STATE_GATED, {
            "confidence": confidence,
            "feedback_json": json.dumps(tags_data) # Store analysis result here
        })
        logger.info(f"      -> Analysis Done. Confidence: {confidence}")

    def _step_gate(self, row: Dict):
        """Step 3: Gate (GATED -> APPROVED/QUARANTINED/PENDING)"""
        pid = row['paper_id']
        confidence = row['confidence']
        logger.info(f"   [Step 3: Gate] {pid} (Conf: {confidence})")
        
        if confidence is None:
            confidence = 0.0
            
        status = STATE_PENDING
        decision = "PENDING_REVIEW"
        
        if confidence >= self.config.confidence_thresholds.high:
            status = STATE_APPROVED
            decision = "APPROVED"
        elif confidence < self.config.confidence_thresholds.low:
            status = STATE_QUARANTINED
            decision = "QUARANTINED"
            
        update_paper_status(pid, status, {
            "gate_decision": decision,
            "gate_reason": f"Confidence {confidence}"
        })
        logger.info(f"      -> Gate Decision: {decision}")

    def _step_finalize(self, row: Dict):
        """Step 4: Finalize (APPROVED -> INDEXED)"""
        pid = row['paper_id']
        logger.info(f"   [Step 4: Finalize] {pid}")
        
        # Placeholder for Embeddings / Vector DB
        # For now, we just mark as INDEXED.
        # If we had a vector store, we would insert here.
        
        # Also create Obsidian Note?
        # We need the analysis data from 'feedback_json' to create the note.
        feedback_json = row['feedback_json']
        if feedback_json:
            try:
                data = json.loads(feedback_json)
                # Construct result_dict for Obsidian
                result_dict = {
                    "id": pid,
                    "title": row['title'],
                    "doi": pid, # Assumption
                    "processing_status": row['gate_decision'],
                    "hybrid_tags": data,
                    "tags": data.get('soft_tags', []),
                    "ai_summary": data.get('reasoning', "No summary provided."),
                    "local_pdf_path": row['pdf_path']
                }
                
                # Save to Obsidian
                # path = save_paper_to_obsidian(result_dict, self.config) # Import usage
                logger.info("      -> Prepared for Obsidian (Mock)")
            except Exception as e:
                logger.warning(f"      -> Failed to parse feedback_json for Obsidian: {e}")

        update_paper_status(pid, STATE_INDEXED)
        logger.info("      -> Status: INDEXED")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    processor = PaperProcessor()
    processor.run(batch_size=5)