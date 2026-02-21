from types import SimpleNamespace

from typer.testing import CliRunner

import src.cli as cli


def test_cli_read_updates_reading_status_via_db_utils(monkeypatch):
    runner = CliRunner()
    called = {}

    import src.services.cli_workflows as cli_workflows

    import src.obsidian as obsidian_module

    monkeypatch.setattr(obsidian_module, "set_reading_status", lambda *_: "10.1000/read")
    monkeypatch.setattr(cli_workflows, "load_config", lambda: SimpleNamespace())

    def _update_reading_status(identifier: str, status: str) -> bool:
        called["identifier"] = identifier
        called["status"] = status
        return True

    monkeypatch.setattr(cli_workflows, "update_reading_status", _update_reading_status)

    result = runner.invoke(cli.app, ["read", "10.1000/read"])
    assert result.exit_code == 0
    assert called["identifier"] == "10.1000/read"
    assert called["status"] == "Reading"


def test_cli_done_skips_db_update_when_note_lookup_fails(monkeypatch):
    runner = CliRunner()
    called = {"updated": False}

    import src.services.cli_workflows as cli_workflows

    import src.obsidian as obsidian_module

    monkeypatch.setattr(obsidian_module, "set_reading_status", lambda *_: None)
    monkeypatch.setattr(cli_workflows, "load_config", lambda: SimpleNamespace())

    def _update_reading_status(*_args, **_kwargs) -> bool:
        called["updated"] = True
        return True

    monkeypatch.setattr(cli_workflows, "update_reading_status", _update_reading_status)

    result = runner.invoke(cli.app, ["done", "missing"])
    assert result.exit_code == 0
    assert "Paper not found in Index" in result.output
    assert called["updated"] is False


def test_cli_deepread_exits_early_when_agents_disabled(monkeypatch):
    runner = CliRunner()
    import src.services.cli_workflows as cli_workflows

    monkeypatch.setattr(
        cli_workflows,
        "load_config",
        lambda: SimpleNamespace(agents=SimpleNamespace(enabled=False)),
    )

    result = runner.invoke(cli.app, ["deepread", "p1"])
    assert result.exit_code == 0
    assert "Agents are disabled" in result.output
