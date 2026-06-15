from __future__ import annotations

from datetime import datetime, timezone
import hashlib

import pytest
from pydantic import ValidationError

from src.schemas.cloud_paper import (
    CloudPaperLocalHydrationManifest,
    CloudPaperPageArtifactInternal,
    CloudPaperPageBlockInternal,
    CloudPaperProvenance,
)
from src.services.cloud_paper_hydration import (
    CloudPaperHydrationConflictError,
    read_cloud_paper_local_hydration_state,
    write_cloud_paper_local_bundle,
)


def _manifest(**overrides: object) -> CloudPaperLocalHydrationManifest:
    payload = {
        "paper_id": "paper_mock_ready",
        "run_id": "run_paper_mock_ready",
        "device_id": "device_001",
        "local_bundle_ref": "storage/artifacts/paper_mock_ready/run_paper_mock_ready",
        "source_pdf_relative_path": "source/source.pdf",
        "page_artifact_relative_path": "page/page.json",
        "source_pdf_sha256": "a" * 64,
        "page_artifact_sha256": "b" * 64,
        "hydrated_at": datetime(2026, 5, 30, 1, 2, 3, tzinfo=timezone.utc),
    }
    payload.update(overrides)
    return CloudPaperLocalHydrationManifest(**payload)


def test_local_hydration_manifest_to_public_state_redacts_device_and_local_refs() -> None:
    manifest = _manifest()

    public_state = manifest.to_public_state()

    assert public_state.status == "hydrated"
    assert public_state.device_id is None
    assert public_state.local_bundle_ref is None
    assert public_state.source_pdf_sha256 == "a" * 64
    assert public_state.page_artifact_sha256 == "b" * 64
    assert public_state.hydrated_at == manifest.hydrated_at


def test_local_hydration_manifest_rejects_absolute_or_cloud_paths() -> None:
    with pytest.raises(ValidationError, match="source_pdf_relative_path must be a relative local bundle path"):
        _manifest(source_pdf_relative_path="/Users/someone/source.pdf")

    with pytest.raises(ValidationError, match="page_artifact_relative_path must be a relative local bundle path"):
        _manifest(page_artifact_relative_path="gs://paperpipe/pages/page.json")


def _page_artifact() -> CloudPaperPageArtifactInternal:
    return CloudPaperPageArtifactInternal(
        paper_id="paper_mock_ready",
        run_id="run_paper_mock_ready",
        page_schema_version="cloud_page_artifact.v1",
        source_pdf_sha256="a" * 64,
        gcs_page_artifact_object_ref="gs://paperpipe-mock-pages/lab_001/paper_mock_ready/run_paper_mock_ready/page.json",
        blocks=[
            CloudPaperPageBlockInternal(
                block_id="block_001",
                page=1,
                kind="text",
                text="Hydration page text.",
            )
        ],
        warnings=[],
        provenance=CloudPaperProvenance(
            uploaded_by="mock_user",
            processor_name="paperpipe-worker",
            processor_version="0.1.0",
            created_at=datetime(2026, 5, 30, 1, 2, 3, tzinfo=timezone.utc),
            source_pdf_sha256="a" * 64,
        ),
    )


def test_local_hydration_writer_uses_safe_paths_and_blocks_stale_overwrite(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("PAPERPIPE_ARTIFACTS_DIR", str(tmp_path / "artifacts"))

    manifest = write_cloud_paper_local_bundle(
        paper_id="paper_mock_ready",
        run_id="run_paper_mock_ready",
        device_id="device_001",
        source_pdf_bytes=b"%PDF-1.4\nfirst",
        page_artifact=_page_artifact(),
        hydrated_at=datetime(2026, 5, 30, 1, 2, 3, tzinfo=timezone.utc),
    )

    assert manifest.source_pdf_relative_path == "source/source.pdf"
    assert manifest.page_artifact_relative_path == "page/page.json"
    assert manifest.to_public_state().local_bundle_ref is None

    with pytest.raises(CloudPaperHydrationConflictError):
        write_cloud_paper_local_bundle(
            paper_id="paper_mock_ready",
            run_id="run_paper_mock_ready",
            device_id="device_001",
            source_pdf_bytes=b"%PDF-1.4\nsecond",
            page_artifact=_page_artifact(),
        )

    manifest_paths = list((tmp_path / "artifacts").glob("*/run_paper_mock_ready/cloud_hydration_manifest.json"))
    assert len(manifest_paths) == 1
    assert (manifest_paths[0].parent / "source" / "source.pdf").read_bytes() == b"%PDF-1.4\nfirst"


def test_local_hydration_state_reader_redacts_manifest_and_detects_stale_source(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("PAPERPIPE_ARTIFACTS_DIR", str(tmp_path / "artifacts"))
    write_cloud_paper_local_bundle(
        paper_id="paper_mock_ready",
        run_id="run_paper_mock_ready",
        device_id="device_001",
        source_pdf_bytes=b"%PDF-1.4\nfirst",
        page_artifact=_page_artifact(),
        hydrated_at=datetime(2026, 5, 30, 1, 2, 3, tzinfo=timezone.utc),
    )
    expected_sha = hashlib.sha256(b"%PDF-1.4\nfirst").hexdigest()

    hydrated = read_cloud_paper_local_hydration_state(
        paper_id="paper_mock_ready",
        run_id="run_paper_mock_ready",
        expected_source_pdf_sha256=expected_sha,
    )
    stale = read_cloud_paper_local_hydration_state(
        paper_id="paper_mock_ready",
        run_id="run_paper_mock_ready",
        expected_source_pdf_sha256="f" * 64,
    )

    assert hydrated.status == "hydrated"
    assert hydrated.device_id is None
    assert hydrated.local_bundle_ref is None
    assert hydrated.source_pdf_sha256 == expected_sha
    assert stale.status == "stale"
    assert stale.source_pdf_sha256 == expected_sha


def test_local_hydration_state_reader_returns_not_hydrated_for_missing_manifest(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("PAPERPIPE_ARTIFACTS_DIR", str(tmp_path / "artifacts"))

    state = read_cloud_paper_local_hydration_state(
        paper_id="paper_mock_ready",
        run_id="run_paper_mock_ready",
        expected_source_pdf_sha256="a" * 64,
    )

    assert state.status == "not_hydrated"
