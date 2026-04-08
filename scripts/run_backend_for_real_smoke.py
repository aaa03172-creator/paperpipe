from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from check_frontend_real_smoke_env import run_preflight


def _validate_override_path(name: str, *, expected: str) -> str | None:
    raw = os.getenv(name)
    if not raw:
        return None
    path = Path(raw).expanduser()
    if expected == "dir" and not path.is_dir():
        return f"{name} not found: {path}"
    if expected == "file" and not path.is_file():
        return f"{name} not found: {path}"
    return None


def _require_candidates() -> bool:
    return os.getenv("PAPERPIPE_REAL_SMOKE_REQUIRE_CANDIDATES", "0") == "1"


def _build_uvicorn_command(port: str) -> list[str]:
    return [
        sys.executable,
        "-m",
        "uvicorn",
        "backend.main:app",
        "--host",
        "127.0.0.1",
        "--port",
        port,
    ]


def _collect_override_errors() -> list[str]:
    errors: list[str] = []
    for name, expected in (
        ("PAPERPIPE_STORAGE_DIR", "dir"),
        ("PAPERPIPE_DB_PATH", "file"),
        ("PAPERPIPE_ARTIFACTS_DIR", "dir"),
    ):
        message = _validate_override_path(name, expected=expected)
        if message:
            errors.append(message)
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Launch backend for frontend real-smoke Playwright")
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Run preflight only and exit without starting uvicorn.",
    )
    args = parser.parse_args()

    backend_port = str(os.getenv("E2E_BACKEND_PORT", "8000"))
    config_path = Path(os.getenv("PAPERPIPE_CONFIG_PATH", "config.yaml")).expanduser()

    override_errors = _collect_override_errors()
    if override_errors:
        for message in override_errors:
            print(message, file=sys.stderr)
        return 1

    code, summary = run_preflight(require_candidates=_require_candidates())
    if code != 0:
        print(json.dumps(summary, indent=2))
        return code

    if args.check_only:
        print(
            json.dumps(
                {
                    "backend_port": backend_port,
                    "config_path": str(config_path.resolve()),
                    "preflight": summary,
                },
                indent=2,
            )
        )
        return 0

    print("Starting backend real smoke server")
    print(f"  config: {config_path.name}")
    if os.getenv("PAPERPIPE_STORAGE_DIR"):
        print("  storage override: enabled")
    if os.getenv("PAPERPIPE_DB_PATH"):
        print("  db override: enabled")
    if os.getenv("PAPERPIPE_ARTIFACTS_DIR"):
        print("  artifacts override: enabled")
    os.execv(sys.executable, _build_uvicorn_command(backend_port))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
