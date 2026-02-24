from pathlib import Path
from types import SimpleNamespace

from typer.testing import CliRunner

import src.cli as cli


class _FakeProc:
    def __init__(self, poll_values: list[int | None]):
        self._poll_values = list(poll_values)
        self._idx = 0

    def poll(self) -> int | None:
        if self._idx < len(self._poll_values):
            value = self._poll_values[self._idx]
            self._idx += 1
            return value
        return 0

    def terminate(self) -> None:
        return None

    def wait(self, timeout: int | None = None) -> int:
        return 0

    def kill(self) -> None:
        return None


def test_start_fails_when_port_is_in_use(monkeypatch, tmp_path: Path):
    runner = CliRunner()
    monkeypatch.setattr(cli, "load_config", lambda: SimpleNamespace())
    monkeypatch.setattr(cli, "bootstrap_database", lambda: tmp_path / "state.db")
    monkeypatch.setattr(cli, "_is_port_available", lambda _host, _port: False)

    result = runner.invoke(cli.app, ["start", "--no-open"])

    assert result.exit_code == 1
    assert "Port already in use" in result.output


def test_start_fails_when_healthcheck_times_out(monkeypatch, tmp_path: Path):
    runner = CliRunner()
    fake_proc = _FakeProc([None])
    terminated = {"called": False}

    monkeypatch.setattr(cli, "load_config", lambda: SimpleNamespace())
    monkeypatch.setattr(cli, "bootstrap_database", lambda: tmp_path / "state.db")
    monkeypatch.setattr(cli, "_is_port_available", lambda _host, _port: True)
    monkeypatch.setattr(cli.subprocess, "Popen", lambda _cmd: fake_proc)
    monkeypatch.setattr(cli, "_wait_for_health", lambda _base_url, _timeout: False)

    def _terminate(proc):
        assert proc is fake_proc
        terminated["called"] = True

    monkeypatch.setattr(cli, "_terminate_process", _terminate)

    result = runner.invoke(cli.app, ["start", "--no-open", "--health-timeout", "3"])

    assert result.exit_code == 1
    assert "Healthcheck timeout" in result.output
    assert terminated["called"] is True


def test_start_returns_zero_when_backend_exits_cleanly(monkeypatch, tmp_path: Path):
    runner = CliRunner()
    fake_proc = _FakeProc([None, 0])
    terminate_calls = {"count": 0}

    monkeypatch.setattr(cli, "load_config", lambda: SimpleNamespace())
    monkeypatch.setattr(cli, "bootstrap_database", lambda: tmp_path / "state.db")
    monkeypatch.setattr(cli, "_is_port_available", lambda _host, _port: True)
    monkeypatch.setattr(cli.subprocess, "Popen", lambda _cmd: fake_proc)
    monkeypatch.setattr(cli, "_wait_for_health", lambda _base_url, _timeout: True)
    monkeypatch.setattr(cli.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(
        cli,
        "_terminate_process",
        lambda _proc: terminate_calls.__setitem__("count", terminate_calls["count"] + 1),
    )

    result = runner.invoke(cli.app, ["start", "--no-open"])

    assert result.exit_code == 0
    assert "Backend:" in result.output
    assert terminate_calls["count"] == 1
