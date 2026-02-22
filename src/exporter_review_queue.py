from __future__ import annotations

import logging
import sqlite3
from typing import Any, Dict, List, Optional

from src.exporter_claimset import feedback_needs_stats_check, span_missing_location

logger = logging.getLogger(__name__)

REVIEW_NEEDS_READER = "NEEDS_READER"
REVIEW_NEEDS_EVIDENCE_LINK = "NEEDS_EVIDENCE_LINK"
REVIEW_NEEDS_STATS_CHECK = "NEEDS_STATS_CHECK"
TEST_FIXTURE_OWNER = "TEST_FIXTURE"


def enqueue_review_followups(
    conn: sqlite3.Connection,
    paper: Dict[str, Any],
    feedback: Dict[str, Any],
    claims: Optional[List[Dict[str, Any]]],
) -> List[str]:
    paper_id = paper.get("paper_id")
    if not paper_id:
        return []

    decisions: List[tuple[str, str]] = []

    if not claims:
        decisions.append((REVIEW_NEEDS_READER, "ClaimSet missing or invalid in feedback_json"))
    else:
        missing_loc = False
        for claim in claims:
            if not isinstance(claim, dict):
                continue
            spans = claim.get("evidence_spans")
            if isinstance(spans, list) and spans:
                if any(span_missing_location(span) for span in spans):
                    missing_loc = True
                    break
        if missing_loc:
            decisions.append(
                (REVIEW_NEEDS_EVIDENCE_LINK, "Evidence span missing location metadata (page/source span)")
            )

    if feedback_needs_stats_check(feedback):
        decisions.append((REVIEW_NEEDS_STATS_CHECK, "Stats verdict includes unverifiable/inconsistent"))

    inserted: List[str] = []
    cur = conn.cursor()
    try:
        for decision, reason in decisions:
            cur.execute(
                """
                SELECT 1 FROM review_queue
                WHERE paper_id = ? AND decision = ? AND resolved_at IS NULL
                LIMIT 1
                """,
                (paper_id, decision),
            )
            if cur.fetchone():
                continue
            cur.execute(
                """
                INSERT INTO review_queue (paper_id, decision, reason)
                VALUES (?, ?, ?)
                """,
                (paper_id, decision, reason),
            )
            inserted.append(decision)
    except sqlite3.OperationalError as exc:
        logger.warning("review_queue unavailable; follow-up enqueue skipped: %s", exc)
        return []

    return inserted


def resolve_review_followups(
    conn: sqlite3.Connection,
    paper: Dict[str, Any],
    feedback: Dict[str, Any],
    claims: Optional[List[Dict[str, Any]]],
) -> List[str]:
    paper_id = paper.get("paper_id")
    if not paper_id:
        return []

    should_have_reader = not claims
    should_have_evidence_link = False
    if claims:
        for claim in claims:
            if not isinstance(claim, dict):
                continue
            spans = claim.get("evidence_spans")
            if isinstance(spans, list) and spans and any(span_missing_location(span) for span in spans):
                should_have_evidence_link = True
                break
    should_have_stats = feedback_needs_stats_check(feedback)

    resolve_targets: List[str] = []
    if not should_have_reader:
        resolve_targets.append(REVIEW_NEEDS_READER)
    if not should_have_evidence_link:
        resolve_targets.append(REVIEW_NEEDS_EVIDENCE_LINK)
    if not should_have_stats:
        resolve_targets.append(REVIEW_NEEDS_STATS_CHECK)

    if not resolve_targets:
        return []

    resolved: List[str] = []
    cur = conn.cursor()
    try:
        for decision in resolve_targets:
            cur.execute(
                """
                UPDATE review_queue
                SET resolved_at = CURRENT_TIMESTAMP,
                    resolution = COALESCE(resolution, 'AUTO_RESOLVED')
                WHERE paper_id = ?
                  AND decision = ?
                  AND resolved_at IS NULL
                """,
                (paper_id, decision),
            )
            if cur.rowcount > 0:
                resolved.append(decision)
    except sqlite3.OperationalError as exc:
        logger.warning("review_queue unavailable; follow-up resolve skipped: %s", exc)
        return []
    return resolved


def auto_skip_test_fixture_followups(conn: sqlite3.Connection, paper: Dict[str, Any]) -> int:
    paper_id = paper.get("paper_id")
    if not paper_id:
        return 0
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE review_queue
        SET owner = ?,
            resolved_at = CURRENT_TIMESTAMP,
            resolution = COALESCE(resolution, 'AUTO_SKIPPED_TEST_FIXTURE'),
            reason = CASE
                WHEN instr(COALESCE(reason, ''), '[auto-skip:test_fixture]') > 0 THEN reason
                ELSE COALESCE(reason, '') || ' [auto-skip:test_fixture]'
            END
        WHERE paper_id = ?
          AND decision = ?
          AND resolved_at IS NULL
        """,
        (TEST_FIXTURE_OWNER, paper_id, REVIEW_NEEDS_READER),
    )
    return cur.rowcount
