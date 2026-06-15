import sqlite3
import json
import logging
import os
import time
from pathlib import Path
from typing import Callable, List, Dict, Any, Optional, TypeVar
from datetime import datetime, timedelta
from src.services.runtime_paths import state_db_path
from src.services.identity import normalize_doi

logger = logging.getLogger(__name__)

DB_PATH = state_db_path()
SQLITE_TIMEOUT_SECONDS = 30.0
SQLITE_BUSY_TIMEOUT_MS = int(SQLITE_TIMEOUT_SECONDS * 1000)
SQLITE_LOCK_RETRY_ATTEMPTS = 3
SQLITE_LOCK_RETRY_BASE_SECONDS = 0.05
ZOTERO_SYNC_COMMIT_BATCH_SIZE = 50
_IMPORTED_DB_PATH = Path(DB_PATH)
_ENV_DERIVED_DB_PATH: Path | None = None
_DOI_UNSET = object()
_T = TypeVar("_T")


def _normalized_doi_or_none(value: Any) -> str | None:
    normalized = normalize_doi(str(value or ""))
    if normalized.startswith("10.") and "/" in normalized:
        return normalized
    return None


def _configure_connection(conn: sqlite3.Connection) -> None:
    conn.execute(f"PRAGMA busy_timeout={SQLITE_BUSY_TIMEOUT_MS}")
    conn.execute("PRAGMA foreign_keys=ON")


def _is_sqlite_lock_error(exc: sqlite3.OperationalError) -> bool:
    message = str(exc).lower()
    if "database is locked" in message or "database is busy" in message:
        return True
    return getattr(exc, "sqlite_errorcode", None) == sqlite3.SQLITE_BUSY


def _with_sqlite_lock_retry(operation: Callable[[], _T], *, operation_name: str) -> _T:
    for attempt in range(1, SQLITE_LOCK_RETRY_ATTEMPTS + 1):
        try:
            return operation()
        except sqlite3.OperationalError as exc:
            if not _is_sqlite_lock_error(exc):
                raise
            if attempt >= SQLITE_LOCK_RETRY_ATTEMPTS:
                logger.error(
                    "SQLite lock persisted during %s after %d attempts: %s",
                    operation_name,
                    attempt,
                    exc,
                )
                raise
            delay = SQLITE_LOCK_RETRY_BASE_SECONDS * (2 ** (attempt - 1))
            logger.warning(
                "SQLite lock during %s; retrying in %.2fs (%d/%d): %s",
                operation_name,
                delay,
                attempt,
                SQLITE_LOCK_RETRY_ATTEMPTS,
                exc,
            )
            time.sleep(delay)
    raise RuntimeError(f"SQLite lock retry exhausted unexpectedly during {operation_name}")


def _execute_with_lock_retry(
    cursor: sqlite3.Cursor,
    sql: str,
    params: tuple[Any, ...] | list[Any] | None = None,
    *,
    operation_name: str,
) -> sqlite3.Cursor:
    if params is None:
        return _with_sqlite_lock_retry(lambda: cursor.execute(sql), operation_name=operation_name)
    return _with_sqlite_lock_retry(lambda: cursor.execute(sql, params), operation_name=operation_name)


def _commit_with_lock_retry(conn: sqlite3.Connection, *, operation_name: str) -> None:
    _with_sqlite_lock_retry(conn.commit, operation_name=operation_name)


def get_db_path() -> Path:
    global DB_PATH, _ENV_DERIVED_DB_PATH
    env_value = os.getenv("PAPERPIPE_DB_PATH")
    if env_value:
        resolved = Path(env_value).expanduser().resolve()
        DB_PATH = resolved
        _ENV_DERIVED_DB_PATH = resolved
        return resolved

    configured = Path(DB_PATH).expanduser().resolve()
    if _ENV_DERIVED_DB_PATH is not None and configured == _ENV_DERIVED_DB_PATH:
        _ENV_DERIVED_DB_PATH = None
        DB_PATH = state_db_path()
        configured = Path(DB_PATH).expanduser().resolve()
    if configured != _IMPORTED_DB_PATH:
        _ENV_DERIVED_DB_PATH = None
        return configured

    resolved = state_db_path()
    DB_PATH = resolved
    _ENV_DERIVED_DB_PATH = None
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


