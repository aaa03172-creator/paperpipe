from __future__ import annotations

import json
import re
from pathlib import Path

from src.schemas.paper_synthesis import PaperSynthesis
from src.services.artifact_transactions import (
    atomic_write_text,
    optional_text,
    remove_empty_dir,
    restore_optional_text,
)
from src.services.runtime_paths import paper_syntheses_root as default_paper_syntheses_root

_SAFE_SEGMENT_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,159}$")


def paper_synthesis_dir(synthesis_id: str, root: Path | None = None) -> Path:
    base = (root or default_paper_syntheses_root()).expanduser().resolve()
    safe_synthesis_id = _normalize_synthesis_id(synthesis_id)
    return _confined_child(base, safe_synthesis_id)


def paper_synthesis_json_path(synthesis_id: str, root: Path | None = None) -> Path:
    return paper_synthesis_dir(synthesis_id, root) / "paper_synthesis.json"


def paper_synthesis_markdown_path(synthesis_id: str, root: Path | None = None) -> Path:
    return paper_synthesis_dir(synthesis_id, root) / "paper_synthesis.md"


def save_paper_synthesis(synthesis: PaperSynthesis, root: Path | None = None) -> Path:
    path = paper_synthesis_json_path(synthesis.synthesis_id, root)
    payload = json.dumps(synthesis.model_dump(mode="json", exclude_none=True), ensure_ascii=False, indent=2)
    _atomic_write_text(path, payload)
    return path


def load_paper_synthesis(synthesis_id: str, root: Path | None = None) -> PaperSynthesis:
    path = paper_synthesis_json_path(synthesis_id, root)
    if not path.exists():
        raise FileNotFoundError(f"Paper synthesis JSON not found: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return PaperSynthesis(**payload)
    except Exception as exc:
        raise ValueError(f"Failed to load Paper synthesis from {path}: {exc}") from exc


def save_paper_synthesis_markdown(synthesis_id: str, markdown: str, root: Path | None = None) -> Path:
    path = paper_synthesis_markdown_path(synthesis_id, root)
    _atomic_write_text(path, markdown)
    return path


def load_paper_synthesis_markdown(synthesis_id: str, root: Path | None = None) -> str:
    path = paper_synthesis_markdown_path(synthesis_id, root)
    if not path.exists():
        raise FileNotFoundError(f"Paper synthesis markdown not found: {path}")
    return path.read_text(encoding="utf-8")


def save_paper_synthesis_bundle(
    synthesis: PaperSynthesis,
    markdown: str,
    root: Path | None = None,
) -> tuple[Path, Path]:
    json_path = paper_synthesis_json_path(synthesis.synthesis_id, root)
    markdown_path = paper_synthesis_markdown_path(synthesis.synthesis_id, root)

    previous_json = _optional_text(json_path)
    previous_markdown = _optional_text(markdown_path)
    payload = json.dumps(synthesis.model_dump(mode="json", exclude_none=True), ensure_ascii=False, indent=2)

    try:
        _atomic_write_text(json_path, payload)
        _atomic_write_text(markdown_path, markdown)
    except Exception:
        _restore_optional_text(json_path, previous_json)
        _restore_optional_text(markdown_path, previous_markdown)
        _remove_empty_dir(json_path.parent)
        raise
    return json_path, markdown_path


def list_paper_synthesis_ids(root: Path | None = None) -> list[str]:
    base = (root or default_paper_syntheses_root()).expanduser().resolve()
    if not base.exists():
        return []
    return sorted(entry.name for entry in base.iterdir() if entry.is_dir())


def _atomic_write_text(path: Path, content: str) -> None:
    atomic_write_text(path, content, error_context="Paper synthesis file")


def _optional_text(path: Path) -> str | None:
    return optional_text(path)


def _restore_optional_text(path: Path, content: str | None) -> None:
    restore_optional_text(path, content, writer=_atomic_write_text)


def _remove_empty_dir(path: Path) -> None:
    remove_empty_dir(path)


def _normalize_synthesis_id(value: str) -> str:
    text = str(value or "").strip()
    if not text or not _SAFE_SEGMENT_RE.fullmatch(text):
        raise ValueError("Paper Synthesis synthesis_id must be a single safe path segment")
    return text


def _confined_child(base: Path, safe_segment: str) -> Path:
    candidate = (base / safe_segment).resolve()
    try:
        candidate.relative_to(base)
    except ValueError as exc:
        raise ValueError("Paper Synthesis synthesis_id escapes storage root") from exc
    return candidate
