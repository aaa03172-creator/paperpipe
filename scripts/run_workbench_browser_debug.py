from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class DebugFlow:
    flow_id: str
    title_grep: str
    description: str


FLOW_ORDER = ("cancel-run", "parser-fallback", "repair-stats")
FLOWS: dict[str, DebugFlow] = {
    "cancel-run": DebugFlow(
        flow_id="cancel-run",
        title_grep="workbench debug cancel run flow",
        description="Seed an active deep-read run, cancel it from /workbench, and keep browser debug artifacts.",
    ),
    "parser-fallback": DebugFlow(
        flow_id="parser-fallback",
        title_grep="workbench debug parser fallback flow",
        description="Run the parser fallback browser flow from /workbench with the fake worker lane enabled.",
    ),
    "repair-stats": DebugFlow(
        flow_id="repair-stats",
        title_grep="workbench debug repair stats flow",
        description="Repair missing saved checks from /workbench and keep terminal/browser debug artifacts.",
    ),
}


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def frontend_root() -> Path:
    return repo_root() / "frontend"


def artifacts_root() -> Path:
    return frontend_root() / "test-results" / "workbench-debug"


def artifacts_dir(flow: DebugFlow) -> Path:
    return artifacts_root() / flow.flow_id


def resolve_flow(flow_id: str) -> DebugFlow:
    try:
        return FLOWS[flow_id]
    except KeyError as exc:
        valid = ", ".join(FLOW_ORDER)
        raise ValueError(f"unknown flow '{flow_id}'. Expected one of: {valid}") from exc


def build_command(flow: DebugFlow, *, headed: bool, reporter: str) -> list[str]:
    command = [
        "npx",
        "playwright",
        "test",
        "-c",
        "playwright.workbench-debug.config.ts",
        "e2e/workbench-debug.spec.ts",
        "-g",
        flow.title_grep,
        "--reporter",
        reporter,
        "--output",
        str(artifacts_dir(flow)),
    ]
    if headed:
        command.append("--headed")
    return command


def build_env(*, flow: DebugFlow, reuse_existing_server: bool) -> dict[str, str]:
    env = os.environ.copy()
    env["PAPERPIPE_WORKBENCH_DEBUG_FLOW"] = flow.flow_id
    if reuse_existing_server:
        env["PLAYWRIGHT_REUSE_EXISTING_SERVER"] = "1"
    return env


def check_only_payload(*, flow: DebugFlow, command: list[str], env: dict[str, str]) -> dict[str, object]:
    payload = {
        "flow": flow.flow_id,
        "description": flow.description,
        "cwd": str(frontend_root()),
        "command": command,
        "env": {
            "PAPERPIPE_WORKBENCH_DEBUG_FLOW": env["PAPERPIPE_WORKBENCH_DEBUG_FLOW"],
            "PLAYWRIGHT_REUSE_EXISTING_SERVER": env.get("PLAYWRIGHT_REUSE_EXISTING_SERVER", "0"),
        },
        "artifacts_root": str(artifacts_root()),
        "artifacts_dir": str(artifacts_dir(flow)),
    }
    return payload


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a targeted dev-only Playwright workbench debug flow.")
    parser.add_argument(
        "--flow",
        default="cancel-run",
        choices=FLOW_ORDER,
        help="Workbench browser debug flow to run.",
    )
    parser.add_argument(
        "--headed",
        action="store_true",
        help="Run the debug flow in headed mode.",
    )
    parser.add_argument(
        "--reuse-existing-server",
        action="store_true",
        help="Reuse an already running frontend/backend pair when possible.",
    )
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Print the resolved command/environment as JSON without executing Playwright.",
    )
    parser.add_argument(
        "--list-flows",
        action="store_true",
        help="List supported flows and exit.",
    )
    parser.add_argument(
        "--reporter",
        default="line",
        help="Playwright reporter to use.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    if args.list_flows:
        for flow_id in FLOW_ORDER:
            flow = FLOWS[flow_id]
            print(f"{flow.flow_id}: {flow.description}")
        return 0

    flow = resolve_flow(args.flow)
    command = build_command(flow, headed=args.headed, reporter=args.reporter)
    env = build_env(flow=flow, reuse_existing_server=args.reuse_existing_server)

    if args.check_only:
        print(json.dumps(check_only_payload(flow=flow, command=command, env=env), indent=2))
        return 0

    print(f"Running workbench browser debug flow: {flow.flow_id}")
    print(f"  description: {flow.description}")
    print(f"  cwd: {frontend_root()}")
    print(f"  artifacts: {artifacts_dir(flow)}")
    print("  note: browser-debug-summary.json is always written; screenshot/trace are retained on failure.")

    completed = subprocess.run(
        command,
        cwd=frontend_root(),
        env=env,
        check=False,
    )
    if completed.returncode != 0:
        print(
            f"Playwright reported a failure. Inspect {artifacts_dir(flow)} for browser-debug-summary.json, screenshot, and trace artifacts.",
            file=sys.stderr,
        )
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
