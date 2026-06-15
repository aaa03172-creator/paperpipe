from __future__ import annotations

import json

from src.chart_packs.cloud_adapter import build_cloud_derived_table_chart_snapshot
from src.services.cloud_paper_downstream import build_cloud_paper_downstream_adapter_response
from src.services.cloud_paper_fake import get_mock_cloud_derived_artifacts


def test_chart_pack_cloud_adapter_builds_snapshot_from_cloud_table_candidate() -> None:
    derived = get_mock_cloud_derived_artifacts("paper_mock_ready")
    downstream = build_cloud_paper_downstream_adapter_response(derived)

    snapshot = build_cloud_derived_table_chart_snapshot(
        downstream,
        table_id="table_001",
        template_id="table_numeric_bar",
    )

    assert snapshot.template_id == "table_numeric_bar"
    assert snapshot.source_ref.source_kind == "cloud_derived_table"
    assert snapshot.source_ref.paper_id == "paper_mock_ready"
    assert snapshot.source_ref.run_id == "run_paper_mock_ready"
    assert snapshot.source_ref.table_id == "table_001"
    assert [column.field_id for column in snapshot.columns] == ["Group", "N"]
    assert [column.value_kind for column in snapshot.columns] == ["text", "numeric"]
    assert snapshot.rows == [{"Group": "Control", "N": 10}, {"Group": "Treatment", "N": 12}]
    assert snapshot.source_row_count == 2
    assert any(warning.code == "cloud_derived_noncanonical" for warning in snapshot.warnings)
    assert snapshot.note is not None and "source_pdf_sha256=" in snapshot.note

    serialized = json.dumps(snapshot.model_dump(mode="json"), sort_keys=True)
    for forbidden in ("gs://", "signed_url", "service_account", "/Users/", "bucket"):
        assert forbidden not in serialized


def test_chart_pack_cloud_adapter_rejects_non_table_candidate() -> None:
    derived = get_mock_cloud_derived_artifacts("paper_mock_ready")
    downstream = build_cloud_paper_downstream_adapter_response(derived)

    try:
        build_cloud_derived_table_chart_snapshot(
            downstream,
            table_id="figure_001",
            template_id="table_numeric_bar",
        )
    except FileNotFoundError as exc:
        assert "cloud-derived table candidate not found" in str(exc)
    else:
        raise AssertionError("expected missing table candidate")
