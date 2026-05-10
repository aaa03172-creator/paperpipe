from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from pathlib import PurePosixPath

from src.schemas.image_evidence import (
    ImageEvidence,
    ImageHandoffTarget,
    ImageViewState,
    normalize_image_evidence_id,
)
from src.services.runtime_paths import image_evidence_root as default_image_evidence_root


def image_evidence_dir(image_evidence_id: str, root: Path | None = None) -> Path:
    base = (root or default_image_evidence_root()).expanduser().resolve()
    safe_image_evidence_id = normalize_image_evidence_id(image_evidence_id)
    path = (base / safe_image_evidence_id).resolve()
    try:
        path.relative_to(base)
    except ValueError as exc:
        raise ValueError("image_evidence_id resolves outside the Image Evidence root") from exc
    return path


def image_evidence_json_path(image_evidence_id: str, root: Path | None = None) -> Path:
    return image_evidence_dir(image_evidence_id, root) / "image_evidence.json"


def image_evidence_view_state_path(image_evidence_id: str, root: Path | None = None) -> Path:
    return image_evidence_dir(image_evidence_id, root) / "view_state.json"


def image_evidence_handoff_path(image_evidence_id: str, root: Path | None = None) -> Path:
    return image_evidence_dir(image_evidence_id, root) / "handoff.json"


def image_evidence_derivatives_dir(image_evidence_id: str, root: Path | None = None) -> Path:
    return image_evidence_dir(image_evidence_id, root) / "derivatives"


def image_evidence_derivative_path(
    image_evidence_id: str,
    derived_output_id: str,
    extension: str = "png",
    root: Path | None = None,
) -> Path:
    normalized_extension = str(extension or "png").strip().lstrip(".") or "png"
    return image_evidence_derivatives_dir(image_evidence_id, root) / f"{derived_output_id}.{normalized_extension}"


def image_evidence_artifact_path(image_evidence_id: str, relative_path: str, root: Path | None = None) -> Path:
    return image_evidence_dir(image_evidence_id, root) / _normalize_bundle_relative_path(relative_path)


def save_image_evidence(image_evidence: ImageEvidence, root: Path | None = None) -> Path:
    path = image_evidence_json_path(image_evidence.image_evidence_id, root)
    payload = json.dumps(image_evidence.model_dump(mode="json", exclude_none=True), ensure_ascii=False, indent=2)
    _atomic_write_text(path, payload)
    return path


