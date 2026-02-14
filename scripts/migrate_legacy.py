import json
import sqlite3
import logging
from pathlib import Path
from datetime import datetime

# Config
DB_PATH = Path("storage/state.db")
FEEDBACK_PATH = Path("storage/feedback.jsonl")
ZOTERO_PATH = Path("storage/zotero_export.json")

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger("migrate")

def load_zotero_titles():
    """Load paper_id -> title mapping from Zotero export."""
    if not ZOTERO_PATH.exists():
        logger.warning(f"Zotero export not found at {ZOTERO_PATH}. Titles will be unknown.")
        return {}
    
    try:
        with open(ZOTERO_PATH, "r") as f:
            data = json.load(f)
        
        mapping = {}
        for item in data.get("items", []):
            if "citationKey" in item and "title" in item:
                mapping[item["citationKey"]] = item["title"]
        return mapping
    except Exception as e:
        logger.error(f"Failed to load Zotero export: {e}")
        return {}

def parse_confidence(user_correction_str):
    """
    Attempt to extract confidence from the user_correction JSON string.
    Returns average confidence of claims, or default 0.8.
    """
    try:
        # The string might start with "Golden Shot by Claude 3.5:\n"
        cleaned_str = user_correction_str
        if "Golden Shot by Claude" in cleaned_str:
             cleaned_str = cleaned_str.split("\n", 1)[1]
        
        data = json.loads(cleaned_str)
        claims = data.get("claims", [])
        
        if not claims:
            return 0.8
        
        total_conf = sum(c.get("confidence", 0.0) for c in claims)
        return round(total_conf / len(claims), 2)
    except Exception:
        # Fallback if parsing fails or pattern doesn't match
        return 0.8

def migrate():
    if not FEEDBACK_PATH.exists():
        logger.error(f"Source file not found: {FEEDBACK_PATH}")
        return

    # 1. Load Metadata
    title_map = load_zotero_titles()
    logger.info(f"Loaded {len(title_map)} titles from Zotero.")

    # 2. Connect DB
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    success_count = 0
    skip_count = 0
    fail_count = 0

    logger.info("Starting migration...")

    # 3. Process Feedback JSONL
    with open(FEEDBACK_PATH, "r") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line: continue

            try:
                rec = json.loads(line)
                paper_id = rec.get("paper_id")
                
                if not paper_id:
                    continue

                # Check existence
                cursor.execute("SELECT 1 FROM papers WHERE paper_id = ?", (paper_id,))
                if cursor.fetchone():
                    # Already exists
                    skip_count += 1
                    continue

                # Prepare Data
                title = title_map.get(paper_id, "Unknown Title")
                confidence = parse_confidence(rec.get("user_correction", ""))
                
                # Insert
                cursor.execute("""
                    INSERT INTO papers (
                        paper_id, title, status, confidence, 
                        gate_decision, feedback_json, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """, (
                    paper_id,
                    title,
                    "INDEXED",  # Mark as processed/indexed
                    confidence,
                    "APPROVED" if confidence > 0.8 else "PENDING_REVIEW", # Simple logic
                    line,       # Raw JSONL line as backup
                ))
                
                success_count += 1
                
            except Exception as e:
                logger.error(f"Failed to process line {line_num}: {e}")
                fail_count += 1

    conn.commit()
    conn.close()

    logger.info("-" * 40)
    logger.info(f"Migration Complete.")
    logger.info(f"✅ Success: {success_count}")
    logger.info(f"⏭️  Skipped: {skip_count} (Already in DB)")
    logger.info(f"❌ Failed:  {fail_count}")
    logger.info("-" * 40)

if __name__ == "__main__":
    migrate()
