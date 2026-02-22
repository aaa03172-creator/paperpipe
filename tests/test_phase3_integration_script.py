import subprocess
from types import SimpleNamespace

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
