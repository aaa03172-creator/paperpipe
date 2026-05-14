from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

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


def _build_worker_command() -> list[str]:
    return [
        sys.executable,
        "-m",
        "src.jobs.worker",
    ]


def _parse_bool_env(name: str, *, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    normalized = raw.strip().lower()
    if not normalized:
        return default
    return normalized in {"1", "true", "yes", "on"}


def _worker_enabled_by_default() -> bool:
    return _parse_bool_env("PAPERPIPE_REAL_SMOKE_ENABLE_WORKER", default=True)


def _terminate_process(proc: subprocess.Popen[bytes] | None) -> None:
    if proc is None or proc.poll() is not None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            return


def _wait_for_health(port: str, timeout_seconds: int) -> bool:
    health_url = f"http://127.0.0.1:{port}/health"
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        try:
            with urlopen(health_url, timeout=1.5) as response:
                if 200 <= response.status < 400:
                    return True
        except URLError:
            pass
        except OSError:
            pass
        time.sleep(0.25)
    return False


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
    parser.add_argument(
        "--health-timeout",
        type=int,
        default=int(os.getenv("PAPERPIPE_REAL_SMOKE_HEALTH_TIMEOUT", "30")),
        help="Seconds to wait for backend /health before failing.",
    )
    parser.add_argument(
        "--worker",
        dest="worker",
        action="store_true",
        default=_worker_enabled_by_default(),
        help="Start the deep-read worker sidecar (default: enabled).",
    )
    parser.add_argument(
        "--no-worker",
        dest="worker",
        action="store_false",
        help="Skip the deep-read worker sidecar.",
    )
    args = parser.parse_args()

    backend_port = str(os.getenv("E2E_BACKEND_PORT", "8000"))
    config_path = Path(os.getenv("PAPERPIPE_CONFIG_PATH", "config.yaml")).expanduser()
    repo_root = Path(__file__).resolve().parents[1]

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
                    "worker_enabled": args.worker,
                    "health_timeout": args.health_timeout,
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
    backend_proc: subprocess.Popen[bytes] | None = None
    worker_proc: subprocess.Popen[bytes] | None = None

    def _handle_stop(_signum: int, _frame: object) -> None:
        raise KeyboardInterrupt

    previous_signal_handlers = {
        signum: signal.getsignal(signum) for signum in (signal.SIGINT, signal.SIGTERM)
    }
    for signum in previous_signal_handlers:
        signal.signal(signum, _handle_stop)

    try:
        backend_proc = subprocess.Popen(_build_uvicorn_command(backend_port), cwd=repo_root)
        if not _wait_for_health(backend_port, args.health_timeout):
            print(f"Backend healthcheck timed out after {args.health_timeout}s", file=sys.stderr)
            return 1

        print(f"  backend: http://127.0.0.1:{backend_port}")
        if args.worker:
            worker_proc = subprocess.Popen(_build_worker_command(), cwd=repo_root)
            print("  worker: enabled")
        else:
            print("  worker: disabled (--no-worker)")

        while True:
            backend_code = backend_proc.poll()
            worker_code = worker_proc.poll() if worker_proc is not None else None
            if backend_code is None and (worker_proc is None or worker_code is None):
                time.sleep(0.5)
                continue
            if backend_code is not None:
                if backend_code != 0:
                    print(f"Backend exited with code {backend_code}", file=sys.stderr)
                    return backend_code
                return 0
            if worker_code is not None:
                print(f"Worker exited with code {worker_code}", file=sys.stderr)
                return worker_code or 1
    except KeyboardInterrupt:
        print("Stopping backend real smoke server")
        return 0
    finally:
        _terminate_process(worker_proc)
        _terminate_process(backend_proc)
        for signum, handler in previous_signal_handlers.items():
            signal.signal(signum, handler)


if __name__ == "__main__":
    raise SystemExit(main())
