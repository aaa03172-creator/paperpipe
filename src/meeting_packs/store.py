from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from src.schemas.meeting_pack import MeetingPack
from src.services.runtime_paths import meeting_packs_root as default_meeting_packs_root


def meeting_pack_dir(pack_id: str, root: Path | None = None) -> Path:
    base = (root or default_meeting_packs_root()).expanduser().resolve()
    return base / pack_id


def meeting_pack_json_path(pack_id: str, root: Path | None = None) -> Path:
    return meeting_pack_dir(pack_id, root) / "meeting_pack.json"


def meeting_pack_markdown_path(pack_id: str, root: Path | None = None) -> Path:
    return meeting_pack_dir(pack_id, root) / "meeting_pack.md"


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
    temp_path = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, temp_name = tempfile.mkstemp(
            prefix=f".{path.stem}.",
            suffix=f"{path.suffix}.tmp",
            dir=str(path.parent),
        )
        os.close(fd)
        temp_path = Path(temp_name)
        temp_path.write_text(content, encoding="utf-8")
        os.replace(temp_path, path)
    except Exception as exc:
        if temp_path and temp_path.exists():
            os.remove(temp_path)
        raise IOError(f"Failed to write Meeting Pack file to {path}: {exc}") from exc


def _optional_text(path: Path) -> str | None:
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8")


def _restore_optional_text(path: Path, content: str | None) -> None:
    if content is None:
        if path.exists():
            os.remove(path)
        return
    _atomic_write_text(path, content)


def _remove_empty_dir(path: Path) -> None:
    if path.exists() and path.is_dir() and not any(path.iterdir()):
        path.rmdir()
