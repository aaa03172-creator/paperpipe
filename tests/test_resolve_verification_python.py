from __future__ import annotations

from pathlib import Path

from scripts import resolve_verification_python as resolver_script


def test_default_python_candidates_prefers_env_and_repo_venvs(
    monkeypatch,
    tmp_path: Path,
) -> None:
    root = tmp_path / "repo"
    env_python = tmp_path / "custom" / "python"
    system_python3 = tmp_path / "system" / "python3"
    system_python = tmp_path / "system" / "python"
    venv314_python = root / ".venv314" / "bin" / "python"
    venv_python = root / ".venv" / "bin" / "python"
    env_python.parent.mkdir(parents=True)
    system_python3.parent.mkdir(parents=True)
    venv314_python.parent.mkdir(parents=True)
    venv_python.parent.mkdir(parents=True)
    env_python.write_text("", encoding="utf-8")
    system_python3.write_text("", encoding="utf-8")
    system_python.write_text("", encoding="utf-8")
    venv314_python.write_text("", encoding="utf-8")
    venv_python.write_text("", encoding="utf-8")

    monkeypatch.setenv("PAPERPIPE_VERIFICATION_PYTHON", str(env_python))
    monkeypatch.setattr(
        resolver_script.shutil,
        "which",
        lambda raw: {
            "python3": str(system_python3),
            "python": str(system_python),
        }.get(raw),
    )

    candidates = resolver_script.default_python_candidates(
        root=root,
        preferred_system_candidates=["python3", "python"],
    )

    assert candidates == [
        env_python.absolute(),
        venv314_python.absolute(),
        venv_python.absolute(),
        system_python3.absolute(),
        system_python.absolute(),
    ]


def test_choose_python_skips_unhealthy_candidate(monkeypatch) -> None:
    first = Path("/repo/.venv/bin/python")
    second = Path("/repo/.venv314/bin/python")

    monkeypatch.setattr(
        resolver_script,
        "probe_candidate",
        lambda **kwargs: {
            "python_bin": str(kwargs["python_bin"]),
            "status": "timeout" if kwargs["python_bin"] == first else "ok",
            "probes": [],
        },
    )

    chosen, probe_results = resolver_script.choose_python(
        candidates=[first, second],
        required_modules=["pytest"],
        timeout_seconds=3,
    )

    assert chosen == second
    assert [item["status"] for item in probe_results] == ["timeout", "ok"]


def test_build_probe_marks_required_module_as_site_import(monkeypatch) -> None:
    observed_calls: list[tuple[str, bool]] = []

    def _fake_run_probe(**kwargs):
        observed_calls.append((kwargs["module_name"], kwargs["no_site"]))
        return {
            "module": kwargs["module_name"],
            "mode": "no-site" if kwargs["no_site"] else "site",
            "status": "ok",
            "returncode": 0,
        }

    monkeypatch.setattr(resolver_script, "_run_probe", _fake_run_probe)

    result = resolver_script.probe_candidate(
        python_bin=Path("/repo/.venv314/bin/python"),
        required_modules=["pytest"],
        timeout_seconds=5,
    )

    assert result["status"] == "ok"
    assert observed_calls == [
        ("select", True),
        ("subprocess", True),
        ("pytest", False),
    ]


def test_run_probe_treats_disappearing_python_as_error(monkeypatch) -> None:
    def _raise_file_not_found(*args, **kwargs):
        raise FileNotFoundError("missing interpreter")

    monkeypatch.setattr(resolver_script.subprocess, "run", _raise_file_not_found)

    result = resolver_script._run_probe(
        python_bin=Path("/repo/.venv314/bin/python"),
        module_name="pytest",
        no_site=False,
        timeout_seconds=5,
    )

    assert result == {
        "module": "pytest",
        "mode": "site",
        "status": "error",
        "returncode": None,
    }
