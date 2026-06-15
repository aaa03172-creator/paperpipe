#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


DEFAULT_PAPER_ID = "cloudpdf_lab_001_fe476330a3bd"


def _fetch_json(url: str, *, api_key: str, timeout_s: float = 2.0) -> tuple[int | None, dict]:
    request = Request(url, headers={"Origin": "http://testserver", "X-API-Key": api_key})
    try:
        with urlopen(request, timeout=timeout_s) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        try:
            payload = json.loads(exc.read().decode("utf-8"))
        except Exception:
            payload = {}
        return exc.code, payload
    except URLError:
        return None, {}


def _wait_for_health(base_url: str, *, timeout_s: int) -> bool:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            with urlopen(f"{base_url}/health", timeout=1.0) as response:
                if response.status == 200:
                    return True
        except Exception:
            pass
        time.sleep(0.5)
    return False


def _terminate(proc: subprocess.Popen[str]) -> None:
    if proc.poll() is not None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=2)


def run_submission_smoke(*, package_dir: Path, port: int, timeout_s: int, paper_id: str) -> dict:
    exe = package_dir / "lattice.exe"
    runtime_exe = package_dir / "LatticeRuntime.exe"
    if runtime_exe.is_file():
        exe = runtime_exe
    elif not exe.is_file():
        raise FileNotFoundError(f"Missing packaged Windows runtime executable: {runtime_exe}")

    api_key = "demo-secret"
    env = os.environ.copy()
    env["PAPERPIPE_INSTALL_LAYOUT"] = "1"
    env["PAPERPIPE_CONFIG_PATH"] = str(package_dir / "config.example.yaml")
    env["LATTICE_API_KEY"] = api_key
    env["PAPERPIPE_SUBMISSION_DEMO_BUNDLE"] = "1"
    env["PAPERPIPE_SUBMISSION_DEMO_BUNDLE_DIR"] = str(package_dir / "submission_demo")
    env["PAPERPIPE_CLOUD_ADAPTER"] = "mock"
    env["PAPERPIPE_CLOUD_METADATA_STORE"] = "memory"
    env["PAPERPIPE_CLOUD_DOWNSTREAM_REGISTRY_STORE"] = "memory"
    env["PAPERPIPE_DEMO_EXPECTED_PAPER_ID"] = paper_id
    env["PAPERPIPE_DEMO_SEARCH_QUERY"] = "amyloid"
    env["LATTICE_START_PATH"] = f"/ui/papers/{paper_id}?source=cloud"

    base_url = f"http://127.0.0.1:{port}"
    proc = subprocess.Popen(
        [str(exe), "start", "--host", "127.0.0.1", "--port", str(port), "--no-open"],
        cwd=package_dir,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    output = ""
    try:
        if not _wait_for_health(base_url, timeout_s=timeout_s):
            if proc.stdout is not None:
                output = proc.stdout.read()
            raise RuntimeError(f"Timed out waiting for /health. output={output!r}")
        preflight_status, preflight = _fetch_json(f"{base_url}/api/cloud/papers/auth-preflight", api_key=api_key)
        page_status, page = _fetch_json(f"{base_url}/api/cloud/papers/{paper_id}/page", api_key=api_key)
        if preflight_status != 200 or preflight.get("status") != "submission_bundle":
            raise RuntimeError(f"Unexpected preflight response: status={preflight_status} payload={preflight}")
        blocks = page.get("blocks") if isinstance(page.get("blocks"), list) else []
        text = "\n".join(str(block.get("text") or "") for block in blocks if isinstance(block, dict))
        if page_status != 200 or "Blood phosphorylated tau 181" not in text or "More than 50 million people worldwide" not in text:
            raise RuntimeError(f"Unexpected page response: status={page_status} payload={page}")
        return {
            "status": "ok",
            "package_dir": str(package_dir),
            "base_url": base_url,
            "paper_id": paper_id,
            "preflight_status": preflight.get("status"),
            "page_block_count": len(blocks),
        }
    finally:
        _terminate(proc)


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke the Windows offline contest submission package.")
    parser.add_argument("--package-dir", type=Path, default=Path("dist") / "Lattice-Windows-Contest-Submission")
    parser.add_argument("--port", type=int, default=8047)
    parser.add_argument("--timeout", type=int, default=45)
    parser.add_argument("--paper-id", default=DEFAULT_PAPER_ID)
    args = parser.parse_args()

    payload = run_submission_smoke(
        package_dir=args.package_dir.resolve(),
        port=args.port,
        timeout_s=args.timeout,
        paper_id=args.paper_id,
    )
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
