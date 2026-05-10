from pathlib import Path

import yaml


def test_first_paper_smoke_wrapper_uses_resolved_python_and_expected_targets() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    content = (repo_root / "scripts" / "run_first_paper_smoke.sh").read_text(encoding="utf-8")

    assert 'RESOLVER_RUNNER="$(command -v python3 || command -v python)"' in content
    assert 'scripts/resolve_verification_python.py" --require-module pytest' in content
    assert "tests/test_readme_first_paper_smoke.py" in content
    assert "tests/test_cli_import_pdf.py" in content
    assert "tests/test_cli_watch_commands.py" in content
    assert "tests/test_paper_notes_api.py" in content
    assert '-k "first_paper or import_pdf or doctor or demo_first_paper"' in content


def test_first_paper_smoke_workflow_is_path_scoped_and_runs_wrapper() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    workflow_path = repo_root / ".github" / "workflows" / "first-paper-smoke.yml"
    workflow = yaml.safe_load(workflow_path.read_text(encoding="utf-8"))

    triggers = workflow[True]
    assert "workflow_dispatch" in triggers
    assert "pull_request" in triggers
    assert "src/cli.py" in triggers["pull_request"]["paths"]
    assert "scripts/run_first_paper_smoke.sh" in triggers["pull_request"]["paths"]
    assert "tests/test_readme_first_paper_smoke.py" in triggers["pull_request"]["paths"]

    steps = workflow["jobs"]["first-paper-smoke"]["steps"]
    run_commands = [step.get("run", "") for step in steps]
    assert "./scripts/run_first_paper_smoke.sh" in run_commands
