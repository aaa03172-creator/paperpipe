from __future__ import annotations

import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path


def _build_wheel(*, repo_root: Path, wheel_dir: Path) -> Path:
    shutil.rmtree(repo_root / "build", ignore_errors=True)
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "wheel",
            ".",
            "--no-deps",
            "-w",
            str(wheel_dir),
        ],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    wheels = sorted(wheel_dir.glob("paperpipe-*.whl"))
    assert len(wheels) == 1
    return wheels[0]


def test_wheel_keeps_src_backend_and_scripts_packages(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    wheel = _build_wheel(repo_root=repo_root, wheel_dir=tmp_path / "wheelhouse")

    with zipfile.ZipFile(wheel) as archive:
        names = set(archive.namelist())

        expected_paths = {
            "src/__init__.py",
            "src/cli.py",
            "src/config.py",
            "scripts/__init__.py",
            "scripts/archive_fixture_no_feedback_papers.py",
            "backend/__init__.py",
            "backend/main.py",
            "backend/services/job_runner.py",
        }
        missing = sorted(expected_paths - names)
        assert not missing, missing

        entry_points_name = next(
            name for name in names if name.endswith(".dist-info/entry_points.txt")
        )
        entry_points = archive.read(entry_points_name).decode("utf-8")
        assert "paperpipe = src.cli:entrypoint" in entry_points
        assert "lattice = src.cli:entrypoint" in entry_points


def test_wheel_target_install_supports_repo_cli_imports(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    wheel = _build_wheel(repo_root=repo_root, wheel_dir=tmp_path / "wheelhouse")
    target_dir = tmp_path / "site"

    install_completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--no-deps",
            "--target",
            str(target_dir),
            str(wheel),
        ],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    assert install_completed.returncode == 0, install_completed.stderr

    env = dict(os.environ)
    existing_pythonpath = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = (
        f"{target_dir}{os.pathsep}{existing_pythonpath}"
        if existing_pythonpath
        else str(target_dir)
    )

    import_completed = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import backend.main; "
                "import scripts.archive_fixture_no_feedback_papers; "
                "import src.cli; "
                "print('ok')"
            ),
        ],
        cwd=repo_root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert import_completed.returncode == 0, import_completed.stderr
    assert import_completed.stdout.strip() == "ok"


def test_fresh_venv_console_script_can_launch_help(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    wheel = _build_wheel(repo_root=repo_root, wheel_dir=tmp_path / "wheelhouse")
    venv_dir = tmp_path / "venv"

    create_venv_completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "venv",
            str(venv_dir),
        ],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    assert create_venv_completed.returncode == 0, create_venv_completed.stderr

    if os.name == "nt":
        venv_python = venv_dir / "Scripts" / "python.exe"
        paperpipe_bin = venv_dir / "Scripts" / "paperpipe.exe"
    else:
        venv_python = venv_dir / "bin" / "python"
        paperpipe_bin = venv_dir / "bin" / "paperpipe"

    install_completed = subprocess.run(
        [
            str(venv_python),
            "-m",
            "pip",
            "install",
            str(wheel),
        ],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    assert install_completed.returncode == 0, install_completed.stderr
    assert paperpipe_bin.exists()

    help_completed = subprocess.run(
        [str(paperpipe_bin), "--help"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )

    assert help_completed.returncode == 0, help_completed.stderr
    assert "PaperPipe Automation Tool" in help_completed.stdout
    assert "show-intake-override-audit" in help_completed.stdout
