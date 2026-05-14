from pathlib import Path

from typer.testing import CliRunner

import src.cli as cli


def test_readme_first_paper_path_matches_cli_surface():
    readme = (Path(__file__).resolve().parents[1] / "README.md").read_text(encoding="utf-8")

    assert "## First Paper in 5 Minutes" in readme
    assert "http://127.0.0.1:8000/ui/papers#import-pdf" in readme
    assert "paperpipe import-pdf path/to/paper.pdf" in readme
    assert "paperpipe demo-first-paper" in readme
    assert "paperpipe doctor" in readme
    assert "paperpipe doctor --fix" in readme

    runner = CliRunner()
    import_help = runner.invoke(cli.app, ["import-pdf", "--help"])
    demo_help = runner.invoke(cli.app, ["demo-first-paper", "--help"])
    doctor_help = runner.invoke(cli.app, ["doctor", "--help"])

    assert import_help.exit_code == 0
    assert "Path to a local PDF file" in import_help.output
    assert demo_help.exit_code == 0
    assert "bundled sample PDF" in demo_help.output
    assert doctor_help.exit_code == 0
    assert "Check environment, config, and dependencies" in doctor_help.output
    assert "--fix" in doctor_help.output
