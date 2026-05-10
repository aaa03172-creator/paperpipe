import os
import sqlite3
from pathlib import Path

from scripts.check_sqlite_restore_drill import run_restore_drill


def _write_db(path: Path, *, table_name: str = "papers") -> None:
    conn = sqlite3.connect(path)
    conn.execute(f'CREATE TABLE "{table_name}" (id TEXT PRIMARY KEY)')
    conn.execute(f'INSERT INTO "{table_name}" (id) VALUES (?)', ("one",))
    conn.commit()
    conn.close()


def _write_operational_db(path: Path) -> None:
    conn = sqlite3.connect(path)
    for table_name in ("papers", "jobs", "execution_runs", "job_events", "review_queue"):
        conn.execute(f'CREATE TABLE "{table_name}" (id TEXT PRIMARY KEY)')
        conn.execute(f'INSERT INTO "{table_name}" (id) VALUES (?)', ("one",))
    conn.commit()
    conn.close()


def _backup_db(source: Path, backup: Path) -> None:
    src = sqlite3.connect(source)
    dst = sqlite3.connect(backup)
    try:
        src.backup(dst)
    finally:
        src.close()
        dst.close()


def test_restore_drill_validates_backup_copy(tmp_path: Path) -> None:
    source = tmp_path / "state.db"
    backup = tmp_path / "state_backup.db"
    work_dir = tmp_path / "drill"
    _write_db(source)
    _backup_db(source, backup)

    result = run_restore_drill(backup_path=backup, required_tables=["papers"], work_dir=work_dir)

    assert result["status"] == "ok"
    assert result["integrity_check"] == "ok"
    assert result["missing_tables"] == []
    assert result["row_counts"] == {"papers": 1}
    assert Path(result["restored_copy"]).exists()
    assert result["backup_path"] == str(backup)


def test_restore_drill_default_tables_cover_operational_state(tmp_path: Path) -> None:
    source = tmp_path / "state.db"
    backup = tmp_path / "state_backup.db"
    _write_operational_db(source)
    _backup_db(source, backup)

    result = run_restore_drill(backup_path=backup, work_dir=tmp_path / "drill")

    assert result["status"] == "ok"
    assert result["missing_tables"] == []
    assert result["required_tables"] == ["papers", "jobs", "execution_runs", "job_events", "review_queue"]
    assert result["row_counts"] == {
        "papers": 1,
        "jobs": 1,
        "execution_runs": 1,
        "job_events": 1,
        "review_queue": 1,
    }


def test_restore_drill_default_tables_report_missing_operational_state(tmp_path: Path) -> None:
    source = tmp_path / "state.db"
    backup = tmp_path / "state_backup.db"
    _write_db(source)
    _backup_db(source, backup)

    result = run_restore_drill(backup_path=backup, work_dir=tmp_path / "drill")

    assert result["status"] == "error"
    assert result["error"] == "required_tables_missing"
    assert result["missing_tables"] == ["jobs", "execution_runs", "job_events", "review_queue"]


def test_restore_drill_reports_missing_required_table(tmp_path: Path) -> None:
    source = tmp_path / "state.db"
    backup = tmp_path / "state_backup.db"
    _write_db(source, table_name="other")
    _backup_db(source, backup)

    result = run_restore_drill(backup_path=backup, required_tables=["papers"], work_dir=tmp_path / "drill")

    assert result["status"] == "error"
    assert result["error"] == "required_tables_missing"
    assert result["missing_tables"] == ["papers"]


def test_restore_drill_reports_missing_backup(tmp_path: Path) -> None:
    result = run_restore_drill(backup_path=tmp_path / "missing.db")

    assert result["status"] == "error"
    assert result["error"] == "backup_not_found"


def test_restore_drill_selects_latest_backup_from_absolute_glob(tmp_path: Path) -> None:
    older_source = tmp_path / "older_state.db"
    newer_source = tmp_path / "newer_state.db"
    backups = tmp_path / "backups"
    backups.mkdir()
    older_backup = backups / "older.db"
    newer_backup = backups / "newer.db"
    _write_db(older_source)
    _write_db(newer_source)
    _backup_db(older_source, older_backup)
    _backup_db(newer_source, newer_backup)

    older_time = newer_backup.stat().st_mtime - 10
    os.utime(older_backup, (older_time, older_time))

    result = run_restore_drill(backup_glob=str(backups / "*.db"), required_tables=["papers"])

    assert result["status"] == "ok"
    assert result["backup_path"] == str(newer_backup)
