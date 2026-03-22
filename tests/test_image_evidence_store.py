from __future__ import annotations

from datetime import datetime, timezone

import pytest

import src.image_evidence.store as image_evidence_store
from src.image_evidence.store import (
    image_evidence_derivative_path,
    image_evidence_handoff_path,
    image_evidence_json_path,
    image_evidence_view_state_path,
    list_image_evidence_ids,
    load_image_derivative_bytes,
    load_image_evidence,
    load_image_handoff_targets,
    load_image_view_state,
    save_image_derivative_bytes,
    save_image_evidence_bundle,
)
from src.schemas.image_evidence import ImageEvidence, ImageHandoffTarget, ImageViewState


def _sample_image_evidence(title: str = "Representative microscopy image") -> ImageEvidence:
    return ImageEvidence(
        image_evidence_id="img_evidence_001",
        title=title,
        created_at=datetime(2026, 3, 22, 10, 0, tzinfo=timezone.utc),
        paper_id="paper-001",
        paper_slug="paper-001-note",
        source_ref={"source_kind": "local_file", "local_path": "/tmp/image-001.tif"},
        content_format="image/tiff",
        metadata={"filename": "image-001.tif", "width_px": 1024, "height_px": 768},
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
            }
        ],
    )


def _sample_view_state() -> ImageViewState:
    return ImageViewState(
        active_channels=["GFP", "DAPI"],
        zoom_level=2.0,
        viewport={"x": 0, "y": 0, "width": 256, "height": 256},
    )


def _sample_handoff_targets() -> list[ImageHandoffTarget]:
    return [
        ImageHandoffTarget(
            target="napari",
            openable_ref="/tmp/image-001.tif",
            view_state_ref={"kind": "view_state_json", "path": "view_state.json"},
            notes="Open with curated channels visible.",
        )
    ]


def test_image_evidence_store_roundtrip_creates_expected_layout(tmp_path) -> None:
    root = tmp_path / "image_evidence"
    image_evidence = _sample_image_evidence()
    view_state = _sample_view_state()
    handoff_targets = _sample_handoff_targets()

    result = save_image_evidence_bundle(
        image_evidence,
        view_state=view_state,
        handoff_targets=handoff_targets,
        root=root,
    )
    save_image_derivative_bytes(image_evidence.image_evidence_id, "thumb_01", b"PNG", root=root)

    loaded = load_image_evidence(image_evidence.image_evidence_id, root)
    loaded_view_state = load_image_view_state(image_evidence.image_evidence_id, root)
    loaded_handoff_targets = load_image_handoff_targets(image_evidence.image_evidence_id, root)
    loaded_derivative = load_image_derivative_bytes(image_evidence.image_evidence_id, "thumb_01", root=root)

    assert result["json"] == image_evidence_json_path(image_evidence.image_evidence_id, root)
    assert result["view_state"] == image_evidence_view_state_path(image_evidence.image_evidence_id, root)
    assert result["handoff"] == image_evidence_handoff_path(image_evidence.image_evidence_id, root)
    assert loaded.title == image_evidence.title
    assert loaded_view_state.active_channels == ["GFP", "DAPI"]
    assert loaded_handoff_targets[0].target == "napari"
    assert loaded_derivative == b"PNG"
    assert image_evidence_derivative_path(image_evidence.image_evidence_id, "thumb_01", root=root).exists()
    assert list_image_evidence_ids(root) == [image_evidence.image_evidence_id]


def test_image_evidence_store_removes_stale_optional_files_on_overwrite(tmp_path) -> None:
    root = tmp_path / "image_evidence"
    original = _sample_image_evidence()
    save_image_evidence_bundle(
        original,
        view_state=_sample_view_state(),
        handoff_targets=_sample_handoff_targets(),
        root=root,
    )

    updated = ImageEvidence(
        image_evidence_id="img_evidence_001",
        title="Updated image evidence",
        created_at=datetime(2026, 3, 22, 11, 0, tzinfo=timezone.utc),
        source_ref={"source_kind": "external_image_ref", "external_ref": "omero://image/123"},
        content_format="image/png",
        metadata={"width_px": 600, "height_px": 400},
    )
    save_image_evidence_bundle(updated, root=root)

    loaded = load_image_evidence(updated.image_evidence_id, root)
    assert loaded.title == "Updated image evidence"
    assert not image_evidence_view_state_path(updated.image_evidence_id, root).exists()
    assert not image_evidence_handoff_path(updated.image_evidence_id, root).exists()
    assert not image_evidence_derivative_path(updated.image_evidence_id, "thumb_01", root=root).exists()


def test_image_evidence_store_rolls_back_if_handoff_write_fails(tmp_path, monkeypatch) -> None:
    root = tmp_path / "image_evidence"
    original = _sample_image_evidence(title="Original title")
    save_image_evidence_bundle(
        original,
        view_state=_sample_view_state(),
        handoff_targets=_sample_handoff_targets(),
        root=root,
    )

    updated = _sample_image_evidence(title="Updated title")
    original_atomic_write_bytes = image_evidence_store._atomic_write_bytes
    call_count = {"value": 0}

    def fail_on_third_write(path, content):
        call_count["value"] += 1
        if call_count["value"] == 3:
            raise IOError("boom")
        return original_atomic_write_bytes(path, content)

    monkeypatch.setattr(image_evidence_store, "_atomic_write_bytes", fail_on_third_write)

    with pytest.raises(OSError):
        save_image_evidence_bundle(
            updated,
            view_state=_sample_view_state(),
            handoff_targets=_sample_handoff_targets(),
            root=root,
        )

    loaded = load_image_evidence(updated.image_evidence_id, root)
    loaded_view_state = load_image_view_state(updated.image_evidence_id, root)
    loaded_handoff_targets = load_image_handoff_targets(updated.image_evidence_id, root)
    assert loaded.title == "Original title"
    assert loaded_view_state.zoom_level == 2.0
    assert loaded_handoff_targets[0].target == "napari"
