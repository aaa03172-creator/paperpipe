#!/usr/bin/env python3
"""Read-only inventory for DOI identity cleanup planning."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.services.identity import normalize_doi
from src.services.runtime_paths import state_db_path


SCHEMA_VERSION = "papers_doi_identity_audit.v1"


def _normalized_doi_or_none(value: Any) -> str | None:
    normalized = normalize_doi(str(value or ""))
    if normalized.startswith("10.") and "/" in normalized:
        return normalized
    return None


def _table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return {str(row[1]) for row in rows}


def audit_papers_doi_identity(conn: sqlite3.Connection) -> dict[str, Any]:
    columns = _table_columns(conn, "papers")
    if not columns:
        return {
            "schema_version": SCHEMA_VERSION,
            "table_present": False,
            "rows_with_doi_count": 0,
            "duplicate_group_count": 0,
            "duplicate_groups": [],
            "non_doi_value_count": 0,
            "non_doi_values": [],
            "unique_constraint_ready": False,
            "blockers": ["papers_table_missing"],
        }

    if "doi" not in columns:
        return {
            "schema_version": SCHEMA_VERSION,
            "table_present": True,
            "rows_with_doi_count": 0,
            "duplicate_group_count": 0,
            "duplicate_groups": [],
            "non_doi_value_count": 0,
            "non_doi_values": [],
            "unique_constraint_ready": False,
            "blockers": ["papers_doi_column_missing"],
        }

    select_columns = ["rowid", "doi"]
    for optional_column in ("paper_id", "title", "source", "status", "pdf_path", "created_at", "updated_at"):
        if optional_column in columns:
            select_columns.append(optional_column)

    rows = conn.execute(
        f"""
        SELECT {', '.join(select_columns)}
        FROM papers
        WHERE doi IS NOT NULL AND TRIM(doi) <> ''
        ORDER BY rowid
        """
    ).fetchall()

    groups: dict[str, list[dict[str, Any]]] = {}
    non_doi_values: list[dict[str, Any]] = []
    for row in rows:
        payload = {column: row[column] for column in select_columns}
        normalized_doi = _normalized_doi_or_none(payload.get("doi"))
        if not normalized_doi:
            non_doi_values.append(payload)
            continue
        payload["normalized_doi"] = normalized_doi
        groups.setdefault(normalized_doi, []).append(payload)

    duplicate_groups = []
    for normalized_doi, group_rows in sorted(groups.items()):
        paper_ids = sorted({str(row.get("paper_id") or "") for row in group_rows if row.get("paper_id")})
        if len(group_rows) > 1 and (len(paper_ids) > 1 or not paper_ids):
            duplicate_groups.append(
                {
                    "normalized_doi": normalized_doi,
                    "row_count": len(group_rows),
                    "paper_ids": paper_ids,
                    "rows": sorted(group_rows, key=lambda item: str(item.get("paper_id") or item.get("rowid") or "")),
                }
            )

    blockers: list[str] = []
    if duplicate_groups:
        blockers.append("duplicate_normalized_doi")
    if non_doi_values:
        blockers.append("non_doi_values_in_doi_column")

    return {
        "schema_version": SCHEMA_VERSION,
        "table_present": True,
        "rows_with_doi_count": len(rows),
        "duplicate_group_count": len(duplicate_groups),
        "duplicate_groups": duplicate_groups,
        "non_doi_value_count": len(non_doi_values),
        "non_doi_values": non_doi_values,
        "unique_constraint_ready": not blockers,
        "blockers": blockers,
    }


def _connect_readonly(db_path: Path) -> sqlite3.Connection:
    if not db_path.exists():
        raise FileNotFoundError(f"Database does not exist: {db_path}")
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=state_db_path(), help="SQLite DB path. Defaults to runtime state DB.")
    args = parser.parse_args(argv)

    conn = _connect_readonly(args.db.expanduser().resolve())
    try:
        payload = audit_papers_doi_identity(conn)
    finally:
        conn.close()

    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
