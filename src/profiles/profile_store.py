import yaml
import os
import tempfile
from collections.abc import Callable
from contextlib import contextmanager
from pathlib import Path
from typing import List

import fcntl

from src.profiles.profile_schema import ProfileConfig, Profile
from src.services.runtime_paths import profiles_config_path


class ProfileRevisionConflictError(ValueError):
    pass


# Backward-compatible alias kept for older callers/tests that still import the
# default profiles path constant directly.
DEFAULT_PROFILE_PATH = profiles_config_path()


def load_profiles(path: Path | None = None) -> ProfileConfig:
    """Safely loads profiles from YAML."""
    path = _resolve_profiles_path(path)
    if not path.exists():
        # Return empty config if file doesn't exist
        return ProfileConfig()
    
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
            
        # Pydantic Validation
        return ProfileConfig(**data)
    except Exception as e:
        # Fallback or re-raise? For strictness, re-raise.
        raise ValueError(f"Failed to load profiles from {path}: {e}")

def save_profiles_snapshot(
    config: ProfileConfig,
    path: Path | None = None,
    *,
    allow_unsafe_overwrite: bool = False,
):
    """
    Atomically saves profiles to YAML.
    1. Write to temp file.
    2. Move to target path.
    """
    path = _resolve_profiles_path(path)
    if _is_operator_profiles_path(path) and not allow_unsafe_overwrite:
        raise ValueError(
            "Raw save_profiles_snapshot() overwrite is blocked for the operator-facing profiles path. "
            "Use rewrite_profiles_config() or upsert_profile() instead."
        )
    _write_profiles_atomic(config, path)


def rewrite_profiles_config(
    mutator: Callable[[ProfileConfig], ProfileConfig],
    path: Path | None = None,
    *,
    allow_operator_bulk_update: bool = False,
) -> ProfileConfig:
    path = _resolve_profiles_path(path)
    if _is_operator_profiles_path(path) and not allow_operator_bulk_update:
        raise ValueError(
            "Bulk rewrite_profiles_config() mutation is blocked for the operator-facing profiles path. "
            "Use upsert_profile() for single-profile writes, or pass allow_operator_bulk_update=True "
            "for explicit system-owned config rewrites."
        )
    with _profiles_lock(path):
        current = load_profiles(path)
        updated = mutator(current.model_copy(deep=True))
        _write_profiles_atomic(updated, path)
        return updated


def upsert_profile(
    profile: Profile,
    path: Path | None = None,
    *,
    expected_revision: int | None = None,
) -> ProfileConfig:
    def _mutate(config: ProfileConfig) -> ProfileConfig:
        stored_profile = profile.model_copy(deep=True)
        for idx, existing in enumerate(config.profiles):
            if existing.id == profile.id:
                if expected_revision is not None and existing.revision != expected_revision:
                    raise ProfileRevisionConflictError(
                        f"Revision conflict for profile {profile.id}: "
                        f"expected {expected_revision}, current {existing.revision}"
                    )
                stored_profile.revision = existing.revision + 1
                config.profiles[idx] = stored_profile
                return config

        if expected_revision is not None:
            raise ProfileRevisionConflictError(
                f"Revision conflict for profile {profile.id}: "
                f"expected existing revision {expected_revision}, but profile was not found"
            )

        stored_profile.revision = 0
        config.profiles.append(stored_profile)
        return config

    return rewrite_profiles_config(_mutate, path, allow_operator_bulk_update=True)


def _resolve_profiles_path(path: Path | None) -> Path:
    return (path or profiles_config_path()).expanduser().resolve()


def _is_operator_profiles_path(path: Path) -> bool:
    return path == profiles_config_path()


@contextmanager
def _profiles_lock(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = path.with_name(f"{path.name}.lock")
    with open(lock_path, "a+", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _write_profiles_atomic(config: ProfileConfig, path: Path) -> None:
    temp_path = None
    
    try:
        # Dump to dict using Pydantic
        data = config.model_dump(exclude_none=True)
        
        # Ensure directory exists
        path.parent.mkdir(parents=True, exist_ok=True)

        fd, temp_name = tempfile.mkstemp(
            prefix=f".{path.stem}.",
            suffix=f"{path.suffix}.tmp",
            dir=str(path.parent),
        )
        os.close(fd)
        temp_path = Path(temp_name)

        with open(temp_path, "w", encoding="utf-8") as f:
            yaml.dump(data, f, sort_keys=False, allow_unicode=True)
            
        # Atomic replace
        os.replace(temp_path, path)
        
    except Exception as e:
        if temp_path and temp_path.exists():
            os.remove(temp_path)
        raise IOError(f"Failed to save profiles to {path}: {e}")
