from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any, TypeVar, cast

import yaml
from pydantic import BaseModel

from src.profiles.research_dna_schema import (
    ApprovalAuditEntry,
    ExternalBenchmarkManifest,
    InterviewLogEntry,
    ResearchDNA,
    RunLogEntry,
    ScreeningLogEntry,
)
from src.services.event_log import sanitize_event_payload_for_log
from src.services.runtime_paths import research_dna_root as default_research_dna_root


TModel = TypeVar("TModel", bound=BaseModel)

PROFILE_FILE = "profile.yaml"
_RESEARCH_DNA_SAFE_ID_RE = re.compile(r"^[a-z0-9_]+$")
LOG_FILE_NAMES = {
    "interview": "interview.jsonl",
    "runs": "runs.jsonl",
    "screening": "screening.jsonl",
    "approval_audit": "approval_audit.jsonl",
}


class ResearchDNARevisionConflictError(RuntimeError):
    pass


def research_dna_dir(dna_id: str, root: Path | None = None) -> Path:
    base = (root or default_research_dna_root()).expanduser().resolve()
    safe_dna_id = _normalize_research_dna_id(dna_id, field_name="dna_id")
    return _confined_child(base, safe_dna_id, field_name="dna_id")


def research_dna_profile_path(dna_id: str, root: Path | None = None) -> Path:
    return research_dna_dir(dna_id, root) / PROFILE_FILE


def research_dna_versions_dir(dna_id: str, root: Path | None = None) -> Path:
    return research_dna_dir(dna_id, root) / "versions"


def research_dna_logs_dir(dna_id: str, root: Path | None = None) -> Path:
    return research_dna_dir(dna_id, root) / "logs"


def research_dna_benchmarks_dir(dna_id: str, root: Path | None = None) -> Path:
    return research_dna_dir(dna_id, root) / "benchmarks"


def research_dna_log_path(dna_id: str, log_name: str, root: Path | None = None) -> Path:
    if log_name not in LOG_FILE_NAMES:
        raise ValueError(f"Unsupported Research DNA log name: {log_name}")
    return research_dna_logs_dir(dna_id, root) / LOG_FILE_NAMES[log_name]


def research_dna_benchmark_manifest_path(dna_id: str, manifest_id: str, root: Path | None = None) -> Path:
    safe_manifest_id = _normalize_research_dna_id(manifest_id, field_name="manifest_id")
    return research_dna_benchmarks_dir(dna_id, root) / f"{safe_manifest_id}.yaml"


def load_research_dna(dna_id: str, root: Path | None = None) -> ResearchDNA:
    path = research_dna_profile_path(dna_id, root)
    if not path.exists():
        raise FileNotFoundError(f"Research DNA profile not found: {path}")

    try:
        with path.open("r", encoding="utf-8") as handle:
            data = yaml.safe_load(handle) or {}
        return ResearchDNA(**data)
    except Exception as exc:
        raise ValueError(f"Failed to load Research DNA from {path}: {exc}") from exc


def save_research_dna(
    dna: ResearchDNA,
    root: Path | None = None,
    *,
    write_version_snapshot: bool = True,
    expected_revision: int | None = None,
) -> Path:
    dna_root = research_dna_dir(dna.id, root)
    dna_root.mkdir(parents=True, exist_ok=True)
    research_dna_versions_dir(dna.id, root).mkdir(parents=True, exist_ok=True)
    research_dna_logs_dir(dna.id, root).mkdir(parents=True, exist_ok=True)

    profile_path = research_dna_profile_path(dna.id, root)
    current_revision = _read_current_revision(profile_path)
    if expected_revision is not None and current_revision != expected_revision:
        raise ResearchDNARevisionConflictError(
            f"Revision conflict for {dna.id}: expected {expected_revision}, current {current_revision}"
        )
    dna.revision = 0 if current_revision is None else current_revision + 1
    _atomic_write_yaml(profile_path, dna.model_dump(mode="json", exclude_none=True))

    if write_version_snapshot and dna.query_versions:
        _sync_query_version_snapshots(dna, root)

    return profile_path


def list_research_dna_ids(root: Path | None = None) -> list[str]:
    base = (root or default_research_dna_root()).expanduser().resolve()
    if not base.exists():
        return []
    return sorted(entry.name for entry in base.iterdir() if entry.is_dir())


