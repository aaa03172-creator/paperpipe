#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Iterable, Sequence


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TIMEOUT_SECONDS = 5
BROKEN_FRAMEWORK_PYTHON = "/Library/Frameworks/Python.framework/Versions/3.13/bin/python3.13"


def _normalize_candidates(raw_candidates: Iterable[str]) -> list[Path]:
    seen: set[str] = set()
    candidates: list[Path] = []
    for raw in raw_candidates:
        if not raw:
            continue
        resolved = raw if "/" in raw else shutil.which(raw)
        if not resolved:
            continue
        path = Path(resolved).expanduser().absolute()
        if not path.exists():
            continue
        key = str(path)
        if key in seen:
            continue
        seen.add(key)
        candidates.append(path)
    return candidates


def default_python_candidates(
    *,
    root: Path = ROOT,
    preferred_system_candidates: Sequence[str] | None = None,
) -> list[Path]:
    env_override = os.environ.get("PAPERPIPE_VERIFICATION_PYTHON", "").strip()
    system_candidates = list(
        preferred_system_candidates
        or [
            "/opt/homebrew/bin/python3.14",
            "python3.14",
            "python3",
            BROKEN_FRAMEWORK_PYTHON,
            "python",
        ]
    )
    raw_candidates = [
        env_override,
        str(root / ".venv314" / "bin" / "python"),
        str(root / ".venv" / "bin" / "python"),
        *system_candidates,
    ]
    return _normalize_candidates(raw_candidates)


def _run_probe(
    *,
    python_bin: Path,
    module_name: str,
    no_site: bool,
    timeout_seconds: int,
) -> dict[str, Any]:
    command = [str(python_bin)]
    if no_site:
        command.append("-S")
    command.extend(["-c", f"import {module_name}; print('ok')"])

    try:
        completed = subprocess.run(
            command,
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return {
            "module": module_name,
            "mode": "no-site" if no_site else "site",
            "status": "timeout",
            "returncode": None,
        }
    except FileNotFoundError:
        return {
            "module": module_name,
            "mode": "no-site" if no_site else "site",
            "status": "error",
            "returncode": None,
        }

    return {
        "module": module_name,
        "mode": "no-site" if no_site else "site",
        "status": "ok" if completed.returncode == 0 else "error",
        "returncode": completed.returncode,
    }


def probe_candidate(
    *,
    python_bin: Path,
    required_modules: Sequence[str],
    timeout_seconds: int,
) -> dict[str, Any]:
    probes = [
        _run_probe(
            python_bin=python_bin,
            module_name="select",
            no_site=True,
            timeout_seconds=timeout_seconds,
        ),
        _run_probe(
            python_bin=python_bin,
            module_name="subprocess",
            no_site=True,
            timeout_seconds=timeout_seconds,
        ),
    ]
    probes.extend(
        _run_probe(
            python_bin=python_bin,
            module_name=module_name,
            no_site=False,
            timeout_seconds=timeout_seconds,
        )
        for module_name in required_modules
    )

    if any(item["status"] == "timeout" for item in probes):
        status = "timeout"
    elif any(item["status"] == "error" for item in probes):
        status = "error"
    else:
        status = "ok"

    return {
        "python_bin": str(python_bin),
        "status": status,
        "probes": probes,
    }


def choose_python(
    *,
    candidates: Sequence[Path] | None = None,
    required_modules: Sequence[str] | None = None,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
) -> tuple[Path | None, list[dict[str, Any]]]:
    probe_results: list[dict[str, Any]] = []
    for candidate in candidates or default_python_candidates():
        result = probe_candidate(
            python_bin=candidate,
            required_modules=required_modules or (),
            timeout_seconds=timeout_seconds,
        )
        probe_results.append(result)
        if result["status"] == "ok":
            return candidate, probe_results
    return None, probe_results


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Resolve a healthy Python interpreter for local verification scripts."
    )
    parser.add_argument(
        "--require-module",
        action="append",
        default=[],
        help="Additional import that must succeed on the chosen interpreter. Repeatable.",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=DEFAULT_TIMEOUT_SECONDS,
        help="Per-probe timeout in seconds.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit a JSON summary instead of the selected interpreter path.",
    )
    args = parser.parse_args()

    chosen, probe_results = choose_python(
        required_modules=args.require_module,
        timeout_seconds=args.timeout_seconds,
    )
    payload = {
        "selected_python": str(chosen) if chosen else None,
        "required_modules": list(args.require_module),
        "timeout_seconds": args.timeout_seconds,
        "probe_results": probe_results,
    }
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        raise SystemExit(0 if chosen else 1)

    if chosen is None:
        print(
            "No healthy verification Python found. "
            "Run `python3 scripts/bootstrap_verification_env.py --run-id local_verification_bootstrap` "
            "or set PAPERPIPE_VERIFICATION_PYTHON.",
            file=sys.stderr,
        )
        raise SystemExit(1)

    print(str(chosen))


if __name__ == "__main__":
    main()
