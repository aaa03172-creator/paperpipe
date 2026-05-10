from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any

from src.schemas.chart_pack import ChartPack
from src.services.runtime_paths import chart_packs_root as default_chart_packs_root

_SAFE_SEGMENT_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,159}$")
_SAFE_ARTIFACT_FILENAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,159}\.[A-Za-z0-9][A-Za-z0-9._-]{0,31}$")


def chart_pack_dir(chart_pack_id: str, root: Path | None = None) -> Path:
    base = (root or default_chart_packs_root()).expanduser().resolve()
    safe_chart_pack_id = _normalize_safe_segment(chart_pack_id, field_name="chart_pack_id")
    return _confined_child(base, safe_chart_pack_id, field_name="chart_pack_id")


def chart_pack_json_path(chart_pack_id: str, root: Path | None = None) -> Path:
    return chart_pack_dir(chart_pack_id, root) / "chart_pack.json"


def chart_pack_markdown_path(chart_pack_id: str, root: Path | None = None) -> Path:
    return chart_pack_dir(chart_pack_id, root) / "chart_pack.md"


def chart_pack_artifact_path(chart_pack_id: str, filename: str, root: Path | None = None) -> Path:
    safe_filename = _normalize_artifact_filename(filename)
    return chart_pack_dir(chart_pack_id, root) / safe_filename


def chart_pack_data_dir(chart_pack_id: str, root: Path | None = None) -> Path:
    return chart_pack_dir(chart_pack_id, root) / "data"


def chart_pack_specs_dir(chart_pack_id: str, root: Path | None = None) -> Path:
    return chart_pack_dir(chart_pack_id, root) / "specs"


def chart_pack_renders_dir(chart_pack_id: str, root: Path | None = None) -> Path:
    return chart_pack_dir(chart_pack_id, root) / "renders"


def chart_pack_data_csv_path(chart_pack_id: str, chart_id: str, root: Path | None = None) -> Path:
    safe_chart_id = _normalize_safe_segment(chart_id, field_name="chart_id")
    return chart_pack_data_dir(chart_pack_id, root) / f"{safe_chart_id}.csv"


def chart_pack_spec_json_path(chart_pack_id: str, chart_id: str, root: Path | None = None) -> Path:
    safe_chart_id = _normalize_safe_segment(chart_id, field_name="chart_id")
    return chart_pack_specs_dir(chart_pack_id, root) / f"{safe_chart_id}.json"


def chart_pack_render_path(
    chart_pack_id: str,
    chart_id: str,
    extension: str = "svg",
    root: Path | None = None,
) -> Path:
    safe_chart_id = _normalize_safe_segment(chart_id, field_name="chart_id")
    normalized_extension = str(extension or "svg").strip().lstrip(".") or "svg"
    safe_extension = _normalize_safe_segment(normalized_extension, field_name="extension")
    return chart_pack_renders_dir(chart_pack_id, root) / f"{safe_chart_id}.{safe_extension}"


def save_chart_pack(chart_pack: ChartPack, root: Path | None = None) -> Path:
    path = chart_pack_json_path(chart_pack.chart_pack_id, root)
    payload = json.dumps(chart_pack.model_dump(mode="json", exclude_none=True), ensure_ascii=False, indent=2)
    _atomic_write_text(path, payload)
    return path


