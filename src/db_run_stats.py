from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta
from typing import Any, Dict, List


def init_run_stats_table(conn: sqlite3.Connection) -> None:
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


def log_run_stat(conn: sqlite3.Connection, profile_id: str, items_fetched: int, limit_hit: bool) -> None:
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO run_stats (profile_id, items_fetched, limit_hit)
        VALUES (?, ?, ?)
        """,
        (profile_id, items_fetched, int(limit_hit)),
    )


def get_profile_stats(conn: sqlite3.Connection, profile_id: str, days: int = 7) -> List[Dict[str, Any]]:
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
    return [dict(row) for row in cursor.fetchall()]
