import sqlite3
import json
import logging
import os
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from src.services.runtime_paths import state_db_path

logger = logging.getLogger(__name__)

DB_PATH = state_db_path()
_IMPORTED_DB_PATH = Path(DB_PATH)


def get_db_path() -> Path:
    global DB_PATH
    env_value = os.getenv("PAPERPIPE_DB_PATH")
    if env_value:
        resolved = Path(env_value).expanduser().resolve()
        DB_PATH = resolved
        return resolved

    configured = Path(DB_PATH).expanduser().resolve()
    if configured != _IMPORTED_DB_PATH:
        return configured

    resolved = state_db_path()
    DB_PATH = resolved
    return resolved


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
    """Initialize runtime tables and apply lightweight compatibility migrations."""
    db_path = get_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.execute("PRAGMA foreign_keys=ON")

    # Jobs Table (Phase 3)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS jobs (
            job_id TEXT PRIMARY KEY,
            run_id TEXT,
            paper_id TEXT,
            persona_id TEXT DEFAULT 'default',
            reasoning_persona TEXT,
            profile_id TEXT,
            run_verify INTEGER DEFAULT 0,
            clean_reindex INTEGER DEFAULT 0,
            status TEXT DEFAULT 'queued',
            progress INTEGER DEFAULT 0,
            stage TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            started_at TIMESTAMP,
            heartbeat_at TIMESTAMP,
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
    if "reasoning_persona" not in existing_cols:
        cursor.execute("ALTER TABLE jobs ADD COLUMN reasoning_persona TEXT")
    if "profile_id" not in existing_cols:
        cursor.execute("ALTER TABLE jobs ADD COLUMN profile_id TEXT")
    if "run_verify" not in existing_cols:
        cursor.execute("ALTER TABLE jobs ADD COLUMN run_verify INTEGER DEFAULT 0")
    if "clean_reindex" not in existing_cols:
        cursor.execute("ALTER TABLE jobs ADD COLUMN clean_reindex INTEGER DEFAULT 0")
    if "heartbeat_at" not in existing_cols:
        cursor.execute("ALTER TABLE jobs ADD COLUMN heartbeat_at TIMESTAMP")
    if "error_code" not in existing_cols:
        cursor.execute("ALTER TABLE jobs ADD COLUMN error_code TEXT")

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS execution_runs (
            run_id TEXT PRIMARY KEY,
            paper_id TEXT,
            trigger_source TEXT,
            pipeline_profile TEXT,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            started_at TEXT,
            finished_at TEXT,
            params_json TEXT,
            metrics_json TEXT
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS job_events (
            event_id TEXT PRIMARY KEY,
            job_id TEXT NOT NULL,
            run_id TEXT,
            ts TEXT NOT NULL,
            level TEXT NOT NULL,
            event_type TEXT NOT NULL,
            message TEXT,
            payload_json TEXT,
            FOREIGN KEY(job_id) REFERENCES jobs(job_id)
        )
        """
    )
    cursor.execute("PRAGMA table_info(job_events)")
    job_event_cols = {row[1] for row in cursor.fetchall()}
    if "run_id" not in job_event_cols:
        cursor.execute("ALTER TABLE job_events ADD COLUMN run_id TEXT")
    if "payload_json" not in job_event_cols:
        cursor.execute("ALTER TABLE job_events ADD COLUMN payload_json TEXT")
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS user_actions (
            action_id TEXT PRIMARY KEY,
            ts TEXT NOT NULL,
            paper_id TEXT,
            action_type TEXT NOT NULL,
            source TEXT NOT NULL,
            payload_json TEXT
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS request_audits (
            audit_id TEXT PRIMARY KEY,
            ts TEXT NOT NULL,
            source TEXT NOT NULL,
            client_ip TEXT,
            host TEXT,
            method TEXT NOT NULL,
            path TEXT NOT NULL,
            status_code INTEGER NOT NULL,
            outcome TEXT NOT NULL,
            payload_json TEXT
        )
        """
    )
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_execution_runs_paper ON execution_runs(paper_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_job_events_job ON job_events(job_id, ts)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_job_events_run ON job_events(run_id, ts)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_actions_paper ON user_actions(paper_id, ts)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_request_audits_ts ON request_audits(ts)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_request_audits_path ON request_audits(path, ts)")

    # Lightweight papers migration used by downloader metrics/dashboard.
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='papers'")
    if cursor.fetchone():
        try:
            paper_cols = _get_paper_columns(cursor)
            if "download_attempts" not in paper_cols:
                cursor.execute("ALTER TABLE papers ADD COLUMN download_attempts TEXT")
            if "issues_state" not in paper_cols:
                cursor.execute("ALTER TABLE papers ADD COLUMN issues_state TEXT")
        except sqlite3.OperationalError:
            pass

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
    db_path = get_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
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


def save_paper_state(
    identifier: str,
    title: str,
    source: str,
    processed_date: str,
    *,
    local_pdf_path: Optional[str | Path] = None,
    feedback_json: Optional[str] = None,
    download_attempts: Optional[List[Dict[str, Any]]] = None,
    status: Optional[str] = None,
    issues_state: Optional[str] = None,
) -> None:
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        columns = _get_paper_columns(cursor)
        if not columns:
            return

        if download_attempts is not None and "download_attempts" not in columns:
            try:
                cursor.execute("ALTER TABLE papers ADD COLUMN download_attempts TEXT")
                columns.add("download_attempts")
            except sqlite3.OperationalError:
                pass

        insert_cols: list[str] = []
        insert_vals: list[Any] = []
        update_set: list[str] = []

        attempts_payload: Optional[str] = None
        if download_attempts is not None:
            try:
                attempts_payload = json.dumps(download_attempts, ensure_ascii=False, default=str)
            except Exception:
                attempts_payload = "[]"

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
        if "status" in columns and status is not None:
            insert_cols.append("status")
            insert_vals.append(status)
            update_set.append("status=excluded.status")
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
        if "pdf_path" in columns and local_pdf_path is not None:
            insert_cols.append("pdf_path")
            insert_vals.append(str(local_pdf_path))
            update_set.append("pdf_path=excluded.pdf_path")
        if "feedback_json" in columns and feedback_json is not None:
            insert_cols.append("feedback_json")
            insert_vals.append(feedback_json)
            update_set.append("feedback_json=excluded.feedback_json")
        if "download_attempts" in columns and attempts_payload is not None:
            insert_cols.append("download_attempts")
            insert_vals.append(attempts_payload)
            update_set.append("download_attempts=excluded.download_attempts")
        if "issues_state" in columns and issues_state is not None:
            insert_cols.append("issues_state")
            insert_vals.append(issues_state)
            update_set.append("issues_state=excluded.issues_state")

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
    paper_columns = _get_paper_columns(cursor)

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
                if "issues_state" in paper_columns:
                    cursor.execute(
                        """
                        INSERT INTO papers (
                            paper_id,
                            title,
                            summary,
                            status,
                            issues_state,
                            pdf_path,
                            created_at,
                            updated_at
                        )
                        VALUES (?, ?, ?, 'NEW', 'unavailable', ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                        """,
                        (paper_id, title, summary, pdf_path),
                    )
                else:
                    cursor.execute(
                        """
                        INSERT INTO papers (paper_id, title, summary, status, pdf_path, created_at, updated_at)
                        VALUES (?, ?, ?, 'NEW', ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                        """,
                        (paper_id, title, summary, pdf_path),
                    )
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
    try:
        fields = ["status = ?", "updated_at = CURRENT_TIMESTAMP"]
        params = [new_status]

        if updates:
            allowed_update_columns = _get_paper_columns(cursor) - {"paper_id", "status", "updated_at"}
            invalid_keys = sorted(key for key in updates if key not in allowed_update_columns)
            if invalid_keys:
                raise ValueError(
                    "Unsupported paper update columns: " + ", ".join(invalid_keys)
                )
            for key, value in updates.items():
                fields.append(f"{key} = ?")
                params.append(value)

        params.append(paper_id)

        query = f"UPDATE papers SET {', '.join(fields)} WHERE paper_id = ?"

        cursor.execute(query, params)
        conn.commit()
    finally:
        conn.close()


def init_run_stats_table() -> None:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS run_stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            profile_id TEXT NOT NULL,
            items_fetched INTEGER DEFAULT 0,
            limit_hit BOOLEAN DEFAULT 0
        )
        """
    )
    conn.commit()
    conn.close()


def log_run_stat(profile_id: str, items_fetched: int, limit_hit: bool) -> None:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO run_stats (profile_id, items_fetched, limit_hit)
        VALUES (?, ?, ?)
        """,
        (profile_id, items_fetched, int(limit_hit)),
    )
    conn.commit()
    conn.close()


