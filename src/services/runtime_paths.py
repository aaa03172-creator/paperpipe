from __future__ import annotations

import os
from pathlib import Path

from src.services.identity import artifact_paper_segment


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
    if os.getenv("PAPERPIPE_HOME"):
        return (paperpipe_home() / "storage").resolve()
    return Path("storage").resolve()


def state_db_path() -> Path:
    value = os.getenv("PAPERPIPE_DB_PATH")
    if value:
        return Path(value).expanduser().resolve()
    return (storage_root() / "state.db").resolve()


def config_file_path(config_path: str | Path = "config.yaml") -> Path:
    value = os.getenv("PAPERPIPE_CONFIG_PATH")
    raw = value if value else config_path
    return Path(raw).expanduser().resolve()


def artifacts_root() -> Path:
    value = os.getenv("PAPERPIPE_ARTIFACTS_DIR")
    if value:
        return Path(value).expanduser().resolve()
    return (storage_root() / "artifacts").resolve()


def artifact_paper_dir(paper_id: str) -> Path:
    return artifacts_root() / artifact_paper_segment(paper_id)


def artifact_run_dir(paper_id: str, run_id: str) -> Path:
    return artifact_paper_dir(paper_id) / str(run_id)


def goldset_root() -> Path:
    value = os.getenv("PAPERPIPE_GOLDSET_DIR")
    if value:
        return Path(value).expanduser().resolve()
    return (paperpipe_home() / "goldset").resolve()


def research_dna_root() -> Path:
    value = os.getenv("PAPERPIPE_RESEARCH_DNA_DIR")
    if value:
        return Path(value).expanduser().resolve()
    return (paperpipe_home() / "research_dna").resolve()


def search_eval_root() -> Path:
    value = os.getenv("PAPERPIPE_SEARCH_EVAL_DIR")
    if value:
        return Path(value).expanduser().resolve()
    return (storage_root() / "search_eval").resolve()


def meeting_packs_root() -> Path:
    value = os.getenv("PAPERPIPE_MEETING_PACKS_DIR")
    if value:
        return Path(value).expanduser().resolve()
    return (storage_root() / "meeting_packs").resolve()


def profiles_config_path() -> Path:
    value = os.getenv("PAPERPIPE_PROFILES_PATH")
    if value:
        return Path(value).expanduser().resolve()
    if os.getenv("PAPERPIPE_CONFIG_PATH"):
        config_path = config_file_path()
        candidates = [
            (config_path.parent / "config" / "profiles.yaml").resolve(),
            config_path.with_name("profiles.yaml").resolve(),
        ]
        for candidate in candidates:
            if candidate.exists():
                return candidate
        return candidates[0]
    cwd_candidate = (Path.cwd() / "config" / "profiles.yaml").resolve()
    if cwd_candidate.exists():
        return cwd_candidate
    return (paperpipe_home() / "config" / "profiles.yaml").resolve()
