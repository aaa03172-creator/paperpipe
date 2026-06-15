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


def test_normalize_bundle_profile_accepts_cloud_ui():
    assert bundle_script.normalize_bundle_profile(" CLOUD-UI ") == "cloud-ui"


def test_normalize_bundle_profile_rejects_unknown_profile():
    try:
        bundle_script.normalize_bundle_profile("surprise")
    except ValueError as exc:
        assert "Unsupported bundle profile" in str(exc)
    else:
        raise AssertionError("expected unsupported bundle profile to raise")


def test_compile_macos_native_launcher_requires_swiftc(tmp_path: Path):
    try:
        bundle_script._compile_macos_native_launcher(
            output_path=tmp_path / "Lattice",
            swiftc=None,
        )
    except RuntimeError as exc:
        assert "swiftc is required" in str(exc)
    else:
        if bundle_script.shutil.which("swiftc") is None:
            raise AssertionError("expected missing swiftc to raise")


def test_make_macos_app_native_webview_wraps_runtime(monkeypatch, tmp_path: Path):
    app_bundle = tmp_path / "Lattice.app"
    macos_dir = app_bundle / "Contents" / "MacOS"
    app_exec = macos_dir / "Lattice"
    macos_dir.mkdir(parents=True)
    app_exec.write_text("runtime-binary", encoding="utf-8")
    app_exec.chmod(0o755)

    def fake_compile(*, output_path: Path, swiftc: str | None = None) -> None:
        output_path.write_text("native-webview-launcher", encoding="utf-8")

    monkeypatch.setattr(bundle_script, "_compile_macos_native_launcher", fake_compile)

    bundle_script._make_macos_app_native_webview(app_bundle)

    runtime_exec = macos_dir / "LatticeRuntime"
    assert runtime_exec.read_text(encoding="utf-8") == "runtime-binary"
    launcher = app_exec.read_text(encoding="utf-8")
    assert launcher == "native-webview-launcher"
    assert app_exec.stat().st_mode & 0o111