def get_profile_stats(profile_id: str, days: int = 7) -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    threshold = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute(
        """
        SELECT * FROM run_stats
        WHERE profile_id = ? AND timestamp >= ?
        ORDER BY timestamp DESC
        """,
        (profile_id, threshold),
    )
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def reconcile_approved_decisions(dry_run: bool = True) -> Dict[str, Any]:
    """
    Reconcile DB status when a paper has an approved decision but non-approved status.

    Reconcile targets:
    - gate_decision == 'APPROVED' and status not in ('APPROVED', 'INDEXED')
    - feedback_json contains decision='APPROVED' and status not in ('APPROVED', 'INDEXED')
      (for manual edits where gate_decision column was not updated)
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT paper_id, status, gate_decision, feedback_json
        FROM papers
        WHERE status NOT IN ('APPROVED', 'INDEXED')
        """
    )
    rows = cursor.fetchall()

    candidates: List[Dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        gate_decision = item.get("gate_decision")
        feedback_json = item.get("feedback_json")

        approved_by_gate = gate_decision == "APPROVED"
        approved_by_feedback = False

        if not approved_by_gate and feedback_json:
            try:
                parsed = json.loads(feedback_json)
                if isinstance(parsed, dict):
                    approved_by_feedback = (
                        parsed.get("decision") == "APPROVED"
                        or parsed.get("gate_decision") == "APPROVED"
                    )
            except Exception:
                approved_by_feedback = False

        if approved_by_gate or approved_by_feedback:
            candidates.append(
                {
                    "paper_id": item["paper_id"],
                    "old_status": item["status"],
                    "source": "gate_decision" if approved_by_gate else "feedback_json",
                }
            )

    updated = 0
    if not dry_run:
        for c in candidates:
            if c["source"] == "gate_decision":
                cursor.execute(
                    """
                    UPDATE papers
                    SET status = 'APPROVED', updated_at = CURRENT_TIMESTAMP
                    WHERE paper_id = ?
                    """,
                    (c["paper_id"],),
                )
            else:
                cursor.execute(
                    """
                    UPDATE papers
                    SET status = 'APPROVED',
                        gate_decision = 'APPROVED',
                        gate_reason = COALESCE(gate_reason, 'Reconciled from feedback_json decision'),
                        updated_at = CURRENT_TIMESTAMP
                    WHERE paper_id = ?
                    """,
                    (c["paper_id"],),
                )
            updated += 1
        conn.commit()

    conn.close()
    return {
        "dry_run": dry_run,
        "candidates": candidates,
        "candidate_count": len(candidates),
        "updated_count": updated,
    }
    
def log_workflow_step(paper_id: str, step: str, message: str, level: str = "INFO"):
    """
    Optional: Log major workflow steps to a separate table or just standard logging.
    For now, we use standard logging, but this is a placeholder for DB logging.
    """
    pass # Implementation future
