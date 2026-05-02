#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]

DEFAULT_PROBES: list[tuple[str, str]] = [
    ("no-site", "select"),
    ("no-site", "subprocess"),
    ("site", "typer"),
    ("site", "fastapi"),
    ("site", "src.cli"),
    ("site", "backend.main"),
]


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _snapshot_dir(run_id: str) -> Path:
    return ROOT / "snapshots" / "python_import_health" / run_id


def _parse_probe(raw: str) -> tuple[str, str]:
    mode, sep, module_name = raw.partition(":")
    if not sep:
        raise argparse.ArgumentTypeError("probe must look like `site:module` or `no-site:module`")
    mode = mode.strip().lower()
    module_name = module_name.strip()
    if mode not in {"site", "no-site"}:
        raise argparse.ArgumentTypeError("probe mode must be `site` or `no-site`")
    if not module_name:
        raise argparse.ArgumentTypeError("probe module name is required")
    return mode, module_name


def _run_probe(
    *,
    python_bin: Path,
    mode: str,
    module_name: str,
    timeout_seconds: int,
) -> dict[str, Any]:
    command = [str(python_bin)]
    if mode == "no-site":
        command.append("-S")
    command.extend(["-c", f"import {module_name}; print('ok')"])

    started_at = time.perf_counter()
    try:
        completed = subprocess.run(
            command,
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        elapsed = time.perf_counter() - started_at
        return {
            "mode": mode,
            "module": module_name,
            "status": "timeout",
            "elapsed_seconds": round(elapsed, 3),
            "returncode": None,
            "stdout": (exc.stdout or "").strip(),
            "stderr_tail": (exc.stderr or "")[-1000:],
        }

    elapsed = time.perf_counter() - started_at
    status = "ok" if completed.returncode == 0 else "error"
    return {
        "mode": mode,
        "module": module_name,
        "status": status,
        "elapsed_seconds": round(elapsed, 3),
        "returncode": completed.returncode,
        "stdout": completed.stdout.strip(),
        "stderr_tail": completed.stderr[-1000:],
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Probe a target Python interpreter for import-health regressions."
    )
    parser.add_argument(
        "--python-bin",
        default=sys.executable,
        help="Interpreter to probe. Defaults to the current runner interpreter.",
    )
    parser.add_argument(
        "--probe",
        action="append",
        type=_parse_probe,
        help="Probe spec in the form `site:module` or `no-site:module`. Repeatable.",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=10,
        help="Per-probe timeout in seconds.",
    )
    parser.add_argument(
        "--run-id",
        default="python_import_health_manual",
        help="Snapshot run id under snapshots/python_import_health/.",
    )
    args = parser.parse_args()

    python_bin = Path(args.python_bin).expanduser().absolute()
    probes = args.probe or list(DEFAULT_PROBES)

    results = [
        _run_probe(
            python_bin=python_bin,
            mode=mode,
            module_name=module_name,
            timeout_seconds=args.timeout_seconds,
        )
        for mode, module_name in probes
    ]

    summary = {
        "run_id": args.run_id,
        "generated_at": _utc_now_iso(),
        "python_bin": str(python_bin),
        "timeout_seconds": args.timeout_seconds,
        "probe_count": len(results),
        "ok_count": sum(1 for item in results if item["status"] == "ok"),
        "error_count": sum(1 for item in results if item["status"] == "error"),
        "timeout_count": sum(1 for item in results if item["status"] == "timeout"),
        "results": results,
    }

    snapshot_dir = _snapshot_dir(args.run_id)
    _write_json(snapshot_dir / "summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
