import logging
import json
from pathlib import Path
from typing import Dict, Any
from datetime import datetime

from src.config import load_config
from src.llm_provider import get_llm_provider
from src.db_utils import get_db_connection
from src.pdf import extract_text_from_pdf

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def run_backfill(limit: int = 50):
    config = load_config()
    llm = get_llm_provider(config.llm, config.entity_aliases)
    
    if not llm.is_available():
        logger.error("LLM Provider not available. Aborting.")
        return

    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Select candidate papers: APPROVED or INDEXED, but missing "soft_tags" in feedback_json
    # We use a simple LIKE query to find those missing the key string.
    query = """
        SELECT * FROM papers 
        WHERE status IN ('APPROVED', 'INDEXED') 
          AND (
            feedback_json IS NULL 
            OR feedback_json NOT LIKE '%soft_tags%'
            OR summary IS NULL 
            OR summary = ''
            OR summary = 'Abstract not available.'
          )
        LIMIT ?
    """
    cursor.execute(query, (limit,))
    rows = cursor.fetchall()
    candidates = [dict(row) for row in rows]
    logger.info(f"Found {len(candidates)} papers requiring backfill analysis.")
    
    success_count = 0
    
    for row in candidates:
        pid = row['paper_id']
        title = row['title']
        pdf_path_str = row['pdf_path']
        logger.info(f"Processing: {pid} ({title})")
        
        try:
            # 1. Prepare Content
            full_text = None
            if pdf_path_str:
                p = Path(pdf_path_str)
                if p.exists():
                    try:
                        # Optimization: Reduce max pages or truncate text early for speed
                        text = extract_text_from_pdf(p, max_pages=3)
                        full_text = text[:5000] if text else None
                    except Exception as e:
                        logger.warning(f"  PDF extraction failed: {e}")
            
            summary = row.get('summary', '') or "Abstract not available."
            
            paper_obj = {
                "title": title,
                "summary": summary,
                "full_text": full_text
            }
            
            # 2. Run LLM Analysis
            logger.info("  -> Requesting LLM Tags...")
            tags_data = llm.tag_paper(paper_obj)
            
            if not tags_data:
                logger.error("  -> LLM returned None. Skipping.")
                continue

            # [NEW] Generate Summary if missing
            new_summary = summary
            if not summary or summary == "Abstract not available.":
                logger.info("  -> Generating One-Liner Summary...")
                one_liner = llm.generate_one_liner(paper_obj)
                if one_liner:
                    new_summary = one_liner
                    logger.info(f"  -> Generated Summary: {new_summary[:50]}...")
                
            # 3. Update DB
            # We want to keep the current status (APPROVED/INDEXED) but update the metadata.
            # Preserve existing ID/Status.
            
            new_feedback = json.dumps(tags_data)
            confidence = tags_data.get('confidence', 0.0)
            
            # Update
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE papers 
                SET feedback_json = ?, confidence = ?, summary = ?, updated_at = ?
                WHERE paper_id = ?
                """,
                (new_feedback, confidence, new_summary, datetime.now().isoformat(timespec="seconds"), pid),
            )
            conn.commit()
            
            logger.info(f"  -> Updated {pid}. Confidence: {confidence}")
            success_count += 1
            
        except Exception as e:
            logger.error(f"  -> Failed to process {pid}: {e}")
            
    logger.info(f"Backfill Complete. Success: {success_count}/{len(candidates)}")
    conn.close()

if __name__ == "__main__":
    run_backfill(limit=100)
