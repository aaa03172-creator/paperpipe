from __future__ import annotations

from datetime import datetime, timezone
import json
import re

from src.chart_packs.service import (
    chart_pack_list_response,
    chart_pack_response_payload,
    generate_chart_pack,
    get_chart_pack,
)
from src.chart_packs.store import chart_pack_artifact_path, chart_pack_render_path, load_chart_pack_render
from src.contracts.document_artifact_v2 import ArtifactMetaV2, DocumentArtifactV2, TableV2
from src.schemas.agent_artifacts import StatCheckEntry, StatsReport, VerificationStatus
from src.schemas.chart_pack import ChartPackRequest
from src.services.runtime_paths import preferred_artifact_paper_dir


def _write_stats_report(root, paper_id: str, run_id: str, report: StatsReport) -> None:
    run_dir = preferred_artifact_paper_dir(paper_id, root=root) / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "stats_report.json").write_text(
        report.model_dump_json(indent=2, exclude_none=True),
        encoding="utf-8",
    )


def _write_v2_document_artifact(root, paper_id: str, run_id: str, document: DocumentArtifactV2) -> None:
    run_dir = preferred_artifact_paper_dir(paper_id, root=root) / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "document_artifact_v2.json").write_text(
        document.model_dump_json(indent=2, exclude_none=True),
        encoding="utf-8",
    )


def test_generate_chart_pack_saves_bundle_and_get_roundtrip(tmp_path) -> None:
    artifacts_root = tmp_path / "artifacts"
    chart_root = tmp_path / "chart_packs"

    _write_stats_report(
        artifacts_root,
        "paper-001",
        "run-001",
        StatsReport(
            doc_id="doc-001",
            run_id="run-001",
            checks=[
                StatCheckEntry(
                    check_id="c1",
                    test_type="t-test",
                    reported_p="0.05",
                    computed_p=0.04,
                    code="print('ok')",
                    outputs="ok",
                    verdict=VerificationStatus.VERIFIED,
                ),
                StatCheckEntry(
                    check_id="c2",
                    test_type="anova",
                    reported_p="< 0.01",
                    computed_p=0.009,
                    code="print('ok')",
                    outputs="ok",
                    verdict=VerificationStatus.VERIFIED,
                ),
            ],
        ),
    )
    _write_v2_document_artifact(
        artifacts_root,
        "paper-002",
        "run-002",
        DocumentArtifactV2(
            document_id="doc-002",
            meta=ArtifactMetaV2(title="V2 doc", authors=[], source_ref="paper.pdf"),
            pages=[],
            tables=[
                TableV2(
                    table_id="tbl-002",
                    caption="Values",
                    data=[
                        ["Group", "Measurement"],
                        ["X", "1.5"],
                        ["Y", "2.0"],
                    ],
                    source_page=0,
                )
            ],
        ),
    )

    request = ChartPackRequest(
        title="Research figures",
        charts=[
            {
                "title": "Verification scatter",
                "template_id": "reported_vs_computed_p_scatter",
                "source_ref": {
                    "source_kind": "stats_report",
                    "paper_id": "paper-001",
                    "run_id": "run-001",
                },
                "field_mappings": [
                    {"target_field": "reported_p", "source_field": "reported_p"},
                    {"target_field": "computed_p", "source_field": "computed_p"},
                ],
            },
            {
                "title": "Measurement line",
                "template_id": "table_numeric_line",
                "source_ref": {
                    "source_kind": "document_table",
                    "paper_id": "paper-002",
                    "run_id": "run-002",
                    "table_id": "tbl-002",
                },
                "field_mappings": [
                    {"target_field": "group", "source_field": "Group"},
                    {"target_field": "measurement", "source_field": "Measurement"},
                ],
            },
        ],
    )

    result = generate_chart_pack(
        request=request,
        root=chart_root,
        artifacts_root=artifacts_root,
        now=datetime(2026, 3, 20, 12, 0, tzinfo=timezone.utc),
    )

    assert result.chart_pack.title == "Research figures"
    assert result.chart_pack.chart_pack_id.startswith("chartpack_20260320T120000Z_")
    assert len(result.chart_pack.charts) == 2
    assert result.chart_pack.charts[0].data_snapshot_ref.path == "data/chart_01_reported-vs-computed-p-scatter.csv"
    assert result.chart_pack.charts[1].spec_ref.path == "specs/chart_02_table-numeric-line.json"
    assert result.chart_pack.charts[0].render_refs[0].path == "renders/chart_01_reported-vs-computed-p-scatter.svg"
    assert "chart_01_reported-vs-computed-p-scatter" in result.data_snapshots
    assert "chart_02_table-numeric-line" in result.specs
    assert result.specs["chart_01_reported-vs-computed-p-scatter"]["mark"] == "point"
    assert result.specs["chart_02_table-numeric-line"]["encoding"] == {"x": "group", "y": "measurement"}
    assert "Some charts include warning states" in result.chart_pack.caution_notes[0]
    assert result.chart_pack.artifact_brief is not None
    assert result.chart_pack.artifact_brief.artifact_family == "chart_pack"
    assert [item.kind for item in result.chart_pack.artifact_brief.plan.items] == ["chart", "chart"]
    assert result.chart_pack.artifact_brief_review is not None
    assert result.chart_pack.artifact_brief_review.overall_status == "warn"
    assert "CHART_WARNING_PRESENT" in result.chart_pack.artifact_brief_review.reason_codes
    assert result.quality_gate is not None
    assert result.quality_gate.overall_status == "warn"
    assert "## Artifact Brief" in result.markdown
    assert "## Artifact Brief Review" in result.markdown

    loaded = get_chart_pack(result.chart_pack.chart_pack_id, root=chart_root)
    assert loaded.chart_pack.chart_pack_id == result.chart_pack.chart_pack_id
    assert loaded.markdown == result.markdown
    assert loaded.data_snapshots == result.data_snapshots
    assert loaded.specs == result.specs
    assert load_chart_pack_render(
        result.chart_pack.chart_pack_id,
        "chart_01_reported-vs-computed-p-scatter",
        root=chart_root,
    ).startswith("<svg")
    assert loaded.chart_pack.artifact_brief is not None
    assert loaded.chart_pack.artifact_brief_review is not None
    assert loaded.chart_pack.artifact_brief_review.reason_codes == ["CHART_WARNING_PRESENT"]
    assert loaded.quality_gate is not None
    assert loaded.quality_gate.reason_codes == ["CHART_WARNING_PRESENT"]
    contract = json.loads(
        chart_pack_artifact_path(result.chart_pack.chart_pack_id, "acceptance_contract.json", chart_root).read_text(
            encoding="utf-8"
        )
    )
    gate = json.loads(
        chart_pack_artifact_path(result.chart_pack.chart_pack_id, "quality_gate.json", chart_root).read_text(
            encoding="utf-8"
        )
    )
    assert any(check["name"] == "artifact_brief_persisted" for check in contract["acceptance_checks"])
    assert "CHART_WARNING_PRESENT" in gate["reason_codes"]
    assert any(check["name"] == "artifact_brief_review" and check["status"] == "warn" for check in gate["checks"])
    assert chart_pack_render_path(
        result.chart_pack.chart_pack_id,
        "chart_01_reported-vs-computed-p-scatter",
        root=chart_root,
    ).exists()

    response = chart_pack_response_payload(result)
    assert response.chart_pack.chart_pack_id == result.chart_pack.chart_pack_id
    assert response.data_snapshots == result.data_snapshots
    assert response.quality_gate is not None
    assert response.quality_gate.overall_status == "warn"


