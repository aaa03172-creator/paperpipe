from __future__ import annotations

from datetime import datetime, timezone
import json
import re
import sqlite3
from typing import Any

from src.db_utils import get_db_connection
from src.services.identity import new_job_id


_EVENT_SECRET_KEY_RE = re.compile(
    r"(?:^|[_-])(?:authorization|api[_-]?key|token|secret|password|cookie)(?:$|[_-])",
    re.IGNORECASE,
)
_EVENT_AUTH_VALUE_RE = re.compile(r"\b(?:Basic|Bearer)\s+[A-Za-z0-9._~+/\-:=]+")
_EVENT_OPENAI_STYLE_KEY_RE = re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9][A-Za-z0-9_-]{7,}\b")
_EVENT_DATABASE_URL_RE = re.compile(r"\b(?:postgres(?:ql)?|mysql|mongodb(?:\+srv)?|redis)://[^\s,;]+", re.IGNORECASE)
_EVENT_REDACTED = "<redacted>"


def _ensure_event_log_tables(connection: sqlite3.Connection) -> None:
    connection.execute(
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
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS job_events (
            event_id TEXT PRIMARY KEY,
            job_id TEXT NOT NULL,
            run_id TEXT,
            ts TEXT NOT NULL,
            level TEXT NOT NULL,
            event_type TEXT NOT NULL,
            message TEXT,
            payload_json TEXT
        )
        """
    )
    job_event_cols = {row[1] for row in connection.execute("PRAGMA table_info(job_events)").fetchall()}
    if "run_id" not in job_event_cols:
        connection.execute("ALTER TABLE job_events ADD COLUMN run_id TEXT")
    if "payload_json" not in job_event_cols:
        connection.execute("ALTER TABLE job_events ADD COLUMN payload_json TEXT")
    connection.execute(
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
    connection.execute(
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
    connection.execute("CREATE INDEX IF NOT EXISTS idx_execution_runs_paper ON execution_runs(paper_id)")
    connection.execute("CREATE INDEX IF NOT EXISTS idx_job_events_job ON job_events(job_id, ts)")
    connection.execute("CREATE INDEX IF NOT EXISTS idx_job_events_run ON job_events(run_id, ts)")
    connection.execute("CREATE INDEX IF NOT EXISTS idx_user_actions_paper ON user_actions(paper_id, ts)")
    connection.execute("CREATE INDEX IF NOT EXISTS idx_request_audits_ts ON request_audits(ts)")
    connection.execute("CREATE INDEX IF NOT EXISTS idx_request_audits_path ON request_audits(path, ts)")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _dump_json(payload: Any | None) -> str | None:
    if payload is None:
        return None
    return json.dumps(payload, ensure_ascii=False, default=str)


def _sanitize_event_text(value: str) -> str:
    text = _EVENT_AUTH_VALUE_RE.sub(_EVENT_REDACTED, value)
    text = _EVENT_OPENAI_STYLE_KEY_RE.sub(_EVENT_REDACTED, text)
    text = _EVENT_DATABASE_URL_RE.sub(_EVENT_REDACTED, text)
    return text


def _sanitize_event_payload(payload: Any) -> Any:
    if isinstance(payload, dict):
        sanitized: dict[str, Any] = {}
        for key, value in payload.items():
            key_text = str(key)
            if _EVENT_SECRET_KEY_RE.search(key_text):
                sanitized[key_text] = _EVENT_REDACTED
            else:
                sanitized[key_text] = _sanitize_event_payload(value)
        return sanitized
    if isinstance(payload, list):
        return [_sanitize_event_payload(item) for item in payload]
    if isinstance(payload, tuple):
        return [_sanitize_event_payload(item) for item in payload]
    if isinstance(payload, str):
        return _sanitize_event_text(payload)
    return payload


def sanitize_event_text_for_log(value: str | None) -> str | None:
    if value is None:
        return None
    return _sanitize_event_text(str(value))


def sanitize_event_payload_for_log(payload: Any) -> Any:
    return _sanitize_event_payload(payload)


def _load_json(raw: str | None) -> Any | None:
    if not raw:
        return None
    try:
        return json.loads(raw)
    except Exception:
        return None


def _sanitized_payload_json_for_read(raw: str | None) -> str | None:
    if raw is None:
        return None
    payload = _load_json(raw)
    if payload is None:
        return _dump_json(_sanitize_event_text(str(raw)))
    return _dump_json(_sanitize_event_payload(payload))


def _sanitized_job_event_row(row: sqlite3.Row) -> dict[str, Any]:
    item = dict(row)
    message = item.get("message")
    if isinstance(message, str):
        item["message"] = _sanitize_event_text(message)
    item["payload_json"] = _sanitized_payload_json_for_read(item.get("payload_json"))
    return item


def ensure_execution_run(
    *,
    run_id: str,
    paper_id: str | None = None,
    trigger_source: str | None = None,
    pipeline_profile: str | None = None,
    status: str = "queued",
    params: dict[str, Any] | None = None,
    conn: sqlite3.Connection | None = None,
) -> None:
    owns_conn = conn is None
    connection = conn or get_db_connection()
    try:
        _ensure_event_log_tables(connection)
        connection.execute(
            """
            INSERT INTO execution_runs (
                run_id, paper_id, trigger_source, pipeline_profile, status, created_at, params_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(run_id) DO UPDATE SET
                paper_id = COALESCE(execution_runs.paper_id, excluded.paper_id),
                trigger_source = COALESCE(execution_runs.trigger_source, excluded.trigger_source),
                pipeline_profile = COALESCE(execution_runs.pipeline_profile, excluded.pipeline_profile),
                params_json = COALESCE(execution_runs.params_json, excluded.params_json)
            """,
            (
                run_id,
                paper_id,
                trigger_source,
                pipeline_profile,
                status,
                _utc_now(),
                _dump_json(_sanitize_event_payload(params)),
            ),
        )
        if owns_conn:
            connection.commit()
    finally:
        if owns_conn:
            connection.close()


def update_execution_run(
    *,
    run_id: str,
    status: str | None = None,
    started_at: str | None = None,
    finished_at: str | None = None,
    metrics: dict[str, Any] | None = None,
    conn: sqlite3.Connection | None = None,
) -> None:
    assignments: list[str] = []
    params: list[Any] = []
    if status is not None:
        assignments.append("status = ?")
        params.append(status)
    if started_at is not None:
        assignments.append("started_at = ?")
        params.append(started_at)
    if finished_at is not None:
        assignments.append("finished_at = ?")
        params.append(finished_at)
    if metrics is not None:
        assignments.append("metrics_json = ?")
        params.append(_dump_json(_sanitize_event_payload(metrics)))
    if not assignments:
        return

    owns_conn = conn is None
    connection = conn or get_db_connection()
    try:
        _ensure_event_log_tables(connection)
        params.append(run_id)
        connection.execute(
            f"UPDATE execution_runs SET {', '.join(assignments)} WHERE run_id = ?",
            params,
        )
        if owns_conn:
            connection.commit()
    finally:
        if owns_conn:
            connection.close()


def log_job_event(
    *,
    job_id: str,
    run_id: str | None = None,
    level: str,
    event_type: str,
    message: str | None = None,
    payload: dict[str, Any] | None = None,
    ts: str | None = None,
    conn: sqlite3.Connection | None = None,
) -> str:
    event_id = new_job_id()
    owns_conn = conn is None
    connection = conn or get_db_connection()
    try:
        _ensure_event_log_tables(connection)
        connection.execute(
            """
            INSERT INTO job_events (
                event_id, job_id, run_id, ts, level, event_type, message, payload_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event_id,
                job_id,
                run_id,
                ts or _utc_now(),
                str(level or "INFO").upper(),
                event_type,
                _sanitize_event_text(message) if message is not None else None,
                _dump_json(_sanitize_event_payload(payload)),
            ),
        )
        if owns_conn:
            connection.commit()
        return event_id
    finally:
        if owns_conn:
            connection.close()


def log_user_action(
    *,
    paper_id: str | None,
    action_type: str,
    source: str,
    payload: dict[str, Any] | None = None,
    ts: str | None = None,
    conn: sqlite3.Connection | None = None,
) -> str:
    action_id = new_job_id()
    owns_conn = conn is None
    connection = conn or get_db_connection()
    try:
        _ensure_event_log_tables(connection)
        connection.execute(
            """
            INSERT INTO user_actions (action_id, ts, paper_id, action_type, source, payload_json)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (action_id, ts or _utc_now(), paper_id, action_type, source, _dump_json(_sanitize_event_payload(payload))),
        )
        if owns_conn:
            connection.commit()
        return action_id
    finally:
        if owns_conn:
            connection.close()


def log_request_audit(
    *,
    source: str,
    client_ip: str | None,
    host: str | None,
    method: str,
    path: str,
    status_code: int,
    outcome: str,
    payload: dict[str, Any] | None = None,
    ts: str | None = None,
    conn: sqlite3.Connection | None = None,
) -> str:
    audit_id = new_job_id()
    owns_conn = conn is None
    connection = conn or get_db_connection()
    try:
        _ensure_event_log_tables(connection)
        connection.execute(
            """
            INSERT INTO request_audits (
                audit_id, ts, source, client_ip, host, method, path, status_code, outcome, payload_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                audit_id,
                ts or _utc_now(),
                source,
                client_ip,
                host,
                method.upper(),
                path,
                int(status_code),
                outcome,
                _dump_json(_sanitize_event_payload(payload)),
            ),
        )
        if owns_conn:
            connection.commit()
        return audit_id
    finally:
        if owns_conn:
            connection.close()


def get_execution_run_params(run_id: str | None) -> dict[str, Any]:
    normalized = str(run_id or "").strip()
    if not normalized:
        return {}

    connection = get_db_connection()
    try:
        _ensure_event_log_tables(connection)
        row = connection.execute(
            "SELECT params_json FROM execution_runs WHERE run_id = ? LIMIT 1",
            (normalized,),
        ).fetchone()
        if not row:
            return {}
        payload = _load_json(row["params_json"])
        sanitized = _sanitize_event_payload(payload)
        return sanitized if isinstance(sanitized, dict) else {}
    finally:
        connection.close()


def list_job_events(job_id: str, *, limit: int = 500) -> list[dict[str, Any]]:
    connection = get_db_connection()
    try:
        _ensure_event_log_tables(connection)
        rows = connection.execute(
            """
            SELECT event_id, job_id, run_id, ts, level, event_type, message, payload_json
            FROM job_events
            WHERE job_id = ?
            ORDER BY ts ASC, rowid ASC
            LIMIT ?
            """,
            (job_id, limit),
        ).fetchall()
        return [_sanitized_job_event_row(row) for row in rows]
    finally:
        connection.close()


def list_run_events(run_id: str, *, limit: int = 500) -> list[dict[str, Any]]:
    connection = get_db_connection()
    try:
        _ensure_event_log_tables(connection)
        try:
            rows = connection.execute(
                """
                SELECT event_id, job_id, run_id, ts, level, event_type, message, payload_json
                FROM job_events
                WHERE run_id = ?
                ORDER BY ts ASC, rowid ASC
                LIMIT ?
                """,
                (run_id, limit),
            ).fetchall()
        except sqlite3.OperationalError as exc:
            # Older local/E2E DB snapshots may still have job_events without run_id.
            if "no such column: run_id" in str(exc).lower():
                return []
            raise
        return [_sanitized_job_event_row(row) for row in rows]
    finally:
        connection.close()


def list_user_actions(
    *,
    paper_id: str | None = None,
    action_type: str | None = None,
    source: str | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    connection = get_db_connection()
    try:
        _ensure_event_log_tables(connection)
        where: list[str] = []
        params: list[Any] = []
        if paper_id:
            where.append("paper_id = ?")
            params.append(str(paper_id))
        if action_type:
            where.append("action_type = ?")
            params.append(str(action_type))
        if source:
            where.append("source = ?")
            params.append(str(source))

        sql = """
            SELECT action_id, ts, paper_id, action_type, source, payload_json
            FROM user_actions
        """
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY ts DESC, rowid DESC LIMIT ?"
        params.append(max(1, int(limit)))

        rows = connection.execute(sql, params).fetchall()
        output: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            item["payload"] = _sanitize_event_payload(_load_json(item.pop("payload_json", None)))
            output.append(item)
        return output
    finally:
        connection.close()


def list_request_audits(
    *,
    path: str | None = None,
    outcome: str | None = None,
    source: str | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    connection = get_db_connection()
    try:
        _ensure_event_log_tables(connection)
        where: list[str] = []
        params: list[Any] = []
        if path:
            where.append("path = ?")
            params.append(str(path))
        if outcome:
            where.append("outcome = ?")
            params.append(str(outcome))
        if source:
            where.append("source = ?")
            params.append(str(source))

        sql = """
            SELECT audit_id, ts, source, client_ip, host, method, path, status_code, outcome, payload_json
            FROM request_audits
        """
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY ts DESC, rowid DESC LIMIT ?"
        params.append(limit)
        rows = connection.execute(sql, params).fetchall()

        items: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            item["payload"] = _sanitize_event_payload(_load_json(item.pop("payload_json", None)))
            items.append(item)
        return items
    finally:
        connection.close()
