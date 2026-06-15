from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from src.schemas.cloud_paper import (
    CLOUD_PAPER_BUNDLE_PUBLIC_SCHEMA_VERSION,
    CLOUD_PAPER_BUNDLE_SCHEMA_VERSION,
    CloudPaperBundleInternal,
    CloudPaperBundlePublic,
    CloudPaperDerivedArtifactFigure,
    CloudPaperDerivedArtifactInternal,
    CloudPaperDerivedArtifactOcrBlock,
    CloudPaperDerivedArtifactSourceLocator,
    CloudPaperDerivedArtifactTable,
    CloudPaperDerivedArtifactsResponse,
    CloudPaperHydrationState,
    CloudPaperPermissions,
    CloudPaperProvenance,
    CloudPaperSearchBlockHit,
    CloudPaperSearchHit,
    CloudPaperSearchResponse,
    CloudPaperWarning,
    derive_cloud_paper_public_bundle,
    derive_cloud_paper_public_derived_artifacts,
)


def _sample_provenance() -> CloudPaperProvenance:
    return CloudPaperProvenance(
        uploaded_by="user_001",
        processor_name="paperpipe-page-worker",
        processor_version="0.1.0",
        model_name="local-ocr",
        model_version="2026-05-30",
        created_at=datetime(2026, 5, 30, 1, 2, 3, tzinfo=timezone.utc),
        source_pdf_sha256="a" * 64,
    )


def _sample_internal_bundle(**overrides: object) -> CloudPaperBundleInternal:
    payload = {
        "paper_id": "paper_001",
        "lab_id": "lab_001",
        "cloud_source_id": "src_001",
        "gcs_pdf_object_ref": "gs://lattice-raw-pdf-dev/lab_001/paper_001/source.pdf",
        "source_pdf_sha256": "a" * 64,
        "source_pdf_size_bytes": 123456,
        "source_pdf_content_type": "application/pdf",
        "gcs_page_artifact_object_ref": "gs://lattice-page-artifacts-dev/lab_001/paper_001/page.json",
        "page_artifact_sha256": "b" * 64,
        "page_schema_version": "cloud_page_artifact.v1",
        "run_id": "run_001",
        "processing_status": "ready",
        "payload_class": "local_only",
        "created_at": datetime(2026, 5, 30, 1, 2, 3, tzinfo=timezone.utc),
        "updated_at": datetime(2026, 5, 30, 1, 5, 0, tzinfo=timezone.utc),
        "provenance": _sample_provenance(),
        "warnings": [
            CloudPaperWarning(
                code="LOW_OCR_CONFIDENCE",
                message="Some page text may need review.",
                severity="medium",
            )
        ],
        "local_hydration": CloudPaperHydrationState(status="not_hydrated"),
    }
    payload.update(overrides)
    return CloudPaperBundleInternal(**payload)


def test_internal_bundle_accepts_private_cloud_refs_and_checksum_metadata() -> None:
    bundle = _sample_internal_bundle()

    assert bundle.schema_version == CLOUD_PAPER_BUNDLE_SCHEMA_VERSION
    assert bundle.gcs_pdf_object_ref.startswith("gs://")
    assert bundle.source_pdf_sha256 == "a" * 64
    assert bundle.page_artifact_sha256 == "b" * 64


def test_public_bundle_derivation_redacts_private_refs_and_paths() -> None:
    bundle = _sample_internal_bundle(
        local_hydration=CloudPaperHydrationState(
            status="hydrated",
            device_id="device_001",
            local_bundle_ref="/Users/jangseongjin/private/paper_001",
            hydrated_at=datetime(2026, 5, 30, 2, 0, tzinfo=timezone.utc),
        )
    )

    public = derive_cloud_paper_public_bundle(
        bundle,
        current_actor_permissions=CloudPaperPermissions(role="reader", can_read_page=True),
    )
    dumped = public.model_dump(mode="json")
    dumped_text = str(dumped)

    assert public.schema_version == CLOUD_PAPER_BUNDLE_PUBLIC_SCHEMA_VERSION
    assert public.paper_id == "paper_001"
    assert public.allowed_actions == ["read_page"]
    assert "gcs_pdf_object_ref" not in dumped_text
    assert "gcs_page_artifact_object_ref" not in dumped_text
    assert "gs://lattice-raw-pdf-dev" not in dumped_text
    assert "/Users/jangseongjin" not in dumped_text
    assert public.local_hydration is not None
    assert public.local_hydration.device_id is None
    assert public.local_hydration.local_bundle_ref is None


def test_reader_can_read_ready_page_but_cannot_hydrate_by_default() -> None:
    bundle = _sample_internal_bundle()

    public = derive_cloud_paper_public_bundle(
        bundle,
        current_actor_permissions=CloudPaperPermissions(role="reader", can_read_page=True),
    )

    assert public.allowed_actions == ["read_page"]
    assert "hydrate_download" not in public.allowed_actions
    assert "read_pdf" not in public.allowed_actions


