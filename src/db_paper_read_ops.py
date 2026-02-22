from __future__ import annotations

from typing import Any, Dict, List, Optional

import sqlite3


def get_paper_columns(cursor: sqlite3.Cursor) -> set[str]:
    cursor.execute("PRAGMA table_info(papers)")
    return {row[1] for row in cursor.fetchall()}


def paper_lookup_conditions(columns: set[str]) -> list[str]:
    conditions: list[str] = []
    if "paper_id" in columns:
        conditions.append("paper_id = ?")
    if "doi" in columns:
        conditions.append("doi = ?")
    return conditions


def get_paper_by_id_with_connection(conn: sqlite3.Connection, identifier: str) -> Optional[Dict[str, Any]]:
    cursor = conn.cursor()
    try:
        columns = get_paper_columns(cursor)
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


def is_paper_processed_with_connection(conn: sqlite3.Connection, identifier: str) -> bool:
    if not identifier:
        return False
    cursor = conn.cursor()
    try:
        columns = get_paper_columns(cursor)
        conditions = paper_lookup_conditions(columns)
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


def get_all_papers_with_connection(conn: sqlite3.Connection) -> List[Dict[str, Any]]:
    cursor = conn.cursor()
    try:
        columns = get_paper_columns(cursor)
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


def get_papers_by_status_with_connection(
    conn: sqlite3.Connection,
    status_list: List[str],
    limit: int = 5,
) -> List[Dict[str, Any]]:
    cursor = conn.cursor()
    placeholders = ",".join(["?"] * len(status_list))
    query = f"""
        SELECT * FROM papers
        WHERE status IN ({placeholders})
        ORDER BY updated_at ASC
        LIMIT ?
    """
    params = status_list + [limit]
    cursor.execute(query, params)
    return [dict(row) for row in cursor.fetchall()]
