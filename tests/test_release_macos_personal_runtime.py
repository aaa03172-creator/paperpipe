import json
from pathlib import Path

import pytest

from scripts import release_macos_personal_runtime as release_script


def _write_valid_release_artifacts(paths: release_script.ReleasePaths) -> None:
    app_executable = paths.app_bundle / "Contents" / "MacOS" / "Lattice"
    app_executable.parent.mkdir(parents=True, exist_ok=True)
    app_executable.write_text("#!/bin/sh\n", encoding="utf-8")
    app_executable.chmod(0o755)

    paths.cli_binary.parent.mkdir(parents=True, exist_ok=True)
    paths.cli_binary.write_text("#!/bin/sh\n", encoding="utf-8")
    paths.cli_binary.chmod(0o755)
    paths.support_dir.mkdir(parents=True, exist_ok=True)


def test_default_artifact_basename_normalizes_machine():
    assert release_script.default_artifact_basename("ARM64") == "Lattice-macos-arm64"


def test_resolve_release_mode_requires_identity_for_notary():
    with pytest.raises(ValueError):
        release_script.resolve_release_mode("", "LATTICE_NOTARY")


def test_require_gatekeeper_rejects_unsigned_alpha_release():
    with pytest.raises(ValueError, match="Gatekeeper-ready release requires both"):
        release_script.validate_gatekeeper_requirement(
            require_gatekeeper=True,
            sign_enabled=False,
            notarize_enabled=False,
        )


def test_require_gatekeeper_allows_signed_notarized_release_path():
    release_script.validate_gatekeeper_requirement(
        require_gatekeeper=True,
        sign_enabled=True,
        notarize_enabled=True,
    )


def test_build_release_paths_uses_expected_filenames(tmp_path: Path):
    paths = release_script.build_release_paths(tmp_path, "Lattice-macos-arm64")

    assert paths.app_bundle == (tmp_path / "dist" / "Lattice.app").resolve()
    assert paths.launcher_bundle == (
        tmp_path / "dist" / "release" / "Lattice Launcher.app"
    ).resolve()
    assert paths.cli_binary == (tmp_path / "dist" / "lattice").resolve()
    assert paths.zip_path == (tmp_path / "dist" / "release" / "Lattice-macos-arm64.zip").resolve()
    assert paths.launcher_zip_path == (
        tmp_path / "dist" / "release" / "Lattice-macos-arm64.launcher.zip"
    ).resolve()
    assert paths.alpha_handoff_path == (
        tmp_path / "dist" / "release" / "Lattice-macos-arm64.alpha-handoff.md"
    ).resolve()
    assert paths.config_example_copy_path == (
        tmp_path / "dist" / "release" / "Lattice-macos-arm64.config.example.yaml"
    ).resolve()
    assert paths.manifest_path == (
        tmp_path / "dist" / "release" / "Lattice-macos-arm64.manifest.json"
    ).resolve()


def test_build_bundle_forwards_bundle_profile(monkeypatch):
    captured: dict[str, object] = {}

    def fake_run(cmd, *, cwd=None):
        captured["cmd"] = cmd
        captured["cwd"] = cwd

    monkeypatch.setattr(release_script, "_run", fake_run)

    release_script._build_bundle(
        clean=True,
        skip_frontend_build=True,
        bundle_profile="cloud-ui",
    )

    assert "--bundle-profile" in captured["cmd"]
    assert "cloud-ui" in captured["cmd"]
    assert "--clean" in captured["cmd"]
    assert "--skip-frontend-build" in captured["cmd"]


def test_build_launcher_bundle_targets_applications_bundle(monkeypatch, tmp_path: Path):
    paths = release_script.build_release_paths(tmp_path, "Lattice-macos-arm64")
    captured: dict[str, list[list[str]]] = {"run": [], "codesign": [], "zip": []}

    def fake_run(cmd, *, cwd=None):
        captured["run"].append(cmd)

    def fake_codesign(path, identity, *, deep):
        captured["codesign"].append([str(path), identity, str(deep)])

    def fake_package_zip(app_bundle, zip_path):
        captured["zip"].append([str(app_bundle), str(zip_path)])

    monkeypatch.setattr(release_script, "_run", fake_run)
    monkeypatch.setattr(release_script, "_codesign", fake_codesign)
    monkeypatch.setattr(release_script, "_package_zip", fake_package_zip)

    release_script._build_launcher_bundle(paths, identity="")

    command = captured["run"][0]
    assert "--app-bundle" in command
    assert command[command.index("--app-bundle") + 1] == "/Applications/Lattice.app"
    assert "--skip-app-validation" in command
    assert "/dist/Lattice.app" not in " ".join(command)
    assert captured["codesign"] == [[str(paths.launcher_bundle), "-", "True"]]
    assert captured["zip"] == [[str(paths.launcher_bundle), str(paths.launcher_zip_path)]]


def test_evaluate_release_preflight_reports_local_ready_but_gatekeeper_blocked(tmp_path: Path):
    paths = release_script.build_release_paths(tmp_path, "Lattice-macos-arm64")
    _write_valid_release_artifacts(paths)

    report = release_script.evaluate_release_preflight(
        paths=paths,
        tools={"codesign": True, "ditto": True, "xcrun": True, "spctl": True, "security": True},
        available_identities=[],
        requested_identity="",
        requested_notary_profile="",
        notary_profile_available=False,
        notary_profile_detail=None,
    )

    assert report.status == "warn"
    assert report.local_release_ready is True
    assert report.gatekeeper_release_ready is False
    assert "No code-signing identities are currently available" in report.blockers
    assert "No notary profile has been configured" in report.blockers


