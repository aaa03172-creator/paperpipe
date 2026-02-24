from __future__ import annotations

import os
from pathlib import Path


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def paperpipe_home() -> Path:
    value = os.getenv("PAPERPIPE_HOME")
    if value:
        return Path(value).expanduser().resolve()
    return repo_root()


def storage_root() -> Path:
    value = os.getenv("PAPERPIPE_STORAGE_DIR")
    if value:
        return Path(value).expanduser().resolve()
    return (paperpipe_home() / "storage").resolve()


def state_db_path() -> Path:
    value = os.getenv("PAPERPIPE_DB_PATH")
    if value:
        return Path(value).expanduser().resolve()
    return (storage_root() / "state.db").resolve()


def artifacts_root() -> Path:
    value = os.getenv("PAPERPIPE_ARTIFACTS_DIR")
    if value:
        return Path(value).expanduser().resolve()
    return (storage_root() / "artifacts").resolve()


def goldset_root() -> Path:
    value = os.getenv("PAPERPIPE_GOLDSET_DIR")
    if value:
        return Path(value).expanduser().resolve()
    return (paperpipe_home() / "goldset").resolve()
