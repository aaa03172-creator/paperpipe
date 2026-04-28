import json
import sqlite3
from pathlib import Path

from scripts.migrate_legacy import run_migration


def _init_db(path: Path) -> None:
    conn = sqlite3.connect(path)
    conn.execute(
        """
        CREATE TABLE papers (
            paper_id TEXT PRIMARY KEY,
            title TEXT,
            status TEXT,
            confidence REAL,
            gate_decision TEXT,
            feedback_json TEXT,
            created_at TEXT,
            updated_at TEXT
        )
        """
    )
    conn.execute(
        """
        INSERT INTO papers (
            paper_id, title, status, confidence, gate_decision, feedback_json, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """,
        ("existing", "Already Imported", "INDEXED", 0.9, "APPROVED", "{}",),
    )
    conn.commit()
    conn.close()


def _write_fixture_files(tmp_path: Path) -> tuple[Path, Path]:
    feedback_path = tmp_path / "feedback.jsonl"
    zotero_path = tmp_path / "zotero_export.json"
    feedback_path.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "paper_id": "new-paper",
                        "user_correction": json.dumps(
                            {"claims": [{"confidence": 0.9}, {"confidence": 0.7}]}
                        ),
                    }
                ),
                json.dumps({"paper_id": "existing", "user_correction": "{}"}),
                "{bad json",
                json.dumps({"user_correction": "{}"}),
            ]
        ),
        encoding="utf-8",
    )
    zotero_path.write_text(
        json.dumps({"items": [{"citationKey": "new-paper", "title": "Imported Title"}]}),
        encoding="utf-8",
    )
    return feedback_path, zotero_path


def test_legacy_migration_dry_run_does_not_insert(tmp_path: Path) -> None:
    db_path = tmp_path / "state.db"
    _init_db(db_path)
    feedback_path, zotero_path = _write_fixture_files(tmp_path)

    summary = run_migration(
        db_path=db_path,
        feedback_path=feedback_path,
        zotero_path=zotero_path,
        apply=False,
    )

    conn = sqlite3.connect(db_path)
    count = conn.execute("SELECT COUNT(*) FROM papers").fetchone()[0]
    conn.close()

    assert summary["dry_run"] is True
    assert summary["candidate_count"] == 1
    assert summary["skipped_existing"] == 1
    assert summary["malformed_lines"] == 1
    assert summary["missing_paper_id"] == 1
    assert summary["inserted_count"] == 0
    assert count == 1


def test_legacy_migration_apply_backs_up_and_inserts(tmp_path: Path) -> None:
    db_path = tmp_path / "state.db"
    backup_path = tmp_path / "backup.db"
    _init_db(db_path)
    feedback_path, zotero_path = _write_fixture_files(tmp_path)

    summary = run_migration(
        db_path=db_path,
        feedback_path=feedback_path,
        zotero_path=zotero_path,
        apply=True,
        backup_path=backup_path,
    )

    conn = sqlite3.connect(db_path)
    row = conn.execute(
        "SELECT title, status, confidence, gate_decision, feedback_json FROM papers WHERE paper_id = ?",
        ("new-paper",),
    ).fetchone()
    conn.close()

    assert summary["dry_run"] is False
    assert summary["candidate_count"] == 1
    assert summary["inserted_count"] == 1
    assert summary["backup_path"] == str(backup_path)
    assert backup_path.exists()
    assert row[:4] == ("Imported Title", "INDEXED", 0.8, "PENDING_REVIEW")
    assert json.loads(row[4])["paper_id"] == "new-paper"