def load_chart_pack(chart_pack_id: str, root: Path | None = None) -> ChartPack:
    path = chart_pack_json_path(chart_pack_id, root)
    if not path.exists():
        raise FileNotFoundError(f"Chart Pack JSON not found: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return ChartPack(**payload)
    except Exception as exc:
        raise ValueError(f"Failed to load Chart Pack from {path}: {exc}") from exc


def save_chart_pack_markdown(chart_pack_id: str, markdown: str, root: Path | None = None) -> Path:
    path = chart_pack_markdown_path(chart_pack_id, root)
    _atomic_write_text(path, markdown)
    return path


def save_chart_pack_artifact_json(
    chart_pack_id: str,
    filename: str,
    payload: dict[str, object],
    root: Path | None = None,
) -> Path:
    path = chart_pack_artifact_path(chart_pack_id, filename, root)
    _atomic_write_text(path, json.dumps(payload, ensure_ascii=False, indent=2))
    return path


def load_chart_pack_artifact_json(
    chart_pack_id: str,
    filename: str,
    root: Path | None = None,
) -> Any:
    path = chart_pack_artifact_path(chart_pack_id, filename, root)
    if not path.exists():
        raise FileNotFoundError(f"Chart Pack artifact JSON not found: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ValueError(f"Failed to load Chart Pack artifact JSON from {path}: {exc}") from exc


def load_chart_pack_markdown(chart_pack_id: str, root: Path | None = None) -> str:
    path = chart_pack_markdown_path(chart_pack_id, root)
    if not path.exists():
        raise FileNotFoundError(f"Chart Pack markdown not found: {path}")
    return path.read_text(encoding="utf-8")


def save_chart_pack_data_csv(chart_pack_id: str, chart_id: str, csv_text: str, root: Path | None = None) -> Path:
    path = chart_pack_data_csv_path(chart_pack_id, chart_id, root)
    _atomic_write_text(path, csv_text)
    return path


def load_chart_pack_data_csv(chart_pack_id: str, chart_id: str, root: Path | None = None) -> str:
    path = chart_pack_data_csv_path(chart_pack_id, chart_id, root)
    if not path.exists():
        raise FileNotFoundError(f"Chart Pack data CSV not found: {path}")
    return path.read_text(encoding="utf-8")


def save_chart_pack_render(
    chart_pack_id: str,
    chart_id: str,
    render_text: str,
    *,
    extension: str = "svg",
    root: Path | None = None,
) -> Path:
    path = chart_pack_render_path(chart_pack_id, chart_id, extension=extension, root=root)
    _atomic_write_text(path, render_text)
    return path


def load_chart_pack_render(
    chart_pack_id: str,
    chart_id: str,
    *,
    extension: str = "svg",
    root: Path | None = None,
) -> str:
    path = chart_pack_render_path(chart_pack_id, chart_id, extension=extension, root=root)
    if not path.exists():
        raise FileNotFoundError(f"Chart Pack render not found: {path}")
    return path.read_text(encoding="utf-8")


def save_chart_pack_spec(
    chart_pack_id: str,
    chart_id: str,
    spec_payload: Any,
    root: Path | None = None,
) -> Path:
    path = chart_pack_spec_json_path(chart_pack_id, chart_id, root)
    payload = json.dumps(spec_payload, ensure_ascii=False, indent=2)
    _atomic_write_text(path, payload)
    return path


def load_chart_pack_spec(chart_pack_id: str, chart_id: str, root: Path | None = None) -> Any:
    path = chart_pack_spec_json_path(chart_pack_id, chart_id, root)
    if not path.exists():
        raise FileNotFoundError(f"Chart Pack spec JSON not found: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ValueError(f"Failed to load Chart Pack spec from {path}: {exc}") from exc


def save_chart_pack_bundle(
    chart_pack: ChartPack,
    markdown: str,
    *,
    data_snapshots: dict[str, str] | None = None,
    specs: dict[str, Any] | None = None,
    renders: dict[str, dict[str, str]] | None = None,
    root: Path | None = None,
) -> dict[str, Path]:
    data_snapshots = dict(data_snapshots or {})
    specs = dict(specs or {})
    renders = {chart_id: dict(render_map) for chart_id, render_map in (renders or {}).items()}
    valid_chart_ids = {chart.chart_id for chart in chart_pack.charts}
    extra_snapshot_ids = sorted(set(data_snapshots) - valid_chart_ids)
    extra_spec_ids = sorted(set(specs) - valid_chart_ids)
    extra_render_ids = sorted(set(renders) - valid_chart_ids)
    if extra_snapshot_ids:
        raise ValueError(f"Unknown chart_id(s) in data_snapshots: {', '.join(extra_snapshot_ids)}")
    if extra_spec_ids:
        raise ValueError(f"Unknown chart_id(s) in specs: {', '.join(extra_spec_ids)}")
    if extra_render_ids:
        raise ValueError(f"Unknown chart_id(s) in renders: {', '.join(extra_render_ids)}")

    json_path = chart_pack_json_path(chart_pack.chart_pack_id, root)
    markdown_path = chart_pack_markdown_path(chart_pack.chart_pack_id, root)
    snapshot_paths: dict[str, Path] = {}
    for chart_id in sorted(data_snapshots):
        snapshot_paths[chart_id] = chart_pack_data_csv_path(chart_pack.chart_pack_id, chart_id, root)

    spec_paths: dict[str, Path] = {}
    for chart_id in sorted(specs):
        spec_paths[chart_id] = chart_pack_spec_json_path(chart_pack.chart_pack_id, chart_id, root)

    render_paths: dict[tuple[str, str], Path] = {}
    for chart_id in sorted(renders):
        for extension in sorted(renders[chart_id]):
            normalized_extension = str(extension or "").strip().lstrip(".")
            if normalized_extension not in {"svg", "png"}:
                raise ValueError(f"Unsupported render extension for Chart Pack: {extension}")
            render_paths[(chart_id, normalized_extension)] = chart_pack_render_path(
                chart_pack.chart_pack_id,
                chart_id,
                extension=normalized_extension,
                root=root,
            )

    expected_paths = {
        json_path,
        markdown_path,
        *snapshot_paths.values(),
        *spec_paths.values(),
        *render_paths.values(),
    }
    tracked_paths: dict[Path, str | None] = {
        path: _optional_text(path)
        for path in sorted(
            {
                *expected_paths,
                *_existing_managed_paths(chart_pack.chart_pack_id, root),
            },
            key=lambda item: str(item),
        )
    }

    payload = json.dumps(chart_pack.model_dump(mode="json", exclude_none=True), ensure_ascii=False, indent=2)

    try:
        _atomic_write_text(json_path, payload)
        _atomic_write_text(markdown_path, markdown)
        for chart_id, path in snapshot_paths.items():
            _atomic_write_text(path, data_snapshots[chart_id])
        for chart_id, path in spec_paths.items():
            _atomic_write_text(path, json.dumps(specs[chart_id], ensure_ascii=False, indent=2))
        for (chart_id, extension), path in render_paths.items():
            _atomic_write_text(path, renders[chart_id][extension])
        for stale_path in sorted(set(tracked_paths) - expected_paths, key=lambda item: str(item)):
            if stale_path.exists():
                os.remove(stale_path)
        _remove_empty_dirs(chart_pack_data_dir(chart_pack.chart_pack_id, root), stop_at=chart_pack_dir(chart_pack.chart_pack_id, root))
        _remove_empty_dirs(chart_pack_specs_dir(chart_pack.chart_pack_id, root), stop_at=chart_pack_dir(chart_pack.chart_pack_id, root))
        _remove_empty_dirs(chart_pack_renders_dir(chart_pack.chart_pack_id, root), stop_at=chart_pack_dir(chart_pack.chart_pack_id, root))
    except Exception:
        for path, previous in tracked_paths.items():
            _restore_optional_text(path, previous)
        _remove_empty_dirs(
            chart_pack_dir(chart_pack.chart_pack_id, root),
            stop_at=(root or default_chart_packs_root()).expanduser().resolve(),
        )
        raise

    result: dict[str, Path] = {
        "json": json_path,
        "markdown": markdown_path,
    }
    result.update({f"data:{chart_id}": path for chart_id, path in snapshot_paths.items()})
    result.update({f"spec:{chart_id}": path for chart_id, path in spec_paths.items()})
    result.update(
        {
            f"render:{chart_id}:{extension}": path
            for (chart_id, extension), path in render_paths.items()
        }
    )
    return result


def list_chart_pack_ids(root: Path | None = None) -> list[str]:
    base = (root or default_chart_packs_root()).expanduser().resolve()
    if not base.exists():
        return []
    return sorted(entry.name for entry in base.iterdir() if entry.is_dir())


def _normalize_safe_segment(value: str, *, field_name: str) -> str:
    text = str(value or "").strip()
    if not text or not _SAFE_SEGMENT_RE.fullmatch(text):
        raise ValueError(f"Chart Pack {field_name} must be a single safe path segment")
    return text


def _normalize_artifact_filename(value: str) -> str:
    text = str(value or "").strip()
    if not text or not _SAFE_ARTIFACT_FILENAME_RE.fullmatch(text):
        raise ValueError("Chart Pack artifact filename must be a single safe filename")
    return text


def _confined_child(base: Path, safe_segment: str, *, field_name: str) -> Path:
    candidate = (base / safe_segment).resolve()
    try:
        candidate.relative_to(base)
    except ValueError as exc:
        raise ValueError(f"Chart Pack {field_name} escapes storage root") from exc
    return candidate


def _existing_managed_paths(chart_pack_id: str, root: Path | None = None) -> set[Path]:
    managed: set[Path] = set()
    for path in (
        chart_pack_json_path(chart_pack_id, root),
        chart_pack_markdown_path(chart_pack_id, root),
    ):
        if path.exists():
            managed.add(path)
    for directory, pattern in (
        (chart_pack_data_dir(chart_pack_id, root), "*.csv"),
        (chart_pack_specs_dir(chart_pack_id, root), "*.json"),
        (chart_pack_renders_dir(chart_pack_id, root), "*.svg"),
        (chart_pack_renders_dir(chart_pack_id, root), "*.png"),
    ):
        if directory.exists():
            managed.update(path for path in directory.glob(pattern) if path.is_file())
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
        raise IOError(f"Failed to write Chart Pack file to {path}: {exc}") from exc


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
        if stop_path is not None and current == stop_path:
            break
        parent = current.parent
        current.rmdir()
        current = parent
