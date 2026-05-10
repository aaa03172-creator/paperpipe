from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, TypeVar, cast

from src.schemas.project_memory import ProjectMemoryItem, ProjectMemoryWorkspace
from src.services.artifact_transactions import (
    atomic_write_text,
    optional_text,
    remove_empty_dir,
    restore_optional_text,
)
from src.services.event_log import sanitize_event_payload_for_log
from src.services.runtime_paths import project_memory_root as default_project_memory_root


TProjectMemoryModel = TypeVar("TProjectMemoryModel", ProjectMemoryItem, ProjectMemoryWorkspace)
_SAFE_SEGMENT_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,159}$")


def project_memory_dir(project_id: str, root: Path | None = None) -> Path:
    base = (root or default_project_memory_root()).expanduser().resolve()
    safe_project_id = _normalize_project_id(project_id)
    return _confined_child(base, safe_project_id)


def project_workspace_json_path(project_id: str, root: Path | None = None) -> Path:
    return project_memory_dir(project_id, root) / "project.json"


def project_memory_jsonl_path(project_id: str, root: Path | None = None) -> Path:
    return project_memory_dir(project_id, root) / "memory.jsonl"


def save_project_memory_workspace(workspace: ProjectMemoryWorkspace, root: Path | None = None) -> Path:
    workspace = sanitize_project_memory_model(workspace)
    path = project_workspace_json_path(workspace.project_id, root)
    payload = json.dumps(workspace.model_dump(mode="json", exclude_none=True), ensure_ascii=False, indent=2)
    _atomic_write_text(path, payload)
    return path


def load_project_memory_workspace(project_id: str, root: Path | None = None) -> ProjectMemoryWorkspace:
    path = project_workspace_json_path(project_id, root)
    if not path.exists():
        raise FileNotFoundError(f"Project Memory workspace JSON not found: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return sanitize_project_memory_model(ProjectMemoryWorkspace(**payload))
    except Exception as exc:
        raise ValueError(f"Failed to load Project Memory workspace from {path}: {exc}") from exc


def save_project_memory_items(
    project_id: str,
    items: list[ProjectMemoryItem],
    root: Path | None = None,
) -> Path:
    _require_workspace_exists(project_id, root)
    items = [sanitize_project_memory_model(item) for item in items]
    _validate_project_items(project_id, items)
    path = project_memory_jsonl_path(project_id, root)
    lines = [
        json.dumps(item.model_dump(mode="json", exclude_none=True), ensure_ascii=False)
        for item in items
    ]
    payload = "\n".join(lines)
    if lines:
        payload = f"{payload}\n"
    _atomic_write_text(path, payload)
    return path


def append_project_memory_item(item: ProjectMemoryItem, root: Path | None = None) -> Path:
    _require_workspace_exists(item.project_id, root)
    path = project_memory_jsonl_path(item.project_id, root)
    items = load_project_memory_items(item.project_id, root) if path.exists() else []
    items.append(item)
    return save_project_memory_items(item.project_id, items, root)


def load_project_memory_items(project_id: str, root: Path | None = None) -> list[ProjectMemoryItem]:
    path = project_memory_jsonl_path(project_id, root)
    if not path.exists():
        raise FileNotFoundError(f"Project Memory items JSONL not found: {path}")
    try:
        items: list[ProjectMemoryItem] = []
        for raw_line in path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line:
                continue
            items.append(sanitize_project_memory_model(ProjectMemoryItem(**json.loads(line))))
        return items
    except Exception as exc:
        raise ValueError(f"Failed to load Project Memory items from {path}: {exc}") from exc


def save_project_memory_bundle(
    workspace: ProjectMemoryWorkspace,
    items: list[ProjectMemoryItem],
    root: Path | None = None,
) -> tuple[Path, Path]:
    workspace = sanitize_project_memory_model(workspace)
    items = [sanitize_project_memory_model(item) for item in items]
    _validate_project_items(workspace.project_id, items)
    json_path = project_workspace_json_path(workspace.project_id, root)
    jsonl_path = project_memory_jsonl_path(workspace.project_id, root)
    previous_workspace = _optional_text(json_path)
    previous_items = _optional_text(jsonl_path)

    workspace_payload = json.dumps(workspace.model_dump(mode="json", exclude_none=True), ensure_ascii=False, indent=2)
    item_lines = [
        json.dumps(item.model_dump(mode="json", exclude_none=True), ensure_ascii=False)
        for item in items
    ]
    items_payload = "\n".join(item_lines)
    if item_lines:
        items_payload = f"{items_payload}\n"

    try:
        _atomic_write_text(json_path, workspace_payload)
        _atomic_write_text(jsonl_path, items_payload)
    except Exception:
        _restore_optional_text(json_path, previous_workspace)
        _restore_optional_text(jsonl_path, previous_items)
        _remove_empty_dir(json_path.parent)
        raise
    return json_path, jsonl_path


def list_project_memory_ids(root: Path | None = None) -> list[str]:
    base = (root or default_project_memory_root()).expanduser().resolve()
    if not base.exists():
        return []
    return sorted(
        entry.name
        for entry in base.iterdir()
        if entry.is_dir() and project_workspace_json_path(entry.name, root).exists()
    )


def sanitize_project_memory_payload(payload: dict[str, Any]) -> dict[str, Any]:
    sanitized = sanitize_event_payload_for_log(payload)
    if isinstance(sanitized, dict):
        return sanitized
    return {}


def sanitize_project_memory_model(model: TProjectMemoryModel) -> TProjectMemoryModel:
    payload = sanitize_project_memory_payload(model.model_dump(mode="json", exclude_none=True))
    return cast(TProjectMemoryModel, model.__class__.model_validate(payload))


def _validate_project_items(project_id: str, items: list[ProjectMemoryItem]) -> None:
    mismatched = sorted({item.project_id for item in items if item.project_id != project_id})
    if mismatched:
        raise ValueError(
            f"Project Memory items must match workspace project_id {project_id}: {', '.join(mismatched)}"
        )
    seen_item_ids: set[str] = set()
    duplicate_item_ids: set[str] = set()
    for item in items:
        if item.item_id in seen_item_ids:
            duplicate_item_ids.add(item.item_id)
        seen_item_ids.add(item.item_id)
    if duplicate_item_ids:
        raise ValueError(
            "Project Memory items must not contain duplicate item_id values: "
            + ", ".join(sorted(duplicate_item_ids))
        )


def _require_workspace_exists(project_id: str, root: Path | None = None) -> None:
    path = project_workspace_json_path(project_id, root)
    if not path.exists():
        raise FileNotFoundError(f"Project Memory workspace JSON not found: {path}")


def _atomic_write_text(path: Path, content: str) -> None:
    atomic_write_text(path, content, error_context="Project Memory file")


def _optional_text(path: Path) -> str | None:
    return optional_text(path)


def _restore_optional_text(path: Path, content: str | None) -> None:
    restore_optional_text(path, content, writer=_atomic_write_text)


def _remove_empty_dir(path: Path) -> None:
    remove_empty_dir(path)


def _normalize_project_id(value: str) -> str:
    text = str(value or "").strip()
    if not text or not _SAFE_SEGMENT_RE.fullmatch(text):
        raise ValueError("Project Memory project_id must be a single safe path segment")
    return text


def _confined_child(base: Path, safe_segment: str) -> Path:
    candidate = (base / safe_segment).resolve()
    try:
        candidate.relative_to(base)
    except ValueError as exc:
        raise ValueError("Project Memory project_id escapes storage root") from exc
    return candidate
