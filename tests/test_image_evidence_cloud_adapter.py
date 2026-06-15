from __future__ import annotations

import json

from src.image_evidence.cloud_adapter import build_cloud_derived_figure_image_evidence_request
from src.services.cloud_paper_downstream import build_cloud_paper_downstream_adapter_response
from src.services.cloud_paper_fake import get_mock_cloud_derived_artifacts


def test_image_evidence_cloud_adapter_builds_request_from_figure_proxy_route() -> None:
    derived = get_mock_cloud_derived_artifacts("paper_mock_ready")
    downstream = build_cloud_paper_downstream_adapter_response(derived)

    request = build_cloud_derived_figure_image_evidence_request(downstream, figure_id="figure_001")

    assert request.image_evidence_id == "imageev_cloud_paper_mock_ready_figure_001"
    assert request.paper_id == "paper_mock_ready"
    assert request.source_ref.source_kind == "external_image_ref"
    assert request.source_ref.external_ref == "/api/cloud/papers/paper_mock_ready/figures/figure_001/image"
    assert request.source_ref.local_path is None
    assert request.content_format == "image/png"
    assert request.derived_outputs[0].kind == "representative_crop"
    assert request.derived_outputs[0].external_ref == "/api/cloud/papers/paper_mock_ready/figures/figure_001/image"
    assert request.linked_claim_refs == []
    assert any(warning.code == "cloud_derived_noncanonical" for warning in request.warnings)
    assert request.metadata.acquisition_note is not None
    assert "source_pdf_sha256=" in request.metadata.acquisition_note

    serialized = json.dumps(request.model_dump(mode="json"), sort_keys=True)
    for forbidden in ("gs://", "signed_url", "service_account", "/Users/", "bucket"):
        assert forbidden not in serialized


def test_image_evidence_cloud_adapter_rejects_missing_figure_proxy() -> None:
    derived = get_mock_cloud_derived_artifacts("paper_mock_ready")
    downstream = build_cloud_paper_downstream_adapter_response(derived)
    figure = downstream.candidates[2].model_copy(update={"image_route": None})
    downstream = downstream.model_copy(update={"candidates": [*downstream.candidates[:2], figure, *downstream.candidates[3:]]})

    try:
        build_cloud_derived_figure_image_evidence_request(downstream, figure_id="figure_001")
    except ValueError as exc:
        assert "same-origin image proxy route" in str(exc)
    else:
        raise AssertionError("expected missing image proxy route")
