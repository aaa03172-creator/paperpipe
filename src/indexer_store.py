from __future__ import annotations

import sqlite3
from typing import Any


def select_index_rows(db_path: str, include_all: bool) -> list[dict[str, Any]]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    if include_all:
        cur.execute("SELECT * FROM papers")
    else:
        cur.execute(
            """
            SELECT *
            FROM papers
            WHERE gate_decision = 'APPROVED'
               OR status IN ('APPROVED', 'INDEXED')
            """
        )

    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows
