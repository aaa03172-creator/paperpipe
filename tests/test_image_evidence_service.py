from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256

import pytest

from src.image_evidence.service import (
    declared_image_evidence_derivative_paths,
    get_image_evidence_bundle,
    image_evidence_list_response,
    load_declared_image_evidence_derivative_artifact,
    register_image_evidence,
)
from src.image_evidence.store import load_image_derivative_bytes
from src.schemas.image_evidence import ImageEvidenceRequest


def test_register_image_evidence_local_file_populates_metadata_and_saves_bundle(tmp_path) -> None:
    root = tmp_path / "image_evidence"
    local_file = tmp_path / "raw-image.tif"
    local_file.write_bytes(b"RAWIMAGE")
    checksum = sha256(b"RAWIMAGE").hexdigest()

    result = register_image_evidence(
        request=ImageEvidenceRequest(
            image_evidence_id="img_service_demo",
            source_ref={"source_kind": "local_file", "local_path": str(local_file)},
            content_format="image/tiff",
            checksum={"algorithm": "sha256", "value": checksum},
            view_state={"viewport": {"x": 0, "y": 0, "width": 128, "height": 128}},
            handoff_targets=[{"target": "napari", "openable_ref": str(local_file)}],
        ),
        root=root,
        now=datetime(2026, 3, 22, 12, 0, tzinfo=timezone.utc),
    )

    assert result.image_evidence.image_evidence_id == "img_service_demo"
    assert result.image_evidence.title == "raw-image.tif"
    assert result.image_evidence.metadata.filename == "raw-image.tif"
    assert result.image_evidence.metadata.source_size_bytes == len(b"RAWIMAGE")
    assert result.image_evidence.view_state_ref is not None
    assert result.image_evidence.handoff_ref is not None
    assert result.image_evidence.warnings == []

    loaded = get_image_evidence_bundle("img_service_demo", root=root)
    assert loaded.image_evidence.model_dump(mode="json") == result.image_evidence.model_dump(mode="json")
    assert loaded.view_state is not None
    assert loaded.handoff_targets[0].target == "napari"


def test_register_image_evidence_missing_file_emits_warning(tmp_path) -> None:
    root = tmp_path / "image_evidence"

    result = register_image_evidence(
        request=ImageEvidenceRequest(
            image_evidence_id="img_missing",
            title="Missing file",
            source_ref={"source_kind": "local_file", "local_path": str(tmp_path / "missing.tif")},
            content_format="image/tiff",
        ),
        root=root,
        now=datetime(2026, 3, 22, 12, 0, tzinfo=timezone.utc),
    )

    assert [warning.code for warning in result.image_evidence.warnings] == ["LOCAL_SOURCE_MISSING"]


def test_register_image_evidence_checksum_mismatch_warns_and_list_sorts_recent_first(tmp_path) -> None:
    root = tmp_path / "image_evidence"
    local_file = tmp_path / "raw-image.tif"
    local_file.write_bytes(b"RAWIMAGE")

    register_image_evidence(
        request=ImageEvidenceRequest(
            image_evidence_id="img_older",
            title="Older",
            source_ref={"source_kind": "external_image_ref", "external_ref": "omero://1"},
            content_format="image/png",
        ),
        root=root,
        now=datetime(2026, 3, 22, 11, 0, tzinfo=timezone.utc),
    )
    newer = register_image_evidence(
        request=ImageEvidenceRequest(
            image_evidence_id="img_newer",
            source_ref={"source_kind": "local_file", "local_path": str(local_file)},
            content_format="image/tiff",
            checksum={"algorithm": "sha256", "value": "deadbeef"},
        ),
        root=root,
        now=datetime(2026, 3, 22, 12, 0, tzinfo=timezone.utc),
    )

    assert [warning.code for warning in newer.image_evidence.warnings] == ["CHECKSUM_MISMATCH"]
    listed = image_evidence_list_response(root=root)
    assert [item.image_evidence_id for item in listed.items] == ["img_newer", "img_older"]


