from __future__ import annotations

import argparse
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.db_orphan_refs import apply_cleanup, backup_db_file, collect_orphans, select_cleanup_candidates


def _default_backup_path(db_path: Path) -> Path:
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    return db_path.with_name(f"{db_path.name}.orphan_cleanup.bak.{ts}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Cleanup orphan paper_id references in jobs/runs (dry-run by default)."
    )
    parser.add_argument("--db", default="storage/state.db", help="SQLite DB path.")
    parser.add_argument(
        "--mode",
        default="test_terminal",
        choices=["test_terminal", "terminal_all"],
        help="Cleanup policy mode.",
    )
    parser.add_argument("--apply", action="store_true", help="Apply deletes. Default is dry-run.")
    parser.add_argument("--backup", default="", help="Backup path used when --apply.")
    parser.add_argument("--print-sample", type=int, default=10, help="Sample candidate rows.")
    args = parser.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"[ERROR] DB not found: {db_path}")
        return 1

    conn = sqlite3.connect(db_path)
    try:
        conn.row_factory = sqlite3.Row
        orphans = collect_orphans(conn)
        candidates = select_cleanup_candidates(orphans, mode=args.mode)
        print(f"[CLEANUP] mode={args.mode}")
        print(f"[CLEANUP] orphan_total={sum(len(v) for v in orphans.values())}")
        print(f"[CLEANUP] candidates={len(candidates)}")
        for rec in candidates[: max(0, args.print_sample)]:
            print(
                f"  - table={rec.table} pk={rec.pk_value} "
                f"paper_id={rec.paper_id} status={rec.status or '-'} reason={rec.reason}"
            )

        if not args.apply:
            print("[CLEANUP] dry-run only (no changes applied)")
            return 0

        if not candidates:
            print("[CLEANUP] no-op (no candidates)")
            return 0

        backup_path = Path(args.backup) if args.backup else _default_backup_path(db_path)
        backup_db_file(db_path, backup_path)
        print(f"[CLEANUP] backup={backup_path}")

        conn.execute("BEGIN IMMEDIATE")
        deleted = apply_cleanup(conn, candidates=candidates)
        conn.commit()
        print("[CLEANUP] deleted:")
        for table, count in deleted.items():
            print(f"  - {table}: {count}")
        return 0
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