def save_external_benchmark_manifest(
    manifest: ExternalBenchmarkManifest,
    root: Path | None = None,
) -> Path:
    manifest_path = research_dna_benchmark_manifest_path(manifest.dna_id, manifest.manifest_id, root)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    _atomic_write_yaml(manifest_path, manifest.model_dump(mode="json", exclude_none=True))
    return manifest_path


def load_external_benchmark_manifest(
    dna_id: str,
    manifest_id: str,
    root: Path | None = None,
) -> ExternalBenchmarkManifest:
    path = research_dna_benchmark_manifest_path(dna_id, manifest_id, root)
    return load_external_benchmark_manifest_from_path(path)


def load_external_benchmark_manifest_from_path(path: Path) -> ExternalBenchmarkManifest:
    if not path.exists():
        raise FileNotFoundError(f"External benchmark manifest not found: {path}")
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = yaml.safe_load(handle) or {}
        return ExternalBenchmarkManifest(**data)
    except Exception as exc:
        raise ValueError(f"Failed to load external benchmark manifest from {path}: {exc}") from exc


def append_interview_log(dna_id: str, entry: InterviewLogEntry, root: Path | None = None) -> Path:
    return _append_jsonl_model(research_dna_log_path(dna_id, "interview", root), entry)


def append_run_log(dna_id: str, entry: RunLogEntry, root: Path | None = None) -> Path:
    return _append_jsonl_model(research_dna_log_path(dna_id, "runs", root), entry)


def append_screening_log(dna_id: str, entry: ScreeningLogEntry, root: Path | None = None) -> Path:
    return _append_jsonl_model(research_dna_log_path(dna_id, "screening", root), entry)


def append_approval_audit(dna_id: str, entry: ApprovalAuditEntry, root: Path | None = None) -> Path:
    return _append_jsonl_model(research_dna_log_path(dna_id, "approval_audit", root), entry)


def sanitize_research_dna_log_payload(payload: dict[str, Any]) -> dict[str, Any]:
    sanitized = sanitize_event_payload_for_log(payload)
    if isinstance(sanitized, dict):
        return sanitized
    return {}


def sanitize_research_dna_log_model(model: TModel) -> TModel:
    payload = sanitize_research_dna_log_payload(model.model_dump(mode="json", exclude_none=True))
    return cast(TModel, model.__class__.model_validate(payload))


def _normalize_research_dna_id(value: str, *, field_name: str) -> str:
    text = str(value or "").strip()
    if not text or not _RESEARCH_DNA_SAFE_ID_RE.fullmatch(text):
        raise ValueError(f"Research DNA {field_name} must be a single safe path segment")
    return text


def _confined_child(base: Path, safe_segment: str, *, field_name: str) -> Path:
    candidate = (base / safe_segment).resolve()
    try:
        candidate.relative_to(base)
    except ValueError as exc:
        raise ValueError(f"Research DNA {field_name} escapes storage root") from exc
    return candidate


def _sync_query_version_snapshots(dna: ResearchDNA, root: Path | None = None) -> None:
    versions_dir = research_dna_versions_dir(dna.id, root)
    versions_dir.mkdir(parents=True, exist_ok=True)
    for query_version in dna.query_versions:
        snapshot_path = versions_dir / f"{query_version.version}.yaml"
        _atomic_write_yaml(
            snapshot_path,
            {
                "schema_version": "research_dna.query_snapshot.v1",
                "dna_id": dna.id,
                "query_version": query_version.model_dump(mode="json", exclude_none=True),
            },
        )


def _append_jsonl_model(path: Path, model: TModel) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = sanitize_research_dna_log_payload(model.model_dump(mode="json", exclude_none=True))
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False))
        handle.write("\n")
    return path


def _atomic_write_yaml(path: Path, data: dict) -> None:
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
        with temp_path.open("w", encoding="utf-8") as handle:
            yaml.safe_dump(data, handle, sort_keys=False, allow_unicode=True)
        os.replace(temp_path, path)
    except Exception as exc:
        if temp_path and temp_path.exists():
            os.remove(temp_path)
        raise IOError(f"Failed to write YAML to {path}: {exc}") from exc


def _read_current_revision(path: Path) -> int | None:
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    revision = data.get("revision", 0)
    if not isinstance(revision, int) or revision < 0:
        raise ValueError(f"Invalid Research DNA revision in {path}: {revision}")
    return revision
