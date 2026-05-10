from __future__ import annotations

import argparse
import json
import logging
import sqlite3
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.config import load_config
from src.db_utils import get_db_connection
from src.llm_provider import get_llm_provider
from src.pdf import extract_text_from_pdf
from src.services.intake_override_log import (
    build_intake_override_log,
    merge_feedback_json_with_intake_override,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class BackfillCandidate:
    paper_id: str
    title: str
    needs_summary_refresh: bool
    needs_analysis_refresh: bool
    needs_intake_override_log: bool


@dataclass(frozen=True)
class BackfillUpdate:
    paper_id: str
    feedback_json: str
    confidence: float | None
    summary: str


def _parse_feedback_payload(feedback_json: Any) -> Dict[str, Any] | None:
    if not feedback_json:
        return None
    try:
        parsed = json.loads(str(feedback_json))
    except Exception:
        return None
    return parsed if isinstance(parsed, dict) else None


def _needs_summary_refresh(summary: Any) -> bool:
    text = str(summary or "").strip()
    return not text or text == "Abstract not available."


def _needs_analysis_refresh(payload: Dict[str, Any] | None) -> bool:
    if not payload:
        return True
    return not isinstance(payload.get("soft_tags"), list)


def _derive_issues_state(status: Any, *, analysis_available: bool) -> str:
    if not analysis_available:
        return "unavailable"
    normalized = str(status or "").strip().upper()
    if normalized in {"APPROVED", "INDEXED"}:
        return "clear"
    if normalized in {"PENDING_REVIEW", "QUARANTINED", "FAILED"}:
        return "flagged"
    return "unavailable"


def _coerce_optional_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _connect_db(db_path: Path | None) -> sqlite3.Connection:
    if db_path is None:
        conn = get_db_connection()
    else:
        conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def _backup_db(db_path: Path, backup_path: Path) -> None:
    backup_path.parent.mkdir(parents=True, exist_ok=True)
    src = sqlite3.connect(db_path)
    dst = sqlite3.connect(backup_path)
    try:
        src.backup(dst)
    finally:
        src.close()
        dst.close()


def _default_backup_path(db_path: Path) -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return db_path.parent / "backups" / f"{db_path.stem}_before_analysis_backfill_{stamp}{db_path.suffix}"


def _build_intake_logged_feedback_json(
    *,
    row: Dict[str, Any],
    feedback_json: str | None,
    analysis_payload: Dict[str, Any],
    llm_tagging_used: bool,
) -> str:
    status = row.get("status")
    stored_tags = (
        analysis_payload.get("soft_tags", [])
        if isinstance(analysis_payload.get("soft_tags"), list)
        else []
    )
    intake_override_log = build_intake_override_log(
        producer="backfill_analysis",
        analysis_available=True,
        llm_tagging_used=llm_tagging_used,
        llm_slot_classification_used=False,
        input_slot=row.get("slot"),
        stored_slot=row.get("slot"),
        input_tags=stored_tags,
        stored_tags=stored_tags,
        processing_status=str(status or "") or None,
        issues_state=_derive_issues_state(status, analysis_available=True),
        confidence=_coerce_optional_float(analysis_payload.get("confidence", row.get("confidence"))),
    )
    base_feedback_json = feedback_json or json.dumps(analysis_payload, ensure_ascii=False)
    return merge_feedback_json_with_intake_override(base_feedback_json, intake_override_log)


def _select_candidates(conn: sqlite3.Connection, *, limit: int) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT *
        FROM papers
        WHERE status IN ('APPROVED', 'INDEXED')
          AND (
            feedback_json IS NULL
            OR feedback_json NOT LIKE '%soft_tags%'
            OR feedback_json NOT LIKE '%intake_override_log%'
            OR summary IS NULL
            OR summary = ''
            OR summary = 'Abstract not available.'
          )
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    return [dict(row) for row in rows]


def _summarize_candidate(row: dict[str, Any]) -> BackfillCandidate:
    parsed_feedback = _parse_feedback_payload(row.get("feedback_json"))
    needs_summary_refresh = _needs_summary_refresh(row.get("summary"))
    needs_analysis_refresh = _needs_analysis_refresh(parsed_feedback)
    has_intake_override_log = bool(
        parsed_feedback and isinstance(parsed_feedback.get("intake_override_log"), dict)
    )
    return BackfillCandidate(
        paper_id=str(row.get("paper_id") or ""),
        title=str(row.get("title") or ""),
        needs_summary_refresh=needs_summary_refresh,
        needs_analysis_refresh=needs_analysis_refresh,
        needs_intake_override_log=needs_analysis_refresh or not has_intake_override_log,
    )


def _build_update(row: dict[str, Any], *, llm: Any, llm_available: bool) -> BackfillUpdate | None:
    pid = row["paper_id"]
    title = row["title"]
    pdf_path_str = row.get("pdf_path")

    raw_feedback = row.get("feedback_json")
    parsed_feedback = _parse_feedback_payload(raw_feedback)
    needs_summary_refresh = _needs_summary_refresh(row.get("summary"))
    needs_analysis_refresh = _needs_analysis_refresh(parsed_feedback)
    has_intake_override_log = bool(parsed_feedback and isinstance(parsed_feedback.get("intake_override_log"), dict))
    needs_log_refresh = needs_analysis_refresh or not has_intake_override_log

    summary = row.get("summary", "") or "Abstract not available."
    new_summary = summary
    analysis_payload = parsed_feedback or {}
    current_feedback_json = raw_feedback
    llm_tagging_used = False

    if needs_analysis_refresh:
        if not llm_available:
            logger.warning("Missing analysis but LLM is unavailable. Skipping %s.", pid)
            return None

        full_text = None
        if pdf_path_str:
            p = Path(pdf_path_str)
            if p.exists():
                try:
                    text = extract_text_from_pdf(p, max_pages=3)
                    full_text = text[:5000] if text else None
                except Exception as exc:
                    logger.warning("PDF extraction failed for %s: %s", pid, exc)

        paper_obj = {"title": title, "summary": summary, "full_text": full_text}

        logger.info("Requesting LLM tags for %s", pid)
        tags_data = llm.tag_paper(paper_obj)
        if not tags_data:
            logger.error("LLM returned None for %s. Skipping.", pid)
            return None

        analysis_payload = tags_data
        current_feedback_json = json.dumps(tags_data, ensure_ascii=False)
        llm_tagging_used = True

        if needs_summary_refresh:
            logger.info("Generating one-liner summary for %s", pid)
            one_liner = llm.generate_one_liner(paper_obj)
            if one_liner:
                new_summary = one_liner

    elif needs_summary_refresh and llm_available and callable(getattr(llm, "generate_one_liner", None)):
        paper_obj = {"title": title, "summary": summary, "full_text": None}
        logger.info("Generating one-liner summary for %s", pid)
        one_liner = llm.generate_one_liner(paper_obj)
        if one_liner:
            new_summary = one_liner

    if needs_log_refresh:
        new_feedback = _build_intake_logged_feedback_json(
            row=row,
            feedback_json=current_feedback_json,
            analysis_payload=analysis_payload,
            llm_tagging_used=llm_tagging_used,
        )
    else:
        new_feedback = current_feedback_json

    if new_feedback is None:
        logger.warning("No feedback payload available for %s. Skipping.", pid)
        return None

    confidence = _coerce_optional_float(analysis_payload.get("confidence", row.get("confidence")))
    return BackfillUpdate(
        paper_id=str(pid),
        feedback_json=str(new_feedback),
        confidence=confidence,
        summary=str(new_summary),
    )


def _apply_updates(conn: sqlite3.Connection, updates: list[BackfillUpdate]) -> int:
    if not updates:
        return 0
    now = datetime.now().isoformat(timespec="seconds")
    conn.execute("BEGIN IMMEDIATE")
    try:
        for item in updates:
            conn.execute(
                """
                UPDATE papers
                SET feedback_json = ?, confidence = ?, summary = ?, updated_at = ?
                WHERE paper_id = ?
                """,
                (item.feedback_json, item.confidence, item.summary, now, item.paper_id),
            )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return len(updates)


def run_backfill(
    limit: int = 50,
    *,
    apply: bool = False,
    db_path: Path | None = None,
    backup_path: Path | None = None,
    sample: int = 20,
) -> dict[str, Any]:
    conn = _connect_db(db_path)
    try:
        candidates = _select_candidates(conn, limit=limit)
        planned = [_summarize_candidate(row) for row in candidates]
        summary: dict[str, Any] = {
            "dry_run": not apply,
            "candidate_count": len(candidates),
            "would_require_llm_tagging": sum(1 for c in planned if c.needs_analysis_refresh),
            "would_refresh_summary": sum(1 for c in planned if c.needs_summary_refresh),
            "would_add_intake_log": sum(1 for c in planned if c.needs_intake_override_log),
            "sample": [
                {
                    "paper_id": c.paper_id,
                    "title": c.title[:120],
                    "needs_summary_refresh": c.needs_summary_refresh,
                    "needs_analysis_refresh": c.needs_analysis_refresh,
                    "needs_intake_override_log": c.needs_intake_override_log,
                }
                for c in planned[: max(0, sample)]
            ],
            "backup_path": None,
            "updated_count": 0,
            "skipped_count": 0,
        }
        logger.info("Found %s papers requiring backfill analysis.", len(candidates))

        if not apply:
            return summary

        if db_path is None:
            raise ValueError("db_path is required when apply=True so a SQLite backup can be created.")

        config = load_config()
        llm = get_llm_provider(config.llm, config.entity_aliases)
        llm_available = bool(llm and llm.is_available())
        if not llm_available:
            logger.warning("LLM Provider not available. Only rows with existing analysis can receive intake logs.")

        updates: list[BackfillUpdate] = []
        for row in candidates:
            try:
                logger.info("Processing: %s (%s)", row.get("paper_id"), row.get("title"))
                update = _build_update(row, llm=llm, llm_available=llm_available)
                if update is None:
                    summary["skipped_count"] += 1
                    continue
                updates.append(update)
            except Exception as exc:
                summary["skipped_count"] += 1
                logger.error("Failed to process %s: %s", row.get("paper_id"), exc)

        if updates:
            resolved_backup_path = backup_path or _default_backup_path(db_path)
            _backup_db(db_path, resolved_backup_path)
            summary["backup_path"] = str(resolved_backup_path)
            summary["updated_count"] = _apply_updates(conn, updates)

        logger.info(
            "Backfill complete. Updated: %s/%s, skipped: %s",
            summary["updated_count"],
            len(candidates),
            summary["skipped_count"],
        )
        return summary
    finally:
        conn.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Backfill paper analysis metadata and intake override logs (dry-run by default)."
    )
    parser.add_argument("--db", default="storage/state.db", help="SQLite DB path (default: storage/state.db).")
    parser.add_argument("--limit", type=int, default=100, help="Maximum candidate rows to inspect.")
    parser.add_argument("--sample", type=int, default=20, help="Candidate sample size to print in JSON output.")
    parser.add_argument("--apply", action="store_true", help="Apply updates. Default is dry-run.")
    parser.add_argument("--backup-path", default="", help="Optional SQLite backup path when --apply is used.")
    args = parser.parse_args(argv)

    db_path = Path(args.db).expanduser()
    if not db_path.exists():
        print(json.dumps({"error": "db_not_found", "db_path": str(db_path)}, indent=2, sort_keys=True))
        return 1

    backup_path = Path(args.backup_path).expanduser() if args.backup_path else None
    try:
        result = run_backfill(
            limit=max(1, args.limit),
            apply=bool(args.apply),
            db_path=db_path,
            backup_path=backup_path,
            sample=max(0, args.sample),
        )
    except Exception as exc:
        print(json.dumps({"error": str(exc), "db_path": str(db_path)}, indent=2, sort_keys=True))
        return 1

    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
