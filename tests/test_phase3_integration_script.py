import subprocess
from types import SimpleNamespace
from pathlib import Path
import sqlite3

import pytest

import scripts.test_phase3_integration as phase3_script


class _FakeProc:
    def __init__(self, exited=False, timeout_on_wait=False):
        self._exited = exited
        self._timeout_on_wait = timeout_on_wait
        self.terminated = False
        self.killed = False

    def poll(self):
        return 0 if self._exited else None

    def terminate(self):
        self.terminated = True

    def wait(self, timeout=None):
        if self._timeout_on_wait:
            raise subprocess.TimeoutExpired(cmd="fake", timeout=timeout)
        return 0

    def kill(self):
        self.killed = True


def test_wait_for_health_returns_true_on_200(monkeypatch):
    calls = {"count": 0}

    def _mock_get(*_args, **_kwargs):
        calls["count"] += 1
        return SimpleNamespace(status_code=200)

    monkeypatch.setattr(phase3_script.requests, "get", _mock_get)

    assert phase3_script._wait_for_health("http://x", timeout_seconds=1, interval_seconds=0.0) is True
    assert calls["count"] >= 1


def test_wait_for_health_returns_false_on_repeated_errors(monkeypatch):
    monkeypatch.setattr(
        phase3_script.requests,
        "get",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(phase3_script.requests.RequestException("boom")),
    )

    assert phase3_script._wait_for_health("http://x", timeout_seconds=0, interval_seconds=0.0) is False


def test_terminate_process_noop_when_already_exited():
    proc = _FakeProc(exited=True)
    phase3_script._terminate_process(proc)
    assert proc.terminated is False
    assert proc.killed is False


def test_terminate_process_kills_on_timeout():
    proc = _FakeProc(exited=False, timeout_on_wait=True)
    phase3_script._terminate_process(proc)
    assert proc.terminated is True
    assert proc.killed is True


def test_wait_for_job_terminal_status_returns_completed(monkeypatch):
    responses = iter(
        [
            {"status": "queued", "progress": 0},
            {"status": "running", "progress": 50},
            {"status": "completed", "progress": 100},
        ]
    )

    def _mock_get(*_args, **_kwargs):
        return SimpleNamespace(json=lambda: next(responses))

    monkeypatch.setattr(phase3_script.requests, "get", _mock_get)
    monkeypatch.setattr(phase3_script.time, "sleep", lambda *_args, **_kwargs: None)

    result = phase3_script._wait_for_job_terminal_status(
        "http://x", "job-1", max_polls=5, interval_seconds=0.0
    )

    assert result["status"] == "completed"


def test_wait_for_job_terminal_status_raises_timeout(monkeypatch):
    def _mock_get(*_args, **_kwargs):
        return SimpleNamespace(json=lambda: {"status": "running", "progress": 10})

    monkeypatch.setattr(phase3_script.requests, "get", _mock_get)
    monkeypatch.setattr(phase3_script.time, "sleep", lambda *_args, **_kwargs: None)

    with pytest.raises(TimeoutError):
        phase3_script._wait_for_job_terminal_status(
            "http://x", "job-1", max_polls=2, interval_seconds=0.0
        )


def test_ensure_test_pdf_for_paper_creates_when_missing(tmp_path, monkeypatch):
    config = SimpleNamespace(paths=SimpleNamespace(library_dir=tmp_path))
    monkeypatch.setattr(phase3_script, "load_config", lambda: config)

    path, created = phase3_script._ensure_test_pdf_for_paper("paper_x")
    assert created is True
    assert path.exists()
    assert path.suffix == ".pdf"

    second_path, created_second = phase3_script._ensure_test_pdf_for_paper("paper_x")
    assert created_second is False
    assert second_path == path


def test_tail_log_handles_missing_file(tmp_path):
    missing = tmp_path / "nope.log"
    out = phase3_script._tail_log(str(missing))
    assert "missing log file" in out


def _connect_with_row_factory(db_path: Path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def test_cleanup_stale_jobs_for_paper_cancels_matching_jobs(tmp_path, monkeypatch):
    db_path = tmp_path / "state.db"
    conn = _connect_with_row_factory(db_path)
    conn.execute(
        """
        CREATE TABLE jobs (
            job_id TEXT PRIMARY KEY,
            paper_id TEXT,
            status TEXT,
            finished_at TEXT,
            error_message TEXT
        )
        """
    )
    conn.execute("INSERT INTO jobs (job_id, paper_id, status) VALUES ('j1', 'test_paper_001', 'running')")
    conn.execute("INSERT INTO jobs (job_id, paper_id, status) VALUES ('j2', 'test_paper_001', 'queued')")
    conn.commit()
    conn.close()

    monkeypatch.setattr(phase3_script, "get_db_connection", lambda: _connect_with_row_factory(db_path))

    cleaned = phase3_script._cleanup_stale_jobs_for_paper("test_paper_001")
    assert cleaned == 2

    conn = _connect_with_row_factory(db_path)
    rows = conn.execute("SELECT job_id, status FROM jobs ORDER BY job_id").fetchall()
    conn.close()
    assert [dict(r)["status"] for r in rows] == ["cancelled", "cancelled"]


def test_cleanup_stale_jobs_for_paper_raises_on_other_running(tmp_path, monkeypatch):
    db_path = tmp_path / "state.db"
    conn = _connect_with_row_factory(db_path)
    conn.execute(
        """
        CREATE TABLE jobs (
            job_id TEXT PRIMARY KEY,
            paper_id TEXT,
            status TEXT,
            finished_at TEXT,
            error_message TEXT
        )
        """
    )
    conn.execute("INSERT INTO jobs (job_id, paper_id, status) VALUES ('j1', 'other-paper', 'running')")
    conn.commit()
    conn.close()

    monkeypatch.setattr(phase3_script, "get_db_connection", lambda: _connect_with_row_factory(db_path))

    with pytest.raises(RuntimeError, match="other running jobs"):
        phase3_script._cleanup_stale_jobs_for_paper("test_paper_001")
