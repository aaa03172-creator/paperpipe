from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import os
from pathlib import Path
import shutil

from src.schemas.cloud_paper import (
    CloudPaperHydrationState,
    CloudPaperLocalHydrationManifest,
    CloudPaperPageArtifactInternal,
)
from src.services.runtime_paths import artifact_run_dir, artifact_run_dir_candidates, artifacts_root


class CloudPaperHydrationConflictError(RuntimeError):
    def __init__(self, manifest: CloudPaperLocalHydrationManifest):
        super().__init__("Local cloud paper bundle is stale or conflicts with the cloud source.")
        self.manifest = manifest


class CloudPaperHydrationWriteError(RuntimeError):
    pass


def write_cloud_paper_local_bundle(
    *,
    paper_id: str,
    run_id: str,
    device_id: str,
    source_pdf_bytes: bytes,
    page_artifact: CloudPaperPageArtifactInternal,
    hydrated_at: datetime | None = None,
) -> CloudPaperLocalHydrationManifest:
    source_pdf_sha256 = hashlib.sha256(source_pdf_bytes).hexdigest()
    page_artifact_bytes = page_artifact.model_dump_json(indent=2).encode("utf-8")
    page_artifact_sha256 = hashlib.sha256(page_artifact_bytes).hexdigest()
    target_dir = artifact_run_dir(paper_id, run_id)
    existing_manifest = _load_existing_manifest(target_dir)
    if existing_manifest is not None:
        if (
            existing_manifest.source_pdf_sha256 == source_pdf_sha256
            and existing_manifest.page_artifact_sha256 == page_artifact_sha256
        ):
            return existing_manifest
        raise CloudPaperHydrationConflictError(existing_manifest)

    tmp_dir = target_dir.parent / f".{target_dir.name}.hydrate-{os.getpid()}"
    try:
        if tmp_dir.exists():
            shutil.rmtree(tmp_dir)
        (tmp_dir / "source").mkdir(parents=True, exist_ok=False)
        (tmp_dir / "page").mkdir(parents=True, exist_ok=False)
        (tmp_dir / "source" / "source.pdf").write_bytes(source_pdf_bytes)
        (tmp_dir / "page" / "page.json").write_bytes(page_artifact_bytes)
        manifest = CloudPaperLocalHydrationManifest(
            paper_id=paper_id,
            run_id=run_id,
            device_id=device_id,
            local_bundle_ref=str(target_dir.relative_to(artifacts_root().parent)),
            source_pdf_relative_path="source/source.pdf",
            page_artifact_relative_path="page/page.json",
            source_pdf_sha256=source_pdf_sha256,
            page_artifact_sha256=page_artifact_sha256,
            hydrated_at=hydrated_at or datetime.now(timezone.utc),
        )
        (tmp_dir / "cloud_hydration_manifest.json").write_text(
            manifest.model_dump_json(indent=2),
            encoding="utf-8",
        )
        target_dir.parent.mkdir(parents=True, exist_ok=True)
        tmp_dir.replace(target_dir)
        return manifest
    except Exception as exc:
        if tmp_dir.exists():
            shutil.rmtree(tmp_dir, ignore_errors=True)
        if isinstance(exc, CloudPaperHydrationConflictError):
            raise
        raise CloudPaperHydrationWriteError(str(exc)) from exc


def read_cloud_paper_local_hydration_state(
    *,
    paper_id: str,
    run_id: str,
    expected_source_pdf_sha256: str | None = None,
) -> CloudPaperHydrationState:
    for target_dir in artifact_run_dir_candidates(paper_id, run_id):
        manifest = _load_existing_manifest(target_dir)
        if manifest is None:
            continue
        public_state = manifest.to_public_state()
        if (
            expected_source_pdf_sha256 is not None
            and manifest.source_pdf_sha256 != expected_source_pdf_sha256.lower()
        ):
            return CloudPaperHydrationState(
                status="stale",
                hydrated_at=public_state.hydrated_at,
                source_pdf_sha256=public_state.source_pdf_sha256,
                page_artifact_sha256=public_state.page_artifact_sha256,
            )
        return public_state
    return CloudPaperHydrationState(status="not_hydrated")


def _load_existing_manifest(target_dir: Path) -> CloudPaperLocalHydrationManifest | None:
    manifest_path = target_dir / "cloud_hydration_manifest.json"
    if not manifest_path.exists():
        return None
    return CloudPaperLocalHydrationManifest.model_validate_json(manifest_path.read_text(encoding="utf-8"))