def test_register_image_evidence_can_persist_declared_derivative_bundle_members(tmp_path) -> None:
    root = tmp_path / "image_evidence"
    local_file = tmp_path / "raw-image.tif"
    local_file.write_bytes(b"RAWIMAGE")

    result = register_image_evidence(
        request=ImageEvidenceRequest(
            image_evidence_id="img_with_derivative",
            source_ref={"source_kind": "local_file", "local_path": str(local_file)},
            content_format="image/tiff",
            derived_outputs=[
                {
                    "derived_output_id": "thumb_01",
                    "kind": "thumbnail",
                    "source_image_evidence_id": "img_with_derivative",
                    "created_by": "operator",
                    "created_at": datetime(2026, 3, 22, 12, 5, tzinfo=timezone.utc),
                    "tool_name": "napari",
                    "bundle_ref": {"kind": "derived_file", "path": "derivatives/thumb_01.png"},
                }
            ],
        ),
        derivative_artifacts={"derivatives/thumb_01.png": b"PNG"},
        root=root,
        now=datetime(2026, 3, 22, 12, 0, tzinfo=timezone.utc),
    )

    assert result.image_evidence.derived_outputs[0].bundle_ref is not None
    assert load_image_derivative_bytes("img_with_derivative", "thumb_01", root=root) == b"PNG"


def test_register_image_evidence_rejects_handoff_view_state_refs_without_top_level_view_state(tmp_path) -> None:
    root = tmp_path / "image_evidence"

    with pytest.raises(ValueError, match="nested view-state refs require declared view-state payload"):
        register_image_evidence(
            request=ImageEvidenceRequest(
                image_evidence_id="img_missing_view_state",
                source_ref={"source_kind": "external_image_ref", "external_ref": "omero://image/123"},
                content_format="image/png",
                handoff_targets=[
                    {
                        "target": "napari",
                        "openable_ref": "/tmp/image-001.tif",
                        "view_state_ref": {"kind": "view_state_json", "path": "view_state.json"},
                        "notes": "Open with curated channels visible.",
                    }
                ],
            ),
            root=root,
            now=datetime(2026, 3, 22, 12, 0, tzinfo=timezone.utc),
        )


def test_load_declared_image_evidence_derivative_artifact_rejects_undeclared_and_invalid_paths(tmp_path) -> None:
    root = tmp_path / "image_evidence"
    local_file = tmp_path / "raw-image.tif"
    local_file.write_bytes(b"RAWIMAGE")

    result = register_image_evidence(
        request=ImageEvidenceRequest(
            image_evidence_id="img_with_derivative",
            source_ref={"source_kind": "local_file", "local_path": str(local_file)},
            content_format="image/tiff",
            derived_outputs=[
                {
                    "derived_output_id": "thumb_01",
                    "kind": "thumbnail",
                    "source_image_evidence_id": "img_with_derivative",
                    "created_by": "operator",
                    "created_at": datetime(2026, 3, 22, 12, 5, tzinfo=timezone.utc),
                    "tool_name": "napari",
                    "bundle_ref": {"kind": "derived_file", "path": "derivatives/thumb_01.png"},
                }
            ],
        ),
        derivative_artifacts={"derivatives/thumb_01.png": b"PNG"},
        root=root,
        now=datetime(2026, 3, 22, 12, 0, tzinfo=timezone.utc),
    )

    assert declared_image_evidence_derivative_paths(result.image_evidence) == {"derivatives/thumb_01.png"}

    _, normalized_path, content = load_declared_image_evidence_derivative_artifact(
        "img_with_derivative",
        "thumb_01.png",
        root=root,
    )
    assert normalized_path == "derivatives/thumb_01.png"
    assert content == b"PNG"

    with pytest.raises(FileNotFoundError, match="is not declared"):
        load_declared_image_evidence_derivative_artifact(
            "img_with_derivative",
            "thumb_02.png",
            root=root,
        )

    with pytest.raises(ValueError, match="artifact_path is invalid"):
        load_declared_image_evidence_derivative_artifact(
            "img_with_derivative",
            "../secret.png",
            root=root,
        )
