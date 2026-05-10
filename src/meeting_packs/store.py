from __future__ import annotations

import json
import re
from pathlib import Path

from src.schemas.meeting_pack import MeetingPack
from src.services.artifact_transactions import (
    atomic_write_text,
    optional_text,
    remove_empty_dir,
    restore_optional_text,
)
from src.services.runtime_paths import meeting_packs_root as default_meeting_packs_root

_SAFE_SEGMENT_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,159}$")
_ARTIFACT_FILENAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,159}\.[A-Za-z0-9][A-Za-z0-9._-]{0,31}$")


def meeting_pack_dir(pack_id: str, root: Path | None = None) -> Path:
    base = (root or default_meeting_packs_root()).expanduser().resolve()
    safe_pack_id = _normalize_safe_segment(pack_id, pattern=_SAFE_SEGMENT_RE, field_name="pack_id")
    return _confined_child(base, safe_pack_id, field_name="pack_id")


def meeting_pack_json_path(pack_id: str, root: Path | None = None) -> Path:
    return meeting_pack_dir(pack_id, root) / "meeting_pack.json"


def meeting_pack_markdown_path(pack_id: str, root: Path | None = None) -> Path:
    return meeting_pack_dir(pack_id, root) / "meeting_pack.md"


def meeting_pack_artifact_path(pack_id: str, filename: str, root: Path | None = None) -> Path:
    safe_filename = _normalize_safe_segment(filename, pattern=_ARTIFACT_FILENAME_RE, field_name="filename")
    return meeting_pack_dir(pack_id, root) / safe_filename


def save_meeting_pack(pack: MeetingPack, root: Path | None = None) -> Path:
    path = meeting_pack_json_path(pack.id, root)
    payload = json.dumps(pack.model_dump(mode="json", exclude_none=True), ensure_ascii=False, indent=2)
    _atomic_write_text(path, payload)
    return path


def load_meeting_pack(pack_id: str, root: Path | None = None) -> MeetingPack:
    path = meeting_pack_json_path(pack_id, root)
    if not path.exists():
        raise FileNotFoundError(f"Meeting Pack JSON not found: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return MeetingPack(**payload)
    except Exception as exc:
        raise ValueError(f"Failed to load Meeting Pack from {path}: {exc}") from exc


def save_meeting_pack_markdown(pack_id: str, markdown: str, root: Path | None = None) -> Path:
    path = meeting_pack_markdown_path(pack_id, root)
    _atomic_write_text(path, markdown)
    return path


def save_meeting_pack_artifact_json(
    pack_id: str,
    filename: str,
    payload: dict[str, object],
    root: Path | None = None,
) -> Path:
    path = meeting_pack_artifact_path(pack_id, filename, root)
    _atomic_write_text(path, json.dumps(payload, ensure_ascii=False, indent=2))
    return path


def load_meeting_pack_markdown(pack_id: str, root: Path | None = None) -> str:
    path = meeting_pack_markdown_path(pack_id, root)
    if not path.exists():
        raise FileNotFoundError(f"Meeting Pack markdown not found: {path}")
    return path.read_text(encoding="utf-8")


def save_meeting_pack_bundle(pack: MeetingPack, markdown: str, root: Path | None = None) -> tuple[Path, Path]:
    json_path = meeting_pack_json_path(pack.id, root)
    markdown_path = meeting_pack_markdown_path(pack.id, root)
    previous_json = _optional_text(json_path)
    previous_markdown = _optional_text(markdown_path)
    payload = json.dumps(pack.model_dump(mode="json", exclude_none=True), ensure_ascii=False, indent=2)

    try:
        _atomic_write_text(json_path, payload)
        _atomic_write_text(markdown_path, markdown)
    except Exception:
        _restore_optional_text(json_path, previous_json)
        _restore_optional_text(markdown_path, previous_markdown)
        _remove_empty_dir(json_path.parent)
        raise
    return json_path, markdown_path


def list_meeting_pack_ids(root: Path | None = None) -> list[str]:
    base = (root or default_meeting_packs_root()).expanduser().resolve()
    if not base.exists():
        return []
    return sorted(entry.name for entry in base.iterdir() if entry.is_dir())


def _atomic_write_text(path: Path, content: str) -> None:
    atomic_write_text(path, content, error_context="Meeting Pack file")


def _optional_text(path: Path) -> str | None:
    return optional_text(path)


def _restore_optional_text(path: Path, content: str | None) -> None:
    restore_optional_text(path, content, writer=_atomic_write_text)


def _remove_empty_dir(path: Path) -> None:
    remove_empty_dir(path)


def _normalize_safe_segment(value: str, *, pattern: re.Pattern[str], field_name: str) -> str:
    text = str(value or "").strip()
    if not text or not pattern.fullmatch(text):
        raise ValueError(f"Meeting Pack {field_name} must be a single safe path segment")
    return text


def _confined_child(base: Path, safe_segment: str, *, field_name: str) -> Path:
    candidate = (base / safe_segment).resolve()
    try:
        candidate.relative_to(base)
    except ValueError as exc:
        raise ValueError(f"Meeting Pack {field_name} escapes storage root") from exc
    return candidate
