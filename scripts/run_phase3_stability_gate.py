from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INTEGRATION_SCRIPT = ROOT / "scripts" / "test_phase3_integration.py"


def run_once(python_exec: str) -> tuple[bool, float, str]:
    start = time.time()
    proc = subprocess.run(
        [python_exec, str(INTEGRATION_SCRIPT)],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )
    elapsed = time.time() - start
    output = (proc.stdout or "").strip()
    if proc.stderr:
        output = f"{output}\n{proc.stderr.strip()}".strip()
    return proc.returncode == 0, elapsed, output


def main() -> int:
    parser = argparse.ArgumentParser(description="Run phase3 integration repeatedly as a stability gate.")
    parser.add_argument("--runs", type=int, default=3, help="Number of repeated runs.")
    parser.add_argument("--python", default=sys.executable, help="Python executable path.")
    args = parser.parse_args()

    total = max(1, args.runs)
    passed = 0
    failures: list[tuple[int, str]] = []

    print(f"[GATE] phase3 integration stability gate start: runs={total}")
    for idx in range(1, total + 1):
        ok, elapsed, output = run_once(args.python)
        status = "PASS" if ok else "FAIL"
        print(f"[GATE] run={idx}/{total} status={status} elapsed_sec={elapsed:.2f}")
        if ok:
            passed += 1
        else:
            tail = "\n".join(output.splitlines()[-20:])
            failures.append((idx, tail))

    print(f"[GATE] summary passed={passed} failed={total - passed}")
    if failures:
        for idx, tail in failures:
            print(f"[GATE][FAIL][run={idx}] tail:\n{tail}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
