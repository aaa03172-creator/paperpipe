from __future__ import annotations

import argparse
import sqlite3
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.services.summary_normalizer import SummaryNormalizationResult, normalize_summary_text


@dataclass(frozen=True)
class SummaryCandidate:
    paper_id: str
    status: str
    before: str
    after: str
    reasons: list[str]


def _is_test_fixture_record(paper_id: str, pdf_path: str | None) -> bool:
    pid = str(paper_id or "")
    path = str(pdf_path or "").replace("\\", "/")
    return (
        pid.startswith("local--")
        or "_test_" in pid
        or pid.startswith("integration_test_")
        or pid == "phase0_test"
        or "/tests/" in path
    )


def _table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    cur = conn.cursor()
    cur.execute(f"PRAGMA table_info({table})")
    return {str(row[1]) for row in cur.fetchall()}


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
    return db_path.parent / "backups" / f"{db_path.stem}_before_summary_normalize_{stamp}{db_path.suffix}"


def collect_candidates(
    conn: sqlite3.Connection,
    *,
    statuses: Iterable[str],
    max_chars: int,
    paper_ids: set[str] | None = None,
    include_test_fixtures: bool = False,
) -> list[SummaryCandidate]:
    conn.row_factory = sqlite3.Row
    cols = _table_columns(conn, "papers")
    has_pdf_path = "pdf_path" in cols
    status_list = [s.strip() for s in statuses if s.strip()]
    if not status_list:
        status_list = ["APPROVED", "INDEXED"]
    placeholders = ",".join("?" for _ in status_list)
    order_by = "updated_at ASC" if "updated_at" in cols else "paper_id ASC"
    pdf_path_expr = "pdf_path" if has_pdf_path else "NULL AS pdf_path"
    rows = conn.execute(
        f"""
        SELECT paper_id, status, summary, {pdf_path_expr}
        FROM papers
        WHERE status IN ({placeholders})
        ORDER BY {order_by}
        """,
        status_list,
    ).fetchall()

    out: list[SummaryCandidate] = []
    for row in rows:
        paper_id = str(row["paper_id"] or "").strip()
        if not paper_id:
            continue
        if not include_test_fixtures and _is_test_fixture_record(paper_id, row["pdf_path"]):
            continue
        if paper_ids is not None and paper_id not in paper_ids:
            continue
        before = str(row["summary"] or "")
        result: SummaryNormalizationResult = normalize_summary_text(before, max_chars=max_chars)
        if not result.changed:
            continue
        out.append(
            SummaryCandidate(
                paper_id=paper_id,
                status=str(row["status"] or ""),
                before=before,
                after=result.text,
                reasons=result.reasons,
            )
        )
    return out


def apply_candidates(conn: sqlite3.Connection, candidates: list[SummaryCandidate]) -> int:
    if not candidates:
        return 0
    cols = _table_columns(conn, "papers")
    has_updated_at = "updated_at" in cols
    conn.execute("BEGIN IMMEDIATE")
    try:
        for item in candidates:
            if has_updated_at:
                conn.execute(
                    """
                    UPDATE papers
                    SET summary = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE paper_id = ?
                    """,
                    (item.after, item.paper_id),
                )
            else:
                conn.execute(
                    """
                    UPDATE papers
                    SET summary = ?
                    WHERE paper_id = ?
                    """,
                    (item.after, item.paper_id),
                )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return len(candidates)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Normalize low-quality summary text in papers.summary (dry-run by default)."
    )
    parser.add_argument("--db", default="storage/state.db", help="SQLite DB path (default: storage/state.db)")
    parser.add_argument("--apply", action="store_true", help="Apply updates. Default is dry-run.")
    parser.add_argument("--max-chars", type=int, default=320, help="Max summary length after normalization.")
    parser.add_argument(
        "--statuses",
        default="APPROVED,INDEXED",
        help="Comma-separated statuses to scan (default: APPROVED,INDEXED).",
    )
    parser.add_argument(
        "--paper-id",
        action="append",
        dest="paper_ids",
        help="Optional target paper_id. Repeat to update specific papers only.",
    )
    parser.add_argument("--sample", type=int, default=20, help="Sample rows to print.")
    parser.add_argument("--backup-path", default="", help="Optional backup path (used when --apply).")
    parser.add_argument(
        "--include-test-fixtures",
        action="store_true",
        help="Include local/integration test fixture records. Default excludes them.",
    )
    args = parser.parse_args()

    db_path = Path(args.db).expanduser()
    if not db_path.exists():
        print(f"[SUMMARY-NORM] db_not_found={db_path}")
        return 1

    statuses = [s.strip() for s in args.statuses.split(",") if s.strip()]
    paper_ids = {p.strip() for p in (args.paper_ids or []) if p.strip()}
    if not paper_ids:
        paper_ids = None

    conn = sqlite3.connect(db_path)
    try:
        candidates = collect_candidates(
            conn,
            statuses=statuses,
            max_chars=max(40, args.max_chars),
            paper_ids=paper_ids,
            include_test_fixtures=bool(args.include_test_fixtures),
        )
        reason_counter: Counter[str] = Counter()
        for c in candidates:
            reason_counter.update(c.reasons)

        print(f"[SUMMARY-NORM] statuses={statuses}")
        print(f"[SUMMARY-NORM] target_paper_ids={'ALL' if paper_ids is None else len(paper_ids)}")
        print(f"[SUMMARY-NORM] candidates={len(candidates)}")
        print(f"[SUMMARY-NORM] reasons={dict(reason_counter)}")
        for c in candidates[: max(0, args.sample)]:
            before_preview = " ".join(c.before.split())[:120]
            after_preview = " ".join(c.after.split())[:120]
            print(
                f"  - {c.paper_id} | {c.status} | reasons={','.join(c.reasons)}\n"
                f"    before={before_preview}\n"
                f"    after ={after_preview}"
            )

        if not args.apply:
            print("[SUMMARY-NORM] dry-run only (no changes applied)")
            return 0

        backup_path = Path(args.backup_path).expanduser() if args.backup_path else _default_backup_path(db_path)
        _backup_db(db_path, backup_path)
        updated = apply_candidates(conn, candidates)
        print(f"[SUMMARY-NORM] backup={backup_path}")
        print(f"[SUMMARY-NORM] updated={updated}")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
