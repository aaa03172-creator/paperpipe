from __future__ import annotations

import subprocess
import tomllib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ALLOWED_REASONING_EFFORTS = {"none", "minimal", "low", "medium", "high", "xhigh"}
ALLOWED_SANDBOX_MODES = {"read-only", "workspace-write"}


def _tracked_agent_configs() -> list[Path]:
    completed = subprocess.run(
        ["git", "ls-files", ".codex/agents"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return [
        ROOT / line.strip()
        for line in completed.stdout.splitlines()
        if line.strip().endswith(".toml")
    ]


def test_tracked_codex_agent_configs_have_safe_development_contracts() -> None:
    paths = _tracked_agent_configs()

    assert paths, "expected at least one tracked .codex/agents/*.toml config"

    for path in paths:
        payload = tomllib.loads(path.read_text(encoding="utf-8"))
        instructions = str(payload.get("developer_instructions") or "")
        sandbox_mode = payload.get("sandbox_mode")

        assert payload.get("name"), f"{path} is missing name"
        assert payload.get("description"), f"{path} is missing description"
        assert payload.get("model"), f"{path} is missing model"
        assert payload.get("model_reasoning_effort") in ALLOWED_REASONING_EFFORTS
        assert sandbox_mode in ALLOWED_SANDBOX_MODES
        assert instructions.strip(), f"{path} is missing developer_instructions"

        if sandbox_mode == "read-only":
            assert "Do not edit code." in instructions


def test_eval_harness_builder_stays_on_eval_not_runtime_redesign() -> None:
    path = ROOT / ".codex/agents/eval_harness_builder.toml"
    payload = tomllib.loads(path.read_text(encoding="utf-8"))
    instructions = str(payload["developer_instructions"])

    assert payload["sandbox_mode"] == "workspace-write"
    assert "Prefer existing repository evaluation surfaces" in instructions
    assert "Do not redesign runtime architecture." in instructions
