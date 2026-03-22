from __future__ import annotations

from datetime import datetime, timezone

from src.chart_packs.service import (
    chart_pack_list_response,
    chart_pack_response_payload,
    generate_chart_pack,
    get_chart_pack,
)
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
    assert "chart_01_reported-vs-computed-p-scatter" in result.data_snapshots
    assert "chart_02_table-numeric-line" in result.specs
    assert result.specs["chart_01_reported-vs-computed-p-scatter"]["mark"] == "point"
    assert result.specs["chart_02_table-numeric-line"]["encoding"] == {"x": "group", "y": "measurement"}
    assert "Some charts include warning states" in result.chart_pack.caution_notes[0]

    loaded = get_chart_pack(result.chart_pack.chart_pack_id, root=chart_root)
    assert loaded.chart_pack.chart_pack_id == result.chart_pack.chart_pack_id
    assert loaded.markdown == result.markdown
    assert loaded.data_snapshots == result.data_snapshots
    assert loaded.specs == result.specs

    response = chart_pack_response_payload(result)
    assert response.chart_pack.chart_pack_id == result.chart_pack.chart_pack_id
    assert response.data_snapshots == result.data_snapshots


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