def _ensure_papers_table(cursor: sqlite3.Cursor) -> set[str]:
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS papers (
            paper_id TEXT PRIMARY KEY,
            doi TEXT,
            title TEXT NOT NULL,
            summary TEXT,
            year INTEGER,
            venue TEXT,
            source TEXT,
            slot TEXT,
            status TEXT NOT NULL DEFAULT 'NEW',
            confidence REAL,
            gate_decision TEXT,
            gate_reason TEXT,
            evidence_snippet TEXT,
            pdf_status TEXT,
            pdf_path TEXT,
            obsidian_path TEXT,
            ris_path TEXT,
            feedback_json TEXT,
            download_attempts TEXT,
            issues_state TEXT,
            agent_version TEXT,
            prompt_version TEXT,
            processed_date TEXT,
            processed_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_papers_status ON papers(status)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_papers_slot ON papers(slot)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_papers_doi ON papers(doi)")
    return _get_paper_columns(cursor)


def init_db():
    """Initialize runtime tables and apply lightweight compatibility migrations."""
    db_path = get_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, timeout=SQLITE_TIMEOUT_SECONDS)
    conn.row_factory = sqlite3.Row
    _configure_connection(conn)
    cursor = conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")

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
            if "summary" not in paper_cols:
                cursor.execute("ALTER TABLE papers ADD COLUMN summary TEXT")
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
    
    _commit_with_lock_retry(conn, operation_name="init_db")
    conn.close()

def get_db_connection():
    db_path = get_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, timeout=SQLITE_TIMEOUT_SECONDS)
    conn.row_factory = sqlite3.Row
    _configure_connection(conn)
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
    doi: Any = _DOI_UNSET,
    pdf_status: Optional[str] = None,
    local_pdf_path: Optional[str | Path] = None,
    ris_path: Optional[str | Path] = None,
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
            columns = _ensure_papers_table(cursor)

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

        if doi is _DOI_UNSET:
            doi_value: Any = _normalized_doi_or_none(identifier)
        elif doi in (None, ""):
            doi_value = None
        else:
            doi_value = _normalized_doi_or_none(doi)

        if "paper_id" in columns and "doi" in columns and doi_value:
            cursor.execute(
                "SELECT paper_id FROM papers WHERE doi = ? AND paper_id <> ? LIMIT 1",
                (doi_value, identifier),
            )
            exact = cursor.fetchone()
            if exact and exact["paper_id"]:
                identifier = str(exact["paper_id"])
            else:
                cursor.execute(
                    "SELECT paper_id, doi FROM papers WHERE doi IS NOT NULL AND paper_id <> ?",
                    (identifier,),
                )
                for existing in cursor.fetchall():
                    if normalize_doi(str(existing["doi"] or "")) == doi_value and existing["paper_id"]:
                        identifier = str(existing["paper_id"])
                        break

        if "paper_id" in columns:
            insert_cols.append("paper_id")
            insert_vals.append(identifier)
            update_set.append("paper_id=excluded.paper_id")
        if "doi" in columns:
            insert_cols.append("doi")
            insert_vals.append(doi_value)
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
        if "pdf_status" in columns and pdf_status is not None:
            insert_cols.append("pdf_status")
            insert_vals.append(str(pdf_status))
            update_set.append("pdf_status=excluded.pdf_status")
        if "ris_path" in columns and ris_path is not None:
            insert_cols.append("ris_path")
            insert_vals.append(str(ris_path))
            update_set.append("ris_path=excluded.ris_path")
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
            _execute_with_lock_retry(
                cursor,
                sql,
                tuple(insert_vals),
                operation_name="save_paper_state upsert",
            )
        else:
            sql = f"INSERT INTO papers ({', '.join(insert_cols)}) VALUES ({placeholders})"
            _execute_with_lock_retry(
                cursor,
                sql,
                tuple(insert_vals),
                operation_name="save_paper_state insert",
            )

        _commit_with_lock_retry(conn, operation_name="save_paper_state commit")
    except sqlite3.OperationalError as exc:
        conn.rollback()
        log_method = logger.error if _is_sqlite_lock_error(exc) else logger.warning
        log_method("Failed to save paper state for %s: %s", identifier, exc)
    finally:
        conn.close()


