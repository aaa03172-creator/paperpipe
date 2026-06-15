from __future__ import annotations

import json

from src.services.cloud_paper_downstream import build_cloud_paper_downstream_adapter_response
from src.services.cloud_paper_fake import get_mock_cloud_derived_artifacts


def test_cloud_derived_artifacts_convert_to_downstream_candidates_without_raw_refs() -> None:
    derived = get_mock_cloud_derived_artifacts("paper_mock_ready")

    response = build_cloud_paper_downstream_adapter_response(derived)

    assert response.schema_version == "cloud_paper_downstream_adapter.v1"
    assert response.paper_id == "paper_mock_ready"
    assert response.run_id == "run_paper_mock_ready"
    assert response.source_pdf_sha256 == derived.source_pdf_sha256
    assert response.provenance_summary.source_pdf_sha256 == derived.source_pdf_sha256
    assert {candidate.kind for candidate in response.candidates} == {
        "ocr_text",
        "table",
        "figure",
        "figure_analysis",
    }
    assert all(candidate.canonical_status == "derived_noncanonical" for candidate in response.candidates)

    by_kind = {candidate.kind: candidate for candidate in response.candidates}
    assert by_kind["table"].allowed_lanes == ["chart_pack", "meeting_pack", "method_comparison", "obsidian_export"]
    assert by_kind["figure"].allowed_lanes == ["image_evidence", "meeting_pack", "obsidian_export"]
    assert by_kind["figure"].image_route == "/api/cloud/papers/paper_mock_ready/figures/figure_001/image"
    assert by_kind["ocr_text"].source.block_id == "block_001"
    assert by_kind["table"].table_rows == [["Control", "10"], ["Treatment", "12"]]

    serialized = json.dumps(response.model_dump(mode="json"), sort_keys=True)
    for forbidden in ("gs://", "signed_url", "service_account", "/Users/", "bucket"):
        assert forbidden not in serialized


def test_cloud_downstream_adapter_preserves_payload_class_and_source_lineage() -> None:
    derived = get_mock_cloud_derived_artifacts("paper_mock_ready")

    response = build_cloud_paper_downstream_adapter_response(derived)

    for candidate in response.candidates:
        assert candidate.paper_id == derived.paper_id
        assert candidate.run_id == derived.run_id
        assert candidate.payload_class == derived.payload_class
        assert candidate.source.source_pdf_sha256 == derived.source_pdf_sha256
        assert candidate.confidence is not None
