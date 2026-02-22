from __future__ import annotations

import json
import sqlite3
from typing import Any, Dict, List


def reconcile_approved_decisions_with_connection(
    conn: sqlite3.Connection, dry_run: bool = True
) -> Dict[str, Any]:
    """
    Reconcile DB status when a paper has an approved decision but non-approved status.

    Reconcile targets:
    - gate_decision == 'APPROVED' and status not in ('APPROVED', 'INDEXED')
    - feedback_json contains decision='APPROVED' and status not in ('APPROVED', 'INDEXED')
      (for manual edits where gate_decision column was not updated)
    """
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT paper_id, status, gate_decision, feedback_json
        FROM papers
        WHERE status NOT IN ('APPROVED', 'INDEXED')
        """
    )
    rows = cursor.fetchall()

    candidates: List[Dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        gate_decision = item.get("gate_decision")
        feedback_json = item.get("feedback_json")

        approved_by_gate = gate_decision == "APPROVED"
        approved_by_feedback = False

        if not approved_by_gate and feedback_json:
            try:
                parsed = json.loads(feedback_json)
                if isinstance(parsed, dict):
                    approved_by_feedback = (
                        parsed.get("decision") == "APPROVED"
                        or parsed.get("gate_decision") == "APPROVED"
                    )
            except Exception:
                approved_by_feedback = False

        if approved_by_gate or approved_by_feedback:
            candidates.append(
                {
                    "paper_id": item["paper_id"],
                    "old_status": item["status"],
                    "source": "gate_decision" if approved_by_gate else "feedback_json",
                }
            )

    updated = 0
    if not dry_run:
        for candidate in candidates:
            if candidate["source"] == "gate_decision":
                cursor.execute(
                    """
                    UPDATE papers
                    SET status = 'APPROVED', updated_at = CURRENT_TIMESTAMP
                    WHERE paper_id = ?
                    """,
                    (candidate["paper_id"],),
                )
            else:
                cursor.execute(
                    """
                    UPDATE papers
                    SET status = 'APPROVED',
                        gate_decision = 'APPROVED',
                        gate_reason = COALESCE(gate_reason, 'Reconciled from feedback_json decision'),
                        updated_at = CURRENT_TIMESTAMP
                    WHERE paper_id = ?
                    """,
                    (candidate["paper_id"],),
                )
            updated += 1
        conn.commit()

    return {
        "dry_run": dry_run,
        "candidates": candidates,
        "candidate_count": len(candidates),
        "updated_count": updated,
    }
