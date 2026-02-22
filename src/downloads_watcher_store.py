from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from src.db_utils import get_db_connection

logger = logging.getLogger(__name__)


def load_manual_required_candidates() -> list[dict[str, Any]]:
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT paper_id, doi, title
            FROM papers
            WHERE lower(coalesce(pdf_status, '')) = 'manual_required'
            """
        )
        return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()


def enqueue_pdf_match_review(
    paper_id: str,
    reason: str,
    decision: str,
    allow_multiple_open: bool = False,
) -> bool:
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        if not allow_multiple_open:
            cur.execute(
                """
                SELECT 1 FROM review_queue
                WHERE paper_id = ? AND decision = ? AND resolved_at IS NULL
                LIMIT 1
                """,
                (paper_id, decision),
            )
            if cur.fetchone():
                return False
        cur.execute(
            """
            INSERT INTO review_queue (paper_id, decision, reason)
            VALUES (?, ?, ?)
            """,
            (paper_id, decision, reason),
        )
        conn.commit()
        return True
    except Exception as exc:
        logger.warning("Failed to enqueue %s for %s: %s", decision, paper_id, exc)
        return False
    finally:
        conn.close()


def update_downloaded_path(paper_id: str, destination: Path) -> None:
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            UPDATE papers
            SET pdf_status = 'downloaded',
                pdf_path = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE paper_id = ?
            """,
            (str(destination), paper_id),
        )
        conn.commit()
    finally:
        conn.close()
