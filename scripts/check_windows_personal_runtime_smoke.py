from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.services.runtime_paths import user_config_base_dir

CONFIG_TEMPLATE_PATH = ROOT / "config.example.yaml"


def windows_cli_binary_path(root: Path = ROOT) -> Path:
    return (root / "dist" / "lattice.exe").resolve()


def default_windows_config_path(base_dir: Path | None = None) -> Path:
    root = base_dir.resolve() if base_dir is not None else user_config_base_dir()
    return (root / "config" / "config.yaml").resolve()


def ensure_smoke_config(config_path: Path, template_path: Path = CONFIG_TEMPLATE_PATH) -> bool:
    if config_path.exists():
        return False
    config_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(template_path, config_path)
    return True


def build_runtime_env(config_path: Path) -> dict[str, str]:
    env = os.environ.copy()
    env["PAPERPIPE_INSTALL_LAYOUT"] = "1"
    env["PAPERPIPE_CONFIG_PATH"] = str(config_path)
    return env


def build_cli_command(mode: str, *, root: Path = ROOT) -> list[str]:
    if mode == "source":
        return [sys.executable, "-m", "src.cli"]
    if mode == "packaged":
        binary_path = windows_cli_binary_path(root)
        if not binary_path.exists():
            raise FileNotFoundError(
                f"Missing packaged Windows launcher: {binary_path}. "
                "Run scripts/build_personal_runtime_bundle.py on a Windows host first."
            )
        return [str(binary_path)]
    raise ValueError(f"Unsupported mode: {mode}")


def _build_packaged_bundle(*, skip_frontend_build: bool, clean: bool) -> None:
    cmd = [sys.executable, str(ROOT / "scripts" / "build_personal_runtime_bundle.py")]
    if skip_frontend_build:
        cmd.append("--skip-frontend-build")
    if clean:
        cmd.append("--clean")
    subprocess.run(cmd, cwd=ROOT, check=True)


def _run_self_test(command_prefix: list[str], env: dict[str, str]) -> dict:
    result = subprocess.run(
        [*command_prefix, "self-test", "--json"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            "self-test did not emit valid JSON. "
            f"stdout={result.stdout!r} stderr={result.stderr!r}"
        ) from exc
    if result.returncode != 0:
        raise RuntimeError(
            f"self-test failed with exit code {result.returncode}. payload={payload}"
        )
    return payload


def _fetch_status(url: str, *, timeout_s: float = 1.0) -> int | None:
    try:
        with urlopen(url, timeout=timeout_s) as response:
            return response.status
    except HTTPError as exc:
        return exc.code
    except URLError:
        return None


def _wait_for_status(url: str, *, expected_status: int, timeout_s: int) -> bool:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        status = _fetch_status(url)
        if status == expected_status:
            return True
        time.sleep(0.25)
    return False


def _terminate_process(proc: subprocess.Popen[str]) -> None:
    if proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            try:
                proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                return
        return
    try:
        proc.wait(timeout=1)
    except subprocess.TimeoutExpired:
        return


def run_smoke(
    *,
    mode: str,
    host: str,
    port: int,
    timeout_s: int,
    config_path: Path,
) -> dict:
    env = build_runtime_env(config_path)
    command_prefix = build_cli_command(mode)
    self_test = _run_self_test(command_prefix, env)

    base_url = f"http://{host}:{port}"
    combined_output = ""
    health_status: int | None = None
    ui_status: int | None = None
    fd, raw_log_path = tempfile.mkstemp(prefix="lattice-windows-smoke-", suffix=".log")
    os.close(fd)
    log_path = Path(raw_log_path)
    with log_path.open("w", encoding="utf-8") as log_handle:
        proc = subprocess.Popen(
            [*command_prefix, "start", "--host", host, "--port", str(port), "--no-open"],
            cwd=ROOT,
            env=env,
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            text=True,
        )
        try:
            health_ok = _wait_for_status(f"{base_url}/health", expected_status=200, timeout_s=timeout_s)
            health_status = 200 if health_ok else _fetch_status(f"{base_url}/health")
            ui_ok = health_ok and _wait_for_status(f"{base_url}/ui", expected_status=200, timeout_s=5)
            ui_status = 200 if ui_ok else _fetch_status(f"{base_url}/ui")
            if not health_ok or not ui_ok:
                _terminate_process(proc)
                combined_output = log_path.read_text(encoding="utf-8", errors="replace")
                raise RuntimeError(
                    f"Runtime smoke failed: health_ok={health_ok}, ui_ok={ui_ok}, "
                    f"process_output={combined_output!r}"
                )
            _terminate_process(proc)
        finally:
            if proc.poll() is None:
                _terminate_process(proc)

    combined_output = log_path.read_text(encoding="utf-8", errors="replace")
    log_path.unlink(missing_ok=True)

    return {
        "mode": mode,
        "command_prefix": command_prefix,
        "base_url": base_url,
        "config_path": str(config_path),
        "self_test": self_test,
        "health_status": health_status,
        "ui_status": ui_status,
        "launcher_output": combined_output,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the first real-host Windows personal-runtime smoke path."
    )
    parser.add_argument(
        "--mode",
        choices=("source", "packaged"),
        default="source",
        help="Smoke the source launcher or the packaged Windows launcher.",
    )
    parser.add_argument(
        "--build-packaged",
        action="store_true",
        help="Build the packaged Windows launcher before running packaged smoke.",
    )
    parser.add_argument(
        "--skip-frontend-build",
        action="store_true",
        help="Reuse the existing frontend/dist bundle when building the packaged launcher.",
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Ask PyInstaller to clean temporary build artifacts first.",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Backend bind host for the smoke run.",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8037,
        help="Backend port for the smoke run.",
    )
    parser.add_argument(
        "--health-timeout",
        type=int,
        default=20,
        help="Seconds to wait for /health before failing.",
    )
    parser.add_argument(
        "--config-path",
        default="",
        help="Optional explicit config path. Empty means the install-layout Windows app-data path.",
    )
    parser.add_argument(
        "--allow-non-windows",
        action="store_true",
        help="Test-only escape hatch for running helper validation off Windows.",
    )
    args = parser.parse_args()

    if os.name != "nt" and not args.allow_non_windows:
        raise SystemExit("This smoke script is intended to run on a Windows host.")

    if args.mode == "packaged" and args.build_packaged:
        _build_packaged_bundle(
            skip_frontend_build=args.skip_frontend_build,
            clean=args.clean,
        )

    config_path = (
        Path(args.config_path).expanduser().resolve()
        if args.config_path
        else default_windows_config_path()
    )
    created_default_config = ensure_smoke_config(config_path)

    payload = run_smoke(
        mode=args.mode,
        host=args.host,
        port=args.port,
        timeout_s=args.health_timeout,
        config_path=config_path,
    )
    payload["created_default_config"] = created_default_config
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
