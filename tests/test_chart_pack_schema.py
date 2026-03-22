from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from src.schemas.chart_pack import (
    CHART_TEMPLATE_MAP,
    ChartArtifactRef,
    ChartPack,
    ChartPackRequest,
    ChartSourceRef,
    chart_template_specs,
)


def _sample_chart_pack() -> ChartPack:
    return ChartPack(
        chart_pack_id="chartpack_20260320T120000Z_demo",
        title="Chart pack demo",
        created_at=datetime(2026, 3, 20, 12, 0, tzinfo=timezone.utc),
        charts=[
            {
                "chart_id": "chart_1",
                "title": "Verification counts",
                "template_id": "stats_check_status_counts",
                "source_ref": {
                    "source_kind": "stats_report",
                    "paper_id": "paper-001",
                    "run_id": "run-001",
                },
                "field_mappings": [
                    {"target_field": "status", "source_field": "verdict"},
                    {"target_field": "value", "source_field": "count"},
                ],
                "data_snapshot_ref": {"kind": "data_csv", "path": "data/chart_1.csv"},
                "spec_ref": {"kind": "spec_json", "path": "specs/chart_1.json"},
                "render_refs": [{"kind": "render_png", "path": "renders/chart_1.png"}],
            }
        ],
        source_items=[{"source_kind": "stats_report", "paper_id": "paper-001", "run_id": "run-001"}],
        caution_notes=["Counts are derived from saved verification checks."],
    )


def test_chart_template_registry_matches_expected_allowlist() -> None:
    specs = chart_template_specs()

    assert [spec.template_id for spec in specs] == [
        "stats_check_status_counts",
        "reported_vs_computed_p_scatter",
        "table_numeric_bar",
        "table_numeric_line",
    ]
    assert CHART_TEMPLATE_MAP["table_numeric_line"].supported_source_kinds == ["document_table"]


def test_chart_pack_request_accepts_explicit_chart_source_refs() -> None:
    request = ChartPackRequest(
        charts=[
            {
                "template_id": "table_numeric_bar",
                "source_ref": {
                    "source_kind": "document_table",
                    "paper_id": "paper-001",
                    "run_id": "run-001",
                    "table_id": "tbl-001",
                },
                "field_mappings": [
                    {"target_field": "x", "source_field": "condition"},
                    {"target_field": "y", "source_field": "value"},
                ],
            }
        ]
    )

    assert request.charts[0].source_ref.source_kind == "document_table"
    assert request.charts[0].source_ref.table_id == "tbl-001"


def test_document_table_source_ref_requires_table_id() -> None:
    with pytest.raises(ValidationError):
        ChartSourceRef(source_kind="document_table", paper_id="paper-001", run_id="run-001")


def test_stats_report_source_ref_rejects_table_id() -> None:
    with pytest.raises(ValidationError):
        ChartSourceRef(
            source_kind="stats_report",
            paper_id="paper-001",
            run_id="run-001",
            table_id="tbl-001",
        )


def test_chart_artifact_ref_requires_pack_relative_path() -> None:
    with pytest.raises(ValidationError):
        ChartArtifactRef(kind="data_csv", path="/tmp/chart.csv")


def test_chart_pack_rejects_duplicate_chart_ids() -> None:
    with pytest.raises(ValidationError):
        ChartPack(
            chart_pack_id="chartpack_20260320T120000Z_demo",
            title="Chart pack demo",
            created_at=datetime(2026, 3, 20, 12, 0, tzinfo=timezone.utc),
            charts=[
                {
                    "chart_id": "chart_1",
                    "title": "A",
                    "template_id": "stats_check_status_counts",
                    "source_ref": {
                        "source_kind": "stats_report",
                        "paper_id": "paper-001",
                        "run_id": "run-001",
                    },
                    "field_mappings": [{"target_field": "status", "source_field": "verdict"}],
                },
                {
                    "chart_id": "chart_1",
                    "title": "B",
                    "template_id": "stats_check_status_counts",
                    "source_ref": {
                        "source_kind": "stats_report",
                        "paper_id": "paper-001",
                        "run_id": "run-001",
                    },
                    "field_mappings": [{"target_field": "status", "source_field": "verdict"}],
                },
            ],
        )


def test_chart_pack_schema_accepts_render_and_spec_refs() -> None:
    chart_pack = _sample_chart_pack()

    assert chart_pack.charts[0].data_snapshot_ref is not None
    assert chart_pack.charts[0].data_snapshot_ref.kind == "data_csv"
    assert chart_pack.charts[0].spec_ref is not None
    assert chart_pack.charts[0].spec_ref.kind == "spec_json"
    assert chart_pack.charts[0].render_refs[0].kind == "render_png"
