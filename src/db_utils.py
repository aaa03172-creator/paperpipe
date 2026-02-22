import sqlite3
import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime

from src.db_reconcile import reconcile_approved_decisions_with_connection
from src.db_run_stats import (
    get_profile_stats as get_profile_stats_with_connection,
    init_run_stats_table as init_run_stats_table_with_connection,
    log_run_stat as log_run_stat_with_connection,
)

logger = logging.getLogger(__name__)

DB_PATH = Path("storage/state.db")


def _get_paper_columns(cursor: sqlite3.Cursor) -> set[str]:
    cursor.execute("PRAGMA table_info(papers)")
    return {row[1] for row in cursor.fetchall()}


def _paper_lookup_conditions(columns: set[str]) -> list[str]:
    conditions: list[str] = []
    if "paper_id" in columns:
        conditions.append("paper_id = ?")
    if "doi" in columns:
        conditions.append("doi = ?")
    return conditions

def init_db():
    """Initialize job-related tables without altering existing papers schema."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Jobs Table (Phase 3)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS jobs (
            job_id TEXT PRIMARY KEY,
            run_id TEXT,
            paper_id TEXT,
            persona_id TEXT DEFAULT 'default',
            run_verify INTEGER DEFAULT 0,
            status TEXT DEFAULT 'queued',
            progress INTEGER DEFAULT 0,
            stage TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            started_at TIMESTAMP,
            finished_at TIMESTAMP,
            artifact_dir TEXT,
            log_path TEXT,
            error_code TEXT,
            error_message TEXT
        )
    """)

    # Lightweight migration for existing DB files.
    cursor.execute("PRAGMA table_info(jobs)")
    existing_cols = {row[1] for row in cursor.fetchall()}
    if "persona_id" not in existing_cols:
        cursor.execute("ALTER TABLE jobs ADD COLUMN persona_id TEXT DEFAULT 'default'")
    if "run_verify" not in existing_cols:
        cursor.execute("ALTER TABLE jobs ADD COLUMN run_verify INTEGER DEFAULT 0")

    # Enforce one open review item per (paper_id, decision) when review_queue exists.
    # This complements app-level idempotency checks and protects concurrent writers.
    try:
        # Resolve historical duplicates first so unique index creation cannot fail.
        cursor.execute(
            """
            UPDATE review_queue
            SET resolved_at = CURRENT_TIMESTAMP,
                resolution = COALESCE(resolution, 'AUTO_DEDUP_DUPLICATE_OPEN'),
                owner = COALESCE(owner, 'SYSTEM')
            WHERE resolved_at IS NULL
              AND EXISTS (
                SELECT 1
                FROM review_queue rq2
                WHERE rq2.paper_id = review_queue.paper_id
                  AND rq2.decision = review_queue.decision
                  AND rq2.resolved_at IS NULL
                  AND rq2.id < review_queue.id
              )
            """
        )
        cursor.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS idx_review_queue_open_unique
            ON review_queue (paper_id, decision)
            WHERE resolved_at IS NULL
            """
        )
    except sqlite3.OperationalError:
        # review_queue may not exist in minimal test/local schemas.
        pass
    
    conn.commit()
    conn.close()

def get_db_connection():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def get_paper_by_id(identifier: str) -> Optional[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        columns = _get_paper_columns(cursor)
        lookup_cols: list[str] = []
        if "paper_id" in columns:
            lookup_cols.append("paper_id")
        if "id" in columns:
            lookup_cols.append("id")
        if "doi" in columns:
            lookup_cols.append("doi")

        for col in lookup_cols:
            cursor.execute(f"SELECT * FROM papers WHERE {col} = ? LIMIT 1", (identifier,))
            row = cursor.fetchone()
            if row:
                return dict(row)
        return None
    except sqlite3.OperationalError:
        return None
    finally:
        conn.close()


def is_paper_processed(identifier: str) -> bool:
    if not identifier:
        return False
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        columns = _get_paper_columns(cursor)
        conditions = _paper_lookup_conditions(columns)
        if not conditions:
            return False
        params = [identifier] * len(conditions)
        cursor.execute(
            f"SELECT 1 FROM papers WHERE {' OR '.join(conditions)} LIMIT 1",
            params,
        )
        return cursor.fetchone() is not None
    except sqlite3.OperationalError:
        return False
    finally:
        conn.close()


def save_paper_state(identifier: str, title: str, source: str, processed_date: str) -> None:
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        columns = _get_paper_columns(cursor)
        if not columns:
            return

        insert_cols: list[str] = []
        insert_vals: list[Any] = []
        update_set: list[str] = []

        if "paper_id" in columns:
            insert_cols.append("paper_id")
            insert_vals.append(identifier)
            update_set.append("paper_id=excluded.paper_id")
        if "doi" in columns:
            insert_cols.append("doi")
            insert_vals.append(identifier)
            update_set.append("doi=excluded.doi")
        if "title" in columns:
            insert_cols.append("title")
            insert_vals.append(title)
            update_set.append("title=excluded.title")
        if "source" in columns:
            insert_cols.append("source")
            insert_vals.append(source)
            update_set.append("source=excluded.source")
        if "processed_date" in columns:
            insert_cols.append("processed_date")
            insert_vals.append(processed_date)
            update_set.append("processed_date=excluded.processed_date")
        if "processed_at" in columns:
            insert_cols.append("processed_at")
            insert_vals.append(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            update_set.append("processed_at=excluded.processed_at")
        if "updated_at" in columns:
            insert_cols.append("updated_at")
            insert_vals.append(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            update_set.append("updated_at=excluded.updated_at")
        if "created_at" in columns:
            insert_cols.append("created_at")
            insert_vals.append(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        if "is_retracted" in columns:
            insert_cols.append("is_retracted")
            insert_vals.append(0)
            update_set.append("is_retracted=COALESCE(papers.is_retracted, 0)")

        if not insert_cols:
            return

        placeholders = ",".join("?" for _ in insert_cols)
        conflict_target = "paper_id" if "paper_id" in columns else ("doi" if "doi" in columns else None)

        if conflict_target:
            sql = (
                f"INSERT INTO papers ({', '.join(insert_cols)}) VALUES ({placeholders}) "
                f"ON CONFLICT({conflict_target}) DO UPDATE SET {', '.join(update_set)}"
            )
            cursor.execute(sql, tuple(insert_vals))
        else:
            sql = f"INSERT INTO papers ({', '.join(insert_cols)}) VALUES ({placeholders})"
            cursor.execute(sql, tuple(insert_vals))

        conn.commit()
    except sqlite3.OperationalError:
        pass
    finally:
        conn.close()


def update_reading_status(identifier: str, reading_status: str) -> bool:
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        columns = _get_paper_columns(cursor)
        if "reading_status" not in columns:
            try:
                cursor.execute("ALTER TABLE papers ADD COLUMN reading_status TEXT DEFAULT 'Inbox'")
                columns.add("reading_status")
            except sqlite3.OperationalError:
                pass
        conditions = _paper_lookup_conditions(columns)
        if "reading_status" not in columns or not conditions:
            return False
        params = [reading_status] + [identifier] * len(conditions)
        cursor.execute(
            f"UPDATE papers SET reading_status = ? WHERE {' OR '.join(conditions)}",
            params,
        )
        conn.commit()
        return cursor.rowcount > 0
    except sqlite3.OperationalError:
        return False
    finally:
        conn.close()


def get_all_papers() -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        columns = _get_paper_columns(cursor)
        if not columns:
            return []
        if "doi" in columns:
            doi_expr = "doi"
        elif "paper_id" in columns:
            doi_expr = "paper_id AS doi"
        else:
            doi_expr = "NULL AS doi"
        title_expr = "title" if "title" in columns else "NULL AS title"
        retracted_expr = "is_retracted" if "is_retracted" in columns else "0 AS is_retracted"
        cursor.execute(f"SELECT {doi_expr}, {title_expr}, {retracted_expr} FROM papers")
        return [dict(row) for row in cursor.fetchall()]
    except sqlite3.OperationalError:
        return []
    finally:
        conn.close()


def mark_as_retracted(identifier: str) -> bool:
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        columns = _get_paper_columns(cursor)
        if "is_retracted" not in columns:
            try:
                cursor.execute("ALTER TABLE papers ADD COLUMN is_retracted BOOLEAN DEFAULT 0")
                columns.add("is_retracted")
            except sqlite3.OperationalError:
                pass
        conditions = _paper_lookup_conditions(columns)
        if "is_retracted" not in columns or not conditions:
            return False
        params = [identifier] * len(conditions)
        cursor.execute(
            f"UPDATE papers SET is_retracted = 1 WHERE {' OR '.join(conditions)}",
            params,
        )
        conn.commit()
        return cursor.rowcount > 0
    except sqlite3.OperationalError:
        return False
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


def init_run_stats_table() -> None:
    conn = get_db_connection()
    init_run_stats_table_with_connection(conn)
    conn.commit()
    conn.close()


def log_run_stat(profile_id: str, items_fetched: int, limit_hit: bool) -> None:
    conn = get_db_connection()
    log_run_stat_with_connection(conn, profile_id, items_fetched, limit_hit)
    conn.commit()
    conn.close()


def get_profile_stats(profile_id: str, days: int = 7) -> List[Dict[str, Any]]:
    conn = get_db_connection()
    rows = get_profile_stats_with_connection(conn, profile_id, days=days)
    conn.close()
    return rows


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
