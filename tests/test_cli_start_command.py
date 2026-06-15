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


def _ready_runtime():
    return SimpleNamespace(
        checks=[
            SimpleNamespace(
                name="backend_entrypoint",
                status="ok",
                detail="backend entrypoint imports successfully",
            )
        ]
    )


def test_start_fails_when_port_is_in_use(monkeypatch, tmp_path: Path):
    runner = CliRunner()
    monkeypatch.setattr(cli, "load_config", lambda: SimpleNamespace())
    monkeypatch.setattr(cli, "bootstrap_database", lambda: tmp_path / "state.db")
    monkeypatch.setattr(cli, "_is_port_available", lambda _host, _port: False)
    monkeypatch.setattr(cli, "_wait_for_health", lambda _base_url, _timeout: False)
    monkeypatch.setattr(cli, "collect_runtime_readiness", _ready_runtime)

    result = runner.invoke(cli.app, ["start", "--no-open"])

    assert result.exit_code == 1
    assert "Port already in use" in result.output


def test_start_reuses_existing_healthy_backend(monkeypatch, tmp_path: Path):
    runner = CliRunner()
    opened: list[str] = []

    monkeypatch.setattr(cli, "load_config", lambda: SimpleNamespace())
    monkeypatch.setattr(cli, "bootstrap_database", lambda: tmp_path / "state.db")
    monkeypatch.setattr(cli, "_is_port_available", lambda _host, _port: False)
    monkeypatch.setattr(cli, "_wait_for_health", lambda _base_url, _timeout: True)
    monkeypatch.setattr(cli.webbrowser, "open", lambda url, new=0: opened.append(url))

    result = runner.invoke(cli.app, ["start", "--port", "8046"])

    assert result.exit_code == 0
    assert "already running" in result.output
    assert opened == ["http://127.0.0.1:8046/ui"]


def test_start_fails_when_healthcheck_times_out(monkeypatch, tmp_path: Path):
    runner = CliRunner()
    fake_proc = _FakeProc([None])
    terminated = {"called": False}

    monkeypatch.setattr(cli, "load_config", lambda: SimpleNamespace())
    monkeypatch.setattr(cli, "bootstrap_database", lambda: tmp_path / "state.db")
    monkeypatch.setattr(cli, "_is_port_available", lambda _host, _port: True)
    monkeypatch.setattr(cli, "collect_runtime_readiness", _ready_runtime)
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
    fake_backend = _FakeProc([None, 0])
    fake_worker = _FakeProc([None, None, None])
    terminate_calls = {"count": 0}
    popen_calls = {"count": 0}

    def _popen(_cmd):
        popen_calls["count"] += 1
        return fake_backend if popen_calls["count"] == 1 else fake_worker

    monkeypatch.setattr(cli, "load_config", lambda: SimpleNamespace())
    monkeypatch.setattr(cli, "bootstrap_database", lambda: tmp_path / "state.db")
    monkeypatch.setattr(cli, "_is_port_available", lambda _host, _port: True)
    monkeypatch.setattr(cli, "collect_runtime_readiness", _ready_runtime)
    monkeypatch.setattr(cli.subprocess, "Popen", _popen)
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
    assert "Worker: ✅ started" in result.output
    assert "/ui" in result.output
    assert terminate_calls["count"] == 2


def test_backend_launch_command_uses_frozen_self_exec(monkeypatch):
    monkeypatch.setattr(cli.sys, "frozen", True, raising=False)
    monkeypatch.setattr(cli.sys, "executable", "/tmp/lattice")

    cmd = cli._build_backend_launch_command("127.0.0.1", 8123)

    assert cmd == ["/tmp/lattice", "serve-backend", "--host", "127.0.0.1", "--port", "8123"]


def test_backend_launch_command_uses_uvicorn_in_dev(monkeypatch):
    monkeypatch.delattr(cli.sys, "frozen", raising=False)
    monkeypatch.setattr(cli.sys, "executable", "/usr/bin/python3")

    cmd = cli._build_backend_launch_command("127.0.0.1", 8123)

    assert cmd == [
        "/usr/bin/python3",
        "-m",
        "uvicorn",
        "backend.main:app",
        "--host",
        "127.0.0.1",
        "--port",
        "8123",
    ]


def test_worker_launch_command_uses_frozen_self_exec(monkeypatch):
    monkeypatch.setattr(cli.sys, "frozen", True, raising=False)
    monkeypatch.setattr(cli.sys, "executable", "/tmp/lattice")

    cmd = cli._build_worker_launch_command()

    assert cmd == ["/tmp/lattice", "serve-worker"]


def test_worker_launch_command_uses_module_in_dev(monkeypatch):
    monkeypatch.delattr(cli.sys, "frozen", raising=False)
    monkeypatch.setattr(cli.sys, "executable", "/usr/bin/python3")

    cmd = cli._build_worker_launch_command()

    assert cmd == [
        "/usr/bin/python3",
        "-m",
        "src.jobs.worker",
    ]


def test_frozen_app_bundle_defaults_to_start_without_args(monkeypatch):
    monkeypatch.setattr(cli.sys, "frozen", True, raising=False)
    monkeypatch.setattr(cli.sys, "platform", "darwin")

    argv = cli._argv_with_frozen_app_default_command(
        ["/Applications/Lattice.app/Contents/MacOS/Lattice"]
    )

    assert argv == [
        "/Applications/Lattice.app/Contents/MacOS/Lattice",
        "start",
        "--port",
        "8046",
    ]


def test_frozen_app_bundle_prefixes_start_for_option_args(monkeypatch):
    monkeypatch.setattr(cli.sys, "frozen", True, raising=False)
    monkeypatch.setattr(cli.sys, "platform", "darwin")

    argv = cli._argv_with_frozen_app_default_command(
        ["/Applications/Lattice.app/Contents/MacOS/Lattice", "--no-open", "--port", "8027"]
    )

    assert argv == [
        "/Applications/Lattice.app/Contents/MacOS/Lattice",
        "start",
        "--no-open",
        "--port",
        "8027",
    ]


def test_frozen_app_bundle_drops_macos_process_serial_number(monkeypatch):
    monkeypatch.setattr(cli.sys, "frozen", True, raising=False)
    monkeypatch.setattr(cli.sys, "platform", "darwin")

    argv = cli._argv_with_frozen_app_default_command(
        ["/Applications/Lattice.app/Contents/MacOS/Lattice", "-psn_0_123456"]
    )

    assert argv == [
        "/Applications/Lattice.app/Contents/MacOS/Lattice",
        "start",
        "--port",
        "8046",
    ]


def test_frozen_app_bundle_keeps_explicit_subcommands(monkeypatch):
    monkeypatch.setattr(cli.sys, "frozen", True, raising=False)
    monkeypatch.setattr(cli.sys, "platform", "darwin")

    argv = cli._argv_with_frozen_app_default_command(
        ["/Applications/Lattice.app/Contents/MacOS/Lattice", "self-test", "--json"]
    )

    assert argv == ["/Applications/Lattice.app/Contents/MacOS/Lattice", "self-test", "--json"]
