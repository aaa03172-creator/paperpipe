from __future__ import annotations

import argparse
import sqlite3
from collections import Counter, defaultdict
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.core.ids import classify_paper_id, is_canonical_paper_id


def run_audit(db_path: Path, sample_limit: int = 5) -> int:
    if not db_path.exists():
        print(f"[ERROR] DB not found: {db_path}")
        return 1

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            "SELECT paper_id, doi, status FROM papers ORDER BY updated_at DESC"
        ).fetchall()
    except sqlite3.OperationalError as exc:
        print(f"[ERROR] Failed to query papers table: {exc}")
        return 2
    finally:
        conn.close()

    total = len(rows)
    category_counts: Counter[str] = Counter()
    samples: dict[str, list[str]] = defaultdict(list)
    canonical_count = 0

    for row in rows:
        paper_id = str(row["paper_id"] or "")
        category = classify_paper_id(paper_id)
        category_counts[category] += 1
        if is_canonical_paper_id(paper_id):
            canonical_count += 1
        if len(samples[category]) < max(1, sample_limit):
            samples[category].append(paper_id)

    canonical_ratio = round(canonical_count / total, 4) if total else 0.0
    print(f"[AUDIT] papers_total={total}")
    print(f"[AUDIT] canonical_count={canonical_count} canonical_ratio={canonical_ratio}")
    print("[AUDIT] category_breakdown:")
    for category, count in sorted(category_counts.items(), key=lambda kv: (-kv[1], kv[0])):
        print(f"  - {category}: {count}")
        for sample in samples[category]:
            print(f"      sample: {sample}")

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit paper_id policy conformance in papers table.")
    parser.add_argument("--db", default="storage/state.db", help="Path to SQLite DB.")
    parser.add_argument(
        "--sample-limit",
        type=int,
        default=5,
        help="Number of sample IDs to print per category.",
    )
    args = parser.parse_args()
    return run_audit(Path(args.db), sample_limit=args.sample_limit)


if __name__ == "__main__":
    raise SystemExit(main())
