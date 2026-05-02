from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from src.schemas.protocol_attachment import ProtocolAttachmentBundle
from src.services.runtime_paths import protocol_attachments_root as default_protocol_attachments_root


def protocol_attachment_dir(attachment_bundle_id: str, root: Path | None = None) -> Path:
    base = (root or default_protocol_attachments_root()).expanduser().resolve()
    return base / attachment_bundle_id


def protocol_attachment_json_path(attachment_bundle_id: str, root: Path | None = None) -> Path:
    return protocol_attachment_dir(attachment_bundle_id, root) / "attachment_bundle.json"


def protocol_attachment_source_path(
    attachment_bundle_id: str,
    relative_path: str,
    root: Path | None = None,
) -> Path:
    return _protocol_attachment_relative_path(attachment_bundle_id, relative_path, root)


def protocol_attachment_extracted_markdown_path(
    attachment_bundle_id: str,
    relative_path: str,
    root: Path | None = None,
) -> Path:
    return _protocol_attachment_relative_path(attachment_bundle_id, relative_path, root)


def save_protocol_attachment_bundle(
    attachment_bundle: ProtocolAttachmentBundle,
    *,
    source_bytes: bytes,
    extracted_markdown: str | None,
    root: Path | None = None,
) -> dict[str, Path]:
    json_path = protocol_attachment_json_path(attachment_bundle.attachment_bundle_id, root)
    source_path = protocol_attachment_source_path(
        attachment_bundle.attachment_bundle_id,
        attachment_bundle.source_ref.path,
        root,
    )
    markdown_path = (
        protocol_attachment_extracted_markdown_path(
            attachment_bundle.attachment_bundle_id,
            attachment_bundle.extracted_markdown_ref.path,
            root,
        )
        if attachment_bundle.extracted_markdown_ref is not None
        else None
    )
    tracked_paths = {
        path: _optional_bytes(path)
        for path in [json_path, source_path, *( [markdown_path] if markdown_path is not None else [] )]
    }

    payload = json.dumps(
        attachment_bundle.model_dump(mode="json", exclude_none=True),
        ensure_ascii=False,
        indent=2,
    ).encode("utf-8")
    try:
        _atomic_write_bytes(json_path, payload)
        _atomic_write_bytes(source_path, source_bytes)
        if markdown_path is not None and extracted_markdown is not None:
            _atomic_write_bytes(markdown_path, extracted_markdown.encode("utf-8"))
        elif markdown_path is not None and markdown_path.exists():
            os.remove(markdown_path)
    except Exception:
        for path, previous in tracked_paths.items():
            _restore_optional_bytes(path, previous)
        _remove_empty_dirs(
            protocol_attachment_dir(attachment_bundle.attachment_bundle_id, root),
            stop_at=(root or default_protocol_attachments_root()).expanduser().resolve(),
        )
        raise

    result = {
        "json": json_path,
        "source": source_path,
    }
    if markdown_path is not None:
        result["markdown"] = markdown_path
    return result


def load_protocol_attachment_bundle(attachment_bundle_id: str, root: Path | None = None) -> ProtocolAttachmentBundle:
    path = protocol_attachment_json_path(attachment_bundle_id, root)
    if not path.exists():
        raise FileNotFoundError(f"Protocol attachment bundle JSON not found: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return ProtocolAttachmentBundle(**payload)
    except Exception as exc:
        raise ValueError(f"Failed to load protocol attachment bundle from {path}: {exc}") from exc


def load_protocol_attachment_markdown(attachment_bundle_id: str, root: Path | None = None) -> str:
    bundle = load_protocol_attachment_bundle(attachment_bundle_id, root)
    if bundle.extracted_markdown_ref is None:
        raise FileNotFoundError(
            f"Protocol attachment extracted markdown not found: attachment_bundle_id={attachment_bundle_id}"
        )
    path = protocol_attachment_extracted_markdown_path(
        attachment_bundle_id,
        bundle.extracted_markdown_ref.path,
        root,
    )
    if not path.exists():
        raise FileNotFoundError(f"Protocol attachment extracted markdown not found: {path}")
    return path.read_text(encoding="utf-8")


def load_protocol_attachment_source_path(attachment_bundle_id: str, root: Path | None = None) -> tuple[ProtocolAttachmentBundle, Path]:
    bundle = load_protocol_attachment_bundle(attachment_bundle_id, root)
    path = protocol_attachment_source_path(
        attachment_bundle_id,
        bundle.source_ref.path,
        root,
    )
    if not path.exists():
        raise FileNotFoundError(f"Protocol attachment source file not found: {path}")
    return bundle, path


def _atomic_write_bytes(path: Path, content: bytes) -> None:
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
        temp_path.write_bytes(content)
        os.replace(temp_path, path)
    except Exception as exc:
        if temp_path and temp_path.exists():
            os.remove(temp_path)
        raise IOError(f"Failed to write protocol attachment file to {path}: {exc}") from exc


def _optional_bytes(path: Path) -> bytes | None:
    if not path.exists():
        return None
    return path.read_bytes()


def _restore_optional_bytes(path: Path, content: bytes | None) -> None:
    if content is None:
        if path.exists():
            os.remove(path)
        return
    _atomic_write_bytes(path, content)


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


def _protocol_attachment_relative_path(
    attachment_bundle_id: str,
    relative_path: str,
    root: Path | None = None,
) -> Path:
    bundle_dir = protocol_attachment_dir(attachment_bundle_id, root)
    candidate = (bundle_dir / relative_path).resolve()
    try:
        candidate.relative_to(bundle_dir.resolve())
    except ValueError as exc:
        raise ValueError(
            f"Protocol attachment path escapes bundle directory: attachment_bundle_id={attachment_bundle_id}"
        ) from exc
    return candidate
