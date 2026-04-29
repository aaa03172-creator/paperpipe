#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
IMPORT_HEALTH_SCRIPT = ROOT / "scripts" / "check_python_import_health.py"
DEFAULT_REQUIREMENTS_FILE = ROOT / "requirements.txt"
DEFAULT_VENV_DIR = ROOT / ".venv314"
DEFAULT_EXTRA_PACKAGES = ["pytest", "langgraph"]
DEFAULT_TIMEOUT_SECONDS = 10


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _snapshot_dir(run_id: str) -> Path:
    return ROOT / "snapshots" / "verification_env_bootstrap" / run_id


def default_python_candidates() -> list[Path]:
    preferred = [
        "/opt/homebrew/bin/python3.14",
        "python3.14",
        "python3",
        "/Library/Frameworks/Python.framework/Versions/3.13/bin/python3.13",
    ]
    seen: set[str] = set()
    candidates: list[Path] = []
    for raw in preferred:
        resolved = shutil.which(raw) if "/" not in raw else raw
        if not resolved:
            continue
        path = Path(resolved).expanduser().absolute()
        key = str(path)
        if key in seen:
            continue
        seen.add(key)
        candidates.append(path)
    return candidates


def is_healthy_import_probe(summary: dict[str, Any]) -> bool:
    probe_count = int(summary.get("probe_count", 0) or 0)
    ok_count = int(summary.get("ok_count", 0) or 0)
    timeout_count = int(summary.get("timeout_count", 0) or 0)
    error_count = int(summary.get("error_count", 0) or 0)
    return probe_count > 0 and ok_count == probe_count and timeout_count == 0 and error_count == 0


def is_bootstrap_success(
    *,
    dry_run: bool,
    venv_import_health_summary: dict[str, Any] | None,
) -> bool:
    return dry_run or venv_import_health_summary is None or is_healthy_import_probe(venv_import_health_summary)


def build_import_health_command(
    *,
    probe_runner: Path,
    python_bin: Path,
    timeout_seconds: int,
    run_id: str,
    probes: list[str],
) -> list[str]:
    command = [
        str(probe_runner),
        str(IMPORT_HEALTH_SCRIPT),
        "--python-bin",
        str(python_bin),
        "--timeout-seconds",
        str(timeout_seconds),
        "--run-id",
        run_id,
    ]
    for probe in probes:
        command.extend(["--probe", probe])
    return command


def build_uv_venv_command(
    *,
    uv_bin: str,
    venv_dir: Path,
    python_bin: Path,
    clear_existing: bool = False,
) -> list[str]:
    command = [
        uv_bin,
        "venv",
        str(venv_dir),
        "--python",
        str(python_bin),
    ]
    if clear_existing:
        command.append("--clear")
    return command


def build_uv_install_command(
    *,
    uv_bin: str,
    venv_python: Path,
    requirements_file: Path,
    extras: list[str],
) -> list[str]:
    command = [
        uv_bin,
        "pip",
        "install",
        "--python",
        str(venv_python),
        "-r",
        str(requirements_file),
    ]
    command.extend(extras)
    return command


def _run_json_command(command: list[str], *, cwd: Path) -> dict[str, Any]:
    completed = subprocess.run(
        command,
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"command_failed returncode={completed.returncode} command={command!r} stderr={completed.stderr!r}"
        )
    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"command_did_not_emit_json command={command!r}") from exc


def _run_checked(command: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=cwd, text=True, capture_output=True, check=True)


