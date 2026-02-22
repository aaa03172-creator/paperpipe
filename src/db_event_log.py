from __future__ import annotations

import atexit
import json
import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from src.core.paper_identity import make_paper_key
from src.db_utils import get_db_connection

_EVENT_BUFFER: list[tuple[str, str, str, str, str, str | None, str | None]] = []
_EVENT_BUFFER_LOCK = threading.Lock()
_EVENT_BUFFER_LIMIT = 25


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _json_or_none(payload: Any) -> str | None:
    if payload is None:
        return None
    try:
        return json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
    except Exception:
        return json.dumps(str(payload), ensure_ascii=False)


def create_run(
    paper_id: str,
    trigger_source: str,
    pipeline_profile: str,
    params: Optional[dict[str, Any]] = None,
    run_id: Optional[str] = None,
) -> str:
    rid = run_id or f"run_{uuid.uuid4().hex}"
    now = _now_iso()

    conn = get_db_connection()
    try:
        conn.execute(
            """
            INSERT INTO runs (
                run_id, date, paper_id, trigger_source, pipeline_profile,
                status, created_at, last_run_at, params_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(run_id) DO UPDATE SET
                paper_id=excluded.paper_id,
                trigger_source=excluded.trigger_source,
                pipeline_profile=excluded.pipeline_profile,
                status=excluded.status,
                params_json=excluded.params_json,
                created_at=COALESCE(runs.created_at, excluded.created_at),
                last_run_at=excluded.last_run_at
            """,
            (
                rid,
                rid,  # legacy compatibility: date column may be PK in old DBs
                paper_id,
                trigger_source,
                pipeline_profile,
                "running",
                now,
                now,
                _json_or_none(params),
            ),
        )
        conn.commit()
    finally:
        conn.close()
    return rid


def finish_run(run_id: str, status: str, metrics: Optional[dict[str, Any]] = None) -> None:
    now = _now_iso()
    conn = get_db_connection()
    try:
        conn.execute(
            """
            UPDATE runs
            SET status = ?, finished_at = ?, last_run_at = ?, metrics_json = ?
            WHERE run_id = ?
            """,
            (status, now, now, _json_or_none(metrics), run_id),
        )
        conn.commit()
    finally:
        conn.close()


def create_job(
    run_id: str,
    paper_id: str,
    job_type: str,
    params: Optional[dict[str, Any]] = None,
    job_id: Optional[str] = None,
) -> str:
    jid = job_id or str(uuid.uuid4())
    now = _now_iso()

    conn = get_db_connection()
    try:
        conn.execute(
            """
            INSERT INTO jobs (job_id, run_id, paper_id, job_type, status, created_at, params_json)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(job_id) DO UPDATE SET
                run_id=excluded.run_id,
                paper_id=excluded.paper_id,
                job_type=excluded.job_type,
                status=excluded.status,
                params_json=excluded.params_json
            """,
            (jid, run_id, paper_id, job_type, "queued", now, _json_or_none(params)),
        )
        conn.commit()
    finally:
        conn.close()
    return jid


def update_job_status(
    job_id: str,
    status: str,
    result_ref: Optional[str] = None,
    error_code: Optional[str] = None,
    error_detail: Optional[str] = None,
    error_taxonomy_code: Optional[str] = None,
    metrics: Optional[dict[str, Any]] = None,
) -> None:
    now = _now_iso()
    started_at = now if status == "running" else None
    finished_at = now if status in {"completed", "failed", "cancelled", "succeeded"} else None

    conn = get_db_connection()
    try:
        conn.execute(
            """
            UPDATE jobs
            SET status = ?,
                started_at = COALESCE(started_at, ?),
                finished_at = COALESCE(?, finished_at),
                result_ref = COALESCE(?, result_ref),
                error_code = COALESCE(?, error_code),
                error_detail = COALESCE(?, error_detail),
                error_taxonomy_code = COALESCE(?, error_taxonomy_code),
                metrics_json = COALESCE(?, metrics_json)
            WHERE job_id = ?
            """,
            (
                status,
                started_at,
                finished_at,
                result_ref,
                error_code,
                error_detail,
                error_taxonomy_code,
                _json_or_none(metrics),
                job_id,
            ),
        )
        conn.commit()
    finally:
        conn.close()


def log_event(
    job_id: str,
    level: str,
    event_type: str,
    message: Optional[str] = None,
    payload: Optional[dict[str, Any]] = None,
) -> str:
    event_id = str(uuid.uuid4())
    _insert_events(
        [
            (
                event_id,
                job_id,
                _now_iso(),
                level,
                event_type,
                message,
                _json_or_none(payload),
            )
        ]
    )
    return event_id


def log_event_buffered(
    job_id: str,
    level: str,
    event_type: str,
    message: Optional[str] = None,
    payload: Optional[dict[str, Any]] = None,
) -> str:
    event_id = str(uuid.uuid4())
    record = (
        event_id,
        job_id,
        _now_iso(),
        level,
        event_type,
        message,
        _json_or_none(payload),
    )
    should_flush = False
    with _EVENT_BUFFER_LOCK:
        _EVENT_BUFFER.append(record)
        if len(_EVENT_BUFFER) >= _EVENT_BUFFER_LIMIT:
            should_flush = True
    if should_flush:
        flush_event_buffer()
    return event_id


def flush_event_buffer() -> int:
    with _EVENT_BUFFER_LOCK:
        if not _EVENT_BUFFER:
            return 0
        batch = list(_EVENT_BUFFER)
        _EVENT_BUFFER.clear()
    _insert_events(batch)
    return len(batch)


def set_event_buffer_limit(limit: int) -> None:
    global _EVENT_BUFFER_LIMIT
    _EVENT_BUFFER_LIMIT = max(1, int(limit))


def _insert_events(events: list[tuple[str, str, str, str, str, str | None, str | None]]) -> None:
    if not events:
        return
    conn = get_db_connection()
    try:
        conn.executemany(
            """
            INSERT INTO job_events (event_id, job_id, ts, level, event_type, message, payload_json)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            events,
        )
        conn.commit()
    finally:
        conn.close()


def log_user_action(
    paper_id: str,
    action_type: str,
    source: str,
    payload: Optional[dict[str, Any]] = None,
) -> str:
    action_id = str(uuid.uuid4())
    conn = get_db_connection()
    try:
        conn.execute(
            """
            INSERT INTO user_actions (action_id, ts, paper_id, action_type, source, payload_json)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                action_id,
                _now_iso(),
                paper_id,
                action_type,
                source,
                _json_or_none(payload),
            ),
        )

        # Best-effort paper_key sync for touched paper rows.
        try:
            conn.execute(
                """
                UPDATE papers
                SET paper_key = COALESCE(NULLIF(TRIM(paper_key), ''), ?),
                    updated_at = CURRENT_TIMESTAMP
                WHERE (paper_id = ? OR doi = ?) AND (paper_key IS NULL OR TRIM(paper_key) = '')
                """,
                (make_paper_key(paper_id), paper_id, paper_id),
            )
        except Exception:
            pass
        conn.commit()
    finally:
        conn.close()
    return action_id


atexit.register(flush_event_buffer)
