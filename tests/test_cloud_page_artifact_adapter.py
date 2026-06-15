from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from src.schemas.cloud_paper import (
    CloudPaperPageArtifactInternal,
    CloudPaperPageBlockInternal,
    CloudPaperProvenance,
    CloudPaperWarning,
    derive_cloud_page_artifact_public,
)


def _provenance() -> CloudPaperProvenance:
    return CloudPaperProvenance(
        uploaded_by="mock_user",
        processor_name="paperpipe-worker",
        processor_version="0.1.0",
        model_name="mock-model",
        model_version="2026-05-30",
        created_at=datetime(2026, 5, 30, 1, 2, 3, tzinfo=timezone.utc),
        source_pdf_sha256="a" * 64,
    )


def _internal_artifact(**overrides: object) -> CloudPaperPageArtifactInternal:
    payload = {
        "paper_id": "paper_mock_ready",
        "run_id": "run_paper_mock_ready",
        "page_schema_version": "cloud_page_artifact.v1",
        "source_pdf_sha256": "a" * 64,
        "gcs_page_artifact_object_ref": "gs://paperpipe-mock-pages/lab_001/paper_mock_ready/page.json",
        "blocks": [
            CloudPaperPageBlockInternal(
                block_id="block_001",
                page=1,
                kind="text",
                text="Mock processed page text.",
                bbox_pct={"left": 0.1, "top": 0.1, "width": 0.8, "height": 0.2},
                metadata={
                    "section": "abstract",
                    "note": "gs://paperpipe-mock-pages/lab_001/paper_mock_ready/page.json",
                    "nested": {"ref": "gs://paperpipe-mock-pages/lab_001/paper_mock_ready/page.json"},
                },
                worker_metadata={
                    "service_account": "worker@example.iam.gserviceaccount.com",
                    "signed_url": "https://storage.example/signed",
                    "local_path": "/Users/someone/page.json",
                },
            )
        ],
        "warnings": [
            CloudPaperWarning(
                code="MOCK_PAGE_WARNING",
                message="Mock warning preserved for viewer.",
                severity="low",
            )
        ],
        "provenance": _provenance(),
        "worker_metadata": {
            "gcs_page_artifact_object_ref": "gs://paperpipe-mock-pages/lab_001/paper_mock_ready/page.json",
            "service_account": "worker@example.iam.gserviceaccount.com",
            "local_path": "/Users/someone/page.json",
        },
    }
    payload.update(overrides)
    return CloudPaperPageArtifactInternal(**payload)


def test_cloud_page_artifact_adapter_preserves_viewer_fields_and_redacts_worker_fields() -> None:
    public = derive_cloud_page_artifact_public(_internal_artifact())

    assert public.paper_id == "paper_mock_ready"
    assert public.run_id == "run_paper_mock_ready"
    assert public.page_schema_version == "cloud_page_artifact.v1"
    assert public.source_pdf_sha256 == "a" * 64
    assert public.blocks[0].block_id == "block_001"
    assert public.blocks[0].page == 1
    assert public.blocks[0].metadata == {"section": "abstract"}
    assert public.warnings[0].code == "MOCK_PAGE_WARNING"
    assert public.provenance_summary.processor_name == "paperpipe-worker"

    public_text = str(public.model_dump(mode="json"))
    assert "gcs_page_artifact_object_ref" not in public_text
    assert "gs://" not in public_text
    assert "signed_url" not in public_text
    assert "service_account" not in public_text
    assert "/Users/" not in public_text
    assert "worker_metadata" not in public_text


def test_cloud_page_artifact_internal_requires_opaque_gcs_ref() -> None:
    with pytest.raises(ValidationError, match="gcs_page_artifact_object_ref must be an opaque GCS object ref"):
        _internal_artifact(gcs_page_artifact_object_ref="https://storage.example/page.json")
