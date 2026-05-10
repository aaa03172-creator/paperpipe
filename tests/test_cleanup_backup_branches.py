from __future__ import annotations

from datetime import datetime, timedelta, timezone

from scripts import cleanup_backup_branches as script


def _backup(name: str, days_ago: int) -> script.BackupBranch:
    now = datetime.now(timezone.utc)
    return script.BackupBranch(name=name, commit_date=now - timedelta(days=days_ago))


def test_select_expired_branches_applies_retention_and_exclusions():
    now = datetime(2026, 2, 24, 0, 0, 0, tzinfo=timezone.utc)
    branches = [
        script.BackupBranch(
            name="master_local_backup_old",
            commit_date=now - timedelta(days=20),
        ),
        script.BackupBranch(
            name="master_local_backup_recent",
            commit_date=now - timedelta(days=2),
        ),
        script.BackupBranch(
            name="master_local_backup_current",
            commit_date=now - timedelta(days=30),
        ),
    ]

    expired = script.select_expired_branches(
        branches,
        retention_days=14,
        now=now,
        exclude_names={"master_local_backup_current"},
    )

    assert [b.name for b in expired] == ["master_local_backup_old"]


def test_main_dry_run_does_not_delete(monkeypatch, capsys):
    monkeypatch.setattr(script, "_run_git", lambda _args: "master")
    monkeypatch.setattr(
        script,
        "list_backup_branches",
        lambda _prefix: [
            _backup("master_local_backup_old", 40),
            _backup("master_local_backup_recent", 1),
        ],
    )

    deleted: list[list[str]] = []
    monkeypatch.setattr(script, "delete_branches", lambda names: deleted.append(list(names)))
    monkeypatch.setattr(
        "sys.argv",
        ["cleanup_backup_branches.py", "--retention-days", "14"],
    )

    rc = script.main()
    out = capsys.readouterr().out

    assert rc == 0
    assert deleted == []
    assert "[BACKUP-CLEANUP] dry-run only (no changes applied)" in out
    assert "expired_candidates=1" in out


def test_main_apply_respects_max_delete(monkeypatch, capsys):
    monkeypatch.setattr(script, "_run_git", lambda _args: "master_local_backup_current")
    monkeypatch.setattr(
        script,
        "list_backup_branches",
        lambda _prefix: [
            _backup("master_local_backup_current", 90),
            _backup("master_local_backup_oldest", 60),
            _backup("master_local_backup_old", 30),
        ],
    )

    deleted: list[list[str]] = []
    monkeypatch.setattr(script, "delete_branches", lambda names: deleted.append(list(names)))
    monkeypatch.setattr(
        "sys.argv",
        [
            "cleanup_backup_branches.py",
            "--retention-days",
            "14",
            "--max-delete",
            "1",
            "--apply",
        ],
    )

    rc = script.main()
    out = capsys.readouterr().out

    assert rc == 0
    assert deleted == [["master_local_backup_oldest"]]
    assert "deleted=1" in out

