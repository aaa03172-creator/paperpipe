from __future__ import annotations

import sqlite3
from pathlib import Path

import src.db_utils as db_utils


class _TrackingCursor:
    def __init__(self, cursor: sqlite3.Cursor, statements: list[str]) -> None:
        self._cursor = cursor
        self._statements = statements

    def execute(self, sql: str, *args, **kwargs):
        self._statements.append(sql)
        return self._cursor.execute(sql, *args, **kwargs)

    def executemany(self, sql: str, *args, **kwargs):
        self._statements.append(sql)
        return self._cursor.executemany(sql, *args, **kwargs)

    def __getattr__(self, name: str):
        return getattr(self._cursor, name)


class _TrackingConnection:
    def __init__(self, conn: sqlite3.Connection, statements: list[str]) -> None:
        object.__setattr__(self, "_conn", conn)
        object.__setattr__(self, "_statements", statements)

    def cursor(self) -> _TrackingCursor:
        return _TrackingCursor(self._conn.cursor(), self._statements)

    def __getattr__(self, name: str):
        return getattr(self._conn, name)

    def __setattr__(self, name: str, value) -> None:
        setattr(self._conn, name, value)


def test_init_db_applies_runtime_sqlite_pragmas(tmp_path: Path, monkeypatch) -> None:
    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    statements: list[str] = []
    original_connect = sqlite3.connect

    def tracked_connect(*args, **kwargs):
        return _TrackingConnection(original_connect(*args, **kwargs), statements)

    monkeypatch.setattr(db_utils.sqlite3, "connect", tracked_connect)
    try:
        db_utils.init_db()
    finally:
        db_utils.DB_PATH = original_db_path

    assert "PRAGMA journal_mode=WAL" in statements
    assert "PRAGMA synchronous=NORMAL" in statements
    assert "PRAGMA foreign_keys=ON" in statements
