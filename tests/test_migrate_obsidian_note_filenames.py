from __future__ import annotations

import json
import os
import subprocess
import sqlite3
import sys
from pathlib import Path


def _write_config(repo_root: Path, tmp_path: Path, vault: Path) -> Path:
    config_path = tmp_path / "config.yaml"
    config_text = (repo_root / "config.example.yaml").read_text(encoding="utf-8")
    config_text = config_text.replace('/path/to/Zotero/storage', (tmp_path / "zotero").as_posix())
    config_text = config_text.replace('/path/to/Obsidian/MyVault', vault.as_posix())
    config_text = config_text.replace('/path/to/PaperPipe_Exports/upload', (tmp_path / "uploads").as_posix())
    config_text = config_text.replace('/path/to/PaperPipe_Watch', (tmp_path / "watch").as_posix())
    config_path.write_text(config_text, encoding="utf-8")
    return config_path


def _write_legacy_note(vault: Path) -> Path:
    note = vault / "Inbox" / "PaperPipe" / "zoteroLegacyPaper.md"
    note.parent.mkdir(parents=True, exist_ok=True)
    note.write_text(
        """---
id: zotero:legacyPaper
aliases:
  - Legacy Paper Title
---

# Legacy Paper Title
""",
        encoding="utf-8",
    )
    return note


def test_migrate_obsidian_note_filenames_runs_as_cli_from_plain_python(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    vault = tmp_path / "vault"
    _write_legacy_note(vault)
    config_path = _write_config(repo_root, tmp_path, vault)

    completed = subprocess.run(
        [sys.executable, str(repo_root / "scripts" / "migrate_obsidian_note_filenames.py")],
        cwd=tmp_path,
        env={**os.environ, "PAPERPIPE_CONFIG_PATH": str(config_path)},
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout)
    assert payload["rename_candidates"] == 1
    assert payload["sample_candidates"][0]["paper_id"] == "zotero:legacyPaper"


def test_migrate_obsidian_note_filenames_help_mentions_backups(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]

    completed = subprocess.run(
        [sys.executable, str(repo_root / "scripts" / "migrate_obsidian_note_filenames.py"), "--help"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0
    assert "--confirm-vault-backup" in completed.stdout
    assert "--db-backup-path" in completed.stdout


def test_migrate_obsidian_note_filenames_apply_requires_vault_backup_ack(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    vault = tmp_path / "vault"
    old_note = _write_legacy_note(vault)
    config_path = _write_config(repo_root, tmp_path, vault)

    completed = subprocess.run(
        [sys.executable, str(repo_root / "scripts" / "migrate_obsidian_note_filenames.py"), "--apply"],
        cwd=tmp_path,
        env={**os.environ, "PAPERPIPE_CONFIG_PATH": str(config_path)},
        capture_output=True,
        text=True,
        check=False,
    )

    payload = json.loads(completed.stdout)
    assert completed.returncode == 2
    assert payload["error"] == "vault_backup_confirmation_required"
    assert old_note.exists()


def test_migrate_obsidian_note_filenames_apply_creates_db_backup_and_updates_db(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    vault = tmp_path / "vault"
    old_note = _write_legacy_note(vault)
    config_path = _write_config(repo_root, tmp_path, vault)
    db_path = tmp_path / "state.db"
    backup_path = tmp_path / "state.before.db"
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE papers (
            paper_id TEXT PRIMARY KEY,
            obsidian_path TEXT,
            updated_at TEXT
        )
        """
    )
    conn.execute(
        "INSERT INTO papers (paper_id, obsidian_path, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP)",
        ("zotero:legacyPaper", "Inbox/PaperPipe/zoteroLegacyPaper.md"),
    )
    conn.commit()
    conn.close()

    completed = subprocess.run(
        [
            sys.executable,
            str(repo_root / "scripts" / "migrate_obsidian_note_filenames.py"),
            "--apply",
            "--confirm-vault-backup",
            "--db-backup-path",
            str(backup_path),
        ],
        cwd=tmp_path,
        env={
            **os.environ,
            "PAPERPIPE_CONFIG_PATH": str(config_path),
            "PAPERPIPE_DB_PATH": str(db_path),
        },
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout)
    assert payload["renamed"] == 1
    assert payload["db_backup_path"] == str(backup_path)
    assert backup_path.exists()
    assert not old_note.exists()

    conn = sqlite3.connect(db_path)
    row = conn.execute("SELECT obsidian_path FROM papers WHERE paper_id = ?", ("zotero:legacyPaper",)).fetchone()
    conn.close()

    assert row is not None
    assert row[0] != "Inbox/PaperPipe/zoteroLegacyPaper.md"
    assert row[0].startswith("Inbox/PaperPipe/")
    assert (vault / row[0]).exists()
