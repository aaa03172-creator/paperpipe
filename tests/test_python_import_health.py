from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_python_import_health_script_supports_custom_probes(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    run_id = "python_import_health_test_custom"

    completed = subprocess.run(
        [
            sys.executable,
            str(repo_root / "scripts" / "check_python_import_health.py"),
            "--python-bin",
            sys.executable,
            "--probe",
            "site:json",
            "--probe",
            "no-site:math",
            "--timeout-seconds",
            "5",
            "--run-id",
            run_id,
        ],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr

    payload = json.loads(completed.stdout)
    assert payload["ok_count"] == 2
    assert payload["error_count"] == 0
    assert payload["timeout_count"] == 0

    summary_path = repo_root / "snapshots" / "python_import_health" / run_id / "summary.json"
    assert summary_path.exists()

    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert [item["module"] for item in summary["results"]] == ["json", "math"]
    assert [item["mode"] for item in summary["results"]] == ["site", "no-site"]


def test_python_import_health_script_default_probes_complete() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    run_id = "python_import_health_test_defaults"

    completed = subprocess.run(
        [
            sys.executable,
            str(repo_root / "scripts" / "check_python_import_health.py"),
            "--python-bin",
            sys.executable,
            "--timeout-seconds",
            "10",
            "--run-id",
            run_id,
        ],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr

    payload = json.loads(completed.stdout)
    assert payload["probe_count"] == 6
    assert payload["ok_count"] == 6
    assert payload["error_count"] == 0
    assert payload["timeout_count"] == 0
    assert {item["module"] for item in payload["results"]} >= {"src.cli", "backend.main"}