def test_evaluate_release_preflight_rejects_invalid_artifact_shapes(tmp_path: Path):
    paths = release_script.build_release_paths(tmp_path, "Lattice-macos-arm64")
    paths.app_bundle.parent.mkdir(parents=True, exist_ok=True)
    paths.app_bundle.write_text("bundle", encoding="utf-8")
    paths.cli_binary.write_text("binary", encoding="utf-8")

    report = release_script.evaluate_release_preflight(
        paths=paths,
        tools={"codesign": True, "ditto": True, "xcrun": True, "spctl": True, "security": True},
        available_identities=["Developer ID Application: Example (TEAMID1234)"],
        requested_identity="Developer ID Application: Example (TEAMID1234)",
        requested_notary_profile="LATTICE_NOTARY",
        notary_profile_available=True,
        notary_profile_detail="{}",
    )

    assert report.status == "error"
    assert report.local_release_ready is False
    assert report.gatekeeper_release_ready is False
    assert report.artifacts["app_bundle"] is False
    assert report.artifacts["cli_binary"] is False
    assert "Missing or invalid dist/Lattice.app" in report.blockers
    assert "Missing or invalid dist/lattice" in report.blockers


def test_evaluate_release_preflight_rejects_non_executable_app_binary(tmp_path: Path):
    paths = release_script.build_release_paths(tmp_path, "Lattice-macos-arm64")
    _write_valid_release_artifacts(paths)
    (paths.app_bundle / "Contents" / "MacOS" / "Lattice").chmod(0o644)

    report = release_script.evaluate_release_preflight(
        paths=paths,
        tools={"codesign": True, "ditto": True, "xcrun": True, "spctl": True, "security": True},
        available_identities=["Developer ID Application: Example (TEAMID1234)"],
        requested_identity="Developer ID Application: Example (TEAMID1234)",
        requested_notary_profile="LATTICE_NOTARY",
        notary_profile_available=True,
        notary_profile_detail="{}",
    )

    assert report.status == "error"
    assert report.local_release_ready is False
    assert report.artifacts["app_bundle"] is False
    assert "Missing or invalid dist/Lattice.app" in report.blockers


def test_evaluate_release_preflight_reports_gatekeeper_ready(tmp_path: Path):
    paths = release_script.build_release_paths(tmp_path, "Lattice-macos-arm64")
    _write_valid_release_artifacts(paths)

    report = release_script.evaluate_release_preflight(
        paths=paths,
        tools={"codesign": True, "ditto": True, "xcrun": True, "spctl": True, "security": True},
        available_identities=["Developer ID Application: Example (TEAMID1234)"],
        requested_identity="Developer ID Application: Example (TEAMID1234)",
        requested_notary_profile="LATTICE_NOTARY",
        notary_profile_available=True,
        notary_profile_detail="{}",
    )

    assert report.status == "ok"
    assert report.local_release_ready is True
    assert report.gatekeeper_release_ready is True
    assert report.matching_identity == "Developer ID Application: Example (TEAMID1234)"


def test_write_manifest_uses_repo_relative_paths(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(release_script, "ROOT", tmp_path)
    paths = release_script.build_release_paths(tmp_path, "Lattice-macos-arm64")
    _write_valid_release_artifacts(paths)
    paths.release_dir.mkdir(parents=True, exist_ok=True)
    paths.zip_path.write_bytes(b"zip-bytes")

    release_script._write_manifest(
        paths=paths,
        artifact_basename="Lattice-macos-arm64",
        sign_enabled=False,
        notarize_enabled=False,
        identity="",
        notary_profile="",
        gatekeeper_output=None,
        notary_payload=None,
        include_launcher=False,
    )

    manifest = json.loads(paths.manifest_path.read_text(encoding="utf-8"))

    assert manifest["paths"]["app_bundle"] == "dist/Lattice.app"
    assert manifest["paths"]["zip_path"] == "dist/release/Lattice-macos-arm64.zip"
    assert not Path(manifest["paths"]["app_bundle"]).is_absolute()
    assert not Path(manifest["paths"]["zip_path"]).is_absolute()
    assert manifest["launcher"]["included"] is False
    assert manifest["hashes"]["launcher_zip_sha256"] is None


def test_write_manifest_records_assisted_launcher_artifact(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(release_script, "ROOT", tmp_path)
    paths = release_script.build_release_paths(tmp_path, "Lattice-macos-arm64")
    _write_valid_release_artifacts(paths)
    paths.release_dir.mkdir(parents=True, exist_ok=True)
    paths.zip_path.write_bytes(b"zip-bytes")
    paths.launcher_zip_path.write_bytes(b"launcher-zip-bytes")
    paths.launcher_bundle.mkdir(parents=True)

    release_script._write_manifest(
        paths=paths,
        artifact_basename="Lattice-macos-arm64",
        sign_enabled=False,
        notarize_enabled=False,
        identity="",
        notary_profile="",
        gatekeeper_output=None,
        notary_payload=None,
        include_launcher=True,
    )

    manifest = json.loads(paths.manifest_path.read_text(encoding="utf-8"))

    assert manifest["launcher"] == {
        "included": True,
        "bundle": "dist/release/Lattice Launcher.app",
        "zip": "dist/release/Lattice-macos-arm64.launcher.zip",
        "assisted_alpha_only": True,
    }
    assert manifest["hashes"]["launcher_zip_sha256"] == release_script._sha256(paths.launcher_zip_path)
