from __future__ import annotations

import argparse
import sqlite3
from collections import Counter
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.db_orphan_refs import collect_orphans


def run_audit(db_path: Path, sample_limit: int = 5) -> int:
    if not db_path.exists():
        print(f"[ERROR] DB not found: {db_path}")
        return 1

    conn = sqlite3.connect(db_path)
    try:
        orphans = collect_orphans(conn)
    finally:
        conn.close()

    total = sum(len(records) for records in orphans.values())
    print(f"[AUDIT] orphan_total={total}")
    for table, records in orphans.items():
        print(f"[AUDIT] {table}: {len(records)}")
        reason_counts = Counter(rec.reason for rec in records)
        for reason, count in sorted(reason_counts.items()):
            print(f"  - reason:{reason} = {count}")
        for rec in records[: max(0, sample_limit)]:
            print(
                f"    sample: table={rec.table} pk={rec.pk_value} "
                f"paper_id={rec.paper_id} status={rec.status or '-'} reason={rec.reason}"
            )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit orphan paper_id references in operational tables.")
    parser.add_argument("--db", default="storage/state.db", help="SQLite DB path.")
    parser.add_argument("--sample-limit", type=int, default=5, help="Samples per table.")
    args = parser.parse_args()
    return run_audit(Path(args.db), sample_limit=args.sample_limit)


if __name__ == "__main__":
    raise SystemExit(main())
