from __future__ import annotations

import argparse
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@dataclass(frozen=True)
class ArchiveCandidate:
    job_id: str
    paper_id: str
    reason: str
    error_message: str
    finished_at: str
    row_data: dict[str, Any]


def _is_test_fixture_paper_id(paper_id: str) -> bool:
    pid = str(paper_id or "")
    return (
        pid.startswith("local--")
        or "_test_" in pid
        or pid.startswith("integration_test_")
        or pid == "phase0_test"
    )


def _ensure_archive_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS job_failures_archive (
            archive_id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id TEXT NOT NULL UNIQUE,
            paper_id TEXT,
            error_message TEXT,
            finished_at TIMESTAMP,
            archived_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            archive_reason TEXT NOT NULL,
            row_json TEXT NOT NULL
        )
        """
    )


def _load_failed_rows(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    conn.row_factory = sqlite3.Row
    return list(
        conn.execute(
            """
            SELECT *
            FROM jobs
            WHERE status = 'failed'
            ORDER BY COALESCE(finished_at, created_at) ASC
            """
        ).fetchall()
    )


def select_archive_candidates(conn: sqlite3.Connection) -> list[ArchiveCandidate]:
    failed_rows = _load_failed_rows(conn)
    completed_ids = {
        str(row[0] or "")
        for row in conn.execute("SELECT DISTINCT paper_id FROM jobs WHERE status = 'completed'")
    }
    candidates: list[ArchiveCandidate] = []

    for row in failed_rows:
        data = dict(row)
        job_id = str(data.get("job_id") or "").strip()
        paper_id = str(data.get("paper_id") or "").strip()
        error_message = str(data.get("error_message") or "").strip()
        finished_at = str(data.get("finished_at") or "")
        if not job_id:
            continue

        reason: str | None = None
        if _is_test_fixture_paper_id(paper_id):
            reason = "test_fixture_failed_legacy"
        elif error_message.startswith("PDF not found for "):
            if paper_id in completed_ids:
                reason = "pdf_not_found_recovered"

        if not reason:
            continue

        candidates.append(
            ArchiveCandidate(
                job_id=job_id,
                paper_id=paper_id,
                reason=reason,
                error_message=error_message,
                finished_at=finished_at,
                row_data=data,
            )
        )
    return candidates


def _backup_db(db_path: Path, backup_path: Path) -> None:
    backup_path.parent.mkdir(parents=True, exist_ok=True)
    src = sqlite3.connect(db_path)
    dst = sqlite3.connect(backup_path)
    try:
        src.backup(dst)
    finally:
        src.close()
        dst.close()


def apply_archive(conn: sqlite3.Connection, candidates: list[ArchiveCandidate]) -> int:
    if not candidates:
        return 0
    _ensure_archive_table(conn)
    conn.execute("BEGIN IMMEDIATE")
    try:
        for c in candidates:
            conn.execute(
                """
                INSERT OR IGNORE INTO job_failures_archive
                    (job_id, paper_id, error_message, finished_at, archive_reason, row_json)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    c.job_id,
                    c.paper_id,
                    c.error_message,
                    c.finished_at,
                    c.reason,
                    json.dumps(c.row_data, ensure_ascii=False, default=str),
                ),
            )
        conn.executemany(
            "DELETE FROM jobs WHERE job_id = ? AND status = 'failed'",
            [(c.job_id,) for c in candidates],
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return len(candidates)


def _default_backup_path(db_path: Path) -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return db_path.parent / "backups" / f"{db_path.stem}_before_failed_archive_{stamp}{db_path.suffix}"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Archive legacy failed jobs (pre-fix noise) into job_failures_archive with dry-run default."
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

        print(f"[ARCHIVE] failed_candidates={len(candidates)}")
        by_reason: dict[str, int] = {}
        for c in candidates:
            by_reason[c.reason] = by_reason.get(c.reason, 0) + 1
        if by_reason:
            print(f"[ARCHIVE] by_reason={by_reason}")
        for c in candidates[: max(0, args.sample)]:
            print(f"  - {c.job_id} | {c.paper_id} | {c.reason} | {c.error_message}")

        if not args.apply:
            print("[ARCHIVE] dry-run only (no changes applied)")
            return 0

        backup_path = Path(args.backup_path).expanduser() if args.backup_path else _default_backup_path(db_path)
        _backup_db(db_path, backup_path)
        archived = apply_archive(conn, candidates)
        print(f"[ARCHIVE] backup={backup_path}")
        print(f"[ARCHIVE] archived={archived}")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
