from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256

from src.image_evidence import get_image_evidence_bundle as package_get_image_evidence_bundle
from src.image_evidence import register_image_evidence as package_register_image_evidence
from src.image_evidence.service import (
    get_image_evidence_bundle,
    image_evidence_list_response,
    register_image_evidence,
)
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


def test_image_evidence_list_skips_unreadable_bundles(tmp_path) -> None:
    root = tmp_path / "image_evidence"

    register_image_evidence(
        request=ImageEvidenceRequest(
            image_evidence_id="img_valid",
            title="Valid",
            source_ref={"source_kind": "external_image_ref", "external_ref": "omero://valid"},
            content_format="image/png",
        ),
        root=root,
        now=datetime(2026, 3, 22, 12, 0, tzinfo=timezone.utc),
    )

    broken_dir = root / "img_broken"
    broken_dir.mkdir(parents=True, exist_ok=True)
    (broken_dir / "image_evidence.json").write_text("{not valid json", encoding="utf-8")

    listed = image_evidence_list_response(root=root)

    assert listed.total == 1
    assert [item.image_evidence_id for item in listed.items] == ["img_valid"]


def test_image_evidence_package_reexports_service_entrypoints(tmp_path) -> None:
    root = tmp_path / "image_evidence"
    local_file = tmp_path / "raw-image.tif"
    local_file.write_bytes(b"RAWIMAGE")

    result = package_register_image_evidence(
        request=ImageEvidenceRequest(
            image_evidence_id="img_pkg_export",
            source_ref={"source_kind": "local_file", "local_path": str(local_file)},
            content_format="image/tiff",
        ),
        root=root,
        now=datetime(2026, 3, 22, 12, 0, tzinfo=timezone.utc),
    )

    loaded = package_get_image_evidence_bundle("img_pkg_export", root=root)
    assert loaded.image_evidence.image_evidence_id == result.image_evidence.image_evidence_id