def test_chart_pack_list_response_orders_latest_first(tmp_path) -> None:
    artifacts_root = tmp_path / "artifacts"
    chart_root = tmp_path / "chart_packs"
    _write_stats_report(
        artifacts_root,
        "paper-001",
        "run-001",
        StatsReport(
            doc_id="doc-001",
            run_id="run-001",
            checks=[
                StatCheckEntry(
                    check_id="c1",
                    test_type="t-test",
                    reported_p="0.05",
                    computed_p=0.04,
                    code="print('ok')",
                    outputs="ok",
                    verdict=VerificationStatus.VERIFIED,
                )
            ],
        ),
    )

    request = ChartPackRequest(
        charts=[
            {
                "template_id": "stats_check_status_counts",
                "source_ref": {
                    "source_kind": "stats_report",
                    "paper_id": "paper-001",
                    "run_id": "run-001",
                },
                "field_mappings": [
                    {"target_field": "status", "source_field": "status"},
                    {"target_field": "value", "source_field": "count"},
                ],
            }
        ]
    )

    older = generate_chart_pack(
        request=request,
        root=chart_root,
        artifacts_root=artifacts_root,
        now=datetime(2026, 3, 20, 10, 0, tzinfo=timezone.utc),
    )
    newer = generate_chart_pack(
        request=request,
        root=chart_root,
        artifacts_root=artifacts_root,
        now=datetime(2026, 3, 20, 11, 0, tzinfo=timezone.utc),
    )

    response = chart_pack_list_response(root=chart_root)
    assert response.total == 2
    assert [item.chart_pack_id for item in response.items] == [
        newer.chart_pack.chart_pack_id,
        older.chart_pack.chart_pack_id,
    ]


