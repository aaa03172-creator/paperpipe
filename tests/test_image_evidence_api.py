from __future__ import annotations

from fastapi.testclient import TestClient

from backend import main as api_main
from src.services.path_masking import mask_local_path


def test_image_evidence_api_register_roundtrip_and_reads(tmp_path, monkeypatch) -> None:
    image_root = tmp_path / "image_evidence"
    local_file = tmp_path / "raw-image.tif"
    local_file.write_bytes(b"RAWIMAGE")

    monkeypatch.setenv("PAPERPIPE_IMAGE_EVIDENCE_DIR", str(image_root))
    monkeypatch.delenv("LATTICE_API_KEY", raising=False)
    monkeypatch.delenv("PAPERPIPE_API_KEY", raising=False)

    client = TestClient(api_main.app)
    created = client.post(
        "/image-evidence/register",
        json={
            "image_evidence_id": "img_api_demo",
            "source_ref": {"source_kind": "local_file", "local_path": str(local_file)},
            "content_format": "image/tiff",
            "view_state": {"viewport": {"x": 0, "y": 0, "width": 64, "height": 64}},
            "handoff_targets": [{"target": "napari", "openable_ref": str(local_file)}],
        },
    )
    assert created.status_code == 200
    payload = created.json()

    assert payload["image_evidence"]["image_evidence_id"] == "img_api_demo"
    assert payload["image_evidence"]["title"] == "raw-image.tif"
    assert payload["image_evidence"]["metadata"]["filename"] == "raw-image.tif"
    assert payload["image_evidence"]["source_ref"]["local_path"] == mask_local_path(str(local_file))
    assert payload["view_state"]["viewport"] == {"x": 0.0, "y": 0.0, "width": 64.0, "height": 64.0}
    assert payload["handoff_targets"][0]["target"] == "napari"
    assert payload["handoff_targets"][0]["openable_ref"] == mask_local_path(str(local_file))

    fetched = client.get("/image-evidence/img_api_demo")
    assert fetched.status_code == 200
    fetched_payload = fetched.json()
    assert fetched_payload["image_evidence"]["image_evidence_id"] == "img_api_demo"
    assert fetched_payload["image_evidence"]["source_ref"]["local_path"] == mask_local_path(str(local_file))
    assert fetched_payload["handoff_targets"][0]["openable_ref"] == mask_local_path(str(local_file))

    listed = client.get("/image-evidence")
    assert listed.status_code == 200
    list_payload = listed.json()
    assert list_payload["total"] == 1
    assert list_payload["items"][0]["image_evidence_id"] == "img_api_demo"
    assert list_payload["items"][0]["has_view_state"] is True
    assert list_payload["items"][0]["has_handoff"] is True

    view_state = client.get("/image-evidence/img_api_demo/view-state")
    assert view_state.status_code == 200
    assert view_state.json()["viewport"] == {"x": 0.0, "y": 0.0, "width": 64.0, "height": 64.0}

    handoff = client.get("/image-evidence/img_api_demo/handoff")
    assert handoff.status_code == 200
    assert handoff.json()[0]["target"] == "napari"
    assert handoff.json()[0]["openable_ref"] == mask_local_path(str(local_file))


def test_image_evidence_api_missing_bundle_returns_404(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("PAPERPIPE_IMAGE_EVIDENCE_DIR", str(tmp_path / "image_evidence"))
    monkeypatch.delenv("LATTICE_API_KEY", raising=False)
    monkeypatch.delenv("PAPERPIPE_API_KEY", raising=False)

    client = TestClient(api_main.app)

    missing = client.get("/image-evidence/missing")
    assert missing.status_code == 404


def test_image_evidence_api_missing_optional_views_return_404(tmp_path, monkeypatch) -> None:
    image_root = tmp_path / "image_evidence"
    local_file = tmp_path / "raw-image.tif"
    local_file.write_bytes(b"RAWIMAGE")

    monkeypatch.setenv("PAPERPIPE_IMAGE_EVIDENCE_DIR", str(image_root))
    monkeypatch.delenv("LATTICE_API_KEY", raising=False)
    monkeypatch.delenv("PAPERPIPE_API_KEY", raising=False)

    client = TestClient(api_main.app)
    created = client.post(
        "/image-evidence/register",
        json={
            "image_evidence_id": "img_api_no_optional",
            "source_ref": {"source_kind": "local_file", "local_path": str(local_file)},
            "content_format": "image/tiff",
        },
    )
    assert created.status_code == 200

    missing_view = client.get("/image-evidence/img_api_no_optional/view-state")
    assert missing_view.status_code == 404

    missing_handoff = client.get("/image-evidence/img_api_no_optional/handoff")
    assert missing_handoff.status_code == 404


def test_image_evidence_api_can_disable_path_masking(tmp_path, monkeypatch) -> None:
    image_root = tmp_path / "image_evidence"
    local_file = tmp_path / "raw-image.tif"
    local_file.write_bytes(b"RAWIMAGE")

    monkeypatch.setenv("PAPERPIPE_IMAGE_EVIDENCE_DIR", str(image_root))
    monkeypatch.setenv("PAPERPIPE_MASK_LOCAL_PATHS", "0")
    monkeypatch.delenv("LATTICE_API_KEY", raising=False)
    monkeypatch.delenv("PAPERPIPE_API_KEY", raising=False)

    client = TestClient(api_main.app)
    created = client.post(
        "/image-evidence/register",
        json={
            "image_evidence_id": "img_api_raw_paths",
            "source_ref": {"source_kind": "local_file", "local_path": str(local_file)},
            "content_format": "image/tiff",
            "handoff_targets": [{"target": "napari", "openable_ref": str(local_file)}],
        },
    )
    assert created.status_code == 200
    payload = created.json()
    assert payload["image_evidence"]["source_ref"]["local_path"] == str(local_file)
    assert payload["handoff_targets"][0]["openable_ref"] == str(local_file)

    handoff = client.get("/image-evidence/img_api_raw_paths/handoff")
    assert handoff.status_code == 200
    assert handoff.json()[0]["openable_ref"] == str(local_file)
