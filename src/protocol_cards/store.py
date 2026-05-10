from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path

from src.schemas.protocol_card import ProtocolCard, ProtocolVersion
from src.services.runtime_paths import protocol_cards_root as default_protocol_cards_root

_SAFE_SEGMENT_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,159}$")


def protocol_card_dir(protocol_id: str, root: Path | None = None) -> Path:
    base = (root or default_protocol_cards_root()).expanduser().resolve()
    safe_protocol_id = _normalize_safe_segment(protocol_id, pattern=_SAFE_SEGMENT_RE, field_name="protocol_id")
    return _confined_child(base, safe_protocol_id, field_name="protocol_id")


def protocol_card_json_path(protocol_id: str, root: Path | None = None) -> Path:
    return protocol_card_dir(protocol_id, root) / "protocol_card.json"


def protocol_card_markdown_path(protocol_id: str, root: Path | None = None) -> Path:
    return protocol_card_dir(protocol_id, root) / "protocol_card.md"


def protocol_card_versions_dir(protocol_id: str, root: Path | None = None) -> Path:
    return protocol_card_dir(protocol_id, root) / "versions"


def protocol_card_version_json_path(
    protocol_id: str,
    version_id: str,
    root: Path | None = None,
) -> Path:
    safe_version_id = _normalize_safe_segment(version_id, pattern=_SAFE_SEGMENT_RE, field_name="version_id")
    return protocol_card_versions_dir(protocol_id, root) / f"{safe_version_id}.json"


def save_protocol_card(protocol_card: ProtocolCard, root: Path | None = None) -> Path:
    path = protocol_card_json_path(protocol_card.protocol_id, root)
    payload = json.dumps(protocol_card.model_dump(mode="json", exclude_none=True), ensure_ascii=False, indent=2)
    _atomic_write_text(path, payload)
    return path