def test_admin_permissions_derive_download_and_management_actions() -> None:
    bundle = _sample_internal_bundle(
        payload_class="lab_allowed",
    )
    permissions = CloudPaperPermissions(
        role="lab_admin",
        can_read_page=True,
        can_read_pdf=True,
        can_hydrate=True,
        can_upload=True,
        can_delete=True,
        can_run_optional_ai=True,
        can_export=True,
        can_share=True,
    )

    public = derive_cloud_paper_public_bundle(bundle, current_actor_permissions=permissions)

    assert public.allowed_actions == [
        "read_page",
        "read_pdf",
        "hydrate_download",
        "run_optional_ai",
        "export",
        "share",
        "upload",
        "delete",
    ]


def test_not_ready_bundle_does_not_allow_page_read_or_hydration() -> None:
    bundle = _sample_internal_bundle(processing_status="running")

    public = derive_cloud_paper_public_bundle(
        bundle,
        current_actor_permissions=CloudPaperPermissions(role="reader", can_read_page=True),
    )

    assert public.allowed_actions == []


def test_public_bundle_model_rejects_private_fields() -> None:
    with pytest.raises(ValidationError) as exc_info:
        CloudPaperBundlePublic(
            schema_version=CLOUD_PAPER_BUNDLE_PUBLIC_SCHEMA_VERSION,
            paper_id="paper_001",
            lab_id="lab_001",
            processing_status="ready",
            payload_class="local_only",
            page_schema_version="cloud_page_artifact.v1",
            run_id="run_001",
            warnings=[],
            permissions=CloudPaperPermissions(role="reader", can_read_page=True),
            provenance_summary=_sample_internal_bundle().provenance.to_summary(),
            local_hydration=CloudPaperHydrationState(status="not_hydrated"),
            allowed_actions=["read_page"],
            gcs_pdf_object_ref="gs://lattice-raw-pdf-dev/lab_001/paper_001/source.pdf",
        )
    assert "gcs_pdf_object_ref" in str(exc_info.value)


def test_payload_class_is_explicit_and_cannot_be_unknown() -> None:
    bundle = _sample_internal_bundle(payload_class="lab_allowed")
    assert bundle.payload_class == "lab_allowed"

    with pytest.raises(ValidationError):
        _sample_internal_bundle(payload_class="public_vendor_ok")


def test_checksum_fields_reject_empty_or_malformed_values() -> None:
    with pytest.raises(ValidationError):
        _sample_internal_bundle(source_pdf_sha256="")

    with pytest.raises(ValidationError):
        _sample_internal_bundle(page_artifact_sha256="not-a-sha256")


def test_public_hydration_state_drops_absolute_or_traversal_paths() -> None:
    hydrated = CloudPaperHydrationState(
        status="hydrated",
        local_bundle_ref="../escape",
        hydrated_at=datetime(2026, 5, 30, 2, 0, tzinfo=timezone.utc),
    )

    public = hydrated.to_public()

    assert public.status == "hydrated"
    assert public.local_bundle_ref is None


def test_public_hydration_state_drops_relative_storage_paths() -> None:
    hydrated = CloudPaperHydrationState(
        status="hydrated",
        local_bundle_ref="storage/artifacts/paper_001/run_001",
        hydrated_at=datetime(2026, 5, 30, 2, 0, tzinfo=timezone.utc),
    )

    public = hydrated.to_public()

    assert public.status == "hydrated"
    assert public.local_bundle_ref is None


def test_public_bundle_rejects_allowed_actions_that_do_not_match_permissions() -> None:
    with pytest.raises(ValidationError, match="allowed_actions"):
        CloudPaperBundlePublic(
            schema_version=CLOUD_PAPER_BUNDLE_PUBLIC_SCHEMA_VERSION,
            paper_id="paper_001",
            lab_id="lab_001",
            processing_status="running",
            payload_class="local_only",
            page_schema_version="cloud_page_artifact.v1",
            run_id="run_001",
            warnings=[],
            permissions=CloudPaperPermissions(role="reader", can_read_page=True),
            provenance_summary=_sample_internal_bundle().provenance.to_summary(),
            local_hydration=CloudPaperHydrationState(status="not_hydrated"),
            allowed_actions=["delete", "read_page"],
        )


