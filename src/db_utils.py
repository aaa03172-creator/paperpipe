import sqlite3
import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

DB_PATH = Path("storage/state.db")

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def sync_zotero_to_db(zotero_json_path: Path) -> int:
    """
    Syncs Zotero export (JSON) to SQLite.
    - Adds new papers as 'NEW'.
    - Updates 'pdf_path' if found in Zotero attachments.
    - Does NOT overwrite existing paper status (idempotent).
    Returns count of new papers added.
    """
    if not zotero_json_path.exists():
        logger.warning(f"Zotero export not found: {zotero_json_path}")
        return 0

    try:
        with open(zotero_json_path, 'r') as f:
            data = json.load(f)
            items = data.get('items', [])
    except Exception as e:
        logger.error(f"Failed to load Zotero JSON: {e}")
        return 0

    new_count = 0
    conn = get_db_connection()
    cursor = conn.cursor()

    for item in items:
        paper_id = item.get('citationKey')
        if not paper_id:
            continue

        title = item.get('title', 'Unknown Title')
        summary = item.get('abstractNote', '')
        
        # Find PDF path
        pdf_path = None
        for att in item.get("attachments", []):
            if att.get("path") and att["path"].lower().endswith(".pdf"):
                pdf_path = att["path"]
                break
        
        # Check if exists
        cursor.execute("SELECT paper_id, pdf_path, summary FROM papers WHERE paper_id = ?", (paper_id,))
        row = cursor.fetchone()

        if row:
            updates = []
            params = []
            
            # Update PDF path if it was missing but now found
            if pdf_path and not row['pdf_path']:
                updates.append("pdf_path = ?")
                params.append(pdf_path)
                
            # Update Summary if missing
            if summary and not row['summary']:
                updates.append("summary = ?")
                params.append(summary)
            
            if updates:
                params.append(paper_id)
                cursor.execute(f"UPDATE papers SET {', '.join(updates)} WHERE paper_id = ?", params)
        else:
            # Insert new
            try:
                cursor.execute("""
                    INSERT INTO papers (paper_id, title, summary, status, pdf_path, created_at, updated_at)
                    VALUES (?, ?, ?, 'NEW', ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """, (paper_id, title, summary, pdf_path))
                new_count += 1
            except sqlite3.IntegrityError:
                pass # Should not happen given check above, but safe to ignore
    
    conn.commit()
    conn.close()
    
    if new_count > 0:
        logger.info(f"📥 Synced {new_count} new papers from Zotero to DB.")
    else:
        logger.info("📥 Zotero Sync: No new papers found.")
        
    return new_count

def get_papers_by_status(status_list: List[str], limit: int = 5) -> List[Dict[str, Any]]:
    """
    Fetch papers matching any of the given statuses.
    Ordered by updated_at ASC (FIFO) to process oldest waiting first.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    placeholders = ','.join(['?'] * len(status_list))
    query = f"""
        SELECT * FROM papers 
        WHERE status IN ({placeholders})
        ORDER BY updated_at ASC
        LIMIT ?
    """
    
    params = status_list + [limit]
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    
    return [dict(row) for row in rows]

def update_paper_status(paper_id: str, new_status: str, updates: Optional[Dict[str, Any]] = None):
    """
    Update paper status and other fields (e.g., confidence, feedback_json).
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    fields = ["status = ?", "updated_at = CURRENT_TIMESTAMP"]
    params = [new_status]
    
    if updates:
        for key, value in updates.items():
            fields.append(f"{key} = ?")
            params.append(value)
    
    params.append(paper_id)
    
    query = f"UPDATE papers SET {', '.join(fields)} WHERE paper_id = ?"
    
    cursor.execute(query, params)
    conn.commit()
    conn.close()
    
def log_workflow_step(paper_id: str, step: str, message: str, level: str = "INFO"):
    """
    Optional: Log major workflow steps to a separate table or just standard logging.
    For now, we use standard logging, but this is a placeholder for DB logging.
    """
    pass # Implementation future
