from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path
from pathlib import PurePosixPath

from src.schemas.talk_pack import TalkPack
from src.services.runtime_paths import talk_packs_root as default_talk_packs_root

_SAFE_SEGMENT_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,159}$")


def talk_pack_dir(talk_pack_id: str, root: Path | None = None) -> Path:
    base = (root or default_talk_packs_root()).expanduser().resolve()
    safe_talk_pack_id = _normalize_talk_pack_id(talk_pack_id)
    return _confined_child(base, safe_talk_pack_id)


def talk_pack_json_path(talk_pack_id: str, root: Path | None = None) -> Path:
    return talk_pack_dir(talk_pack_id, root) / "talk_pack.json"


def talk_pack_artifact_path(talk_pack_id: str, filename: str, root: Path | None = None) -> Path:
    return talk_pack_dir(talk_pack_id, root) / _normalize_artifact_filename(filename)


def save_talk_pack(pack: TalkPack, root: Path | None = None) -> Path:
    path = talk_pack_json_path(pack.talk_pack_id, root)
    payload = json.dumps(pack.model_dump(mode="json", exclude_none=True), ensure_ascii=False, indent=2)
    _atomic_write_text(path, payload)
    return path


def load_talk_pack(talk_pack_id: str, root: Path | None = None) -> TalkPack:
    path = talk_pack_json_path(talk_pack_id, root)
    if not path.exists():
        raise FileNotFoundError(f"Talk Pack JSON not found: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return TalkPack(**payload)
    except Exception as exc:
        raise ValueError(f"Failed to load Talk Pack from {path}: {exc}") from exc


def save_talk_pack_artifact_text(
    talk_pack_id: str,
    filename: str,
    content: str,
    root: Path | None = None,
) -> Path:
    path = talk_pack_artifact_path(talk_pack_id, filename, root)
    _atomic_write_text(path, content)
    return path


def save_talk_pack_artifact_bytes(
    talk_pack_id: str,
    filename: str,
    content: bytes,
    root: Path | None = None,
) -> Path:
    path = talk_pack_artifact_path(talk_pack_id, filename, root)
    _atomic_write_bytes(path, content)
    return path


def load_talk_pack_artifact_text(
    talk_pack_id: str,
    filename: str,
    root: Path | None = None,
) -> str:
    path = talk_pack_artifact_path(talk_pack_id, filename, root)
    if not path.exists():
        raise FileNotFoundError(f"Talk Pack artifact text not found: {path}")
    return path.read_text(encoding="utf-8")


def load_talk_pack_artifact_bytes(
    talk_pack_id: str,
    filename: str,
    root: Path | None = None,
) -> bytes:
    path = talk_pack_artifact_path(talk_pack_id, filename, root)
    if not path.exists():
        raise FileNotFoundError(f"Talk Pack artifact bytes not found: {path}")
    return path.read_bytes()


def save_talk_pack_artifact_json(
    talk_pack_id: str,
    filename: str,
    payload: dict[str, object],
    root: Path | None = None,
) -> Path:
    path = talk_pack_artifact_path(talk_pack_id, filename, root)
    _atomic_write_text(path, json.dumps(payload, ensure_ascii=False, indent=2))
    return path


def load_talk_pack_artifact_json(
    talk_pack_id: str,
    filename: str,
    root: Path | None = None,
) -> dict[str, object]:
    path = talk_pack_artifact_path(talk_pack_id, filename, root)
    if not path.exists():
        raise FileNotFoundError(f"Talk Pack artifact JSON not found: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ValueError(f"Failed to load Talk Pack artifact JSON from {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"Talk Pack artifact JSON must deserialize to an object: {path}")
    return payload


def save_talk_pack_bundle(
    pack: TalkPack,
    *,
    text_artifacts: dict[str, str] | None = None,
    json_artifacts: dict[str, dict[str, object]] | None = None,
    binary_artifacts: dict[str, bytes] | None = None,
    root: Path | None = None,
) -> dict[str, Path]:
    text_artifacts = dict(text_artifacts or {})
    json_artifacts = dict(json_artifacts or {})
    binary_artifacts = dict(binary_artifacts or {})
    _validate_declared_bundle_members(
        pack,
        text_artifacts=text_artifacts,
        json_artifacts=json_artifacts,
        binary_artifacts=binary_artifacts,
    )

    json_path = talk_pack_json_path(pack.talk_pack_id, root)
    text_paths = {
        filename: talk_pack_artifact_path(pack.talk_pack_id, filename, root)
        for filename in sorted(text_artifacts)
    }
    json_artifact_paths = {
        filename: talk_pack_artifact_path(pack.talk_pack_id, filename, root)
        for filename in sorted(json_artifacts)
    }
    binary_artifact_paths = {
        filename: talk_pack_artifact_path(pack.talk_pack_id, filename, root)
        for filename in sorted(binary_artifacts)
    }
    expected_paths = {
        json_path,
        *text_paths.values(),
        *json_artifact_paths.values(),
        *binary_artifact_paths.values(),
    }
    tracked_paths: dict[Path, bytes | None] = {
        path: _optional_bytes(path)
        for path in sorted(
            {
                *expected_paths,
                *_existing_managed_paths(pack.talk_pack_id, root),
            },
            key=lambda item: str(item),
        )
    }
    payload = json.dumps(pack.model_dump(mode="json", exclude_none=True), ensure_ascii=False, indent=2)

    try:
        _atomic_write_text(json_path, payload)
        for filename, path in text_paths.items():
            _atomic_write_text(path, text_artifacts[filename])
        for filename, path in json_artifact_paths.items():
            _atomic_write_text(path, json.dumps(json_artifacts[filename], ensure_ascii=False, indent=2))
        for filename, path in binary_artifact_paths.items():
            _atomic_write_bytes(path, binary_artifacts[filename])
        for stale_path in sorted(set(tracked_paths) - expected_paths, key=lambda item: str(item)):
            if stale_path.exists():
                os.remove(stale_path)
        _remove_empty_dirs(
            talk_pack_dir(pack.talk_pack_id, root),
            stop_at=(root or default_talk_packs_root()).expanduser().resolve(),
        )
    except Exception:
        for path, previous in tracked_paths.items():
            _restore_optional_bytes(path, previous)
        _remove_empty_dirs(
            talk_pack_dir(pack.talk_pack_id, root),
            stop_at=(root or default_talk_packs_root()).expanduser().resolve(),
        )
        raise

    results = {"json": json_path}
    for filename, path in text_paths.items():
        results[f"text:{filename}"] = path
    for filename, path in json_artifact_paths.items():
        results[f"json:{filename}"] = path
    for filename, path in binary_artifact_paths.items():
        results[f"binary:{filename}"] = path
    return results


def list_talk_pack_ids(root: Path | None = None) -> list[str]:
    base = (root or default_talk_packs_root()).expanduser().resolve()
    if not base.exists():
        return []
    return sorted(entry.name for entry in base.iterdir() if entry.is_dir())


def _existing_managed_paths(talk_pack_id: str, root: Path | None = None) -> set[Path]:
    managed: set[Path] = set()
    json_path = talk_pack_json_path(talk_pack_id, root)
    if json_path.exists():
        managed.add(json_path)
        try:
            payload = json.loads(json_path.read_text(encoding="utf-8"))
        except Exception:
            payload = None
        if isinstance(payload, dict):
            for member in payload.get("output_members", []) or []:
                if isinstance(member, dict) and member.get("status") == "generated":
                    path = member.get("path")
                    if isinstance(path, str) and path.strip():
                        _add_existing_managed_artifact_path(
                            managed,
                            talk_pack_id=talk_pack_id,
                            path=path,
                            root=root,
                        )
            for artifact in payload.get("review_artifacts", []) or []:
                if isinstance(artifact, dict):
                    path = artifact.get("path")
                    if isinstance(path, str) and path.strip():
                        _add_existing_managed_artifact_path(
                            managed,
                            talk_pack_id=talk_pack_id,
                            path=path,
                            root=root,
                        )
    return managed


def _add_existing_managed_artifact_path(
    managed: set[Path],
    *,
    talk_pack_id: str,
    path: str,
    root: Path | None,
) -> None:
    try:
        managed.add(talk_pack_artifact_path(talk_pack_id, path, root))
    except ValueError:
        return


def _validate_declared_bundle_members(
    pack: TalkPack,
    *,
    text_artifacts: dict[str, str],
    json_artifacts: dict[str, dict[str, object]],
    binary_artifacts: dict[str, bytes],
) -> None:
    artifact_maps = {
        "text_artifacts": set(text_artifacts),
        "json_artifacts": set(json_artifacts),
        "binary_artifacts": set(binary_artifacts),
    }
    seen_paths: dict[str, str] = {}
    duplicate_paths: list[str] = []
    for map_name, paths in artifact_maps.items():
        for path in paths:
            previous = seen_paths.get(path)
            if previous is not None:
                duplicate_paths.append(path)
            else:
                seen_paths[path] = map_name
    if duplicate_paths:
        raise ValueError(
            "Talk Pack artifact paths must not appear in multiple payload maps: "
            + ", ".join(sorted(set(duplicate_paths)))
        )

    expected_output_paths = {
        member.path
        for member in pack.output_members
        if member.status == "generated"
    }
    expected_review_paths = {artifact.path for artifact in pack.review_artifacts}
    expected_paths = expected_output_paths | expected_review_paths
    provided_paths = set(seen_paths)

    missing_paths = sorted(expected_paths - provided_paths)
    if missing_paths:
        raise ValueError(
            "Talk Pack bundle is missing declared generated artifact payloads for: "
            + ", ".join(missing_paths)
        )

    unexpected_paths = sorted(provided_paths - expected_paths)
    if unexpected_paths:
        raise ValueError(
            "Talk Pack bundle includes undeclared artifact payloads: "
            + ", ".join(unexpected_paths)
        )


def _normalize_artifact_filename(filename: str) -> str:
    raw = str(filename or "").strip()
    pure = PurePosixPath(raw)
    if (
        not raw
        or "\\" in raw
        or pure.is_absolute()
        or any(part in {"", ".", ".."} for part in raw.split("/"))
    ):
        raise ValueError(f"Talk Pack artifact filename is invalid: {filename}")
    return pure.as_posix()


def _normalize_talk_pack_id(value: str) -> str:
    text = str(value or "").strip()
    if not text or not _SAFE_SEGMENT_RE.fullmatch(text):
        raise ValueError("Talk Pack talk_pack_id must be a single safe path segment")
    return text


def _confined_child(base: Path, safe_segment: str) -> Path:
    candidate = (base / safe_segment).resolve()
    try:
        candidate.relative_to(base)
    except ValueError as exc:
        raise ValueError("Talk Pack talk_pack_id escapes storage root") from exc
    return candidate


def _atomic_write_text(path: Path, content: str) -> None:
    _atomic_write_bytes(path, content.encode("utf-8"))


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
        raise IOError(f"Failed to write Talk Pack file to {path}: {exc}") from exc


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
        if stop_path is not None and current == stop_path:
            break
        parent = current.parent
        current.rmdir()
        current = parent