def find_duplicate_doi_paper_rows() -> List[Dict[str, Any]]:
    """Return existing paper rows that share a normalized DOI without mutating data."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        columns = _get_paper_columns(cursor)
        if "paper_id" not in columns or "doi" not in columns:
            return []

        select_columns = ["paper_id", "doi"]
        for optional_column in (
            "title",
            "source",
            "status",
            "pdf_status",
            "pdf_path",
            "obsidian_path",
            "processed_date",
            "created_at",
            "updated_at",
        ):
            if optional_column in columns:
                select_columns.append(optional_column)

        cursor.execute(
            f"""
            SELECT {', '.join(select_columns)}
            FROM papers
            WHERE doi IS NOT NULL AND TRIM(doi) <> ''
            """
        )

        grouped_rows: dict[str, list[dict[str, Any]]] = {}
        for row in cursor.fetchall():
            normalized_doi = _normalized_doi_or_none(row["doi"])
            if not normalized_doi:
                continue
            paper_row = {column: row[column] for column in select_columns}
            paper_row["normalized_doi"] = normalized_doi
            grouped_rows.setdefault(normalized_doi, []).append(paper_row)

        duplicate_groups: list[dict[str, Any]] = []
        for normalized_doi, rows in sorted(grouped_rows.items()):
            paper_ids = sorted({str(row.get("paper_id") or "") for row in rows if row.get("paper_id")})
            if len(rows) > 1 and len(paper_ids) > 1:
                duplicate_groups.append(
                    {
                        "normalized_doi": normalized_doi,
                        "row_count": len(rows),
                        "paper_ids": paper_ids,
                        "rows": sorted(rows, key=lambda item: str(item.get("paper_id") or "")),
                    }
                )
        return duplicate_groups
    except sqlite3.OperationalError:
        return []
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
        _execute_with_lock_retry(
            cursor,
            f"UPDATE papers SET reading_status = ? WHERE {' OR '.join(conditions)}",
            params,
            operation_name="update_reading_status",
        )
        _commit_with_lock_retry(conn, operation_name="update_reading_status commit")
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
        _execute_with_lock_retry(
            cursor,
            f"UPDATE papers SET is_retracted = 1 WHERE {' OR '.join(conditions)}",
            params,
            operation_name="mark_as_retracted",
        )
        _commit_with_lock_retry(conn, operation_name="mark_as_retracted commit")
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
    write_ops_since_commit = 0
    conn = get_db_connection()
    cursor = conn.cursor()
    paper_columns = _get_paper_columns(cursor)

    for item in items:
        paper_id = item.get('citationKey')
        if not paper_id:
            continue

        title = item.get('title', 'Unknown Title')
        summary = item.get('abstractNote', '')
        doi_value = _normalized_doi_or_none(item.get("DOI") or item.get("doi"))
        
        # Find PDF path
        pdf_path = None
        for att in item.get("attachments", []):
            if att.get("path") and att["path"].lower().endswith(".pdf"):
                pdf_path = att["path"]
                break
        
        existing_select = "paper_id, pdf_path, summary"
        if "doi" in paper_columns:
            existing_select += ", doi"
        if "source" in paper_columns:
            existing_select += ", source"

        # Check if exists by Zotero citation key first, then by normalized DOI.
        cursor.execute(f"SELECT {existing_select} FROM papers WHERE paper_id = ?", (paper_id,))
        row = cursor.fetchone()
        if row is None and "doi" in paper_columns and doi_value:
            cursor.execute(f"SELECT {existing_select} FROM papers WHERE doi IS NOT NULL")
            for existing in cursor.fetchall():
                if _normalized_doi_or_none(existing["doi"]) == doi_value:
                    row = existing
                    paper_id = str(existing["paper_id"])
                    break

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

            if "doi" in paper_columns and doi_value and not row["doi"]:
                updates.append("doi = ?")
                params.append(doi_value)

            if "source" in paper_columns and not row["source"]:
                updates.append("source = ?")
                params.append("zotero")

            if updates:
                params.append(paper_id)
                _execute_with_lock_retry(
                    cursor,
                    f"UPDATE papers SET {', '.join(updates)} WHERE paper_id = ?",
                    params,
                    operation_name="sync_zotero_to_db update",
                )
                write_ops_since_commit += 1
                if write_ops_since_commit >= ZOTERO_SYNC_COMMIT_BATCH_SIZE:
                    _commit_with_lock_retry(conn, operation_name="sync_zotero_to_db batch commit")
                    write_ops_since_commit = 0
        else:
            # Insert new
            try:
                insert_cols = ["paper_id", "title", "summary", "status"]
                insert_vals = [paper_id, title, summary, "NEW"]
                if "doi" in paper_columns:
                    insert_cols.append("doi")
                    insert_vals.append(doi_value)
                if "source" in paper_columns:
                    insert_cols.append("source")
                    insert_vals.append("zotero")
                if "issues_state" in paper_columns:
                    insert_cols.append("issues_state")
                    insert_vals.append("unavailable")
                if "pdf_path" in paper_columns:
                    insert_cols.append("pdf_path")
                    insert_vals.append(pdf_path)
                if "created_at" in paper_columns:
                    insert_cols.append("created_at")
                    insert_vals.append(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                if "updated_at" in paper_columns:
                    insert_cols.append("updated_at")
                    insert_vals.append(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

                placeholders = ",".join("?" for _ in insert_cols)
                _execute_with_lock_retry(
                    cursor,
                    f"INSERT INTO papers ({', '.join(insert_cols)}) VALUES ({placeholders})",
                    tuple(insert_vals),
                    operation_name="sync_zotero_to_db insert",
                )
                new_count += 1
                write_ops_since_commit += 1
                if write_ops_since_commit >= ZOTERO_SYNC_COMMIT_BATCH_SIZE:
                    _commit_with_lock_retry(conn, operation_name="sync_zotero_to_db batch commit")
                    write_ops_since_commit = 0
            except sqlite3.IntegrityError:
                pass # Should not happen given check above, but safe to ignore
    
    if write_ops_since_commit:
        _commit_with_lock_retry(conn, operation_name="sync_zotero_to_db final commit")
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

        _execute_with_lock_retry(
            cursor,
            query,
            params,
            operation_name="update_paper_status",
        )
        _commit_with_lock_retry(conn, operation_name="update_paper_status commit")
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
    _commit_with_lock_retry(conn, operation_name="init_run_stats_table commit")
    conn.close()


def _ensure_legacy_runs_table(cursor: sqlite3.Cursor) -> None:
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS runs (
            date TEXT PRIMARY KEY,
            status TEXT,
            processed_count INTEGER,
            last_run_at TIMESTAMP
        )
        """
    )


