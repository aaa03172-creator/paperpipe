import sqlite3
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional

from src.db_bootstrap import (
    ensure_event_log_tables,
    ensure_jobs_table,
    ensure_paper_key_column,
    ensure_review_queue_open_unique_index,
    ensure_runs_table,
)
from src.db_paper_ops import (
    get_all_papers_with_connection,
    get_paper_by_id_with_connection,
    get_papers_by_status_with_connection,
    is_paper_processed_with_connection,
    mark_as_retracted_with_connection,
    save_paper_state_with_connection,
    sync_zotero_to_db_with_connection,
    update_paper_status_with_connection,
    update_reading_status_with_connection,
)
from src.db_reconcile import reconcile_approved_decisions_with_connection
from src.db_run_stats import (
    get_profile_stats as get_profile_stats_with_connection,
    init_run_stats_table as init_run_stats_table_with_connection,
    log_run_stat as log_run_stat_with_connection,
)

logger = logging.getLogger(__name__)

DB_PATH = Path("storage/state.db")

def init_db():
    """Initialize job-related tables without altering existing papers schema."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            conn.execute("PRAGMA journal_mode = WAL")
            conn.execute("PRAGMA synchronous = NORMAL")
        except sqlite3.OperationalError:
            pass
        ensure_jobs_table(conn)
        ensure_runs_table(conn)
        ensure_event_log_tables(conn)
        ensure_paper_key_column(conn)
        ensure_review_queue_open_unique_index(conn)
        conn.commit()
    finally:
        conn.close()

def get_db_connection():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA foreign_keys = ON")
    except sqlite3.OperationalError:
        pass
    return conn


def get_paper_by_id(identifier: str) -> Optional[Dict[str, Any]]:
    conn = get_db_connection()
    try:
        return get_paper_by_id_with_connection(conn, identifier)
    finally:
        conn.close()


def is_paper_processed(identifier: str) -> bool:
    conn = get_db_connection()
    try:
        return is_paper_processed_with_connection(conn, identifier)
    finally:
        conn.close()


def save_paper_state(identifier: str, title: str, source: str, processed_date: str) -> None:
    conn = get_db_connection()
    try:
        save_paper_state_with_connection(conn, identifier, title, source, processed_date)
        conn.commit()
    finally:
        conn.close()


def update_reading_status(identifier: str, reading_status: str) -> bool:
    conn = get_db_connection()
    try:
        updated = update_reading_status_with_connection(conn, identifier, reading_status)
        conn.commit()
        return updated
    finally:
        conn.close()


def get_all_papers() -> List[Dict[str, Any]]:
    conn = get_db_connection()
    try:
        return get_all_papers_with_connection(conn)
    finally:
        conn.close()


def mark_as_retracted(identifier: str) -> bool:
    conn = get_db_connection()
    try:
        updated = mark_as_retracted_with_connection(conn, identifier)
        conn.commit()
        return updated
    finally:
        conn.close()

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

    conn = get_db_connection()
    try:
        new_count = sync_zotero_to_db_with_connection(conn, zotero_json_path)
        conn.commit()
    finally:
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
    try:
        return get_papers_by_status_with_connection(conn, status_list, limit=limit)
    finally:
        conn.close()

def update_paper_status(paper_id: str, new_status: str, updates: Optional[Dict[str, Any]] = None):
    """
    Update paper status and other fields (e.g., confidence, feedback_json).
    """
    conn = get_db_connection()
    try:
        update_paper_status_with_connection(conn, paper_id, new_status, updates=updates)
        conn.commit()
    finally:
        conn.close()


def init_run_stats_table() -> None:
    conn = get_db_connection()
    try:
        init_run_stats_table_with_connection(conn)
        conn.commit()
    finally:
        conn.close()


def log_run_stat(profile_id: str, items_fetched: int, limit_hit: bool) -> None:
    conn = get_db_connection()
    try:
        log_run_stat_with_connection(conn, profile_id, items_fetched, limit_hit)
        conn.commit()
    finally:
        conn.close()


def get_profile_stats(profile_id: str, days: int = 7) -> List[Dict[str, Any]]:
    conn = get_db_connection()
    try:
        return get_profile_stats_with_connection(conn, profile_id, days=days)
    finally:
        conn.close()


def reconcile_approved_decisions(dry_run: bool = True) -> Dict[str, Any]:
    conn = get_db_connection()
    try:
        return reconcile_approved_decisions_with_connection(conn, dry_run=dry_run)
    finally:
        conn.close()
    
def log_workflow_step(paper_id: str, step: str, message: str, level: str = "INFO"):
    """
    Optional: Log major workflow steps to a separate table or just standard logging.
    For now, we use standard logging, but this is a placeholder for DB logging.
    """
    pass # Implementation future
