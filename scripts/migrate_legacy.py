from __future__ import annotations

import argparse
import json
import logging
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

DEFAULT_DB_PATH = Path("storage/state.db")
DEFAULT_FEEDBACK_PATH = Path("storage/feedback.jsonl")
DEFAULT_ZOTERO_PATH = Path("storage/zotero_export.json")

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("migrate")


@dataclass(frozen=True)
class LegacyPaperCandidate:
    paper_id: str
    title: str
    confidence: float
    gate_decision: str
    raw_feedback_json: str


def load_zotero_titles(zotero_path: Path = DEFAULT_ZOTERO_PATH) -> dict[str, str]:
    """Load paper_id -> title mapping from Zotero export."""
    if not zotero_path.exists():
        logger.warning("Zotero export not found at %s. Titles will be unknown.", zotero_path)
        return {}

    try:
        data = json.loads(zotero_path.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.error("Failed to load Zotero export: %s", exc)
        return {}

    mapping: dict[str, str] = {}
    for item in data.get("items", []):
        if "citationKey" in item and "title" in item:
            mapping[str(item["citationKey"])] = str(item["title"])
    return mapping


def parse_confidence(user_correction_str: Any) -> float:
    """
    Attempt to extract confidence from the user_correction JSON string.
    Returns average confidence of claims, or default 0.8.
    """
    try:
        cleaned_str = str(user_correction_str or "")
        if "Golden Shot by Claude" in cleaned_str:
            cleaned_str = cleaned_str.split("\n", 1)[1]

        data = json.loads(cleaned_str)
        claims = data.get("claims", [])

        if not claims:
            return 0.8

        total_conf = sum(c.get("confidence", 0.0) for c in claims)
        return round(total_conf / len(claims), 2)
    except Exception:
        return 0.8


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
    return db_path.parent / "backups" / f"{db_path.stem}_before_legacy_migrate_{stamp}{db_path.suffix}"


def _existing_paper_ids(conn: sqlite3.Connection, paper_ids: list[str]) -> set[str]:
    if not paper_ids:
        return set()
    existing: set[str] = set()
    for paper_id in paper_ids:
        row = conn.execute("SELECT 1 FROM papers WHERE paper_id = ?", (paper_id,)).fetchone()
        if row:
            existing.add(paper_id)
    return existing


def collect_candidates(
    conn: sqlite3.Connection,
    *,
    feedback_path: Path,
    zotero_path: Path,
) -> tuple[list[LegacyPaperCandidate], dict[str, Any]]:
    title_map = load_zotero_titles(zotero_path)
    stats: dict[str, Any] = {
        "source_lines": 0,
        "malformed_lines": 0,
        "missing_paper_id": 0,
        "skipped_existing": 0,
        "zotero_titles": len(title_map),
    }

    parsed_rows: list[tuple[str, str, dict[str, Any]]] = []
    for line_num, raw_line in enumerate(feedback_path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw_line.strip()
        if not line:
            continue
        stats["source_lines"] += 1
        try:
            rec = json.loads(line)
        except Exception:
            stats["malformed_lines"] += 1
            continue
        if not isinstance(rec, dict):
            stats["malformed_lines"] += 1
            continue

        paper_id = str(rec.get("paper_id") or "").strip()
        if not paper_id:
            stats["missing_paper_id"] += 1
            continue

        parsed_rows.append((paper_id, line, rec))

    existing = _existing_paper_ids(conn, [paper_id for paper_id, _, _ in parsed_rows])
    candidates: list[LegacyPaperCandidate] = []
    for paper_id, raw_line, rec in parsed_rows:
        if paper_id in existing:
            stats["skipped_existing"] += 1
            continue
        confidence = parse_confidence(rec.get("user_correction", ""))
        candidates.append(
            LegacyPaperCandidate(
                paper_id=paper_id,
                title=title_map.get(paper_id, "Unknown Title"),
                confidence=confidence,
                gate_decision="APPROVED" if confidence > 0.8 else "PENDING_REVIEW",
                raw_feedback_json=raw_line,
            )
        )

    return candidates, stats


def apply_candidates(conn: sqlite3.Connection, candidates: list[LegacyPaperCandidate]) -> int:
    if not candidates:
        return 0

    conn.execute("BEGIN IMMEDIATE")
    try:
        for item in candidates:
            conn.execute(
                """
                INSERT INTO papers (
                    paper_id, title, status, confidence,
                    gate_decision, feedback_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """,
                (
                    item.paper_id,
                    item.title,
                    "INDEXED",
                    item.confidence,
                    item.gate_decision,
                    item.raw_feedback_json,
                ),
            )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return len(candidates)


def run_migration(
    *,
    db_path: Path = DEFAULT_DB_PATH,
    feedback_path: Path = DEFAULT_FEEDBACK_PATH,
    zotero_path: Path = DEFAULT_ZOTERO_PATH,
    apply: bool = False,
    backup_path: Path | None = None,
    sample: int = 20,
) -> dict[str, Any]:
    if not db_path.exists():
        raise FileNotFoundError(f"DB not found: {db_path}")
    if not feedback_path.exists():
        raise FileNotFoundError(f"Source file not found: {feedback_path}")

    conn = sqlite3.connect(db_path)
    try:
        candidates, stats = collect_candidates(conn, feedback_path=feedback_path, zotero_path=zotero_path)
        summary: dict[str, Any] = {
            "dry_run": not apply,
            "db_path": str(db_path),
            "feedback_path": str(feedback_path),
            "zotero_path": str(zotero_path),
            "candidate_count": len(candidates),
            "inserted_count": 0,
            "backup_path": None,
            **stats,
            "sample": [
                {
                    "paper_id": item.paper_id,
                    "title": item.title[:120],
                    "confidence": item.confidence,
                    "gate_decision": item.gate_decision,
                }
                for item in candidates[: max(0, sample)]
            ],
        }

        if not apply:
            return summary

        if candidates:
            resolved_backup_path = backup_path or _default_backup_path(db_path)
            _backup_db(db_path, resolved_backup_path)
            summary["backup_path"] = str(resolved_backup_path)
            summary["inserted_count"] = apply_candidates(conn, candidates)

        return summary
    finally:
        conn.close()


def migrate(*, apply: bool = False) -> dict[str, Any]:
    return run_migration(apply=apply)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Import legacy storage/feedback.jsonl paper rows into SQLite (dry-run by default)."
    )
    parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH, help="SQLite DB path.")
    parser.add_argument("--feedback", type=Path, default=DEFAULT_FEEDBACK_PATH, help="Legacy feedback JSONL path.")
    parser.add_argument("--zotero", type=Path, default=DEFAULT_ZOTERO_PATH, help="Zotero export JSON path.")
    parser.add_argument("--sample", type=int, default=20, help="Candidate sample size to print.")
    parser.add_argument("--backup-path", type=Path, default=None, help="Optional SQLite backup path when --apply is used.")
    parser.add_argument("--apply", action="store_true", help="Apply inserts. Default is dry-run.")
    args = parser.parse_args(argv)

    try:
        summary = run_migration(
            db_path=args.db.expanduser(),
            feedback_path=args.feedback.expanduser(),
            zotero_path=args.zotero.expanduser(),
            apply=bool(args.apply),
            backup_path=args.backup_path.expanduser() if args.backup_path else None,
            sample=max(0, args.sample),
        )
    except Exception as exc:
        print(json.dumps({"error": str(exc)}, indent=2, sort_keys=True))
        return 1

    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
