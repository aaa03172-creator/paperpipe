from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import pytest

from src.profiles.profile_schema import Profile, ProfileConfig
from src.profiles.profile_store import (
    ProfileRevisionConflictError,
    load_profiles,
    rewrite_profiles_config,
    save_profiles_snapshot,
    upsert_profile,
)


def test_save_profiles_handles_parallel_writes_without_temp_path_collision(tmp_path):
    path = tmp_path / "config" / "profiles.yaml"
    config_a = ProfileConfig(
        profiles=[
            Profile(
                id="alpha",
                title="Alpha",
            )
        ]
    )
    config_b = ProfileConfig(
        profiles=[
            Profile(
                id="beta",
                title="Beta",
            )
        ]
    )

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(save_profiles_snapshot, config_a, path),
            pool.submit(save_profiles_snapshot, config_b, path),
        ]
        for future in futures:
            future.result()

    loaded = load_profiles(path)
    assert len(loaded.profiles) == 1
    assert loaded.profiles[0].id in {"alpha", "beta"}


def test_upsert_profile_preserves_unrelated_entries_across_parallel_writes(tmp_path):
    path = tmp_path / "config" / "profiles.yaml"
    alpha = Profile(id="alpha", title="Alpha")
    beta = Profile(id="beta", title="Beta")

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(upsert_profile, alpha, path),
            pool.submit(upsert_profile, beta, path),
        ]
        for future in futures:
            future.result()

    loaded = load_profiles(path)
    ids = {profile.id for profile in loaded.profiles}
    assert ids == {"alpha", "beta"}


def test_update_profiles_uses_lock_and_latest_file_state(tmp_path):
    path = tmp_path / "config" / "profiles.yaml"
    save_profiles_snapshot(ProfileConfig(profiles=[Profile(id="alpha", title="Alpha")]), path)

    def add_beta(config: ProfileConfig) -> ProfileConfig:
        config.profiles.append(Profile(id="beta", title="Beta"))
        return config

    def add_gamma(config: ProfileConfig) -> ProfileConfig:
        config.profiles.append(Profile(id="gamma", title="Gamma"))
        return config

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(rewrite_profiles_config, add_beta, path),
            pool.submit(rewrite_profiles_config, add_gamma, path),
        ]
        for future in futures:
            future.result()

    loaded = load_profiles(path)
    ids = {profile.id for profile in loaded.profiles}
    assert ids == {"alpha", "beta", "gamma"}


def test_upsert_profile_rejects_stale_parallel_same_profile_update(tmp_path):
    path = tmp_path / "config" / "profiles.yaml"
    upsert_profile(Profile(id="alpha", title="Alpha"), path)
    current = load_profiles(path).profiles[0]

    candidate_a = current.model_copy(update={"title": "Alpha A"})
    candidate_b = current.model_copy(update={"title": "Alpha B"})

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(upsert_profile, candidate_a, path, expected_revision=current.revision),
            pool.submit(upsert_profile, candidate_b, path, expected_revision=current.revision),
        ]

    results = []
    errors = []
    for future in futures:
        try:
            results.append(future.result())
        except ProfileRevisionConflictError as exc:
            errors.append(exc)

    assert len(results) == 1
    assert len(errors) == 1

    loaded = load_profiles(path)
    assert len(loaded.profiles) == 1
    assert loaded.profiles[0].id == "alpha"
    assert loaded.profiles[0].revision == 1
    assert loaded.profiles[0].title in {"Alpha A", "Alpha B"}


def test_save_profiles_snapshot_blocks_operator_path_raw_overwrite(tmp_path, monkeypatch):
    path = tmp_path / "config" / "profiles.yaml"
    monkeypatch.setenv("PAPERPIPE_PROFILES_PATH", str(path))

    with pytest.raises(ValueError, match="Raw save_profiles_snapshot\\(\\) overwrite is blocked"):
        save_profiles_snapshot(ProfileConfig(profiles=[Profile(id="alpha", title="Alpha")]), path)

    save_profiles_snapshot(
        ProfileConfig(profiles=[Profile(id="alpha", title="Alpha")]),
        path,
        allow_unsafe_overwrite=True,
    )
    loaded = load_profiles(path)
    assert loaded.profiles[0].id == "alpha"


def test_rewrite_profiles_config_blocks_operator_path_bulk_mutation_without_explicit_opt_in(tmp_path, monkeypatch):
    path = tmp_path / "config" / "profiles.yaml"
    monkeypatch.setenv("PAPERPIPE_PROFILES_PATH", str(path))
    save_profiles_snapshot(
        ProfileConfig(profiles=[Profile(id="alpha", title="Alpha")]),
        path,
        allow_unsafe_overwrite=True,
    )

    with pytest.raises(ValueError, match="Bulk rewrite_profiles_config\\(\\) mutation is blocked"):
        rewrite_profiles_config(lambda config: config, path)

    updated = rewrite_profiles_config(
        lambda config: ProfileConfig(
            profiles=[*config.profiles, Profile(id="beta", title="Beta")]
        ),
        path,
        allow_operator_bulk_update=True,
    )
    ids = {profile.id for profile in updated.profiles}
    assert ids == {"alpha", "beta"}


def test_upsert_profile_allows_operator_path_single_profile_write(tmp_path, monkeypatch):
    path = tmp_path / "config" / "profiles.yaml"
    monkeypatch.setenv("PAPERPIPE_PROFILES_PATH", str(path))

    created = upsert_profile(Profile(id="alpha", title="Alpha"), path)
    assert created.profiles[0].id == "alpha"
    assert created.profiles[0].revision == 0

    updated = upsert_profile(
        created.profiles[0].model_copy(update={"title": "Alpha v2"}),
        path,
        expected_revision=0,
    )
    assert updated.profiles[0].title == "Alpha v2"
    assert updated.profiles[0].revision == 1
