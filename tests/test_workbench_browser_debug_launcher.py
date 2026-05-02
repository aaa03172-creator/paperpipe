from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_workbench_browser_debug_check_only_defaults_to_cancel_run() -> None:
    script_path = Path("scripts/run_workbench_browser_debug.py").resolve()

    result = subprocess.run(
        [sys.executable, str(script_path), "--check-only"],
        cwd=Path.cwd(),
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["flow"] == "cancel-run"
    assert payload["env"]["PAPERPIPE_WORKBENCH_DEBUG_FLOW"] == "cancel-run"
    assert "playwright.workbench-debug.config.ts" in payload["command"]
    assert "workbench debug cancel run flow" in payload["command"]
    assert payload["artifacts_dir"].endswith("frontend/test-results/workbench-debug/cancel-run")
    assert "--output" in payload["command"]
    assert payload["artifacts_dir"] in payload["command"]


def test_workbench_browser_debug_check_only_enables_parser_flow_and_reuse() -> None:
    script_path = Path("scripts/run_workbench_browser_debug.py").resolve()

    result = subprocess.run(
        [
            sys.executable,
            str(script_path),
            "--flow",
            "parser-fallback",
            "--reuse-existing-server",
            "--check-only",
        ],
        cwd=Path.cwd(),
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["flow"] == "parser-fallback"
    assert payload["env"]["PAPERPIPE_WORKBENCH_DEBUG_FLOW"] == "parser-fallback"
    assert payload["env"]["PLAYWRIGHT_REUSE_EXISTING_SERVER"] == "1"
    assert "workbench debug parser fallback flow" in payload["command"]
    assert payload["artifacts_dir"].endswith("frontend/test-results/workbench-debug/parser-fallback")


def test_workbench_browser_debug_check_only_supports_repair_stats_flow() -> None:
    script_path = Path("scripts/run_workbench_browser_debug.py").resolve()

    result = subprocess.run(
        [
            sys.executable,
            str(script_path),
            "--flow",
            "repair-stats",
            "--check-only",
        ],
        cwd=Path.cwd(),
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["flow"] == "repair-stats"
    assert payload["env"]["PAPERPIPE_WORKBENCH_DEBUG_FLOW"] == "repair-stats"
    assert "workbench debug repair stats flow" in payload["command"]
    assert payload["artifacts_dir"].endswith("frontend/test-results/workbench-debug/repair-stats")
