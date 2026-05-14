from __future__ import annotations

import os
import tempfile
from collections.abc import Callable
from pathlib import Path


def atomic_write_text(path: Path, content: str, *, error_context: str = "artifact file") -> None:
    atomic_write_bytes(path, content.encode("utf-8"), error_context=error_context)


def atomic_write_bytes(path: Path, content: bytes, *, error_context: str = "artifact file") -> None:
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
        raise IOError(f"Failed to write {error_context} to {path}: {exc}") from exc


def optional_text(path: Path) -> str | None:
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8")


def optional_bytes(path: Path) -> bytes | None:
    if not path.exists():
        return None
    return path.read_bytes()


def restore_optional_text(
    path: Path,
    content: str | None,
    *,
    writer: Callable[[Path, str], None] = atomic_write_text,
) -> None:
    if content is None:
        remove_file_if_exists(path)
        return
    writer(path, content)


def restore_optional_bytes(
    path: Path,
    content: bytes | None,
    *,
    writer: Callable[[Path, bytes], None] = atomic_write_bytes,
) -> None:
    if content is None:
        remove_file_if_exists(path)
        return
    writer(path, content)


def remove_file_if_exists(path: Path) -> None:
    if path.exists():
        os.remove(path)


def remove_empty_dir(path: Path) -> None:
    if path.exists() and path.is_dir() and not any(path.iterdir()):
        path.rmdir()


def remove_empty_dirs(path: Path, *, stop_at: Path | None = None) -> None:
    current = path
    stop_path = stop_at.resolve() if stop_at is not None else None
    while current.exists() and current.is_dir() and not any(current.iterdir()):
        if stop_path is not None and current.resolve() == stop_path:
            break
        current.rmdir()
        if stop_path is not None and current.parent.resolve() == stop_path:
            break
        current = current.parent
