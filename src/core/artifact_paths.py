from __future__ import annotations

import os
from pathlib import Path
from typing import Iterator, Optional

from src.core.paper_identity import make_paper_key


def get_artifacts_root() -> Path:
    env_root = os.getenv("PAPERPIPE_ARTIFACTS_DIR")
    if env_root:
        return Path(env_root).expanduser()
    return Path("storage") / "artifacts"


def resolve_paper_key(paper_id: str, paper_key: Optional[str] = None) -> str:
    key = str(paper_key or "").strip()
    if key:
        return key
    return make_paper_key(paper_id)


def build_paper_artifact_dir(paper_id: str, paper_key: Optional[str] = None) -> Path:
    return get_artifacts_root() / resolve_paper_key(paper_id, paper_key)


def build_legacy_paper_artifact_dir(paper_id: str) -> Path:
    return get_artifacts_root() / str(paper_id)


def build_artifact_dir(run_id: str, paper_id: str, paper_key: Optional[str] = None) -> Path:
    return build_paper_artifact_dir(paper_id=paper_id, paper_key=paper_key) / run_id


def iter_artifact_dir_candidates(
    run_id: str,
    paper_id: str,
    paper_key: Optional[str] = None,
) -> Iterator[Path]:
    primary = build_artifact_dir(run_id=run_id, paper_id=paper_id, paper_key=paper_key)
    yield primary
    legacy = build_legacy_paper_artifact_dir(paper_id=paper_id) / run_id
    if legacy != primary:
        yield legacy


def resolve_existing_artifact_dir(
    run_id: str,
    paper_id: str,
    paper_key: Optional[str] = None,
) -> Optional[Path]:
    for candidate in iter_artifact_dir_candidates(run_id=run_id, paper_id=paper_id, paper_key=paper_key):
        if candidate.exists():
            return candidate
    return None


def iter_paper_dir_candidates(paper_id: str, paper_key: Optional[str] = None) -> Iterator[Path]:
    primary = build_paper_artifact_dir(paper_id=paper_id, paper_key=paper_key)
    yield primary
    legacy = build_legacy_paper_artifact_dir(paper_id=paper_id)
    if legacy != primary:
        yield legacy
