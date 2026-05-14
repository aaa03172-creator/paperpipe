from __future__ import annotations

from pathlib import Path

from scripts import bootstrap_verification_env as bootstrap_script


def test_default_python_candidates_prefers_homebrew_python314(monkeypatch):
    paths = {
        "/opt/homebrew/bin/python3.14": "/opt/homebrew/bin/python3.14",
        "python3.14": None,
        "python3": "/usr/local/bin/python3",
        "/Library/Frameworks/Python.framework/Versions/3.13/bin/python3.13": "/Library/Frameworks/Python.framework/Versions/3.13/bin/python3.13",
    }

    monkeypatch.setattr(bootstrap_script.shutil, "which", lambda raw: paths.get(raw))

    candidates = bootstrap_script.default_python_candidates()

    assert candidates == [
        Path("/opt/homebrew/bin/python3.14"),
        Path("/usr/local/bin/python3"),
        Path("/Library/Frameworks/Python.framework/Versions/3.13/bin/python3.13"),
    ]


def test_is_healthy_import_probe_requires_full_success():
    assert bootstrap_script.is_healthy_import_probe(
        {"probe_count": 2, "ok_count": 2, "timeout_count": 0, "error_count": 0}
    )
    assert not bootstrap_script.is_healthy_import_probe(
        {"probe_count": 2, "ok_count": 1, "timeout_count": 1, "error_count": 0}
    )


def test_default_extra_packages_cover_agent_smoke_dependency() -> None:
    assert bootstrap_script.DEFAULT_EXTRA_PACKAGES == ["pytest", "langgraph"]


def test_bootstrap_success_requires_healthy_venv_import_probe() -> None:
    assert bootstrap_script.is_bootstrap_success(
        dry_run=False,
        venv_import_health_summary={"probe_count": 2, "ok_count": 2, "timeout_count": 0, "error_count": 0},
    )
    assert not bootstrap_script.is_bootstrap_success(
        dry_run=False,
        venv_import_health_summary={"probe_count": 2, "ok_count": 1, "timeout_count": 1, "error_count": 0},
    )
    assert bootstrap_script.is_bootstrap_success(
        dry_run=True,
        venv_import_health_summary={"probe_count": 2, "ok_count": 0, "timeout_count": 2, "error_count": 0},
    )


def test_build_uv_commands_include_expected_paths(tmp_path: Path):
    venv_dir = tmp_path / ".venv314"
    python_bin = Path("/opt/homebrew/bin/python3.14")
    requirements_file = tmp_path / "requirements.txt"

    create_command = bootstrap_script.build_uv_venv_command(
        uv_bin="/opt/homebrew/bin/uv",
        venv_dir=venv_dir,
        python_bin=python_bin,
        clear_existing=True,
    )
    install_command = bootstrap_script.build_uv_install_command(
        uv_bin="/opt/homebrew/bin/uv",
        venv_python=venv_dir / "bin" / "python",
        requirements_file=requirements_file,
        extras=["pytest", "ruff"],
    )

    assert create_command == [
        "/opt/homebrew/bin/uv",
        "venv",
        str(venv_dir),
        "--python",
        str(python_bin),
        "--clear",
    ]
    assert install_command == [
        "/opt/homebrew/bin/uv",
        "pip",
        "install",
        "--python",
        str(venv_dir / "bin" / "python"),
        "-r",
        str(requirements_file),
        "pytest",
        "ruff",
    ]
