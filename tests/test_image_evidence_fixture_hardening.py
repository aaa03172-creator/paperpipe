from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path

from src.image_evidence.service import get_image_evidence_bundle, register_image_evidence
from src.image_evidence.store import load_image_derivative_bytes, save_image_derivative_bytes
from src.schemas.image_evidence import ImageEvidenceRequest


FIXTURE_ROOT = Path(__file__).resolve().parent / "fixtures" / "image_evidence_case"


def _load_request(name: str, *, raw_path: Path | None = None) -> ImageEvidenceRequest:
    payload = json.loads((FIXTURE_ROOT / f"{name}_request.json").read_text(encoding="utf-8"))
    if raw_path is not None:
        raw_value = str(raw_path)
        payload["source_ref"]["local_path"] = raw_value
        for handoff_target in payload.get("handoff_targets", []):
            if handoff_target.get("openable_ref") == "__RAW_PATH__":
                handoff_target["openable_ref"] = raw_value
    return ImageEvidenceRequest(**payload)


def test_image_evidence_fixture_hardening_replays_recorded_cases(tmp_path) -> None:
    output_root = tmp_path / "image_evidence"
    local_raw = FIXTURE_ROOT / "raw" / "local-alpha.tif"
    local_thumb = (FIXTURE_ROOT / "derived" / "thumb_local.png").read_bytes()

    local_request = _load_request("local_file", raw_path=local_raw)
    external_request = _load_request("external_ref")
    mismatch_request = _load_request("checksum_mismatch", raw_path=local_raw)

    fixed_now = datetime(2026, 3, 22, 18, 0, 0, tzinfo=timezone.utc)
    local_first = register_image_evidence(request=local_request, root=output_root, now=fixed_now)
    save_image_derivative_bytes("img_fixture_local", "thumb_local", local_thumb, root=output_root)
    local_second = register_image_evidence(request=local_request, root=output_root, now=fixed_now)
    save_image_derivative_bytes("img_fixture_local", "thumb_local", local_thumb, root=output_root)
    external_result = register_image_evidence(
        request=external_request,
        root=output_root,
        now=datetime(2026, 3, 22, 18, 5, 0, tzinfo=timezone.utc),
    )
    mismatch_result = register_image_evidence(
        request=mismatch_request,
        root=output_root,
        now=datetime(2026, 3, 22, 18, 10, 0, tzinfo=timezone.utc),
    )

    assert local_first.image_evidence.model_dump(mode="json") == local_second.image_evidence.model_dump(mode="json")
    assert local_first.view_state is not None
    assert local_first.handoff_targets[0].target == "napari"
    assert local_first.image_evidence.metadata.filename == "local-alpha.tif"
    assert local_first.image_evidence.metadata.source_size_bytes == local_raw.stat().st_size
    assert local_first.image_evidence.warnings == []
    assert load_image_derivative_bytes("img_fixture_local", "thumb_local", root=output_root) == local_thumb

    loaded_local = get_image_evidence_bundle("img_fixture_local", root=output_root)
    assert loaded_local.view_state is not None
    assert loaded_local.view_state.active_channels == ["GFP", "DAPI"]
    assert loaded_local.handoff_targets[0].notes == "Open with saved viewport."
    assert (output_root / "img_fixture_local" / "image_evidence.json").exists()
    assert (output_root / "img_fixture_local" / "view_state.json").exists()
    assert (output_root / "img_fixture_local" / "handoff.json").exists()
    assert (output_root / "img_fixture_local" / "derivatives" / "thumb_local.png").exists()

    assert external_result.image_evidence.source_ref.source_kind == "external_image_ref"
    assert external_result.image_evidence.title == "OMERO image 7"
    assert external_result.image_evidence.warnings == []
    assert external_result.handoff_targets[0].target == "omero"
    assert (output_root / "img_fixture_external" / "handoff.json").exists()

    assert [warning.code for warning in mismatch_result.image_evidence.warnings] == ["CHECKSUM_MISMATCH"]
    assert mismatch_result.image_evidence.title == "local-alpha.tif"
    assert (output_root / "img_fixture_checksum_mismatch" / "image_evidence.json").exists()
