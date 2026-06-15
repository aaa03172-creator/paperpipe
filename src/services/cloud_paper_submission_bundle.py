from __future__ import annotations

import os
from pathlib import Path
import sys

from pydantic import ValidationError

from src.schemas.cloud_paper import (
    CloudPaperBundlePublic,
    CloudPaperDerivedArtifactsResponse,
    CloudPaperPageArtifactPublic,
)


def submission_demo_enabled() -> bool:
    return str(os.getenv("PAPERPIPE_SUBMISSION_DEMO_BUNDLE") or "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _resource_candidates() -> list[Path]:
    candidates: list[Path] = []
    env_dir = os.getenv("PAPERPIPE_SUBMISSION_DEMO_BUNDLE_DIR")
    if env_dir:
        candidates.append(Path(env_dir).expanduser())

    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        candidates.append(Path(str(meipass)) / "submission_demo")

    executable = Path(sys.executable).resolve()
    candidates.append(executable.parent.parent / "Resources" / "submission_demo")
    candidates.append(Path.cwd() / "submission_demo")
    candidates.append(Path(__file__).resolve().parents[2] / "packaging" / "submission_demo")
    return candidates


def submission_demo_root() -> Path | None:
    for candidate in _resource_candidates():
        if (candidate / "cloud_papers").is_dir():
            return candidate
    return None


def _paper_dir(root: Path, paper_id: str) -> Path:
    return root / "cloud_papers" / paper_id


def _load_model(model_type, path: Path):
    try:
        return model_type.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValidationError, ValueError):
        return None


def list_submission_demo_bundles() -> list[CloudPaperBundlePublic]:
    root = submission_demo_root()
    if root is None:
        return []

    bundles: list[CloudPaperBundlePublic] = []
    for paper_dir in sorted((root / "cloud_papers").iterdir()):
        if not paper_dir.is_dir():
            continue
        bundle = _load_model(CloudPaperBundlePublic, paper_dir / "bundle.json")
        if bundle is not None:
            bundles.append(bundle)
    return bundles


def get_submission_demo_bundle(paper_id: str) -> CloudPaperBundlePublic | None:
    root = submission_demo_root()
    if root is None:
        return None
    return _load_model(CloudPaperBundlePublic, _paper_dir(root, paper_id) / "bundle.json")


def get_submission_demo_page(paper_id: str) -> CloudPaperPageArtifactPublic | None:
    root = submission_demo_root()
    if root is None:
        return None
    return _load_model(CloudPaperPageArtifactPublic, _paper_dir(root, paper_id) / "page.json")


def get_submission_demo_derived_artifacts(paper_id: str) -> CloudPaperDerivedArtifactsResponse | None:
    root = submission_demo_root()
    if root is None:
        return None
    return _load_model(CloudPaperDerivedArtifactsResponse, _paper_dir(root, paper_id) / "derived.json")
