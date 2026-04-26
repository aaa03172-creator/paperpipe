from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.jobs.queue import DuplicateOpenJobError, JobQueue, QueueBackpressureError
from src.services.event_log import get_execution_run_params, log_job_event, update_execution_run
from src.services.runtime_paths import storage_root


STALE_RUNNING_RECLAIMED_ERROR_CODE = "STALE_RUNNING_RECLAIMED"
REQUEUE_RECLAIMED_TRIGGER_SOURCE = "ops_requeue_reclaimed"
STALE_RUNNING_INCIDENT_EVENT_TYPE = "job_stale_incident_snapshot_captured"
STALE_RUNNING_INCIDENTS_DIR_NAME = "stale_running_incidents"
INCIDENT_SNAPSHOT_STRING_LIMIT = 1000
INCIDENT_SNAPSHOT_LIST_LIMIT = 20
INCIDENT_SNAPSHOT_REDACTED = "<redacted>"
INCIDENT_SNAPSHOT_SECRET_KEY_PARTS = (
    "authorization",
    "api_key",
    "apikey",
    "token",
    "secret",
    "password",
    "cookie",
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_optional_datetime(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    normalized = text.replace("Z", "+00:00")
    if "T" not in normalized and " " in normalized:
        normalized = normalized.replace(" ", "T", 1)
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _recommended_action(*, log_exists: bool, artifact_dir_exists: bool) -> str:
    if artifact_dir_exists and log_exists:
        return "inspect_artifacts_and_log_before_manual_recovery"
    if artifact_dir_exists:
        return "inspect_artifacts_before_manual_recovery"
    if log_exists:
        return "inspect_job_log_before_manual_recovery"
    return "inspect_worker_health_before_manual_recovery"


def _row_activity_anchor(row: sqlite3.Row) -> datetime | None:
    heartbeat_at = _parse_optional_datetime(
        row["heartbeat_at"] if "heartbeat_at" in row.keys() else None
    )
    started_at = _parse_optional_datetime(row["started_at"] if "started_at" in row.keys() else None)
    created_at = _parse_optional_datetime(row["created_at"] if "created_at" in row.keys() else None)
    return heartbeat_at or started_at or created_at


def _row_value(row: sqlite3.Row, key: str, default: Any = None) -> Any:
    return row[key] if key in row.keys() else default


def _safe_path_segment(value: str) -> str:
    segment = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in value.strip())
    return (segment[:80] or "job").strip("._") or "job"


def _snapshot_key_looks_secret(key: str | None) -> bool:
    normalized = str(key or "").strip().lower().replace("-", "_")
    return any(part in normalized for part in INCIDENT_SNAPSHOT_SECRET_KEY_PARTS)


def _bounded_snapshot_value(value: Any, *, key_name: str | None = None) -> Any:
    if _snapshot_key_looks_secret(key_name):
        return INCIDENT_SNAPSHOT_REDACTED
    if isinstance(value, str):
        if len(value) <= INCIDENT_SNAPSHOT_STRING_LIMIT:
            return value
        return f"{value[:INCIDENT_SNAPSHOT_STRING_LIMIT]}...[truncated]"
    if isinstance(value, dict):
        return {
            str(key)[:120]: _bounded_snapshot_value(item, key_name=str(key))
            for key, item in list(value.items())[:INCIDENT_SNAPSHOT_LIST_LIMIT]
        }
    if isinstance(value, list):
        return [_bounded_snapshot_value(item) for item in value[:INCIDENT_SNAPSHOT_LIST_LIMIT]]
    if isinstance(value, tuple):
        return [_bounded_snapshot_value(item) for item in list(value)[:INCIDENT_SNAPSHOT_LIST_LIMIT]]
    return value


def _load_bounded_json_object(raw: Any) -> dict[str, Any] | None:
    text = str(raw or "").strip()
    if not text:
        return None
    try:
        payload = json.loads(text)
    except Exception:
        return None
    if not isinstance(payload, dict):
        return None
    return _bounded_snapshot_value(payload)


def _path_observation(raw_path: Any) -> dict[str, Any]:
    path_text = str(raw_path or "").strip()
    observation: dict[str, Any] = {
        "path": path_text or None,
        "exists": False,
        "kind": None,
        "mtime": None,
        "size_bytes": None,
    }
    if not path_text:
        return observation

    path = Path(path_text).expanduser()
    try:
        if not path.exists():
            return observation
        stat = path.stat()
    except OSError as exc:
        observation["error"] = str(exc)
        return observation

    observation["exists"] = True
    observation["kind"] = "directory" if path.is_dir() else "file" if path.is_file() else "other"
    observation["mtime"] = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat()
    if path.is_file():
        observation["size_bytes"] = int(stat.st_size)
    return observation


def _snapshot_row(row: sqlite3.Row | None, keys: list[str]) -> dict[str, Any] | None:
    if row is None:
        return None
    payload: dict[str, Any] = {}
    for key in keys:
        value = _row_value(row, key)
        if value is None:
            payload[key] = None
        elif key.endswith("_json"):
            payload[key] = _load_bounded_json_object(value) or _bounded_snapshot_value(
                value,
                key_name=key,
            )
        else:
            payload[key] = _bounded_snapshot_value(value, key_name=key)
    return payload


def _collect_recent_job_events(
    conn: sqlite3.Connection,
    *,
    job_id: str,
    limit: int = INCIDENT_SNAPSHOT_LIST_LIMIT,
) -> list[dict[str, Any]]:
    try:
        rows = conn.execute(
            """
            SELECT ts, level, event_type, message, payload_json
            FROM job_events
            WHERE job_id = ?
            ORDER BY ts DESC
            LIMIT ?
            """,
            (job_id, int(limit)),
        ).fetchall()
    except sqlite3.OperationalError:
        return []

    events: list[dict[str, Any]] = []
    for row in rows:
        entry: dict[str, Any] = {
            "ts": str(row["ts"] or "").strip() or None,
            "level": str(row["level"] or "").strip() or None,
            "event_type": str(row["event_type"] or "").strip() or None,
            "message": _bounded_snapshot_value(str(row["message"] or "").strip())
            if row["message"]
            else None,
        }
        parsed_payload = _load_bounded_json_object(row["payload_json"])
        if parsed_payload is not None:
            entry["payload"] = parsed_payload
        elif str(row["payload_json"] or "").strip():
            entry["payload_parse_error"] = True
        events.append(entry)
    events.reverse()
    return events


def _incident_snapshot_root() -> Path:
    return storage_root() / STALE_RUNNING_INCIDENTS_DIR_NAME


def _incident_file_mtime(path: Path) -> str | None:
    try:
        return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat()
    except OSError:
        return None


def _incident_sort_timestamp(entry: dict[str, Any]) -> datetime:
    parsed = _parse_optional_datetime(entry.get("captured_at")) or _parse_optional_datetime(
        entry.get("file_mtime")
    )
    return parsed or datetime.min.replace(tzinfo=timezone.utc)


def _load_incident_summary(incident_path: Path) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "incident_id": incident_path.parent.name,
        "incident_type": None,
        "captured_at": None,
        "job_id": None,
        "run_id": None,
        "paper_id": None,
        "status": None,
        "is_stale_candidate": False,
        "running_for_seconds": None,
        "stale_after_seconds": None,
        "artifact_kind": None,
        "layer": None,
        "incident_path": str(incident_path),
        "file_mtime": _incident_file_mtime(incident_path),
        "path_observations_available": False,
        "recent_job_events_count": 0,
        "parse_error": False,
    }
    try:
        raw = json.loads(incident_path.read_text(encoding="utf-8"))
    except Exception:
        entry["parse_error"] = True
        return entry
    if not isinstance(raw, dict):
        entry["parse_error"] = True
        return entry

    incident_id = str(raw.get("incident_id") or "").strip()
    if incident_id:
        entry["incident_id"] = incident_id
    for key in (
        "incident_type",
        "captured_at",
        "job_id",
        "run_id",
        "paper_id",
        "status",
        "artifact_kind",
        "layer",
    ):
        value = str(raw.get(key) or "").strip()
        entry[key] = value or None
    entry["is_stale_candidate"] = bool(raw.get("is_stale_candidate"))
    for key in ("running_for_seconds", "stale_after_seconds"):
        value = raw.get(key)
        entry[key] = int(value) if isinstance(value, int) else None
    entry["path_observations_available"] = isinstance(raw.get("path_observations"), dict)
    recent_events = raw.get("recent_job_events")
    if isinstance(recent_events, list):
        entry["recent_job_events_count"] = len(recent_events)
    return entry


