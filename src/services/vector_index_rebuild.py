from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.contracts.document_artifact_v2 import DocumentArtifactV2
from src.schemas.agent_artifacts import DocumentArtifact
from src.services.runtime_paths import artifacts_root, rag_root, storage_root


CONFIRM_REBUILD_PHRASE = "REBUILD_LOCAL_CHROMA"


@dataclass(frozen=True)
class VectorRebuildCandidate:
    paper_segment: str
    run_id: str
    document_id: str
    run_dir: str
    document_artifact_path: str
    index_artifact_path: str | None
    run_status: str | None
    sort_timestamp: str
    chunk_count: int | None


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def load_document_artifact_for_rebuild(path: Path) -> DocumentArtifact | DocumentArtifactV2:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("document artifact must be a JSON object")
    if "document_id" in payload:
        return DocumentArtifactV2.model_validate(payload)
    if "doc_id" in payload and "pages" in payload and "source" not in payload and "metadata" not in payload:
        return DocumentArtifactV2.model_validate(
            {
                "document_id": payload["doc_id"],
                "meta": {
                    "title": str(payload["doc_id"]),
                    "authors": [],
                    "source_ref": "",
                },
                "pages": payload.get("pages") or [],
                "tables": payload.get("tables") or [],
            }
        )
    if "doc_id" in payload:
        return DocumentArtifact.model_validate(payload)
    raise ValueError("document artifact missing document_id/doc_id")


def _relative(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path)


def _timestamp_for_run(run_dir: Path, run_meta: dict[str, Any]) -> str:
    for key in ("finished_at", "updated_at", "started_at", "created_at"):
        value = str(run_meta.get(key) or "").strip()
        if value:
            return value
    return datetime.fromtimestamp(run_dir.stat().st_mtime, tz=timezone.utc).isoformat()


def _document_id_from_artifact(document_artifact: dict[str, Any], run_meta: dict[str, Any]) -> str:
    for key in ("document_id", "doc_id"):
        value = str(document_artifact.get(key) or "").strip()
        if value:
            return value
    value = str(run_meta.get("paper_id") or "").strip()
    return value


def collect_vector_rebuild_candidates(
    *,
    artifact_root: Path | None = None,
    latest_only: bool = True,
) -> list[VectorRebuildCandidate]:
    root = (artifact_root or artifacts_root()).expanduser().resolve()
    if not root.exists():
        return []

    candidates: list[VectorRebuildCandidate] = []
    for document_path in sorted(root.glob("*/*/document_artifact.json")):
        run_dir = document_path.parent
        run_meta_path = run_dir / "run_meta.json"
        index_path = run_dir / "index_artifact.json"
        document_artifact = _read_json(document_path)
        run_meta = _read_json(run_meta_path)
        document_id = _document_id_from_artifact(document_artifact, run_meta)
        if not document_id:
            continue
        index_artifact = _read_json(index_path) if index_path.exists() else {}
        chunk_count = index_artifact.get("chunk_count")
        candidates.append(
            VectorRebuildCandidate(
                paper_segment=run_dir.parent.name,
                run_id=run_dir.name,
                document_id=document_id,
                run_dir=_relative(run_dir, root),
                document_artifact_path=_relative(document_path, root),
                index_artifact_path=_relative(index_path, root) if index_path.exists() else None,
                run_status=str(run_meta.get("status") or "").strip() or None,
                sort_timestamp=_timestamp_for_run(run_dir, run_meta),
                chunk_count=int(chunk_count) if isinstance(chunk_count, int) else None,
            )
        )

    if not latest_only:
        return candidates

    latest_by_document: dict[str, VectorRebuildCandidate] = {}
    for candidate in candidates:
        existing = latest_by_document.get(candidate.document_id)
        if existing is None or candidate.sort_timestamp > existing.sort_timestamp:
            latest_by_document[candidate.document_id] = candidate
    return sorted(latest_by_document.values(), key=lambda item: (item.paper_segment, item.run_id))


def build_vector_rebuild_dry_run_plan(
    *,
    artifact_root: Path | None = None,
    vector_root: Path | None = None,
    backup_root: Path | None = None,
    latest_only: bool = True,
    sample_limit: int = 25,
) -> dict[str, Any]:
    resolved_artifact_root = (artifact_root or artifacts_root()).expanduser().resolve()
    resolved_vector_root = (vector_root or rag_root()).expanduser().resolve()
    resolved_backup_root = (backup_root or (storage_root() / "backups")).expanduser().resolve()
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    proposed_backup_dir = resolved_backup_root / f"rag_before_rebuild_{timestamp}"
    candidates = collect_vector_rebuild_candidates(
        artifact_root=resolved_artifact_root,
        latest_only=latest_only,
    )

    return {
        "schema_version": "vector_rebuild_dry_run.v1",
        "dry_run": True,
        "will_modify_chroma": False,
        "latest_only": latest_only,
        "artifact_root": str(resolved_artifact_root),
        "vector_root": str(resolved_vector_root),
        "backup_root": str(resolved_backup_root),
        "proposed_backup_dir": str(proposed_backup_dir),
        "candidate_count": len(candidates),
        "total_candidate_chunks": sum(item.chunk_count or 0 for item in candidates),
        "candidates": [asdict(item) for item in candidates],
        "candidates_sample": [asdict(item) for item in candidates[:sample_limit]],
    }


def validate_vector_rebuild_candidates(
    *,
    artifact_root: Path,
    candidates: list[dict[str, Any]],
    sample_limit: int = 25,
) -> dict[str, Any]:
    root = artifact_root.expanduser().resolve()
    valid_count = 0
    v1_count = 0
    v2_count = 0
    failures: list[dict[str, str]] = []
    for candidate in candidates:
        relative_path = str(candidate.get("document_artifact_path") or "")
        try:
            doc = load_document_artifact_for_rebuild(root / relative_path)
            valid_count += 1
            if isinstance(doc, DocumentArtifactV2):
                v2_count += 1
            else:
                v1_count += 1
        except Exception as exc:
            failures.append(
                {
                    "document_artifact_path": relative_path,
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )

    return {
        "valid_count": valid_count,
        "v1_count": v1_count,
        "v2_count": v2_count,
        "failure_count": len(failures),
        "failures": failures[:sample_limit],
    }


def validate_vector_rebuild_apply(*, apply: bool, confirm: str | None) -> str | None:
    if not apply:
        return None
    if str(confirm or "").strip() != CONFIRM_REBUILD_PHRASE:
        return f"Refusing rebuild without --confirm {CONFIRM_REBUILD_PHRASE}"
    return None
