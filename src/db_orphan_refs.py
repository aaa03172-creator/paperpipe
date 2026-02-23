from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


TERMINAL_STATUSES = {"completed", "failed", "cancelled", "succeeded"}
DEFAULT_TABLES = ("jobs", "runs", "review_queue", "user_actions")
TABLE_PRIMARY_KEYS = {
    "jobs": "job_id",
    "runs": "run_id",
    "review_queue": "id",
    "user_actions": "action_id",
}


@dataclass(frozen=True)
class OrphanRecord:
    table: str
    pk_column: str
    pk_value: str
    paper_id: str
    reason: str
    status: str
    row: dict[str, Any]


def is_test_like_paper_id(paper_id: str | None) -> bool:
    pid = str(paper_id or "").strip().lower()
    if not pid:
        return False
    return (
        pid.startswith("test_")
        or pid.startswith("integration_test_")
        or pid.startswith("phase0_test")
        or pid.startswith("local--")
        or "_test_" in pid
    )


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name = ?",
        (table,),
    ).fetchone()
    return bool(row)


def _table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    try:
        rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    except sqlite3.OperationalError:
        return set()
    return {str(row[1]) for row in rows}


def _fetch_orphans_for_table(conn: sqlite3.Connection, table: str) -> list[dict[str, Any]]:
    if not _table_exists(conn, table):
        return []
    columns = _table_columns(conn, table)
    if "paper_id" not in columns:
        return []

    query = f"""
        SELECT *
        FROM {table}
        WHERE paper_id IS NOT NULL
          AND TRIM(paper_id) != ''
          AND NOT EXISTS (
            SELECT 1 FROM papers
            WHERE papers.paper_id = {table}.paper_id
          )
    """
    conn.row_factory = sqlite3.Row
    rows = conn.execute(query).fetchall()
    return [dict(row) for row in rows]


def collect_orphans(
    conn: sqlite3.Connection,
    *,
    tables: tuple[str, ...] = DEFAULT_TABLES,
) -> dict[str, list[OrphanRecord]]:
    out: dict[str, list[OrphanRecord]] = {}
    for table in tables:
        pk_column = TABLE_PRIMARY_KEYS.get(table)
        if not pk_column:
            continue

        rows = _fetch_orphans_for_table(conn, table)
        records: list[OrphanRecord] = []
        for row in rows:
            if pk_column not in row:
                continue
            paper_id = str(row.get("paper_id") or "").strip()
            status = str(row.get("status") or "").strip().lower()

            reasons: list[str] = ["paper_missing"]
            if is_test_like_paper_id(paper_id):
                reasons.append("test_like")
            if status in TERMINAL_STATUSES:
                reasons.append("terminal")

            records.append(
                OrphanRecord(
                    table=table,
                    pk_column=pk_column,
                    pk_value=str(row[pk_column]),
                    paper_id=paper_id,
                    reason="+".join(reasons),
                    status=status,
                    row=row,
                )
            )
        out[table] = records
    return out


def select_cleanup_candidates(
    orphans: dict[str, list[OrphanRecord]],
    *,
    mode: str = "test_terminal",
) -> list[OrphanRecord]:
    """
    mode:
      - test_terminal: orphan + test_like + terminal status from jobs/runs only
      - terminal_all: orphan + terminal status from jobs/runs only
    """
    selected: list[OrphanRecord] = []
    for table, records in orphans.items():
        if table not in {"jobs", "runs"}:
            continue
        for rec in records:
            is_terminal = rec.status in TERMINAL_STATUSES
            if mode == "test_terminal":
                if is_terminal and is_test_like_paper_id(rec.paper_id):
                    selected.append(rec)
            elif mode == "terminal_all":
                if is_terminal:
                    selected.append(rec)
            else:
                raise ValueError(f"Unsupported cleanup mode: {mode}")
    return selected


def ensure_cleanup_log_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS orphan_cleanup_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cleanup_batch_id TEXT NOT NULL,
            table_name TEXT NOT NULL,
            record_id TEXT NOT NULL,
            paper_id TEXT,
            reason TEXT NOT NULL,
            snapshot_json TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_orphan_cleanup_log_batch
        ON orphan_cleanup_log(cleanup_batch_id)
        """
    )


def apply_cleanup(
    conn: sqlite3.Connection,
    *,
    candidates: list[OrphanRecord],
    batch_id: str | None = None,
) -> dict[str, int]:
    ensure_cleanup_log_table(conn)
    bid = batch_id or str(uuid.uuid4())
    now_iso = datetime.now(timezone.utc).isoformat()

    deleted_by_table: dict[str, int] = {}
    for rec in candidates:
        conn.execute(
            """
            INSERT INTO orphan_cleanup_log (
                cleanup_batch_id,
                table_name,
                record_id,
                paper_id,
                reason,
                snapshot_json,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                bid,
                rec.table,
                rec.pk_value,
                rec.paper_id,
                rec.reason,
                json.dumps(rec.row, ensure_ascii=False, sort_keys=True),
                now_iso,
            ),
        )
        conn.execute(
            f"DELETE FROM {rec.table} WHERE {rec.pk_column} = ?",
            (rec.pk_value,),
        )
        deleted_by_table[rec.table] = deleted_by_table.get(rec.table, 0) + 1

    deleted_by_table["total"] = sum(v for k, v in deleted_by_table.items() if k != "total")
    return deleted_by_table


def backup_db_file(db_path: Path, backup_path: Path) -> None:
    import shutil

    backup_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(db_path, backup_path)
