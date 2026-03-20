from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from src.schemas.method_comparison import MethodComparison
from src.services.runtime_paths import method_comparisons_root as default_method_comparisons_root


def method_comparison_dir(comparison_id: str, root: Path | None = None) -> Path:
    base = (root or default_method_comparisons_root()).expanduser().resolve()
    return base / comparison_id


def method_comparison_json_path(comparison_id: str, root: Path | None = None) -> Path:
    return method_comparison_dir(comparison_id, root) / "comparison.json"


def method_comparison_csv_path(comparison_id: str, root: Path | None = None) -> Path:
    return method_comparison_dir(comparison_id, root) / "comparison.csv"


def method_comparison_markdown_path(comparison_id: str, root: Path | None = None) -> Path:
    return method_comparison_dir(comparison_id, root) / "comparison.md"


def save_method_comparison(comparison: MethodComparison, root: Path | None = None) -> Path:
    path = method_comparison_json_path(comparison.comparison_id, root)
    payload = json.dumps(comparison.model_dump(mode="json", exclude_none=True), ensure_ascii=False, indent=2)
    _atomic_write_text(path, payload)
    return path


def load_method_comparison(comparison_id: str, root: Path | None = None) -> MethodComparison:
    path = method_comparison_json_path(comparison_id, root)
    if not path.exists():
        raise FileNotFoundError(f"Method Comparison JSON not found: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return MethodComparison(**payload)
    except Exception as exc:
        raise ValueError(f"Failed to load Method Comparison from {path}: {exc}") from exc


def save_method_comparison_csv(comparison_id: str, csv_text: str, root: Path | None = None) -> Path:
    path = method_comparison_csv_path(comparison_id, root)
    _atomic_write_text(path, csv_text)
    return path


def load_method_comparison_csv(comparison_id: str, root: Path | None = None) -> str:
    path = method_comparison_csv_path(comparison_id, root)
    if not path.exists():
        raise FileNotFoundError(f"Method Comparison CSV not found: {path}")
    return path.read_text(encoding="utf-8")


def save_method_comparison_markdown(comparison_id: str, markdown: str, root: Path | None = None) -> Path:
    path = method_comparison_markdown_path(comparison_id, root)
    _atomic_write_text(path, markdown)
    return path


def load_method_comparison_markdown(comparison_id: str, root: Path | None = None) -> str:
    path = method_comparison_markdown_path(comparison_id, root)
    if not path.exists():
        raise FileNotFoundError(f"Method Comparison markdown not found: {path}")
    return path.read_text(encoding="utf-8")


def save_method_comparison_bundle(
    comparison: MethodComparison,
    csv_text: str,
    markdown: str,
    root: Path | None = None,
) -> tuple[Path, Path, Path]:
    json_path = method_comparison_json_path(comparison.comparison_id, root)
    csv_path = method_comparison_csv_path(comparison.comparison_id, root)
    markdown_path = method_comparison_markdown_path(comparison.comparison_id, root)

    previous_json = _optional_text(json_path)
    previous_csv = _optional_text(csv_path)
    previous_markdown = _optional_text(markdown_path)
    payload = json.dumps(comparison.model_dump(mode="json", exclude_none=True), ensure_ascii=False, indent=2)

    try:
        _atomic_write_text(json_path, payload)
        _atomic_write_text(csv_path, csv_text)
        _atomic_write_text(markdown_path, markdown)
    except Exception:
        _restore_optional_text(json_path, previous_json)
        _restore_optional_text(csv_path, previous_csv)
        _restore_optional_text(markdown_path, previous_markdown)
        _remove_empty_dir(json_path.parent)
        raise
    return json_path, csv_path, markdown_path


def list_method_comparison_ids(root: Path | None = None) -> list[str]:
    base = (root or default_method_comparisons_root()).expanduser().resolve()
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
        raise IOError(f"Failed to write Method Comparison file to {path}: {exc}") from exc


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
