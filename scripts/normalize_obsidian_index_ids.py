from __future__ import annotations

import argparse
import csv
import json
import shutil
import sqlite3
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.core.ids import is_canonical_paper_id, normalize_doi


def _normalize_note_path(value: str | None) -> str:
    raw = str(value or "").strip().replace("\\", "/")
    if not raw:
        return ""
    while raw.startswith("./"):
        raw = raw[2:]
    return raw


def load_obsidian_path_map(db_path: Path) -> dict[str, str]:
    if not db_path.exists():
        return {}

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        table_info = conn.execute("PRAGMA table_info(papers)").fetchall()
        columns = {str(row["name"]) for row in table_info}
        if "paper_id" not in columns or "obsidian_path" not in columns:
            return {}

        rows = conn.execute(
            """
            SELECT paper_id, obsidian_path
            FROM papers
            WHERE obsidian_path IS NOT NULL AND TRIM(obsidian_path) != ''
            """
        ).fetchall()
    except sqlite3.OperationalError:
        return {}
    finally:
        conn.close()

    resolved: dict[str, str] = {}
    ambiguous: set[str] = set()
    for row in rows:
        paper_id = str(row["paper_id"] or "").strip()
        if not is_canonical_paper_id(paper_id):
            continue
        note_path = _normalize_note_path(row["obsidian_path"])
        if not note_path:
            continue

        existing = resolved.get(note_path)
        if existing and existing != paper_id:
            ambiguous.add(note_path)
            continue
        resolved[note_path] = paper_id

    for path in ambiguous:
        resolved.pop(path, None)
    return resolved


def build_plan(
    *,
    index_path: Path,
    db_path: Path,
) -> tuple[list[dict[str, Any]], list[dict[str, str]], dict[str, str]]:
    if not index_path.exists():
        raise FileNotFoundError(f"CSV index not found: {index_path}")

    with index_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames or "Paper_ID" not in reader.fieldnames:
            raise ValueError("CSV index must include a Paper_ID column.")
        rows = list(reader)

    obsidian_path_map = load_obsidian_path_map(db_path)
    obsidian_path_map_lower = {key.lower(): value for key, value in obsidian_path_map.items()}

    plan: list[dict[str, Any]] = []
    for idx, row in enumerate(rows):
        current = str(row.get("Paper_ID") or "").strip()
        if not current or is_canonical_paper_id(current):
            continue

        proposed = ""
        reason = ""

        doi_value = normalize_doi(row.get("DOI"))
        if doi_value:
            proposed = f"doi:{doi_value}"
            reason = "doi"
        else:
            note_path = _normalize_note_path(row.get("Note_Path"))
            if note_path:
                proposed = obsidian_path_map.get(note_path) or obsidian_path_map_lower.get(note_path.lower(), "")
                reason = "obsidian_path" if proposed else ""

        if not proposed or proposed == current:
            continue

        plan.append(
            {
                "row_index": idx,
                "line": idx + 2,
                "paper_id_current": current,
                "paper_id_proposed": proposed,
                "reason": reason,
                "title": str(row.get("Title") or "").strip(),
                "note_path": str(row.get("Note_Path") or "").strip(),
            }
        )

    return plan, rows, obsidian_path_map


def apply_plan(rows: list[dict[str, str]], plan: list[dict[str, Any]]) -> None:
    for item in plan:
        row_index = int(item["row_index"])
        rows[row_index]["Paper_ID"] = str(item["paper_id_proposed"])


def write_rows(index_path: Path, rows: list[dict[str, str]]) -> None:
    headers = list(rows[0].keys()) if rows else ["Date", "Slot", "Paper_ID", "Title"]
    with index_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=headers, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _default_backup_path(index_path: Path) -> Path:
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    return index_path.with_name(f"{index_path.name}.bak.{ts}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Normalize legacy Paper_ID values in Obsidian index CSV (dry-run by default)."
    )
    parser.add_argument("--index", default="obsidian/00_Index/paper_collection.csv", help="Path to Obsidian CSV index.")
    parser.add_argument("--db", default="storage/state.db", help="Path to SQLite DB for note_path->paper_id fallback.")
    parser.add_argument(
        "--out",
        default="storage/obsidian_index_paper_id_plan.json",
        help="Path to write migration plan JSON.",
    )
    parser.add_argument("--apply", action="store_true", help="Apply replacements to CSV. Default is dry-run.")
    parser.add_argument("--backup", default="", help="Backup path for CSV when --apply is used.")
    parser.add_argument("--print-sample", type=int, default=10, help="Number of candidate rows to print.")
    args = parser.parse_args()

    index_path = Path(args.index)
    db_path = Path(args.db)

    try:
        plan, rows, obsidian_path_map = build_plan(index_path=index_path, db_path=db_path)
    except FileNotFoundError as exc:
        print(f"[ERROR] {exc}")
        return 1
    except ValueError as exc:
        print(f"[ERROR] {exc}")
        return 2

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[PLAN] candidates={len(plan)}")
    print(f"[PLAN] out={out_path}")
    print(f"[PLAN] obsidian_path_map_entries={len(obsidian_path_map)}")
    reason_counts = Counter(item["reason"] for item in plan)
    for reason, count in sorted(reason_counts.items()):
        print(f"  - reason:{reason} = {count}")

    sample_count = max(0, args.print_sample)
    for item in plan[:sample_count]:
        print(
            f"  - L{item['line']}: {item['paper_id_current']} -> {item['paper_id_proposed']} "
            f"[{item['reason']}] {item['title']}"
        )

    if not args.apply:
        print("[PLAN] dry-run only (no CSV changes applied)")
        return 0

    if not plan:
        print("[APPLY] no-op (no candidates)")
        return 0

    backup_path = Path(args.backup) if args.backup else _default_backup_path(index_path)
    backup_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(index_path, backup_path)
    print(f"[APPLY] backup={backup_path}")

    apply_plan(rows, plan)
    write_rows(index_path, rows)
    print(f"[APPLY] updated_csv={index_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
