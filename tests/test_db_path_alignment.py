from pathlib import Path
import sqlite3

import src.db as legacy_db
import src.db_utils as db_utils


def test_db_paths_are_aligned():
    assert Path(legacy_db._resolved_db_path()) == db_utils.get_db_path()


def test_db_utils_connections_use_extended_timeout(monkeypatch, tmp_path):
    captured = {}

    def fake_connect(path, **kwargs):
        captured["path"] = path
        captured["kwargs"] = kwargs
        captured["statements"] = []

        class _Connection:
            row_factory = None

            def execute(self, statement, *_args, **_kwargs):
                captured["statements"].append(statement)
                return None

        return _Connection()

    monkeypatch.setenv("PAPERPIPE_DB_PATH", str(tmp_path / "state.db"))
    monkeypatch.setattr(db_utils.sqlite3, "connect", fake_connect)

    conn = db_utils.get_db_connection()

    assert conn is not None
    assert captured["kwargs"]["timeout"] == db_utils.SQLITE_TIMEOUT_SECONDS
    assert f"PRAGMA busy_timeout={db_utils.SQLITE_BUSY_TIMEOUT_MS}" in captured["statements"]


def test_sqlite_lock_retry_retries_busy_errors(monkeypatch, caplog):
    attempts = {"count": 0}
    sleeps = []

    def flaky_operation():
        attempts["count"] += 1
        if attempts["count"] < 3:
            raise sqlite3.OperationalError("database is locked")
        return "ok"

    monkeypatch.setattr(db_utils.time, "sleep", lambda delay: sleeps.append(delay))

    result = db_utils._with_sqlite_lock_retry(flaky_operation, operation_name="test op")

    assert result == "ok"
    assert attempts["count"] == 3
    assert sleeps == [
        db_utils.SQLITE_LOCK_RETRY_BASE_SECONDS,
        db_utils.SQLITE_LOCK_RETRY_BASE_SECONDS * 2,
    ]
    assert "SQLite lock during test op" in caplog.text


def test_sqlite_lock_retry_does_not_retry_unrelated_operational_errors():
    attempts = {"count": 0}

    def broken_operation():
        attempts["count"] += 1
        raise sqlite3.OperationalError("no such table: papers")

    try:
        db_utils._with_sqlite_lock_retry(broken_operation, operation_name="test op")
    except sqlite3.OperationalError as exc:
        assert "no such table" in str(exc)
    else:
        raise AssertionError("Expected unrelated OperationalError to be re-raised")

    assert attempts["count"] == 1
