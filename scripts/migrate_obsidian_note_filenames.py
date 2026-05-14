#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sqlite3
import sys
from dataclasses import dataclass
from datetime import datetime
from importlib.util import find_spec
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
VENV_PYTHON = ROOT / ".venv" / "bin" / "python"
if find_spec("yaml") is None and VENV_PYTHON.exists() and Path(sys.executable).resolve() != VENV_PYTHON.resolve():
    os.execv(str(VENV_PYTHON), [str(VENV_PYTHON), str(Path(__file__).resolve()), *sys.argv[1:]])

import yaml

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.config import load_config
from src.db_utils import get_db_connection, get_db_path
from src.exporter import _default_obsidian_stem_for_paper_id, _preferred_obsidian_stem


ZOTERO_NOTE_GLOB = "zotero*.md"
OLD_REL_PREFIX = "Inbox/PaperPipe/"


@dataclass
class RenameCandidate:
    paper_id: str
    old_path: Path
    new_path: Path
    stateful: bool
    frontmatter: dict[str, Any]
    body: str


def _parse_frontmatter(path: Path) -> tuple[dict[str, Any], str]:
    content = path.read_text(encoding="utf-8", errors="replace")
    if not content.startswith("---"):
        return {}, content
    lines = content.splitlines()
    end_index = None
    for idx in range(1, len(lines)):
        if lines[idx].strip() == "---":
            end_index = idx
            break
    if end_index is None:
        return {}, content
    try:
        frontmatter = yaml.safe_load("\n".join(lines[1:end_index])) or {}
    except Exception:
        frontmatter = {}
    if not isinstance(frontmatter, dict):
        frontmatter = {}
    body = "\n".join(lines[end_index + 1 :]).lstrip("\n")
    return frontmatter, body


def _compose_note(frontmatter: dict[str, Any], body: str) -> str:
    rendered_frontmatter = yaml.safe_dump(
        frontmatter,
        sort_keys=False,
        allow_unicode=True,
        default_flow_style=False,
    ).strip()
    cleaned_body = body.strip()
    if not rendered_frontmatter:
        return f"{cleaned_body}\n" if cleaned_body else ""
    if cleaned_body:
        return f"---\n{rendered_frontmatter}\n---\n\n{cleaned_body}\n"
    return f"---\n{rendered_frontmatter}\n---\n"


def _paper_state_exists(vault_path: Path, stem: str) -> bool:
    return (vault_path / ".pp" / stem / "state.json").exists()


def _clean_suffix(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]+", "", value.replace(":", "-"))[:24] or "paper"


def _build_target_path(
    *,
    vault_path: Path,
    paper_id: str,
    title: str,
    reserved_paths: set[Path],
) -> Path:
    root = vault_path / "Inbox" / "PaperPipe"
    root.mkdir(parents=True, exist_ok=True)

    preferred = root / f"{_preferred_obsidian_stem({'title': title, 'paper_id': paper_id})}.md"
    if preferred not in reserved_paths:
        return preferred

    fallback = root / f"{_default_obsidian_stem_for_paper_id(paper_id)}.md"
    if fallback not in reserved_paths:
        return fallback

    suffix = _clean_suffix(paper_id)
    return root / f"{_preferred_obsidian_stem({'title': title, 'paper_id': paper_id})} - {suffix}.md"


def _iter_candidates(vault_path: Path) -> list[RenameCandidate]:
    root = vault_path / "Inbox" / "PaperPipe"
    reserved_paths = {path for path in root.glob("*.md")}
    candidates: list[RenameCandidate] = []

    for note_path in sorted(root.glob(ZOTERO_NOTE_GLOB)):
        frontmatter, body = _parse_frontmatter(note_path)
        paper_id = str(frontmatter.get("id") or "").strip()
        if not paper_id.startswith("zotero:"):
            continue
        stateful = _paper_state_exists(vault_path, note_path.stem)
        if stateful:
            candidates.append(
                RenameCandidate(
                    paper_id=paper_id,
                    old_path=note_path,
                    new_path=note_path,
                    stateful=True,
                    frontmatter=frontmatter,
                    body=body,
                )
            )
            continue
        aliases = frontmatter.get("aliases")
        title = ""
        if isinstance(aliases, list) and aliases:
            title = str(aliases[0] or "").strip()
        elif aliases:
            title = str(aliases).strip()
        if not title:
            title = note_path.stem
        reserved_paths.discard(note_path)
        new_path = _build_target_path(
            vault_path=vault_path,
            paper_id=paper_id,
            title=title,
            reserved_paths=reserved_paths,
        )
        reserved_paths.add(new_path)
        candidates.append(
            RenameCandidate(
                paper_id=paper_id,
                old_path=note_path,
                new_path=new_path,
                stateful=False,
                frontmatter=frontmatter,
                body=body,
            )
        )
    return candidates


