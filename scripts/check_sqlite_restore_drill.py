from __future__ import annotations

import argparse
import glob
import json
import shutil
import sqlite3
import tempfile
from pathlib import Path
from typing import Any


DEFAULT_BACKUP_GLOB = "storage/backups/*.db"
DEFAULT_REQUIRED_TABLES = ("papers",)


def _latest_backup(pattern: str) -> Path | None:
    expanded_pattern = str(Path(pattern).expanduser()) if pattern.startswith("~") else pattern
    candidates = [Path(path) for path in glob.glob(expanded_pattern) if Path(path).is_file()]
    if not candidates:
        return None
    return max(candidates, key=lambda path: path.stat().st_mtime)


def _connect_readonly(path: Path) -> sqlite3.Connection:
    uri = f"file:{path.resolve()}?mode=ro"
    return sqlite3.connect(uri, uri=True)


def _table_names(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type = 'table'
          AND name NOT LIKE 'sqlite_%'
        ORDER BY name
        """
    ).fetchall()
    return {str(row[0]) for row in rows}


def _quote_identifier(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def _row_count(conn: sqlite3.Connection, table: str) -> int | None:
    try:
        row = conn.execute(f"SELECT COUNT(*) FROM {_quote_identifier(table)}").fetchone()
    except sqlite3.Error:
        return None
    return int(row[0]) if row else None


def run_restore_drill(
    *,
    backup_path: Path | None = None,
    backup_glob: str = DEFAULT_BACKUP_GLOB,
    required_tables: list[str] | None = None,
    work_dir: Path | None = None,
) -> dict[str, Any]:
    required = [table.strip() for table in (required_tables or list(DEFAULT_REQUIRED_TABLES)) if table.strip()]
    selected_backup = backup_path or _latest_backup(backup_glob)
    if selected_backup is None:
        return {
            "status": "error",
            "error": "backup_not_found",
            "backup_glob": backup_glob,
        }

    selected_backup = selected_backup.expanduser()
    if not selected_backup.exists():
        return {
            "status": "error",
            "error": "backup_not_found",
            "backup_path": str(selected_backup),
        }
    if not selected_backup.is_file():
        return {
            "status": "error",
            "error": "backup_not_file",
            "backup_path": str(selected_backup),
        }

    backup_size = selected_backup.stat().st_size
    temp_context = tempfile.TemporaryDirectory(prefix="paperpipe_restore_drill_") if work_dir is None else None
    drill_root = Path(temp_context.name) if temp_context is not None else work_dir.expanduser()
    drill_root.mkdir(parents=True, exist_ok=True)
    restored_copy = drill_root / f"restore_drill_{selected_backup.name}"

    try:
        shutil.copy2(selected_backup, restored_copy)
        conn = _connect_readonly(restored_copy)
        try:
            integrity_row = conn.execute("PRAGMA integrity_check").fetchone()
            integrity = str(integrity_row[0]) if integrity_row else "missing"
            tables = sorted(_table_names(conn))
            table_set = set(tables)
            missing_tables = [table for table in required if table not in table_set]
            row_counts = {table: _row_count(conn, table) for table in required if table in table_set}
        finally:
            conn.close()
    except Exception as exc:
        return {
            "status": "error",
            "error": "restore_drill_failed",
            "backup_path": str(selected_backup),
            "restored_copy": str(restored_copy),
            "exception": str(exc),
        }
    finally:
        if temp_context is not None:
            temp_context.cleanup()

    status = "ok" if integrity == "ok" and not missing_tables else "error"
    error = None
    if integrity != "ok":
        error = "integrity_check_failed"
    elif missing_tables:
        error = "required_tables_missing"

    result: dict[str, Any] = {
        "status": status,
        "error": error,
        "backup_path": str(selected_backup),
        "backup_size_bytes": backup_size,
        "restored_copy": str(restored_copy) if work_dir is not None else None,
        "integrity_check": integrity,
        "required_tables": required,
        "missing_tables": missing_tables,
        "table_count": len(tables),
        "tables": tables,
        "row_counts": row_counts,
    }
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run a non-destructive SQLite restore drill by copying a backup DB to a temp path "
            "and validating it there."
        )
    )
    parser.add_argument("--backup", type=Path, default=None, help="SQLite backup DB to drill. Defaults to latest match.")
    parser.add_argument(
        "--backup-glob",
        default=DEFAULT_BACKUP_GLOB,
        help=f"Glob used when --backup is omitted (default: {DEFAULT_BACKUP_GLOB}).",
    )
    parser.add_argument(
        "--required-table",
        action="append",
        dest="required_tables",
        help="Required table name. Repeatable. Default: papers.",
    )
    parser.add_argument(
        "--work-dir",
        type=Path,
        default=None,
        help="Optional directory to keep the restored copy for inspection. Default uses a temporary directory.",
    )
    args = parser.parse_args(argv)

    result = run_restore_drill(
        backup_path=args.backup,
        backup_glob=args.backup_glob,
        required_tables=args.required_tables,
        work_dir=args.work_dir,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result.get("status") == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
