from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.core.ids import classify_paper_id, is_canonical_paper_id, propose_canonical_paper_id


def load_zotero_keys(zotero_json_path: Path) -> set[str]:
    if not zotero_json_path.exists():
        return set()
    try:
        payload = json.loads(zotero_json_path.read_text(encoding="utf-8"))
    except Exception:
        return set()
    items = payload.get("items", [])
    out: set[str] = set()
    for item in items:
        key = str(item.get("citationKey") or "").strip()
        if key:
            out.add(key)
    return out


def build_plan(db_path: Path, *, zotero_keys: set[str] | None = None) -> list[dict]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            "SELECT paper_id, doi, pdf_path, status FROM papers ORDER BY updated_at DESC"
        ).fetchall()
    finally:
        conn.close()

    zotero_key_set = zotero_keys or set()
    plan: list[dict] = []
    for row in rows:
        current = str(row["paper_id"] or "").strip()
        zotero_key = current if current in zotero_key_set else None
        proposed = propose_canonical_paper_id(
            current,
            zotero_key=zotero_key,
            doi=row["doi"],
            pdf_path=row["pdf_path"],
        )
        if not current:
            continue
        if proposed == current:
            continue
        plan.append(
            {
                "paper_id_current": current,
                "paper_id_proposed": proposed,
                "status": row["status"],
                "category_current": classify_paper_id(current),
                "category_proposed": classify_paper_id(proposed),
            }
        )
    return plan


def main() -> int:
    parser = argparse.ArgumentParser(description="Dry-run planner for paper_id canonical migration.")
    parser.add_argument("--db", default="storage/state.db", help="SQLite DB path.")
    parser.add_argument(
        "--out",
        default="storage/paper_id_migration_plan.json",
        help="Output JSON path for migration candidates.",
    )
    parser.add_argument(
        "--print-sample",
        type=int,
        default=10,
        help="Number of sample rows to print.",
    )
    parser.add_argument(
        "--zotero-json",
        default="storage/zotero_export.json",
        help="Path to Zotero export JSON used to prioritize zotero:{citationKey} IDs.",
    )
    args = parser.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"[ERROR] DB not found: {db_path}")
        return 1

    zotero_keys = load_zotero_keys(Path(args.zotero_json))
    plan = build_plan(db_path, zotero_keys=zotero_keys)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[PLAN] total_candidates={len(plan)}")
    canonical_targets = sum(1 for item in plan if is_canonical_paper_id(item["paper_id_proposed"]))
    print(f"[PLAN] canonical_targets={canonical_targets}")
    print(f"[PLAN] output={out_path}")

    sample_count = max(0, args.print_sample)
    for item in plan[:sample_count]:
        print(
            f"  - {item['paper_id_current']} -> {item['paper_id_proposed']} "
            f"({item['category_current']} -> {item['category_proposed']})"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
