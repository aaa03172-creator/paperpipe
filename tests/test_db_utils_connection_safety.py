import pytest

import src.db_utils as db_utils


class _FakeConn:
    def __init__(self):
        self.committed = False
        self.closed = False

    def commit(self):
        self.committed = True

    def close(self):
        self.closed = True


def test_update_paper_status_closes_connection_on_error(monkeypatch):
    conn = _FakeConn()
    monkeypatch.setattr(db_utils, "get_db_connection", lambda: conn)

    def _raise(*_args, **_kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(db_utils, "update_paper_status_with_connection", _raise)

    with pytest.raises(RuntimeError, match="boom"):
        db_utils.update_paper_status("p1", "FAILED")

    assert conn.closed is True
    assert conn.committed is False


def test_get_papers_by_status_closes_connection_on_error(monkeypatch):
    conn = _FakeConn()
    monkeypatch.setattr(db_utils, "get_db_connection", lambda: conn)

    def _raise(*_args, **_kwargs):
        raise RuntimeError("query error")

    monkeypatch.setattr(db_utils, "get_papers_by_status_with_connection", _raise)

    with pytest.raises(RuntimeError, match="query error"):
        db_utils.get_papers_by_status(["NEW"], limit=1)

    assert conn.closed is True


def test_log_run_stat_closes_connection_on_error(monkeypatch):
    conn = _FakeConn()
    monkeypatch.setattr(db_utils, "get_db_connection", lambda: conn)

    def _raise(*_args, **_kwargs):
        raise RuntimeError("stats error")

    monkeypatch.setattr(db_utils, "log_run_stat_with_connection", _raise)

    with pytest.raises(RuntimeError, match="stats error"):
        db_utils.log_run_stat("profile", 10, False)

    assert conn.closed is True
    assert conn.committed is False
