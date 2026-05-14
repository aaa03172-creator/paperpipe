from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.services.fixture_visibility import classify_test_fixture_paper_record


@dataclass(frozen=True)
class FixturePaperArchiveCandidate:
    paper_id: str
    title: str
    status: str
    fixture_reason: str
    archive_reason: str
    row_data: dict[str, Any]


def _ensure_archive_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS fixture_papers_archive (
            archive_id INTEGER PRIMARY KEY AUTOINCREMENT,
            paper_id TEXT NOT NULL UNIQUE,
            title TEXT,
            status TEXT,
            fixture_reason TEXT NOT NULL,
            archived_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            archive_reason TEXT NOT NULL,
            row_json TEXT NOT NULL
        )
        """
    )


def _load_paper_rows(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    conn.row_factory = sqlite3.Row
    return list(conn.execute("SELECT * FROM papers ORDER BY paper_id").fetchall())


def _feedback_json_missing(value: object) -> bool:
    return value is None or not str(value).strip()


def select_archive_candidates(conn: sqlite3.Connection) -> list[FixturePaperArchiveCandidate]:
    candidates: list[FixturePaperArchiveCandidate] = []
    for row in _load_paper_rows(conn):
        data = dict(row)
        if not _feedback_json_missing(data.get("feedback_json")):
            continue

        is_fixture, fixture_reason = classify_test_fixture_paper_record(data)
        if not is_fixture or not fixture_reason:
            continue

        paper_id = str(data.get("paper_id") or "").strip()
        if not paper_id:
            continue

        candidates.append(
            FixturePaperArchiveCandidate(
                paper_id=paper_id,
                title=str(data.get("title") or "").strip(),
                status=str(data.get("status") or "").strip(),
                fixture_reason=fixture_reason,
                archive_reason="fixture_no_feedback_json",
                row_data=data,
            )
        )
    return candidates


def backup_db(db_path: Path, backup_path: Path) -> None:
    backup_path.parent.mkdir(parents=True, exist_ok=True)
    src = sqlite3.connect(db_path)
    dst = sqlite3.connect(backup_path)
    try:
        src.backup(dst)
    finally:
        src.close()
        dst.close()


def apply_archive(conn: sqlite3.Connection, candidates: list[FixturePaperArchiveCandidate]) -> int:
    if not candidates:
        return 0

    _ensure_archive_table(conn)
    conn.execute("BEGIN IMMEDIATE")
    try:
        for candidate in candidates:
            conn.execute(
                """
                INSERT OR IGNORE INTO fixture_papers_archive
                    (paper_id, title, status, fixture_reason, archive_reason, row_json)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    candidate.paper_id,
                    candidate.title,
                    candidate.status,
                    candidate.fixture_reason,
                    candidate.archive_reason,
                    json.dumps(candidate.row_data, ensure_ascii=False, default=str),
                ),
            )
        conn.executemany(
            """
            DELETE FROM papers
            WHERE paper_id = ?
              AND COALESCE(TRIM(feedback_json), '') = ''
            """,
            [(candidate.paper_id,) for candidate in candidates],
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return len(candidates)


def default_backup_path(db_path: Path) -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return db_path.parent / "backups" / f"{db_path.stem}_before_fixture_paper_archive_{stamp}{db_path.suffix}"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Archive fixture-only paper rows with empty feedback_json. Dry-run by default."
    )
    parser.add_argument("--db", default="storage/state.db", help="SQLite DB path (default: storage/state.db)")
    parser.add_argument("--apply", action="store_true", help="Apply archive+delete. Default is dry-run.")
    parser.add_argument("--sample", type=int, default=20, help="Number of candidate rows to print.")
    parser.add_argument("--max-count", type=int, default=0, help="Limit candidates to archive (0 = all).")
    parser.add_argument("--backup-path", default="", help="Optional backup file path. Auto-generated if omitted.")
    args = parser.parse_args()

    db_path = Path(args.db).expanduser()
    if not db_path.exists():
        print(f"[ARCHIVE] db_not_found={db_path}")
        return 1

    conn = sqlite3.connect(db_path)
    try:
        candidates = select_archive_candidates(conn)
        if args.max_count and args.max_count > 0:
            candidates = candidates[: args.max_count]

        print(f"[ARCHIVE] fixture_no_feedback_candidates={len(candidates)}")
        by_fixture_reason: dict[str, int] = {}
        by_status: dict[str, int] = {}
        for candidate in candidates:
            by_fixture_reason[candidate.fixture_reason] = by_fixture_reason.get(candidate.fixture_reason, 0) + 1
            status = candidate.status or "unknown"
            by_status[status] = by_status.get(status, 0) + 1
        if by_fixture_reason:
            print(f"[ARCHIVE] by_fixture_reason={by_fixture_reason}")
        if by_status:
            print(f"[ARCHIVE] by_status={by_status}")
        for candidate in candidates[: max(0, args.sample)]:
            print(
                f"  - {candidate.paper_id} | {candidate.status or '-'} | "
                f"{candidate.fixture_reason} | {candidate.title or '-'}"
            )

        if not args.apply:
            print("[ARCHIVE] dry-run only (no changes applied)")
            return 0

        backup_path = Path(args.backup_path).expanduser() if args.backup_path else default_backup_path(db_path)
        backup_db(db_path, backup_path)
        archived = apply_archive(conn, candidates)
        print(f"[ARCHIVE] backup={backup_path}")
        print(f"[ARCHIVE] archived={archived}")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
