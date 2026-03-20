from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

import src.cli as cli
from src.profiles.profile_schema import Profile, ProfileConfig
from src.profiles.profile_store import save_profiles_snapshot


def _write_projection_profile(path: Path) -> str:
    profile = Profile(
        id="research_dna_dna_guard_test",
        title="Guard Test [DNA Projection]",
        enabled=False,
        schedule="manual",
        notes="\n".join(
            [
                "ResearchDNA Projection",
                "schema_version: research_dna.profile_projection.v1",
                "source_dna_id: dna_guard_test",
            ]
        ),
    )
    save_profiles_snapshot(ProfileConfig(profiles=[profile]), path, allow_unsafe_overwrite=True)
    return profile.id


def test_profiles_cli_blocks_editing_research_dna_projection(tmp_path, monkeypatch):
    runner = CliRunner()
    profiles_path = tmp_path / "config" / "profiles.yaml"
    monkeypatch.setenv("PAPERPIPE_PROFILES_PATH", str(profiles_path))
    profile_id = _write_projection_profile(profiles_path)

    result = runner.invoke(cli.app, ["profiles", profile_id, "add broader query"])
    assert result.exit_code == 0
    assert "read-only here" in result.output
    assert "research-dna project-profile" in result.output


def test_profiles_audit_skips_research_dna_projection(tmp_path, monkeypatch):
    runner = CliRunner()
    profiles_path = tmp_path / "config" / "profiles.yaml"
    monkeypatch.setenv("PAPERPIPE_PROFILES_PATH", str(profiles_path))
    profile_id = _write_projection_profile(profiles_path)

    result = runner.invoke(cli.app, ["audit", "--days", "7"])
    assert result.exit_code == 0
    assert f"Skipping ResearchDNA projection profile: {profile_id}" in result.output
