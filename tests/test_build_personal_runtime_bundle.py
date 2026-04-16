from pathlib import Path

from scripts import build_personal_runtime_bundle as bundle_script


def test_cli_binary_output_path_uses_windows_exe(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(bundle_script.sys, "platform", "win32")

    assert bundle_script.cli_binary_output_path(tmp_path) == (
        tmp_path / "dist" / "lattice.exe"
    ).resolve()


def test_cli_binary_cleanup_paths_cover_both_platform_variants(tmp_path: Path):
    assert bundle_script._cli_binary_cleanup_paths(tmp_path) == [
        (tmp_path / "dist" / "lattice").resolve(),
        (tmp_path / "dist" / "lattice.exe").resolve(),
    ]
