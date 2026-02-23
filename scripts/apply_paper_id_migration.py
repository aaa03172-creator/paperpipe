from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.core.paper_identity import make_paper_key
from scripts.plan_paper_id_migration import build_plan


TABLES_WITH_PAPER_ID = ("papers", "review_queue", "jobs", "runs", "user_actions")


def _table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    try:
        rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    except sqlite3.OperationalError:
        return set()
    return {str(row[1]) for row in rows}


def _normalize_mappings(raw_plan: list[dict]) -> list[tuple[str, str]]:
    mappings: list[tuple[str, str]] = []
    for item in raw_plan:
        current = str(item.get("paper_id_current") or "").strip()
        proposed = str(item.get("paper_id_proposed") or "").strip()
        if not current or not proposed or current == proposed:
            continue
        mappings.append((current, proposed))
    return mappings


def validate_plan(conn: sqlite3.Connection, mappings: list[tuple[str, str]]) -> tuple[bool, list[str]]:
    errors: list[str] = []
    seen_current: set[str] = set()
    proposed_map: dict[str, str] = {}
    for current, proposed in mappings:
        if current in seen_current:
            errors.append(f"Duplicate current paper_id in plan: {current}")
        seen_current.add(current)
        other_current = proposed_map.get(proposed)
        if other_current and other_current != current:
            errors.append(f"Conflicting proposed paper_id: {proposed} <= {other_current}, {current}")
        proposed_map[proposed] = current

    papers_cols = _table_columns(conn, "papers")
    if "paper_id" not in papers_cols:
        errors.append("papers table missing paper_id column")
        return False, errors

    existing_ids = {
        str(row[0])
        for row in conn.execute("SELECT paper_id FROM papers WHERE paper_id IS NOT NULL").fetchall()
    }
    currents = {current for current, _ in mappings}
    for current, proposed in mappings:
        if current not in existing_ids:
            errors.append(f"Current paper_id not found in papers: {current}")
        if proposed in existing_ids and proposed not in currents:
            errors.append(f"Proposed paper_id already exists and is not being remapped: {proposed}")

    return len(errors) == 0, errors


def collect_impacts(conn: sqlite3.Connection, mappings: list[tuple[str, str]]) -> dict[str, int]:
    currents = [current for current, _ in mappings]
    if not currents:
        return {}

    placeholders = ",".join("?" for _ in currents)
    impacts: dict[str, int] = {}
    for table in TABLES_WITH_PAPER_ID:
        cols = _table_columns(conn, table)
        if "paper_id" not in cols:
            continue
        query = f"SELECT COUNT(*) FROM {table} WHERE paper_id IN ({placeholders})"
        count = int(conn.execute(query, currents).fetchone()[0])
        impacts[table] = count
    return impacts


def apply_mappings(conn: sqlite3.Connection, mappings: list[tuple[str, str]]) -> None:
    papers_cols = _table_columns(conn, "papers")
    has_paper_key = "paper_key" in papers_cols
    has_updated_at = "updated_at" in papers_cols
    now_iso = datetime.now(timezone.utc).isoformat()

    for current, proposed in mappings:
        set_fields = ["paper_id = ?"]
        params = [proposed]
        if has_paper_key:
            set_fields.append("paper_key = ?")
            params.append(make_paper_key(proposed))
        if has_updated_at:
            set_fields.append("updated_at = ?")
            params.append(now_iso)
        params.append(current)
        conn.execute(
            f"UPDATE papers SET {', '.join(set_fields)} WHERE paper_id = ?",
            params,
        )

    for table in TABLES_WITH_PAPER_ID:
        if table == "papers":
            continue
        cols = _table_columns(conn, table)
        if "paper_id" not in cols:
            continue
        for current, proposed in mappings:
            conn.execute(
                f"UPDATE {table} SET paper_id = ? WHERE paper_id = ?",
                (proposed, current),
            )


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply canonical paper_id migration plan to DB.")
    parser.add_argument("--db", default="storage/state.db", help="SQLite DB path.")
    parser.add_argument(
        "--plan",
        default="",
        help="Path to migration plan JSON. If omitted, plan is generated in-memory from current DB.",
    )
    parser.add_argument("--apply", action="store_true", help="Apply changes. Default is dry-run.")
    parser.add_argument(
        "--backup",
        default="",
        help="Backup DB path used when --apply is set. Defaults to <db>.bak",
    )
    args = parser.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"[ERROR] DB not found: {db_path}")
        return 1

    if args.plan:
        plan_path = Path(args.plan)
        if not plan_path.exists():
            print(f"[ERROR] Plan file not found: {plan_path}")
            return 2
        raw_plan = json.loads(plan_path.read_text(encoding="utf-8"))
    else:
        raw_plan = build_plan(db_path)

    mappings = _normalize_mappings(raw_plan)
    print(f"[MIGRATION] mappings={len(mappings)}")
    if not mappings:
        print("[MIGRATION] no-op (no mappings)")
        return 0

    conn = sqlite3.connect(db_path)
    try:
        ok, errors = validate_plan(conn, mappings)
        if not ok:
            print("[MIGRATION] validation failed")
            for err in errors:
                print(f"  - {err}")
            return 3

        impacts = collect_impacts(conn, mappings)
        print("[MIGRATION] table impacts:")
        for table, count in impacts.items():
            print(f"  - {table}: {count}")

        if not args.apply:
            print("[MIGRATION] dry-run only (no changes applied)")
            return 0

        backup_path = Path(args.backup) if args.backup else db_path.with_suffix(db_path.suffix + ".bak")
        backup_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(db_path, backup_path)
        print(f"[MIGRATION] backup created: {backup_path}")

        conn.execute("PRAGMA foreign_keys = OFF")
        conn.execute("BEGIN IMMEDIATE")
        apply_mappings(conn, mappings)
        conn.commit()
        conn.execute("PRAGMA foreign_keys = ON")
        print("[MIGRATION] apply complete")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