def test_cloud_search_response_requires_ready_readable_public_hits() -> None:
    ready_bundle = derive_cloud_paper_public_bundle(
        _sample_internal_bundle(),
        current_actor_permissions=CloudPaperPermissions(role="reader", can_read_page=True),
    )

    response = CloudPaperSearchResponse(
        query=" processed text ",
        items=[
            CloudPaperSearchHit(
                bundle=ready_bundle,
                matched_blocks=[
                    CloudPaperSearchBlockHit(
                        block_id="block_001",
                        page=1,
                        kind="text",
                        text_snippet="Mock processed text.",
                        payload_class="local_only",
                        metadata={"section": "abstract", "service_account": "hidden@example.com"},
                    )
                ],
            )
        ],
    )

    assert response.schema_version == "cloud_paper_search.v1"
    assert response.query == "processed text"
    assert response.items[0].matched_blocks[0].metadata == {"section": "abstract"}

    running_bundle = derive_cloud_paper_public_bundle(
        _sample_internal_bundle(processing_status="running"),
        current_actor_permissions=CloudPaperPermissions(role="reader", can_read_page=True),
    )
    with pytest.raises(ValidationError, match="ready page artifacts"):
        CloudPaperSearchHit(
            bundle=running_bundle,
            matched_blocks=[
                CloudPaperSearchBlockHit(
                    block_id="block_001",
                    page=1,
                    kind="text",
                    text_snippet="Mock processed text.",
                    payload_class="local_only",
                )
            ],
        )


def test_cloud_derived_artifacts_public_response_redacts_raw_refs_and_preserves_source_lineage() -> None:
    internal = CloudPaperDerivedArtifactInternal(
        paper_id="paper_001",
        run_id="run_001",
        source_pdf_sha256="a" * 64,
        gcs_derived_artifact_object_ref="gs://lattice-derived-dev/lab_001/paper_001/run_001/derived.json",
        payload_class="local_only",
        ocr_blocks=[
            CloudPaperDerivedArtifactOcrBlock(
                ocr_block_id="ocr_001",
                text="OCR text recovered from a rendered PDF page.",
                confidence=0.91,
                source=CloudPaperDerivedArtifactSourceLocator(
                    page=1,
                    source_pdf_sha256="a" * 64,
                    bbox_pct={"left": 0.1, "top": 0.2, "width": 0.6, "height": 0.1},
                ),
                metadata={
                    "engine": "mock-ocr",
                    "gcs_image_object_ref": "gs://lattice-derived-dev/page-1.png",
                    "local_path": "/Users/mock/page-1.png",
                },
            )
        ],
        tables=[
            CloudPaperDerivedArtifactTable(
                table_id="table_001",
                page=2,
                caption="Mock reconstructed cohort table.",
                columns=["Group", "N"],
                rows=[["Control", "10"], ["Treatment", "12"]],
                confidence=0.82,
                source=CloudPaperDerivedArtifactSourceLocator(page=2, source_pdf_sha256="a" * 64),
            )
        ],
        figures=[
            CloudPaperDerivedArtifactFigure(
                figure_id="figure_001",
                page=3,
                caption="Mock figure crop.",
                bbox_pct={"left": 0.1, "top": 0.1, "width": 0.7, "height": 0.5},
                image_available=True,
                image_route="/api/cloud/papers/paper_001/figures/figure_001/image",
                confidence=0.77,
                source=CloudPaperDerivedArtifactSourceLocator(page=3, source_pdf_sha256="a" * 64),
                metadata={"signed_url": "https://signed.example.test/private"},
            )
        ],
        provenance=_sample_provenance(),
        worker_metadata={
            "service_account": "worker@example.iam.gserviceaccount.com",
            "local_path": "/Users/mock/derived.json",
        },
    )

    public = derive_cloud_paper_public_derived_artifacts(internal)
    payload = public.model_dump(mode="json")
    payload_text = str(payload)

    assert public.schema_version == "cloud_paper_derived_artifacts.v1"
    assert public.paper_id == "paper_001"
    assert public.ocr_blocks[0].source.page == 1
    assert public.tables[0].rows[1] == ["Treatment", "12"]
    assert public.figures[0].image_route == "/api/cloud/papers/paper_001/figures/figure_001/image"
    assert public.provenance_summary.source_pdf_sha256 == "a" * 64
    assert "gcs_derived_artifact_object_ref" not in payload_text
    assert "gs://" not in payload_text
    assert "signed_url" not in payload_text
    assert "service_account" not in payload_text
    assert "/Users/" not in payload_text


def test_cloud_derived_artifacts_public_response_rejects_private_extra_fields() -> None:
    with pytest.raises(ValidationError, match="gcs_derived_artifact_object_ref"):
        CloudPaperDerivedArtifactsResponse(
            paper_id="paper_001",
            run_id="run_001",
            source_pdf_sha256="a" * 64,
            payload_class="local_only",
            provenance_summary=_sample_provenance().to_summary(),
            gcs_derived_artifact_object_ref="gs://lattice-derived-dev/private.json",
        )
