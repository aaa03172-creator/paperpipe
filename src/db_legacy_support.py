from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from typing import Any


def ensure_legacy_tables(conn: sqlite3.Connection) -> None:
    cursor = conn.cursor()
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
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS embeddings (
            doi TEXT PRIMARY KEY,
            vector TEXT,
            updated_at TIMESTAMP
        )
        """
    )

    try:
        cursor.execute("ALTER TABLE papers ADD COLUMN is_retracted BOOLEAN DEFAULT 0")
    except sqlite3.OperationalError:
        pass
    try:
        cursor.execute("ALTER TABLE papers ADD COLUMN reading_status TEXT DEFAULT 'Inbox'")
    except sqlite3.OperationalError:
        pass
    try:
        cursor.execute("ALTER TABLE papers ADD COLUMN processed_date TEXT")
    except sqlite3.OperationalError:
        pass


def save_embedding_with_connection(conn: sqlite3.Connection, doi: str, vector: list[Any]) -> None:
    cursor = conn.cursor()
    vector_json = json.dumps(vector)
    cursor.execute(
        """
        INSERT INTO embeddings (doi, vector, updated_at)
        VALUES (?, ?, ?)
        ON CONFLICT(doi) DO UPDATE SET
            vector=excluded.vector,
            updated_at=excluded.updated_at
        """,
        (doi, vector_json, datetime.now()),
    )


def get_all_embeddings_with_connection(conn: sqlite3.Connection) -> dict[str, list[Any]]:
    cursor = conn.cursor()
    cursor.execute("SELECT doi, vector FROM embeddings")
    rows = cursor.fetchall()
    result: dict[str, list[Any]] = {}
    for row in rows:
        try:
            result[row[0]] = json.loads(row[1])
        except Exception:
            pass
    return result