def record_run_status(
    target_date: str,
    status: str,
    *,
    processed_count: int | None = None,
    last_run_at: str | None = None,
) -> None:
    """Compatibility helper for legacy daily-run status tracking."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        _ensure_legacy_runs_table(cursor)
        normalized_status = str(status or "").strip().upper()
        resolved_last_run_at = last_run_at or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        _execute_with_lock_retry(
            cursor,
            """
            INSERT INTO runs (date, status, processed_count, last_run_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(date) DO UPDATE SET
                status = excluded.status,
                processed_count = COALESCE(excluded.processed_count, runs.processed_count),
                last_run_at = excluded.last_run_at
            """,
            (
                target_date,
                normalized_status,
                processed_count,
                resolved_last_run_at,
            ),
            operation_name="record_run_status",
        )
        _commit_with_lock_retry(conn, operation_name="record_run_status commit")
    finally:
        conn.close()


def log_run_stat(profile_id: str, items_fetched: int, limit_hit: bool) -> None:
    conn = get_db_connection()
    cursor = conn.cursor()
    _execute_with_lock_retry(
        cursor,
        """
        INSERT INTO run_stats (profile_id, items_fetched, limit_hit)
        VALUES (?, ?, ?)
        """,
        (profile_id, items_fetched, int(limit_hit)),
        operation_name="log_run_stat",
    )
    _commit_with_lock_retry(conn, operation_name="log_run_stat commit")
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
                _execute_with_lock_retry(
                    cursor,
                    """
                    UPDATE papers
                    SET status = 'APPROVED', updated_at = CURRENT_TIMESTAMP
                    WHERE paper_id = ?
                    """,
                    (c["paper_id"],),
                    operation_name="reconcile_approved_decisions gate update",
                )
            else:
                _execute_with_lock_retry(
                    cursor,
                    """
                    UPDATE papers
                    SET status = 'APPROVED',
                        gate_decision = 'APPROVED',
                        gate_reason = COALESCE(gate_reason, 'Reconciled from feedback_json decision'),
                        updated_at = CURRENT_TIMESTAMP
                    WHERE paper_id = ?
                    """,
                    (c["paper_id"],),
                    operation_name="reconcile_approved_decisions feedback update",
                )
            updated += 1
        _commit_with_lock_retry(conn, operation_name="reconcile_approved_decisions commit")

    conn.close()
    return {
        "dry_run": dry_run,
        "candidates": candidates,
        "candidate_count": len(candidates),
        "updated_count": updated,
    }
