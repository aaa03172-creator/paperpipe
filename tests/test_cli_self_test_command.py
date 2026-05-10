from typer.testing import CliRunner

import src.cli as cli
from src.schemas.ops import RuntimeReadinessCheck, RuntimeReadinessResponse


def test_self_test_returns_zero_for_non_error(monkeypatch):
    runner = CliRunner()

    monkeypatch.setattr(
        cli,
        "collect_runtime_readiness",
        lambda: RuntimeReadinessResponse(
            status="degraded",
            checks=[RuntimeReadinessCheck(name="ui_bundle", status="warn", detail="built bundle missing")],
        ),
    )

    result = runner.invoke(cli.app, ["self-test"])

    assert result.exit_code == 0
    assert "Runtime self-test" in result.output
    assert "ui_bundle" in result.output


def test_self_test_returns_nonzero_for_error(monkeypatch):
    runner = CliRunner()

    monkeypatch.setattr(
        cli,
        "collect_runtime_readiness",
        lambda: RuntimeReadinessResponse(
            status="error",
            checks=[RuntimeReadinessCheck(name="config_file", status="error", detail="missing config")],
        ),
    )

    result = runner.invoke(cli.app, ["self-test"])

    assert result.exit_code == 1
    assert "config_file" in result.output


def test_self_test_json_output(monkeypatch):
    runner = CliRunner()

    monkeypatch.setattr(
        cli,
        "collect_runtime_readiness",
        lambda: RuntimeReadinessResponse(
            status="ok",
            checks=[RuntimeReadinessCheck(name="runtime_db", status="ok", detail="ok", path="/tmp/state.db")],
        ),
    )

    result = runner.invoke(cli.app, ["self-test", "--json"])

    assert result.exit_code == 0
    assert '"status": "ok"' in result.output
