from __future__ import annotations

import json

from src.method_comparisons.cloud_adapter import build_method_comparison_cloud_derived_context
from src.services.cloud_paper_downstream import build_cloud_paper_downstream_adapter_response
from src.services.cloud_paper_fake import get_mock_cloud_derived_artifacts


def test_method_comparison_cloud_adapter_keeps_ocr_and_tables_background_only() -> None:
    derived = get_mock_cloud_derived_artifacts("paper_mock_ready")
    downstream = build_cloud_paper_downstream_adapter_response(derived)

    context = build_method_comparison_cloud_derived_context(downstream)

    assert context.schema_version == "method_comparison_cloud_derived_context.v1"
    assert context.paper_id == "paper_mock_ready"
    assert context.run_id == "run_paper_mock_ready"
    assert context.readiness == "background_only"
    assert {item.kind for item in context.items} == {"ocr_text", "table"}
    assert all(item.canonical_status == "derived_noncanonical" for item in context.items)
    assert all(item.comparison_cell_status == "missing" for item in context.items)
    assert all(item.evidence_refs == [] for item in context.items)
    assert context.items[0].source_page >= 1

    serialized = json.dumps(context.model_dump(mode="json"), sort_keys=True)
    assert "claimset.resolved.json" not in serialized
    assert "evidence_backed" not in serialized
    for forbidden in ("gs://", "signed_url", "service_account", "/Users/", "bucket"):
        assert forbidden not in serialized


def test_method_comparison_cloud_adapter_filters_non_method_lanes() -> None:
    derived = get_mock_cloud_derived_artifacts("paper_mock_ready")
    downstream = build_cloud_paper_downstream_adapter_response(derived)
    first = downstream.candidates[0].model_copy(update={"allowed_lanes": ["meeting_pack"]})
    downstream = downstream.model_copy(update={"candidates": [first, *downstream.candidates[1:]]})

    context = build_method_comparison_cloud_derived_context(downstream)

    assert "ocr_text" not in {item.kind for item in context.items}
