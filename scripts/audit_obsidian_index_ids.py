from __future__ import annotations

import argparse
import csv
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.core.ids import classify_paper_id, is_canonical_paper_id
from scripts.normalize_obsidian_index_ids import build_plan


def run_audit(
    *,
    index_path: Path,
    db_path: Path,
    sample_limit: int = 5,
) -> int:
    if not index_path.exists():
        print(f"[ERROR] CSV index not found: {index_path}")
        return 1

    with index_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames or "Paper_ID" not in reader.fieldnames:
            print("[ERROR] CSV index must include a Paper_ID column.")
            return 2
        rows = list(reader)

    category_counts: Counter[str] = Counter()
    samples: dict[str, list[str]] = defaultdict(list)
    canonical_count = 0
    for row in rows:
        paper_id = str(row.get("Paper_ID") or "").strip()
        category = classify_paper_id(paper_id)
        category_counts[category] += 1
        if is_canonical_paper_id(paper_id):
            canonical_count += 1
        if len(samples[category]) < max(1, sample_limit):
            samples[category].append(paper_id)

    total = len(rows)
    canonical_ratio = round((canonical_count / total), 4) if total else 0.0
    print(f"[AUDIT] rows_total={total}")
    print(f"[AUDIT] canonical_count={canonical_count} canonical_ratio={canonical_ratio}")
    print("[AUDIT] category_breakdown:")
    for category, count in sorted(category_counts.items(), key=lambda item: (-item[1], item[0])):
        print(f"  - {category}: {count}")
        for sample in samples[category]:
            print(f"      sample: {sample}")

    plan, _, _ = build_plan(index_path=index_path, db_path=db_path)
    reason_counts = Counter(item["reason"] for item in plan)
    print(f"[AUDIT] migratable_candidates={len(plan)}")
    for reason, count in sorted(reason_counts.items()):
        print(f"  - candidate_reason:{reason} = {count}")

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit canonical Paper_ID conformance in Obsidian CSV index.")
    parser.add_argument("--index", default="obsidian/00_Index/paper_collection.csv", help="Path to Obsidian CSV index.")
    parser.add_argument("--db", default="storage/state.db", help="Path to SQLite DB.")
    parser.add_argument("--sample-limit", type=int, default=5, help="Samples per category.")
    args = parser.parse_args()
    return run_audit(index_path=Path(args.index), db_path=Path(args.db), sample_limit=args.sample_limit)


if __name__ == "__main__":
    raise SystemExit(main())