def test_generate_chart_pack_uses_distinct_default_ids_for_distinct_requests_same_second(tmp_path) -> None:
    artifacts_root = tmp_path / "artifacts"
    chart_root = tmp_path / "chart_packs"
    _write_stats_report(
        artifacts_root,
        "paper-001",
        "run-001",
        StatsReport(
            doc_id="doc-001",
            run_id="run-001",
            checks=[
                StatCheckEntry(
                    check_id="c1",
                    test_type="t-test",
                    reported_p="0.05",
                    computed_p=0.04,
                    code="print('ok')",
                    outputs="ok",
                    verdict=VerificationStatus.VERIFIED,
                )
            ],
        ),
    )

    base_chart = {
        "template_id": "stats_check_status_counts",
        "source_ref": {
            "source_kind": "stats_report",
            "paper_id": "paper-001",
            "run_id": "run-001",
        },
        "field_mappings": [
            {"target_field": "status", "source_field": "status"},
            {"target_field": "value", "source_field": "count"},
        ],
    }
    now = datetime(2026, 3, 20, 12, 0, tzinfo=timezone.utc)
    first = generate_chart_pack(
        request=ChartPackRequest(charts=[base_chart]),
        root=chart_root,
        artifacts_root=artifacts_root,
        now=now,
    )
    second = generate_chart_pack(
        request=ChartPackRequest(
            charts=[
                {
                    **base_chart,
                    "filters": [{"field": "status", "op": "eq", "value": "verified"}],
                }
            ]
        ),
        root=chart_root,
        artifacts_root=artifacts_root,
        now=now,
    )

    assert first.chart_pack.chart_pack_id != second.chart_pack.chart_pack_id
    assert chart_pack_list_response(root=chart_root).total == 2


def test_generate_chart_pack_artifact_brief_passes_for_clean_table_chart(tmp_path) -> None:
    artifacts_root = tmp_path / "artifacts"
    chart_root = tmp_path / "chart_packs"
    _write_v2_document_artifact(
        artifacts_root,
        "paper-010",
        "run-010",
        DocumentArtifactV2(
            document_id="doc-010",
            meta=ArtifactMetaV2(title="Clean table doc", authors=[], source_ref="paper.pdf"),
            pages=[],
            tables=[
                TableV2(
                    table_id="tbl-010",
                    caption="Concentrations",
                    data=[
                        ["Condition", "Value"],
                        ["A", "1.0"],
                        ["B", "2.5"],
                    ],
                    source_page=0,
                )
            ],
        ),
    )

    result = generate_chart_pack(
        request=ChartPackRequest(
            title="Clean table chart",
            charts=[
                {
                    "title": "Concentration bar",
                    "template_id": "table_numeric_bar",
                    "source_ref": {
                        "source_kind": "document_table",
                        "paper_id": "paper-010",
                        "run_id": "run-010",
                        "table_id": "tbl-010",
                    },
                    "field_mappings": [
                        {"target_field": "condition", "source_field": "Condition"},
                        {"target_field": "value", "source_field": "Value"},
                    ],
                }
            ],
        ),
        root=chart_root,
        artifacts_root=artifacts_root,
        now=datetime(2026, 3, 20, 12, 30, tzinfo=timezone.utc),
    )

    assert result.chart_pack.artifact_brief is not None
    assert [item.support_status for item in result.chart_pack.artifact_brief.plan.items] == ["direct"]
    assert result.chart_pack.artifact_brief_review is not None
    assert result.chart_pack.artifact_brief_review.overall_status == "pass"
    assert result.chart_pack.artifact_brief_review.reason_codes == []
    assert result.quality_gate is not None
    assert result.quality_gate.overall_status == "pass"
    gate = json.loads(
        chart_pack_artifact_path(result.chart_pack.chart_pack_id, "quality_gate.json", chart_root).read_text(
            encoding="utf-8"
        )
    )
    assert gate["overall_status"] == "pass"
    assert gate["handoff_ready"] is True