def _stateful_frontmatter(frontmatter: dict[str, Any], *, legacy_slug: str) -> dict[str, Any]:
    updated = dict(frontmatter)
    current_pp = updated.get("pp")
    pp = dict(current_pp) if isinstance(current_pp, dict) else {}
    if not str(pp.get("structured_path") or "").strip():
        pp["structured_path"] = f".pp/{legacy_slug}/state.json"
    updated["pp"] = pp
    return updated


def _replace_vault_links(vault_path: Path, rename_map: dict[str, str]) -> int:
    replacements = 0
    for path in vault_path.rglob("*.md"):
        if not path.is_file():
            continue
        original = path.read_text(encoding="utf-8", errors="replace")
        updated = original
        for old_rel, new_rel in rename_map.items():
            old_no_ext = old_rel[:-3] if old_rel.endswith(".md") else old_rel
            new_no_ext = new_rel[:-3] if new_rel.endswith(".md") else new_rel
            updated = updated.replace(old_rel, new_rel)
            updated = updated.replace(old_no_ext, new_no_ext)
        if updated != original:
            path.write_text(updated, encoding="utf-8")
            replacements += 1
    return replacements


def _update_index_csvs(vault_path: Path, rename_map: dict[str, str]) -> list[str]:
    changed: list[str] = []
    index_root = vault_path / "00_Index"
    if not index_root.exists():
        return changed
    for csv_path in sorted(index_root.glob("*.csv")):
        rows_changed = False
        with csv_path.open("r", encoding="utf-8", newline="") as fh:
            reader = csv.DictReader(fh)
            fieldnames = list(reader.fieldnames or [])
            rows = list(reader)
        if "Note_Path" not in fieldnames:
            continue
        for row in rows:
            note_path = str(row.get("Note_Path") or "").strip()
            if note_path in rename_map:
                row["Note_Path"] = rename_map[note_path]
                rows_changed = True
        if rows_changed:
            with csv_path.open("w", encoding="utf-8", newline="") as fh:
                writer = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
                writer.writeheader()
                writer.writerows(rows)
            changed.append(str(csv_path))
    return changed


def _update_db_obsidian_paths(rename_map_by_paper_id: dict[str, str]) -> int:
    conn = get_db_connection()
    try:
        cols = [row[1] for row in conn.execute("PRAGMA table_info(papers)").fetchall()]
        if "paper_id" not in cols or "obsidian_path" not in cols:
            return 0
        updated = 0
        for paper_id, new_relpath in rename_map_by_paper_id.items():
            cur = conn.execute(
                "UPDATE papers SET obsidian_path = ?, updated_at = CURRENT_TIMESTAMP WHERE paper_id = ?",
                (new_relpath, paper_id),
            )
            updated += cur.rowcount
        conn.commit()
        return updated
    finally:
        conn.close()


def _default_db_backup_path(db_path: Path) -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return db_path.parent / "backups" / f"{db_path.stem}_before_obsidian_note_filename_migrate_{stamp}{db_path.suffix}"


