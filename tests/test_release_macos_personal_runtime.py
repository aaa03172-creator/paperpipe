from pathlib import Path

import pytest

from scripts import release_macos_personal_runtime as release_script


def test_default_artifact_basename_normalizes_machine():
    assert release_script.default_artifact_basename("ARM64") == "Lattice-macos-arm64"


def test_resolve_release_mode_requires_identity_for_notary():
    with pytest.raises(ValueError):
        release_script.resolve_release_mode("", "LATTICE_NOTARY")


def test_build_release_paths_uses_expected_filenames(tmp_path: Path):
    paths = release_script.build_release_paths(tmp_path, "Lattice-macos-arm64")

    assert paths.app_bundle == (tmp_path / "dist" / "Lattice.app").resolve()
    assert paths.cli_binary == (tmp_path / "dist" / "lattice").resolve()
    assert paths.zip_path == (tmp_path / "dist" / "release" / "Lattice-macos-arm64.zip").resolve()
    assert paths.alpha_handoff_path == (
        tmp_path / "dist" / "release" / "Lattice-macos-arm64.alpha-handoff.md"
    ).resolve()
    assert paths.config_example_copy_path == (
        tmp_path / "dist" / "release" / "Lattice-macos-arm64.config.example.yaml"
    ).resolve()
    assert paths.manifest_path == (
        tmp_path / "dist" / "release" / "Lattice-macos-arm64.manifest.json"
    ).resolve()


def test_evaluate_release_preflight_reports_local_ready_but_gatekeeper_blocked(tmp_path: Path):
    paths = release_script.build_release_paths(tmp_path, "Lattice-macos-arm64")
    paths.app_bundle.parent.mkdir(parents=True, exist_ok=True)
    paths.app_bundle.write_text("bundle")
    paths.cli_binary.parent.mkdir(parents=True, exist_ok=True)
    paths.cli_binary.write_text("binary")
    paths.support_dir.mkdir(parents=True, exist_ok=True)

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


def test_evaluate_release_preflight_reports_gatekeeper_ready(tmp_path: Path):
    paths = release_script.build_release_paths(tmp_path, "Lattice-macos-arm64")
    paths.app_bundle.parent.mkdir(parents=True, exist_ok=True)
    paths.app_bundle.write_text("bundle")
    paths.cli_binary.parent.mkdir(parents=True, exist_ok=True)
    paths.cli_binary.write_text("binary")
    paths.support_dir.mkdir(parents=True, exist_ok=True)

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
