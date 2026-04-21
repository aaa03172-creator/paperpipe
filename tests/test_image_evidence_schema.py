from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from src.schemas.image_evidence import (
    ImageArtifactRef,
    ImageEvidence,
    ImageEvidenceRequest,
    ImageSourceRef,
    summarize_image_evidence,
)


def _sample_image_evidence() -> ImageEvidence:
    return ImageEvidence(
        image_evidence_id="img_evidence_001",
        title="Representative microscopy image",
        created_at=datetime(2026, 3, 22, 10, 0, tzinfo=timezone.utc),
        paper_id="paper-001",
        paper_slug="paper-001-note",
        source_ref={
            "source_kind": "local_file",
            "local_path": "/Users/jangseongjin/data/image-001.tif",
        },
        content_format="image/tiff",
        checksum={"algorithm": "sha256", "value": "abc123"},
        metadata={
            "filename": "image-001.tif",
            "width_px": 1024,
            "height_px": 768,
            "channel_count": 3,
            "modality": "fluorescence",
        },
        view_state_ref={"kind": "view_state_json", "path": "view_state.json"},
        handoff_ref={"kind": "handoff_json", "path": "handoff.json"},
        derived_outputs=[
            {
                "derived_output_id": "thumb_01",
                "kind": "thumbnail",
                "source_image_evidence_id": "img_evidence_001",
                "created_by": "operator",
                "created_at": datetime(2026, 3, 22, 10, 5, tzinfo=timezone.utc),
                "tool_name": "napari",
                "bundle_ref": {"kind": "derived_file", "path": "derivatives/thumb_01.png"},
                "view_state_ref": {"kind": "view_state_json", "path": "view_state.json"},
            }
        ],
        linked_claim_refs=[{"claim_id": "claim-001", "note": "Representative image only"}],
        linked_artifact_refs=[{"artifact_kind": "meeting_pack", "artifact_id": "pack-001"}],
        warnings=[{"code": "REPRESENTATIVE_ONLY", "message": "Image is illustrative, not exhaustive."}],
    )


def test_image_evidence_request_accepts_embedded_view_state_and_handoff_metadata() -> None:
    request = ImageEvidenceRequest(
        title=" Representative microscopy image ",
        source_ref={"source_kind": "external_image_ref", "external_ref": "omero://image/123"},
        content_format=" image/png ",
        metadata={"width_px": 600, "height_px": 400},
        view_state={
            "active_channels": [" GFP ", " DAPI "],
            "zoom_level": 2.5,
            "viewport": {"x": 0, "y": 0, "width": 256, "height": 256},
        },
        handoff_targets=[
            {
                "target": "napari",
                "openable_ref": "/tmp/image.png",
                "view_state_ref": {"kind": "view_state_json", "path": "view_state.json"},
            }
        ],
    )

    assert request.title == "Representative microscopy image"
    assert request.content_format == "image/png"
    assert request.view_state is not None
    assert request.view_state.active_channels == ["GFP", "DAPI"]
    assert request.handoff_targets[0].target == "napari"


def test_local_file_source_ref_requires_local_path() -> None:
    with pytest.raises(ValidationError):
        ImageSourceRef(source_kind="local_file")


def test_external_image_ref_rejects_local_path() -> None:
    with pytest.raises(ValidationError):
        ImageSourceRef(
            source_kind="external_image_ref",
            external_ref="omero://image/123",
            local_path="/tmp/image.tif",
        )


def test_image_artifact_ref_requires_relative_path() -> None:
    with pytest.raises(ValidationError):
        ImageArtifactRef(kind="derived_file", path="/tmp/thumb.png")


def test_image_evidence_rejects_duplicate_derived_output_ids() -> None:
    with pytest.raises(ValidationError):
        ImageEvidence(
            image_evidence_id="img_evidence_001",
            title="Representative microscopy image",
            created_at=datetime(2026, 3, 22, 10, 0, tzinfo=timezone.utc),
            source_ref={"source_kind": "local_file", "local_path": "/tmp/image.tif"},
            content_format="image/tiff",
            derived_outputs=[
                {
                    "derived_output_id": "thumb_01",
                    "kind": "thumbnail",
                    "source_image_evidence_id": "img_evidence_001",
                    "created_by": "operator",
                    "created_at": datetime(2026, 3, 22, 10, 5, tzinfo=timezone.utc),
                    "tool_name": "napari",
                    "bundle_ref": {"kind": "derived_file", "path": "derivatives/thumb_01.png"},
                },
                {
                    "derived_output_id": "thumb_01",
                    "kind": "overlay",
                    "source_image_evidence_id": "img_evidence_001",
                    "created_by": "operator",
                    "created_at": datetime(2026, 3, 22, 10, 6, tzinfo=timezone.utc),
                    "tool_name": "napari",
                    "bundle_ref": {"kind": "derived_file", "path": "derivatives/thumb_01_overlay.png"},
                },
            ],
        )


def test_image_evidence_rejects_derived_view_state_refs_without_matching_top_level_ref() -> None:
    with pytest.raises(ValidationError, match="derived_outputs.view_state_ref requires top-level view_state_ref"):
        ImageEvidence(
            image_evidence_id="img_evidence_001",
            title="Representative microscopy image",
            created_at=datetime(2026, 3, 22, 10, 0, tzinfo=timezone.utc),
            source_ref={"source_kind": "local_file", "local_path": "/tmp/image.tif"},
            content_format="image/tiff",
            derived_outputs=[
                {
                    "derived_output_id": "thumb_01",
                    "kind": "thumbnail",
                    "source_image_evidence_id": "img_evidence_001",
                    "created_by": "operator",
                    "created_at": datetime(2026, 3, 22, 10, 5, tzinfo=timezone.utc),
                    "tool_name": "napari",
                    "bundle_ref": {"kind": "derived_file", "path": "derivatives/thumb_01.png"},
                    "view_state_ref": {"kind": "view_state_json", "path": "view_state.json"},
                }
            ],
        )

    with pytest.raises(
        ValidationError,
        match="derived_outputs.view_state_ref values must match ImageEvidence.view_state_ref.path",
    ):
        ImageEvidence(
            image_evidence_id="img_evidence_001",
            title="Representative microscopy image",
            created_at=datetime(2026, 3, 22, 10, 0, tzinfo=timezone.utc),
            source_ref={"source_kind": "local_file", "local_path": "/tmp/image.tif"},
            content_format="image/tiff",
            view_state_ref={"kind": "view_state_json", "path": "view_state.json"},
            derived_outputs=[
                {
                    "derived_output_id": "thumb_01",
                    "kind": "thumbnail",
                    "source_image_evidence_id": "img_evidence_001",
                    "created_by": "operator",
                    "created_at": datetime(2026, 3, 22, 10, 5, tzinfo=timezone.utc),
                    "tool_name": "napari",
                    "bundle_ref": {"kind": "derived_file", "path": "derivatives/thumb_01.png"},
                    "view_state_ref": {"kind": "view_state_json", "path": "alternate_view_state.json"},
                }
            ],
        )


def test_image_evidence_schema_preserves_raw_vs_derived_separation() -> None:
    image_evidence = _sample_image_evidence()
    summary = summarize_image_evidence(image_evidence)

    assert image_evidence.source_ref.local_path == "/Users/jangseongjin/data/image-001.tif"
    assert image_evidence.derived_outputs[0].bundle_ref is not None
    assert image_evidence.derived_outputs[0].bundle_ref.path == "derivatives/thumb_01.png"
    assert summary.derived_output_count == 1
    assert summary.has_view_state is True
    assert summary.has_handoff is True