def load_image_evidence(image_evidence_id: str, root: Path | None = None) -> ImageEvidence:
    path = image_evidence_json_path(image_evidence_id, root)
    if not path.exists():
        raise FileNotFoundError(f"Image Evidence JSON not found: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return ImageEvidence(**payload)
    except Exception as exc:
        raise ValueError(f"Failed to load Image Evidence from {path}: {exc}") from exc


def save_image_view_state(image_evidence_id: str, view_state: ImageViewState, root: Path | None = None) -> Path:
    path = image_evidence_view_state_path(image_evidence_id, root)
    payload = json.dumps(view_state.model_dump(mode="json", exclude_none=True), ensure_ascii=False, indent=2)
    _atomic_write_text(path, payload)
    return path


def load_image_view_state(image_evidence_id: str, root: Path | None = None) -> ImageViewState:
    path = image_evidence_view_state_path(image_evidence_id, root)
    if not path.exists():
        raise FileNotFoundError(f"Image Evidence view-state JSON not found: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return ImageViewState(**payload)
    except Exception as exc:
        raise ValueError(f"Failed to load Image Evidence view-state from {path}: {exc}") from exc


def save_image_handoff_targets(
    image_evidence_id: str,
    handoff_targets: list[ImageHandoffTarget],
    root: Path | None = None,
) -> Path:
    path = image_evidence_handoff_path(image_evidence_id, root)
    payload = json.dumps(
        [target.model_dump(mode="json", exclude_none=True) for target in handoff_targets],
        ensure_ascii=False,
        indent=2,
    )
    _atomic_write_text(path, payload)
    return path


def load_image_handoff_targets(image_evidence_id: str, root: Path | None = None) -> list[ImageHandoffTarget]:
    path = image_evidence_handoff_path(image_evidence_id, root)
    if not path.exists():
        raise FileNotFoundError(f"Image Evidence handoff JSON not found: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return [ImageHandoffTarget(**item) for item in payload]
    except Exception as exc:
        raise ValueError(f"Failed to load Image Evidence handoff targets from {path}: {exc}") from exc


def save_image_derivative_bytes(
    image_evidence_id: str,
    derived_output_id: str,
    content: bytes,
    *,
    extension: str = "png",
    root: Path | None = None,
) -> Path:
    path = image_evidence_derivative_path(image_evidence_id, derived_output_id, extension=extension, root=root)
    _atomic_write_bytes(path, content)
    return path


def load_image_derivative_bytes(
    image_evidence_id: str,
    derived_output_id: str,
    *,
    extension: str = "png",
    root: Path | None = None,
) -> bytes:
    path = image_evidence_derivative_path(image_evidence_id, derived_output_id, extension=extension, root=root)
    if not path.exists():
        raise FileNotFoundError(f"Image Evidence derivative file not found: {path}")
    return path.read_bytes()


def load_image_evidence_artifact_bytes(
    image_evidence_id: str,
    relative_path: str,
    root: Path | None = None,
) -> bytes:
    path = image_evidence_artifact_path(image_evidence_id, relative_path, root)
    if not path.exists():
        raise FileNotFoundError(f"Image Evidence artifact file not found: {path}")
    return path.read_bytes()


def save_image_evidence_bundle(
    image_evidence: ImageEvidence,
    *,
    view_state: ImageViewState | None = None,
    handoff_targets: list[ImageHandoffTarget] | None = None,
    derivative_artifacts: dict[str, bytes] | None = None,
    root: Path | None = None,
) -> dict[str, Path]:
    derivative_artifacts = {
        _normalize_bundle_relative_path(path): content
        for path, content in dict(derivative_artifacts or {}).items()
    }
    _validate_declared_bundle_members(
        image_evidence,
        view_state=view_state,
        handoff_targets=handoff_targets,
        derivative_artifacts=derivative_artifacts,
    )
    json_path = image_evidence_json_path(image_evidence.image_evidence_id, root)
    view_state_path = image_evidence_view_state_path(image_evidence.image_evidence_id, root)
    handoff_path = image_evidence_handoff_path(image_evidence.image_evidence_id, root)
    derivative_paths = {
        relative_path: image_evidence_dir(image_evidence.image_evidence_id, root) / relative_path
        for relative_path in sorted(derivative_artifacts)
    }
    expected_paths = {
        json_path,
        *derivative_paths.values(),
    }
    if image_evidence.view_state_ref is not None:
        expected_paths.add(view_state_path)
    if image_evidence.handoff_ref is not None:
        expected_paths.add(handoff_path)
    tracked_paths = {
        path: _optional_bytes(path)
        for path in sorted(
            {
                *expected_paths,
                *_existing_managed_paths(image_evidence.image_evidence_id, root),
            },
            key=lambda item: str(item),
        )
    }
    payload = json.dumps(image_evidence.model_dump(mode="json", exclude_none=True), ensure_ascii=False, indent=2)

    try:
        _atomic_write_text(json_path, payload)
        if view_state is not None:
            save_image_view_state(image_evidence.image_evidence_id, view_state, root)
        if handoff_targets is not None:
            save_image_handoff_targets(image_evidence.image_evidence_id, handoff_targets, root)
        for relative_path, path in derivative_paths.items():
            _atomic_write_bytes(path, derivative_artifacts[relative_path])
        for stale_path in sorted(set(tracked_paths) - expected_paths, key=lambda item: str(item)):
            if stale_path.exists():
                os.remove(stale_path)
        _remove_empty_dirs(image_evidence_dir(image_evidence.image_evidence_id, root), stop_at=(root or default_image_evidence_root()).expanduser().resolve())
    except Exception:
        for path, previous in tracked_paths.items():
            _restore_optional_bytes(path, previous)
        _remove_empty_dirs(image_evidence_dir(image_evidence.image_evidence_id, root), stop_at=(root or default_image_evidence_root()).expanduser().resolve())
        raise

    result: dict[str, Path] = {"json": json_path}
    if image_evidence.view_state_ref is not None:
        result["view_state"] = view_state_path
    if image_evidence.handoff_ref is not None:
        result["handoff"] = handoff_path
    result.update({f"derivative:{relative_path}": path for relative_path, path in derivative_paths.items()})
    return result


def list_image_evidence_ids(root: Path | None = None) -> list[str]:
    base = (root or default_image_evidence_root()).expanduser().resolve()
    if not base.exists():
        return []
    return sorted(entry.name for entry in base.iterdir() if entry.is_dir())


def _existing_managed_paths(image_evidence_id: str, root: Path | None = None) -> set[Path]:
    managed: set[Path] = set()
    for path in (
        image_evidence_json_path(image_evidence_id, root),
        image_evidence_view_state_path(image_evidence_id, root),
        image_evidence_handoff_path(image_evidence_id, root),
    ):
        if path.exists():
            managed.add(path)
    derivatives_dir = image_evidence_derivatives_dir(image_evidence_id, root)
    if derivatives_dir.exists():
        managed.update(path for path in derivatives_dir.rglob("*") if path.is_file())
    return managed


def _expected_derivative_paths(image_evidence: ImageEvidence, root: Path | None = None) -> set[Path]:
    expected: set[Path] = set()
    for derived_output in image_evidence.derived_outputs:
        if derived_output.bundle_ref is None:
            continue
        expected.add(
            image_evidence_dir(image_evidence.image_evidence_id, root)
            / _normalize_bundle_relative_path(derived_output.bundle_ref.path)
        )
    return expected


def _declared_derivative_paths(image_evidence: ImageEvidence) -> set[str]:
    declared: set[str] = set()
    for derived_output in image_evidence.derived_outputs:
        if derived_output.bundle_ref is None:
            continue
        declared.add(_normalize_bundle_relative_path(derived_output.bundle_ref.path))
    return declared


def _validate_declared_bundle_members(
    image_evidence: ImageEvidence,
    *,
    view_state: ImageViewState | None,
    handoff_targets: list[ImageHandoffTarget] | None,
    derivative_artifacts: dict[str, bytes],
) -> None:
    declared_view_state_path = (
        _normalize_bundle_relative_path(image_evidence.view_state_ref.path)
        if image_evidence.view_state_ref is not None
        else None
    )
    declared_handoff_path = (
        _normalize_bundle_relative_path(image_evidence.handoff_ref.path)
        if image_evidence.handoff_ref is not None
        else None
    )
    if declared_view_state_path not in (None, "view_state.json"):
        raise ValueError("Image Evidence bundle view-state ref must use view_state.json.")
    if declared_handoff_path not in (None, "handoff.json"):
        raise ValueError("Image Evidence bundle handoff ref must use handoff.json.")

    if image_evidence.view_state_ref is not None and view_state is None:
        raise ValueError("Image Evidence bundle is missing declared view-state payload.")
    if image_evidence.view_state_ref is None and view_state is not None:
        raise ValueError("Image Evidence bundle includes undeclared view-state payload.")

    if image_evidence.handoff_ref is not None and handoff_targets is None:
        raise ValueError("Image Evidence bundle is missing declared handoff payload.")
    if image_evidence.handoff_ref is None and handoff_targets is not None:
        raise ValueError("Image Evidence bundle includes undeclared handoff payload.")

    nested_view_state_paths = {
        _normalize_bundle_relative_path(output.view_state_ref.path)
        for output in image_evidence.derived_outputs
        if output.view_state_ref is not None
    }
    nested_view_state_paths.update(
        _normalize_bundle_relative_path(target.view_state_ref.path)
        for target in (handoff_targets or [])
        if target.view_state_ref is not None
    )
    if nested_view_state_paths and declared_view_state_path is None:
        raise ValueError("Image Evidence bundle nested view-state refs require declared view-state payload.")
    if declared_view_state_path is not None and nested_view_state_paths not in (set(), {declared_view_state_path}):
        raise ValueError("Image Evidence bundle nested view-state refs must match declared view-state path.")

    declared_paths = _declared_derivative_paths(image_evidence)
    provided_paths = set(derivative_artifacts)

    missing_paths = sorted(declared_paths - provided_paths)
    if missing_paths:
        raise ValueError(
            "Image Evidence bundle is missing declared derivative artifact payloads for: "
            + ", ".join(missing_paths)
        )

    unexpected_paths = sorted(provided_paths - declared_paths)
    if unexpected_paths:
        raise ValueError(
            "Image Evidence bundle includes undeclared derivative artifact payloads: "
            + ", ".join(unexpected_paths)
        )


def _normalize_bundle_relative_path(path: str) -> str:
    raw = str(path or "").strip()
    if not raw:
        raise ValueError("Image Evidence bundle-relative path must be non-empty")
    pure = PurePosixPath(raw)
    if pure.is_absolute() or any(part in {"", ".", ".."} for part in pure.parts):
        raise ValueError(f"Image Evidence bundle-relative path is invalid: {path}")
    return pure.as_posix()


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
        raise IOError(f"Failed to write Image Evidence file to {path}: {exc}") from exc


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