def _choose_python(
    *,
    probe_runner: Path,
    timeout_seconds: int,
    run_id: str,
    explicit_python: Path | None,
) -> tuple[Path, list[dict[str, Any]]]:
    probe_results: list[dict[str, Any]] = []
    candidates = [explicit_python.absolute()] if explicit_python is not None else default_python_candidates()
    if not candidates:
        raise RuntimeError("no_python_candidates_found")

    core_probes = ["no-site:select", "no-site:subprocess"]
    for index, candidate in enumerate(candidates, start=1):
        candidate_run_id = f"{run_id}_candidate_{index}"
        command = build_import_health_command(
            probe_runner=probe_runner,
            python_bin=candidate,
            timeout_seconds=timeout_seconds,
            run_id=candidate_run_id,
            probes=core_probes,
        )
        summary = _run_json_command(command, cwd=ROOT)
        probe_results.append(summary)
        if is_healthy_import_probe(summary):
            return candidate, probe_results

    raise RuntimeError(
        "no_healthy_python_candidate_found "
        + json.dumps(
            [
                {
                    "python_bin": item.get("python_bin"),
                    "ok_count": item.get("ok_count"),
                    "timeout_count": item.get("timeout_count"),
                    "error_count": item.get("error_count"),
                }
                for item in probe_results
            ],
            ensure_ascii=False,
        )
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create a bounded healthy verification virtualenv and validate it with import-health probes."
    )
    parser.add_argument("--python-bin", help="Optional explicit interpreter to use.")
    parser.add_argument(
        "--venv-dir",
        default=str(DEFAULT_VENV_DIR),
        help="Verification virtualenv path. Defaults to .venv314.",
    )
    parser.add_argument(
        "--requirements-file",
        default=str(DEFAULT_REQUIREMENTS_FILE),
        help="Requirements file to install into the verification environment.",
    )
    parser.add_argument(
        "--extra-package",
        action="append",
        default=list(DEFAULT_EXTRA_PACKAGES),
        help="Extra package to install after requirements.txt. Repeatable.",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=DEFAULT_TIMEOUT_SECONDS,
        help="Per import-health probe timeout.",
    )
    parser.add_argument(
        "--run-id",
        default="verification_env_bootstrap_manual",
        help="Snapshot run id under snapshots/verification_env_bootstrap/.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the planned commands and summary without creating the environment.",
    )
    args = parser.parse_args()

    probe_runner = Path(sys.executable).expanduser().absolute()
    explicit_python = Path(args.python_bin).expanduser() if args.python_bin else None
    chosen_python, candidate_probe_results = _choose_python(
        probe_runner=probe_runner,
        timeout_seconds=args.timeout_seconds,
        run_id=args.run_id,
        explicit_python=explicit_python,
    )

    uv_bin = shutil.which("uv")
    if not uv_bin:
        raise RuntimeError("uv_not_found")

    venv_dir = Path(args.venv_dir).expanduser().absolute()
    requirements_file = Path(args.requirements_file).expanduser().absolute()
    extras = [str(item).strip() for item in (args.extra_package or []) if str(item).strip()]
    clear_existing = venv_dir.exists()
    create_command = build_uv_venv_command(
        uv_bin=uv_bin,
        venv_dir=venv_dir,
        python_bin=chosen_python,
        clear_existing=clear_existing,
    )
    venv_python = venv_dir / "bin" / "python"
    install_command = build_uv_install_command(
        uv_bin=uv_bin,
        venv_python=venv_python,
        requirements_file=requirements_file,
        extras=extras,
    )
    venv_import_health_run_id = f"{args.run_id}_venv_import_health"
    venv_import_health_command = build_import_health_command(
        probe_runner=probe_runner,
        python_bin=venv_python,
        timeout_seconds=args.timeout_seconds,
        run_id=venv_import_health_run_id,
        probes=[],
    )

    executed_steps: list[dict[str, Any]] = []
    venv_import_health_summary: dict[str, Any] | None = None

    if not args.dry_run:
        created = _run_checked(create_command, cwd=ROOT)
        executed_steps.append(
            {
                "step": "create_venv",
                "returncode": created.returncode,
                "stdout": created.stdout.strip(),
                "stderr": created.stderr.strip(),
            }
        )
        installed = _run_checked(install_command, cwd=ROOT)
        executed_steps.append(
            {
                "step": "install_requirements",
                "returncode": installed.returncode,
                "stdout_tail": installed.stdout[-1000:].strip(),
                "stderr_tail": installed.stderr[-1000:].strip(),
            }
        )
        venv_import_health_summary = _run_json_command(venv_import_health_command, cwd=ROOT)

    summary = {
        "run_id": args.run_id,
        "generated_at": _utc_now_iso(),
        "dry_run": args.dry_run,
        "probe_runner": str(probe_runner),
        "chosen_python_bin": str(chosen_python),
        "venv_dir": str(venv_dir),
        "venv_python": str(venv_python),
        "clear_existing": clear_existing,
        "requirements_file": str(requirements_file),
        "extra_packages": extras,
        "candidate_probe_results": candidate_probe_results,
        "create_command": create_command,
        "install_command": install_command,
        "venv_import_health_command": venv_import_health_command,
        "executed_steps": executed_steps,
        "venv_import_health_summary": venv_import_health_summary,
        "venv_import_health_ok": is_bootstrap_success(
            dry_run=args.dry_run,
            venv_import_health_summary=venv_import_health_summary,
        ),
    }

    snapshot_dir = _snapshot_dir(args.run_id)
    _write_json(snapshot_dir / "summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    raise SystemExit(0 if summary["venv_import_health_ok"] else 2)


if __name__ == "__main__":
    main()
