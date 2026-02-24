from types import SimpleNamespace

from typer.testing import CliRunner

import src.cli as cli


def test_cli_test_unpaywall_reports_found_link(monkeypatch):
    runner = CliRunner()

    monkeypatch.setattr(
        cli,
        "load_config",
        lambda: SimpleNamespace(system=SimpleNamespace(unpaywall_email="test@example.com")),
    )

    import src.downloader as downloader

    monkeypatch.setattr(downloader, "_fetch_oa_link", lambda _doi, _email: "https://example.org/found.pdf")

    result = runner.invoke(cli.app, ["test-unpaywall", "--doi", "10.1000/test-doi"])

    assert result.exit_code == 0
    assert "Found OA Link" in result.output
    assert "https://example.org/found.pdf" in result.output


def test_cli_test_unpaywall_reports_missing_link(monkeypatch):
    runner = CliRunner()

    monkeypatch.setattr(
        cli,
        "load_config",
        lambda: SimpleNamespace(system=SimpleNamespace(unpaywall_email="test@example.com")),
    )

    import src.downloader as downloader

    monkeypatch.setattr(downloader, "_fetch_oa_link", lambda _doi, _email: None)

    result = runner.invoke(cli.app, ["test-unpaywall", "--doi", "10.1000/test-doi"])

    assert result.exit_code == 0
    assert "No OA Link found" in result.output