def test_get_chart_pack_ignores_corrupted_quality_gate_sidecar(tmp_path) -> None:
    chart_root = tmp_path / "chart_packs"
    artifacts_root = tmp_path / "artifacts"
    _write_stats_report(
        artifacts_root,
        "paper-011",
        "run-011",
        StatsReport(
            doc_id="doc-011",
            run_id="run-011",
            checks=[
                StatCheckEntry(
                    check_id="c-011",
                    test_type="t-test",
                    reported_p="0.03",
                    computed_p=0.03,
                    code="print('ok')",
                    outputs="ok",
                    verdict=VerificationStatus.VERIFIED,
                )
            ],
        ),
    )

    created = generate_chart_pack(
        request=ChartPackRequest(
            chart_pack_id="chartpack_corrupted_gate_demo",
            title="Corrupted quality gate demo",
            charts=[
                {
                    "title": "Verification status counts",
                    "template_id": "stats_check_status_counts",
                    "source_ref": {
                        "source_kind": "stats_report",
                        "paper_id": "paper-011",
                        "run_id": "run-011",
                    },
                    "field_mappings": [
                        {"target_field": "status", "source_field": "status"},
                        {"target_field": "value", "source_field": "count"},
                    ],
                    "sort": {"field": "status", "direction": "asc"},
                }
            ],
        ),
        root=chart_root,
        artifacts_root=artifacts_root,
        now=datetime(2026, 3, 20, 12, 45, tzinfo=timezone.utc),
    )

    quality_gate_path = chart_pack_artifact_path(created.chart_pack.chart_pack_id, "quality_gate.json", chart_root)
    quality_gate_path.write_text("{not-valid-json", encoding="utf-8")

    loaded = get_chart_pack(created.chart_pack.chart_pack_id, root=chart_root)

    assert loaded.chart_pack.chart_pack_id == created.chart_pack.chart_pack_id
    assert loaded.quality_gate is None
    assert loaded.markdown == created.markdown
    assert loaded.data_snapshots == created.data_snapshots


def test_generate_chart_pack_renders_signed_numeric_series_safely(tmp_path) -> None:
    artifacts_root = tmp_path / "artifacts"
    chart_root = tmp_path / "chart_packs"
    _write_v2_document_artifact(
        artifacts_root,
        "paper-012",
        "run-012",
        DocumentArtifactV2(
            document_id="doc-012",
            meta=ArtifactMetaV2(title="Signed values doc", authors=[], source_ref="paper.pdf"),
            pages=[],
            tables=[
                TableV2(
                    table_id="tbl-012",
                    caption="Signed values",
                    data=[
                        ["Condition", "Value"],
                        ["A", "-2.0"],
                        ["B", "3.0"],
                        ["C", "0.0"],
                    ],
                    source_page=0,
                )
            ],
        ),
    )

    result = generate_chart_pack(
        request=ChartPackRequest(
            title="Signed numeric charts",
            charts=[
                {
                    "title": "Signed bar",
                    "template_id": "table_numeric_bar",
                    "source_ref": {
                        "source_kind": "document_table",
                        "paper_id": "paper-012",
                        "run_id": "run-012",
                        "table_id": "tbl-012",
                    },
                    "field_mappings": [
                        {"target_field": "condition", "source_field": "Condition"},
                        {"target_field": "value", "source_field": "Value"},
                    ],
                },
                {
                    "title": "Signed line",
                    "template_id": "table_numeric_line",
                    "source_ref": {
                        "source_kind": "document_table",
                        "paper_id": "paper-012",
                        "run_id": "run-012",
                        "table_id": "tbl-012",
                    },
                    "field_mappings": [
                        {"target_field": "condition", "source_field": "Condition"},
                        {"target_field": "value", "source_field": "Value"},
                    ],
                },
            ],
        ),
        root=chart_root,
        artifacts_root=artifacts_root,
        now=datetime(2026, 3, 20, 13, 0, tzinfo=timezone.utc),
    )

    bar_svg = load_chart_pack_render(result.chart_pack.chart_pack_id, "chart_01_table-numeric-bar", root=chart_root)
    line_svg = load_chart_pack_render(result.chart_pack.chart_pack_id, "chart_02_table-numeric-line", root=chart_root)

    assert 'height="-' not in bar_svg
    assert ">-2<" in bar_svg
    polyline_match = re.search(r'<polyline[^>]*points="([^"]+)"', line_svg)
    assert polyline_match is not None
    polyline_points = [tuple(map(float, pair.split(","))) for pair in polyline_match.group(1).split()]
    assert len(polyline_points) == 3
    assert all(56.0 <= y <= 352.0 for _, y in polyline_points)