def collect_stale_running_incidents(*, limit: int) -> dict[str, Any]:
    now = utc_now()
    root = _incident_snapshot_root()
    payload = {
        "generated_at": now.isoformat(),
        "incidents_root": str(root),
        "incidents_total": 0,
        "returned_total": 0,
        "incidents": [],
    }
    if not root.exists() or not root.is_dir():
        return payload

    incident_paths = [path for path in root.glob("*/incident.json") if path.is_file()]
    entries = [_load_incident_summary(path) for path in incident_paths]
    entries.sort(key=_incident_sort_timestamp, reverse=True)
    bounded_limit = max(int(limit), 0)
    payload["incidents_total"] = len(entries)
    payload["incidents"] = entries[:bounded_limit]
    payload["returned_total"] = len(payload["incidents"])
    return payload


def _bool_db_flag(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value in (None, ""):
        return False
    try:
        return bool(int(value))
    except (TypeError, ValueError):
        return bool(value)


def _parser_backend_from_params(params: dict[str, Any]) -> str | None:
    parser_backend = str(params.get("parser_backend") or "").strip().lower()
    if parser_backend in {"fitz_pdfplumber", "docling"}:
        return parser_backend
    return None


def _has_reclaim_event(conn: sqlite3.Connection, job_id: str) -> bool:
    try:
        row = conn.execute(
            """
            SELECT 1
            FROM job_events
            WHERE job_id = ? AND event_type = 'job_reclaimed_stale_running'
            LIMIT 1
            """,
            (job_id,),
        ).fetchone()
    except sqlite3.OperationalError:
        return False
    return row is not None


def _collect_requeue_links(conn: sqlite3.Connection, job_ids: list[str]) -> dict[str, dict[str, Any]]:
    normalized_job_ids: list[str] = []
    seen_job_ids: set[str] = set()
    for job_id in job_ids:
        normalized = str(job_id or "").strip()
        if not normalized or normalized in seen_job_ids:
            continue
        seen_job_ids.add(normalized)
        normalized_job_ids.append(normalized)
    if not normalized_job_ids:
        return {}

    placeholders = ",".join("?" for _ in normalized_job_ids)
    try:
        rows = conn.execute(
            f"""
            SELECT job_id, ts, payload_json
            FROM job_events
            WHERE event_type = 'job_requeued_replacement'
              AND job_id IN ({placeholders})
            ORDER BY ts DESC
            """,
            normalized_job_ids,
        ).fetchall()
    except sqlite3.OperationalError:
        return {}

    links: dict[str, dict[str, Any]] = {}
    for row in rows:
        original_job_id = str(row["job_id"] or "").strip()
        if not original_job_id or original_job_id in links:
            continue
        event_payload: dict[str, Any] = {}
        try:
            if row["payload_json"]:
                event_payload = json.loads(str(row["payload_json"]))
        except Exception:
            event_payload = {}
        replacement_job_id = str(event_payload.get("replacement_job_id") or "").strip()
        replacement_run_id = str(event_payload.get("replacement_run_id") or "").strip()
        entry: dict[str, Any] = {
            "requeued_at": str(row["ts"] or "").strip() or None,
        }
        if replacement_job_id:
            entry["replacement_job_id"] = replacement_job_id
        if replacement_run_id:
            entry["replacement_run_id"] = replacement_run_id
        links[original_job_id] = entry
    return links


def _collect_requeue_summary(conn: sqlite3.Connection) -> dict[str, Any]:
    payload = {
        "stale_running_requeued_total": 0,
        "last_stale_running_requeued_at": None,
    }
    try:
        row = conn.execute(
            """
            SELECT COUNT(*) AS total, MAX(ts) AS last_ts
            FROM job_events
            WHERE event_type = 'job_requeued_replacement'
            """
        ).fetchone()
    except sqlite3.OperationalError:
        return payload

    if row is None:
        return payload
    payload["stale_running_requeued_total"] = int(row["total"] or 0)
    payload["last_stale_running_requeued_at"] = str(row["last_ts"] or "").strip() or None
    return payload


def _collect_reclaim_summary(conn: sqlite3.Connection) -> dict[str, Any]:
    payload = {
        "stale_running_reclaimed_total": 0,
        "last_stale_running_reclaimed_at": None,
        "stale_running_requeued_total": 0,
        "last_stale_running_requeued_at": None,
        "recent_stale_running_reclaims": [],
    }
    try:
        row = conn.execute(
            """
            SELECT COUNT(*) AS total, MAX(ts) AS last_ts
            FROM job_events
            WHERE event_type = 'job_reclaimed_stale_running'
            """
        ).fetchone()
    except sqlite3.OperationalError:
        return payload

    if row is None:
        return payload
    payload["stale_running_reclaimed_total"] = int(row["total"] or 0)
    payload["last_stale_running_reclaimed_at"] = str(row["last_ts"] or "").strip() or None
    payload.update(_collect_requeue_summary(conn))
    try:
        recent_rows = conn.execute(
            """
            SELECT job_id, run_id, ts, payload_json
            FROM job_events
            WHERE event_type = 'job_reclaimed_stale_running'
            ORDER BY ts DESC
            LIMIT 3
            """
        ).fetchall()
    except sqlite3.OperationalError:
        recent_rows = []

    requeue_links = _collect_requeue_links(
        conn,
        [str(event_row["job_id"] or "").strip() for event_row in recent_rows],
    )
    recent_entries: list[dict[str, Any]] = []
    for event_row in recent_rows:
        event_payload: dict[str, Any] = {}
        try:
            if event_row["payload_json"]:
                event_payload = json.loads(str(event_row["payload_json"]))
        except Exception:
            event_payload = {}
        job_id = str(event_row["job_id"] or "").strip()
        entry = {
            "job_id": job_id,
            "run_id": str(event_row["run_id"] or "").strip() or None,
            "paper_id": str(event_payload.get("paper_id") or "").strip() or None,
            "reclaimed_at": str(event_row["ts"] or "").strip() or None,
            "error_code": str(event_payload.get("error_code") or "").strip()
            or STALE_RUNNING_RECLAIMED_ERROR_CODE,
        }
        entry.update(requeue_links.get(job_id, {}))
        recent_entries.append(entry)
    payload["recent_stale_running_reclaims"] = recent_entries
    return payload


def collect_stale_jobs(db_path: Path, stale_after_seconds: int, limit: int) -> dict[str, Any]:
    now = utc_now()
    empty_payload = {
        "generated_at": now.isoformat(),
        "stale_after_seconds": int(stale_after_seconds),
        "running_jobs_total": 0,
        "stale_candidates_total": 0,
        "stale_running_reclaimed_total": 0,
        "last_stale_running_reclaimed_at": None,
        "stale_running_requeued_total": 0,
        "last_stale_running_requeued_at": None,
        "recent_stale_running_reclaims": [],
        "stale_jobs": [],
    }
    if not db_path.exists():
        return empty_payload

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        reclaim_summary = _collect_reclaim_summary(conn)
        try:
            rows = conn.execute(
                """
                SELECT *
                FROM jobs
                WHERE status = 'running'
                ORDER BY COALESCE(started_at, created_at) ASC
                """
            ).fetchall()
        except sqlite3.OperationalError:
            payload = dict(empty_payload)
            payload["stale_running_reclaimed_total"] = int(
                reclaim_summary.get("stale_running_reclaimed_total") or 0
            )
            payload["last_stale_running_reclaimed_at"] = reclaim_summary.get(
                "last_stale_running_reclaimed_at"
            )
            payload["stale_running_requeued_total"] = int(
                reclaim_summary.get("stale_running_requeued_total") or 0
            )
            payload["last_stale_running_requeued_at"] = reclaim_summary.get(
                "last_stale_running_requeued_at"
            )
            payload["recent_stale_running_reclaims"] = list(
                reclaim_summary.get("recent_stale_running_reclaims") or []
            )
            return payload
    finally:
        conn.close()

    stale_jobs: list[dict[str, Any]] = []
    running_jobs_total = len(rows)
    for row in rows:
        anchor = _row_activity_anchor(row)
        if anchor is None:
            continue
        running_for_seconds = max(int((now - anchor).total_seconds()), 0)
        if running_for_seconds < int(stale_after_seconds):
            continue

        raw_log_path = str(row["log_path"] or "").strip()
        raw_artifact_dir = str(row["artifact_dir"] or "").strip()
        log_exists = bool(raw_log_path and Path(raw_log_path).exists())
        artifact_dir_exists = bool(raw_artifact_dir and Path(raw_artifact_dir).exists())

        stale_jobs.append(
            {
                "job_id": str(row["job_id"]),
                "paper_id": str(row["paper_id"] or "").strip() or None,
                "run_id": str(row["run_id"] or "").strip() or None,
                "status": "running",
                "stage": str(row["stage"] or "").strip() or None,
                "progress": int(row["progress"]) if row["progress"] is not None else None,
                "created_at": str(row["created_at"] or "").strip() or None,
                "started_at": str(row["started_at"] or "").strip() or None,
                "running_for_seconds": running_for_seconds,
                "log_exists": log_exists,
                "artifact_dir_exists": artifact_dir_exists,
                "recommended_action": _recommended_action(
                    log_exists=log_exists,
                    artifact_dir_exists=artifact_dir_exists,
                ),
            }
        )

    stale_jobs.sort(key=lambda item: int(item["running_for_seconds"]), reverse=True)
    stale_candidates_total = len(stale_jobs)
    return {
        "generated_at": now.isoformat(),
        "stale_after_seconds": int(stale_after_seconds),
        "running_jobs_total": running_jobs_total,
        "stale_candidates_total": stale_candidates_total,
        "stale_running_reclaimed_total": int(reclaim_summary.get("stale_running_reclaimed_total") or 0),
        "last_stale_running_reclaimed_at": reclaim_summary.get("last_stale_running_reclaimed_at"),
        "stale_running_requeued_total": int(reclaim_summary.get("stale_running_requeued_total") or 0),
        "last_stale_running_requeued_at": reclaim_summary.get("last_stale_running_requeued_at"),
        "recent_stale_running_reclaims": list(reclaim_summary.get("recent_stale_running_reclaims") or []),
        "stale_jobs": stale_jobs[: max(int(limit), 0)],
    }


def collect_queue_health(
    db_path: Path,
    *,
    stale_after_seconds: int,
    queued_age_warn_after_seconds: int,
) -> dict[str, Any]:
    stale_payload = collect_stale_jobs(
        db_path,
        stale_after_seconds=stale_after_seconds,
        limit=0,
    )
    payload = {
        "generated_at": str(stale_payload.get("generated_at") or ""),
        "available": False,
        "stale_after_seconds": int(stale_after_seconds),
        "queued_age_warn_after_seconds": int(queued_age_warn_after_seconds),
        "queued_jobs_total": 0,
        "running_jobs_total": int(stale_payload.get("running_jobs_total") or 0),
        "oldest_queued_age_seconds": None,
        "stale_running_suspected_total": int(stale_payload.get("stale_candidates_total") or 0),
        "stale_running_reclaimed_total": int(stale_payload.get("stale_running_reclaimed_total") or 0),
        "last_stale_running_reclaimed_at": stale_payload.get("last_stale_running_reclaimed_at"),
        "stale_running_requeued_total": int(stale_payload.get("stale_running_requeued_total") or 0),
        "last_stale_running_requeued_at": stale_payload.get("last_stale_running_requeued_at"),
        "recent_stale_running_reclaims": list(stale_payload.get("recent_stale_running_reclaims") or []),
    }
    if not db_path.exists():
        return payload

    now = utc_now()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        try:
            queued_total_row = conn.execute(
                "SELECT COUNT(*) AS total FROM jobs WHERE status = 'queued'"
            ).fetchone()
            oldest_queued_row = conn.execute(
                """
                SELECT created_at
                FROM jobs
                WHERE status = 'queued'
                ORDER BY created_at ASC
                LIMIT 1
                """
            ).fetchone()
        except sqlite3.OperationalError:
            return payload
    finally:
        conn.close()

    payload["available"] = True
    payload["queued_jobs_total"] = int(queued_total_row["total"] or 0) if queued_total_row else 0
    oldest_created_at = None if oldest_queued_row is None else _parse_optional_datetime(oldest_queued_row["created_at"])
    if oldest_created_at is not None:
        payload["oldest_queued_age_seconds"] = max(int((now - oldest_created_at).total_seconds()), 0)
    return payload


def capture_stale_running_incident_snapshot(
    db_path: Path,
    *,
    job_id: str,
    stale_after_seconds: int,
) -> dict[str, Any]:
    """Write a bounded local support artifact for a suspected stale-running job."""
    now = utc_now()
    if not db_path.exists():
        return {"outcome": "not_found"}

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        try:
            row = conn.execute(
                "SELECT * FROM jobs WHERE job_id = ? LIMIT 1",
                (job_id,),
            ).fetchone()
        except sqlite3.OperationalError:
            return {"outcome": "not_found"}

        if row is None:
            return {"outcome": "not_found"}

        run_id = str(_row_value(row, "run_id") or "").strip() or None
        paper_id = str(_row_value(row, "paper_id") or "").strip() or None
        status = str(_row_value(row, "status") or "").strip().lower() or "unknown"
        anchor = _row_activity_anchor(row)
        running_for_seconds = None
        if anchor is not None:
            running_for_seconds = max(int((now - anchor).total_seconds()), 0)
        is_stale_candidate = bool(
            status == "running"
            and running_for_seconds is not None
            and running_for_seconds >= int(stale_after_seconds)
        )

        run_row = None
        if run_id:
            try:
                run_row = conn.execute(
                    "SELECT * FROM execution_runs WHERE run_id = ? LIMIT 1",
                    (run_id,),
                ).fetchone()
            except sqlite3.OperationalError:
                run_row = None

        recent_events = _collect_recent_job_events(conn, job_id=job_id)
        captured_at = now.isoformat()
        incident_id = (
            f"stale_running_{now.strftime('%Y%m%dT%H%M%SZ')}_{_safe_path_segment(job_id)}"
        )
        incident_dir = _incident_snapshot_root() / incident_id
        incident_dir.mkdir(parents=True, exist_ok=True)
        incident_path = incident_dir / "incident.json"

        snapshot = {
            "artifact_kind": "review_support",
            "layer": "review_gate_artifact",
            "incident_type": "stale_running_suspicion",
            "incident_id": incident_id,
            "captured_at": captured_at,
            "stale_after_seconds": int(stale_after_seconds),
            "job_id": str(_row_value(row, "job_id") or job_id),
            "run_id": run_id,
            "paper_id": paper_id,
            "status": status,
            "activity_anchor_at": anchor.isoformat() if anchor is not None else None,
            "running_for_seconds": running_for_seconds,
            "is_stale_candidate": is_stale_candidate,
            "job": _snapshot_row(
                row,
                [
                    "job_id",
                    "run_id",
                    "paper_id",
                    "status",
                    "stage",
                    "progress",
                    "created_at",
                    "started_at",
                    "heartbeat_at",
                    "finished_at",
                    "error_code",
                    "error_message",
                    "log_path",
                    "artifact_dir",
                ],
            ),
            "execution_run": _snapshot_row(
                run_row,
                [
                    "run_id",
                    "paper_id",
                    "trigger_source",
                    "pipeline_profile",
                    "status",
                    "created_at",
                    "started_at",
                    "finished_at",
                    "params_json",
                    "metrics_json",
                ],
            ),
            "path_observations": {
                "log_path": _path_observation(_row_value(row, "log_path")),
                "artifact_dir": _path_observation(_row_value(row, "artifact_dir")),
            },
            "recent_job_events": recent_events,
            "notes": [
                "This support artifact is not canonical job state.",
                "It captures metadata only; it does not copy PDF, log, or artifact contents.",
            ],
        }
        incident_path.write_text(
            json.dumps(snapshot, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )
        try:
            log_job_event(
                job_id=job_id,
                run_id=run_id,
                level="INFO",
                event_type=STALE_RUNNING_INCIDENT_EVENT_TYPE,
                message="captured stale-running incident snapshot",
                payload={
                    "paper_id": paper_id,
                    "incident_id": incident_id,
                    "incident_path": str(incident_path),
                    "is_stale_candidate": is_stale_candidate,
                    "running_for_seconds": running_for_seconds,
                    "stale_after_seconds": int(stale_after_seconds),
                },
                ts=captured_at,
                conn=conn,
            )
            conn.commit()
        except sqlite3.Error:
            conn.rollback()
            raise

        return {
            "outcome": "captured",
            "incident_id": incident_id,
            "job_id": str(_row_value(row, "job_id") or job_id),
            "run_id": run_id,
            "paper_id": paper_id,
            "status": status,
            "is_stale_candidate": is_stale_candidate,
            "running_for_seconds": running_for_seconds,
            "stale_after_seconds": int(stale_after_seconds),
            "captured_at": captured_at,
            "incident_path": str(incident_path),
        }
    finally:
        conn.close()


def reclaim_stale_running_job(
    db_path: Path,
    *,
    job_id: str,
    stale_after_seconds: int,
) -> dict[str, Any]:
    now = utc_now()
    if not db_path.exists():
        return {"outcome": "not_found"}

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        cursor = conn.cursor()
        cursor.execute("BEGIN IMMEDIATE")
        try:
            row = cursor.execute(
                "SELECT * FROM jobs WHERE job_id = ? LIMIT 1",
                (job_id,),
            ).fetchone()
        except sqlite3.OperationalError:
            conn.rollback()
            return {"outcome": "not_found"}

        if row is None:
            conn.rollback()
            return {"outcome": "not_found"}

        status = str(row["status"] or "").strip().lower()
        if status != "running":
            conn.rollback()
            return {
                "outcome": "not_running",
                "job_id": str(row["job_id"]),
                "status": status or None,
            }

        anchor = _row_activity_anchor(row)
        if anchor is None:
            conn.rollback()
            return {
                "outcome": "not_stale",
                "job_id": str(row["job_id"]),
                "status": "running",
                "running_for_seconds": None,
            }

        running_for_seconds = max(int((now - anchor).total_seconds()), 0)
        if running_for_seconds < int(stale_after_seconds):
            conn.rollback()
            return {
                "outcome": "not_stale",
                "job_id": str(row["job_id"]),
                "status": "running",
                "running_for_seconds": running_for_seconds,
            }

        ts = now.isoformat()
        error_message = (
            f"Operator reclaimed stale running job after {running_for_seconds}s "
            "without a fresh heartbeat."
        )
        jobs_columns = {info[1] for info in cursor.execute("PRAGMA table_info(jobs)").fetchall()}
        assignments = [
            ("status", "failed"),
            ("finished_at", ts),
        ]
        if "error_code" in jobs_columns:
            assignments.append(("error_code", STALE_RUNNING_RECLAIMED_ERROR_CODE))
        if "error_message" in jobs_columns:
            assignments.append(("error_message", error_message))

        set_clause = ", ".join(f"{column} = ?" for column, _ in assignments)
        params = [value for _, value in assignments]
        params.append(job_id)
        cursor.execute(
            f"UPDATE jobs SET {set_clause} WHERE job_id = ? AND status = 'running'",
            params,
        )
        if cursor.rowcount == 0:
            conn.rollback()
            return {
                "outcome": "not_running",
                "job_id": str(row["job_id"]),
                "status": "running",
            }

        run_id = str(row["run_id"] or "").strip() or None
        paper_id = str(row["paper_id"] or "").strip() or None
        if run_id:
            update_execution_run(
                run_id=run_id,
                status="failed",
                finished_at=ts,
                conn=conn,
            )
        log_job_event(
            job_id=job_id,
            run_id=run_id,
            level="ERROR",
            event_type="job_reclaimed_stale_running",
            message=error_message,
            payload={
                "status": "failed",
                "paper_id": paper_id,
                "error_code": STALE_RUNNING_RECLAIMED_ERROR_CODE,
                "running_for_seconds": running_for_seconds,
                "stale_after_seconds": int(stale_after_seconds),
            },
            ts=ts,
            conn=conn,
        )
        conn.commit()
        return {
            "outcome": "reclaimed",
            "job_id": str(row["job_id"]),
            "paper_id": paper_id,
            "run_id": run_id,
            "previous_status": "running",
            "status": "failed",
            "error_code": STALE_RUNNING_RECLAIMED_ERROR_CODE,
            "error_message": error_message,
            "running_for_seconds": running_for_seconds,
            "stale_after_seconds": int(stale_after_seconds),
            "reclaimed_at": ts,
        }
    finally:
        conn.close()


def requeue_reclaimed_job(db_path: Path, *, job_id: str) -> dict[str, Any]:
    """Explicitly enqueue a fresh replacement for a reclaimed stale-running job."""
    if not db_path.exists():
        return {"outcome": "not_found"}

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        try:
            row = conn.execute(
                "SELECT * FROM jobs WHERE job_id = ? LIMIT 1",
                (job_id,),
            ).fetchone()
        except sqlite3.OperationalError:
            return {"outcome": "not_found"}

        if row is None:
            return {"outcome": "not_found"}

        status = str(_row_value(row, "status") or "").strip().lower()
        if status != "failed":
            return {
                "outcome": "not_reclaimed",
                "job_id": str(_row_value(row, "job_id") or job_id),
                "status": status or None,
            }

        error_code = str(_row_value(row, "error_code") or "").strip()
        if error_code != STALE_RUNNING_RECLAIMED_ERROR_CODE and not _has_reclaim_event(conn, job_id):
            return {
                "outcome": "not_reclaimed",
                "job_id": str(_row_value(row, "job_id") or job_id),
                "status": status,
                "error_code": error_code or None,
            }

        paper_id = str(_row_value(row, "paper_id") or "").strip()
        if not paper_id:
            return {
                "outcome": "missing_paper",
                "job_id": str(_row_value(row, "job_id") or job_id),
                "status": status,
            }

        original_run_id = str(_row_value(row, "run_id") or "").strip() or None
        persona_id = str(_row_value(row, "persona_id", "default") or "default")
        reasoning_persona = str(_row_value(row, "reasoning_persona") or "").strip() or None
        profile_id = str(_row_value(row, "profile_id") or "").strip() or None
        run_verify = _bool_db_flag(_row_value(row, "run_verify"))
        clean_reindex = _bool_db_flag(_row_value(row, "clean_reindex"))
    finally:
        conn.close()

    run_params = get_execution_run_params(original_run_id)
    parser_backend = _parser_backend_from_params(run_params)
    reasoning_persona = reasoning_persona or str(run_params.get("reasoning_persona") or "").strip() or None
    profile_id = profile_id or str(run_params.get("profile_id") or "").strip() or None

    queue = JobQueue()
    try:
        replacement_job_id = queue.enqueue(
            paper_id=paper_id,
            clean_reindex=clean_reindex,
            run_verify=run_verify,
            persona_id=persona_id,
            reasoning_persona=reasoning_persona,
            profile_id=profile_id,
            parser_backend=parser_backend,
            trigger_source=REQUEUE_RECLAIMED_TRIGGER_SOURCE,
            pipeline_profile="deepread",
        )
    except DuplicateOpenJobError as exc:
        return {
            "outcome": "duplicate_open",
            "paper_id": exc.paper_id,
            "job_id": exc.job_id,
            "run_id": exc.run_id,
            "status": exc.status,
        }
    except QueueBackpressureError as exc:
        return {
            "outcome": "queue_full",
            "queued_count": exc.queued_count,
            "limit": exc.limit,
        }

    replacement = queue.get_job(replacement_job_id)
    replacement_run_id = replacement.run_id if replacement else None
    ts = utc_now().isoformat()
    log_job_event(
        job_id=job_id,
        run_id=original_run_id,
        level="INFO",
        event_type="job_requeued_replacement",
        message="operator enqueued fresh replacement for reclaimed stale-running job",
        payload={
            "status": "queued",
            "paper_id": paper_id,
            "replacement_job_id": replacement_job_id,
            "replacement_run_id": replacement_run_id,
        },
        ts=ts,
    )
    log_job_event(
        job_id=replacement_job_id,
        run_id=replacement_run_id,
        level="INFO",
        event_type="job_requeued_from_reclaimed",
        message="queued as explicit replacement for reclaimed stale-running job",
        payload={
            "status": "queued",
            "paper_id": paper_id,
            "original_job_id": job_id,
            "original_run_id": original_run_id,
        },
        ts=ts,
    )
    return {
        "outcome": "requeued",
        "original_job_id": job_id,
        "original_run_id": original_run_id,
        "job_id": replacement_job_id,
        "run_id": replacement_run_id,
        "paper_id": paper_id,
        "status": "queued",
        "requeued_at": ts,
    }