def load_protocol_card(protocol_id: str, root: Path | None = None) -> ProtocolCard:
    path = protocol_card_json_path(protocol_id, root)
    if not path.exists():
        raise FileNotFoundError(f"Protocol Card JSON not found: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return ProtocolCard(**payload)
    except Exception as exc:
        raise ValueError(f"Failed to load Protocol Card from {path}: {exc}") from exc


def save_protocol_card_markdown(protocol_id: str, markdown: str, root: Path | None = None) -> Path:
    path = protocol_card_markdown_path(protocol_id, root)
    _atomic_write_text(path, markdown)
    return path


def load_protocol_card_markdown(protocol_id: str, root: Path | None = None) -> str:
    path = protocol_card_markdown_path(protocol_id, root)
    if not path.exists():
        raise FileNotFoundError(f"Protocol Card markdown not found: {path}")
    return path.read_text(encoding="utf-8")


def save_protocol_version(protocol_version: ProtocolVersion, root: Path | None = None) -> Path:
    path = protocol_card_version_json_path(protocol_version.protocol_id, protocol_version.version_id, root)
    payload = json.dumps(protocol_version.model_dump(mode="json", exclude_none=True), ensure_ascii=False, indent=2)
    _atomic_write_text(path, payload)
    return path


def load_protocol_version(
    protocol_id: str,
    version_id: str,
    root: Path | None = None,
) -> ProtocolVersion:
    path = protocol_card_version_json_path(protocol_id, version_id, root)
    if not path.exists():
        raise FileNotFoundError(f"Protocol Version JSON not found: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return ProtocolVersion(**payload)
    except Exception as exc:
        raise ValueError(f"Failed to load Protocol Version from {path}: {exc}") from exc


def load_protocol_versions(protocol_id: str, root: Path | None = None) -> list[ProtocolVersion]:
    versions_dir = protocol_card_versions_dir(protocol_id, root)
    if not versions_dir.exists():
        return []
    versions = [
        load_protocol_version(protocol_id, path.stem, root)
        for path in sorted(versions_dir.glob("*.json"))
        if path.is_file()
    ]
    return sorted(versions, key=lambda item: (item.version_number, item.created_at, item.version_id))


def save_protocol_card_bundle(
    protocol_card: ProtocolCard,
    markdown: str,
    *,
    versions: list[ProtocolVersion] | None = None,
    root: Path | None = None,
) -> dict[str, Path]:
    versions = list(versions or [])
    summary_ids = {summary.version_id for summary in protocol_card.version_summaries}
    version_ids = {version.version_id for version in versions}
    missing_versions = sorted(summary_ids - version_ids)
    extra_versions = sorted(version_ids - summary_ids)
    if missing_versions:
        raise ValueError(f"Missing version payload(s) for summary id(s): {', '.join(missing_versions)}")
    if extra_versions:
        raise ValueError(f"Unknown version payload(s): {', '.join(extra_versions)}")

    json_path = protocol_card_json_path(protocol_card.protocol_id, root)
    markdown_path = protocol_card_markdown_path(protocol_card.protocol_id, root)
    version_paths = {
        version.version_id: protocol_card_version_json_path(protocol_card.protocol_id, version.version_id, root)
        for version in sorted(versions, key=lambda item: item.version_id)
    }
    expected_paths = {
        json_path,
        markdown_path,
        *version_paths.values(),
    }
    tracked_paths: dict[Path, str | None] = {
        path: _optional_text(path)
        for path in sorted(
            {
                *expected_paths,
                *_existing_managed_paths(protocol_card.protocol_id, root),
            },
            key=lambda item: str(item),
        )
    }

    payload = json.dumps(protocol_card.model_dump(mode="json", exclude_none=True), ensure_ascii=False, indent=2)
    try:
        _atomic_write_text(json_path, payload)
        _atomic_write_text(markdown_path, markdown)
        for version in sorted(versions, key=lambda item: item.version_id):
            version_payload = json.dumps(
                version.model_dump(mode="json", exclude_none=True),
                ensure_ascii=False,
                indent=2,
            )
            _atomic_write_text(version_paths[version.version_id], version_payload)
        for stale_path in sorted(set(tracked_paths) - expected_paths, key=lambda item: str(item)):
            if stale_path.exists():
                os.remove(stale_path)
        _remove_empty_dirs(
            protocol_card_versions_dir(protocol_card.protocol_id, root),
            stop_at=protocol_card_dir(protocol_card.protocol_id, root),
        )
    except Exception:
        for path, previous in tracked_paths.items():
            _restore_optional_text(path, previous)
        _remove_empty_dirs(
            protocol_card_dir(protocol_card.protocol_id, root),
            stop_at=(root or default_protocol_cards_root()).expanduser().resolve(),
        )
        raise

    result: dict[str, Path] = {
        "json": json_path,
        "markdown": markdown_path,
    }
    result.update({f"version:{version_id}": path for version_id, path in version_paths.items()})
    return result


def list_protocol_card_ids(root: Path | None = None) -> list[str]:
    base = (root or default_protocol_cards_root()).expanduser().resolve()
    if not base.exists():
        return []
    return sorted(entry.name for entry in base.iterdir() if entry.is_dir())


def _existing_managed_paths(protocol_id: str, root: Path | None = None) -> set[Path]:
    managed: set[Path] = set()
    for path in (
        protocol_card_json_path(protocol_id, root),
        protocol_card_markdown_path(protocol_id, root),
    ):
        if path.exists():
            managed.add(path)
    versions_dir = protocol_card_versions_dir(protocol_id, root)
    if versions_dir.exists():
        managed.update(path for path in versions_dir.glob("*.json") if path.is_file())
    return managed


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
        raise IOError(f"Failed to write Protocol Card file to {path}: {exc}") from exc


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


def _remove_empty_dirs(path: Path, *, stop_at: Path | None = None) -> None:
    current = path
    stop_path = stop_at.resolve() if stop_at is not None else None
    while current.exists() and current.is_dir() and not any(current.iterdir()):
        if stop_path is not None and current.resolve() == stop_path:
            break
        current.rmdir()
        if stop_path is not None and current.parent.resolve() == stop_path:
            break
        current = current.parent


def _normalize_safe_segment(value: str, *, pattern: re.Pattern[str], field_name: str) -> str:
    text = str(value or "").strip()
    if not text or not pattern.fullmatch(text):
        raise ValueError(f"Protocol Card {field_name} must be a single safe path segment")
    return text


def _confined_child(base: Path, safe_segment: str, *, field_name: str) -> Path:
    candidate = (base / safe_segment).resolve()
    try:
        candidate.relative_to(base)
    except ValueError as exc:
        raise ValueError(f"Protocol Card {field_name} escapes storage root") from exc
    return candidate
