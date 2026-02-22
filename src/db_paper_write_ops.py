from __future__ import annotations

from datetime import datetime
from pathlib import Path
import re
from typing import Any, Dict, Optional

import sqlite3

from src.db_paper_read_ops import get_paper_columns, paper_lookup_conditions


def save_paper_state_with_connection(
    conn: sqlite3.Connection,
    identifier: str,
    title: str,
    source: str,
    processed_date: str,
) -> None:
    cursor = conn.cursor()
    try:
        columns = get_paper_columns(cursor)
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
        conflict_target = (
            "paper_id" if "paper_id" in columns else ("doi" if "doi" in columns else None)
        )

        if conflict_target:
            sql = (
                f"INSERT INTO papers ({', '.join(insert_cols)}) VALUES ({placeholders}) "
                f"ON CONFLICT({conflict_target}) DO UPDATE SET {', '.join(update_set)}"
            )
            cursor.execute(sql, tuple(insert_vals))
        else:
            sql = f"INSERT INTO papers ({', '.join(insert_cols)}) VALUES ({placeholders})"
            cursor.execute(sql, tuple(insert_vals))
    except sqlite3.OperationalError:
        pass


def update_reading_status_with_connection(
    conn: sqlite3.Connection,
    identifier: str,
    reading_status: str,
) -> bool:
    cursor = conn.cursor()
    try:
        columns = get_paper_columns(cursor)
        if "reading_status" not in columns:
            try:
                cursor.execute("ALTER TABLE papers ADD COLUMN reading_status TEXT DEFAULT 'Inbox'")
                columns.add("reading_status")
            except sqlite3.OperationalError:
                pass
        conditions = paper_lookup_conditions(columns)
        if "reading_status" not in columns or not conditions:
            return False
        params = [reading_status] + [identifier] * len(conditions)
        cursor.execute(
            f"UPDATE papers SET reading_status = ? WHERE {' OR '.join(conditions)}",
            params,
        )
        return cursor.rowcount > 0
    except sqlite3.OperationalError:
        return False


def mark_as_retracted_with_connection(conn: sqlite3.Connection, identifier: str) -> bool:
    cursor = conn.cursor()
    try:
        columns = get_paper_columns(cursor)
        if "is_retracted" not in columns:
            try:
                cursor.execute("ALTER TABLE papers ADD COLUMN is_retracted BOOLEAN DEFAULT 0")
                columns.add("is_retracted")
            except sqlite3.OperationalError:
                pass
        conditions = paper_lookup_conditions(columns)
        if "is_retracted" not in columns or not conditions:
            return False
        params = [identifier] * len(conditions)
        cursor.execute(
            f"UPDATE papers SET is_retracted = 1 WHERE {' OR '.join(conditions)}",
            params,
        )
        return cursor.rowcount > 0
    except sqlite3.OperationalError:
        return False


def update_paper_status_with_connection(
    conn: sqlite3.Connection,
    paper_id: str,
    new_status: str,
    updates: Optional[Dict[str, Any]] = None,
) -> None:
    cursor = conn.cursor()
    columns = get_paper_columns(cursor)
    fields = ["status = ?", "updated_at = CURRENT_TIMESTAMP"]
    params = [new_status]

    if updates:
        for key, value in updates.items():
            if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", key):
                continue
            if key not in columns:
                continue
            fields.append(f"{key} = ?")
            params.append(value)

    params.append(paper_id)
    query = f"UPDATE papers SET {', '.join(fields)} WHERE paper_id = ?"
    cursor.execute(query, params)


def sync_zotero_to_db_with_connection(conn: sqlite3.Connection, zotero_json_path: Path) -> int:
    """
    Syncs Zotero export (JSON) to SQLite.
    - Adds new papers as 'NEW'.
    - Updates 'pdf_path' if found in Zotero attachments.
    - Does NOT overwrite existing paper status (idempotent).
    Returns count of new papers added.
    """
    import json

    if not zotero_json_path.exists():
        return 0

    try:
        with open(zotero_json_path, "r") as handle:
            data = json.load(handle)
            items = data.get("items", [])
    except Exception:
        return 0

    new_count = 0
    cursor = conn.cursor()

    for item in items:
        paper_id = item.get("citationKey")
        if not paper_id:
            continue

        title = item.get("title", "Unknown Title")
        summary = item.get("abstractNote", "")

        pdf_path = None
        for attachment in item.get("attachments", []):
            if attachment.get("path") and attachment["path"].lower().endswith(".pdf"):
                pdf_path = attachment["path"]
                break

        cursor.execute("SELECT paper_id, pdf_path, summary FROM papers WHERE paper_id = ?", (paper_id,))
        row = cursor.fetchone()

        if row:
            updates = []
            params = []

            if pdf_path and not row["pdf_path"]:
                updates.append("pdf_path = ?")
                params.append(pdf_path)
            if summary and not row["summary"]:
                updates.append("summary = ?")
                params.append(summary)

            if updates:
                params.append(paper_id)
                cursor.execute(f"UPDATE papers SET {', '.join(updates)} WHERE paper_id = ?", params)
        else:
            try:
                cursor.execute(
                    """
                    INSERT INTO papers (paper_id, title, summary, status, pdf_path, created_at, updated_at)
                    VALUES (?, ?, ?, 'NEW', ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                    """,
                    (paper_id, title, summary, pdf_path),
                )
                new_count += 1
            except sqlite3.IntegrityError:
                pass

    return new_count