def _backup_db(db_path: Path, backup_path: Path) -> None:
    backup_path.parent.mkdir(parents=True, exist_ok=True)
    src = sqlite3.connect(db_path)
    dst = sqlite3.connect(backup_path)
    try:
        src.backup(dst)
    finally:
        src.close()
        dst.close()


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Rename legacy zotero-prefixed Obsidian paper notes to cleaner filenames "
            "(dry-run by default; --apply requires vault-backup confirmation)."
        )
    )
    parser.add_argument("--apply", action="store_true", help="Apply changes. Default is dry-run.")
    parser.add_argument(
        "--confirm-vault-backup",
        action="store_true",
        help=(
            "Required with --apply. Confirms the operator has a trusted Obsidian vault backup "
            "covering notes, links, indexes, and .pp state."
        ),
    )
    parser.add_argument(
        "--db-backup-path",
        type=Path,
        default=None,
        help="Optional SQLite backup path used before --apply. Auto-generated next to the DB when omitted.",
    )
    parser.add_argument(
        "--include-stateful",
        action="store_true",
        help="Also rename stateful notes while preserving legacy .pp structured_path references.",
    )
    args = parser.parse_args()

    config = load_config()
    vault_path = Path(config.paths.obsidian_vault).expanduser()
    candidates = _iter_candidates(vault_path)
    stateful = [item for item in candidates if item.stateful]
    if args.include_stateful:
        reserved_paths = {
            path
            for path in (vault_path / "Inbox" / "PaperPipe").glob("*.md")
            if path.is_file() and path not in {item.old_path for item in stateful}
        }
        retargeted_stateful: list[RenameCandidate] = []
        for item in stateful:
            aliases = item.frontmatter.get("aliases")
            title = ""
            if isinstance(aliases, list) and aliases:
                title = str(aliases[0] or "").strip()
            elif aliases:
                title = str(aliases).strip()
            if not title:
                title = item.old_path.stem
            new_path = _build_target_path(
                vault_path=vault_path,
                paper_id=item.paper_id,
                title=title,
                reserved_paths=reserved_paths,
            )
            reserved_paths.add(new_path)
            retargeted_stateful.append(
                RenameCandidate(
                    paper_id=item.paper_id,
                    old_path=item.old_path,
                    new_path=new_path,
                    stateful=True,
                    frontmatter=item.frontmatter,
                    body=item.body,
                )
            )
        stateful = retargeted_stateful
    stateless = [item for item in candidates if not item.stateful and item.old_path != item.new_path]
    stateful_renames = [item for item in stateful if item.old_path != item.new_path]
    stateful_skipped = [item for item in stateful if item.old_path == item.new_path]
    rename_targets = stateless + stateful_renames

    summary = {
        "vault_path": str(vault_path),
        "total_zotero_notes": len(candidates),
        "stateful_skipped": len(stateful_skipped),
        "rename_candidates": len(rename_targets),
        "stateless_rename_candidates": len(stateless),
        "stateful_rename_candidates": len(stateful_renames),
        "apply": args.apply,
        "include_stateful": args.include_stateful,
        "requires_vault_backup_confirmation": True,
        "vault_backup_confirmed": args.confirm_vault_backup,
        "db_backup_path": None,
        "sample_candidates": [
            {
                "paper_id": item.paper_id,
                "old": item.old_path.name,
                "new": item.new_path.name,
            }
            for item in rename_targets[:20]
        ],
    }

    if not args.apply:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0

    if not args.confirm_vault_backup:
        summary.update(
            {
                "error": "vault_backup_confirmation_required",
                "message": (
                    "--apply requires --confirm-vault-backup because this script rewrites vault notes, "
                    "vault links, index CSVs, and DB obsidian_path values."
                ),
            }
        )
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 2

    db_path = get_db_path()
    if not db_path.exists():
        summary.update(
            {
                "error": "db_not_found",
                "db_path": str(db_path),
            }
        )
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 1

    db_backup_path = args.db_backup_path.expanduser() if args.db_backup_path else _default_db_backup_path(db_path)
    _backup_db(db_path, db_backup_path)
    summary["db_backup_path"] = str(db_backup_path)

    rename_map: dict[str, str] = {}
    rename_map_by_paper_id: dict[str, str] = {}

    for item in rename_targets:
        frontmatter = item.frontmatter
        body = item.body
        if item.stateful:
            frontmatter = _stateful_frontmatter(frontmatter, legacy_slug=item.old_path.stem)
        item.new_path.parent.mkdir(parents=True, exist_ok=True)
        item.new_path.write_text(_compose_note(frontmatter, body), encoding="utf-8")
        item.old_path.unlink()
        old_rel = str(item.old_path.relative_to(vault_path)).replace("\\", "/")
        new_rel = str(item.new_path.relative_to(vault_path)).replace("\\", "/")
        rename_map[old_rel] = new_rel
        rename_map_by_paper_id[item.paper_id] = new_rel

    changed_markdown_files = _replace_vault_links(vault_path, rename_map)
    changed_csvs = _update_index_csvs(vault_path, rename_map)
    updated_db_rows = _update_db_obsidian_paths(rename_map_by_paper_id)

    summary.update(
        {
            "renamed": len(rename_targets),
            "changed_markdown_files": changed_markdown_files,
            "changed_csv_files": changed_csvs,
            "updated_db_rows": updated_db_rows,
        }
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
