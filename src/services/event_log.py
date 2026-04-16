from __future__ import annotations

from datetime import datetime, timezone
import json
import sqlite3
from typing import Any

from src.db_utils import get_db_connection
from src.services.identity import new_job_id


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _dump_json(payload: Any | None) -> str | None:
    if payload is None:
        return None
    return json.dumps(payload, ensure_ascii=False, default=str)


def _load_json(raw: str | None) -> Any | None:
    if not raw:
        return None
    try:
        return json.loads(raw)
    except Exception:
        return None


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
                _dump_json(params),
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
        params.append(_dump_json(metrics))
    if not assignments:
        return

    owns_conn = conn is None
    connection = conn or get_db_connection()
    try:
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
                message,
                _dump_json(payload),
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
    conn: sqlite3.Connection | None = None,
) -> str:
    action_id = new_job_id()
    owns_conn = conn is None
    connection = conn or get_db_connection()
    try:
        connection.execute(
            """
            INSERT INTO user_actions (action_id, ts, paper_id, action_type, source, payload_json)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (action_id, _utc_now(), paper_id, action_type, source, _dump_json(payload)),
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
                _dump_json(payload),
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
        try:
            row = connection.execute(
                "SELECT params_json FROM execution_runs WHERE run_id = ? LIMIT 1",
                (normalized,),
            ).fetchone()
        except sqlite3.OperationalError as exc:
            if "no such table: execution_runs" in str(exc).lower():
                return {}
            raise
        if not row:
            return {}
        payload = _load_json(row["params_json"])
        return payload if isinstance(payload, dict) else {}
    finally:
        connection.close()


def list_job_events(job_id: str, *, limit: int = 500) -> list[dict[str, Any]]:
    connection = get_db_connection()
    try:
        try:
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
        except sqlite3.OperationalError as exc:
            if "no such table: job_events" in str(exc).lower():
                return []
            raise
        return [dict(row) for row in rows]
    finally:
        connection.close()


def list_run_events(run_id: str, *, limit: int = 500) -> list[dict[str, Any]]:
    connection = get_db_connection()
    try:
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
            # Older local/E2E DB snapshots may still be missing the table entirely
            # or may still have job_events without run_id.
            message = str(exc).lower()
            if "no such table: job_events" in message or "no such column: run_id" in message:
                return []
            raise
        return [dict(row) for row in rows]
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

        try:
            rows = connection.execute(sql, params).fetchall()
        except sqlite3.OperationalError as exc:
            if "no such table: user_actions" in str(exc).lower():
                return []
            raise
        output: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            item["payload"] = _load_json(item.pop("payload_json", None))
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
        params.append(max(1, int(limit)))
        rows = connection.execute(sql, params).fetchall()

        items: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            item["payload"] = _load_json(item.pop("payload_json", None))
            items.append(item)
        return items
    finally:
        connection.close()
