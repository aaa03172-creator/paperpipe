from __future__ import annotations

from src.chart_packs.source_loader import build_chart_data_snapshot
from src.contracts.document_artifact_v2 import ArtifactMetaV2, DocumentArtifactV2, TableV2
from src.schemas.agent_artifacts import (
    DocumentArtifact,
    PaperMetadata,
    SourceInfo,
    StatCheckEntry,
    StatsReport,
    TableData,
    VerificationStatus,
)
from src.schemas.chart_pack import ChartRequest
from src.services.runtime_paths import preferred_artifact_paper_dir


def _write_stats_report(root, paper_id: str, run_id: str, report: StatsReport) -> None:
    run_dir = preferred_artifact_paper_dir(paper_id, root=root) / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "stats_report.json").write_text(
        report.model_dump_json(indent=2, exclude_none=True),
        encoding="utf-8",
    )


def _write_legacy_document_artifact(root, paper_id: str, run_id: str, document: DocumentArtifact) -> None:
    run_dir = preferred_artifact_paper_dir(paper_id, root=root) / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "document_artifact.json").write_text(
        document.model_dump_json(indent=2, exclude_none=True),
        encoding="utf-8",
    )


def _write_v2_document_artifact(root, paper_id: str, run_id: str, document: DocumentArtifactV2) -> None:
    run_dir = preferred_artifact_paper_dir(paper_id, root=root) / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "document_artifact_v2.json").write_text(
        document.model_dump_json(indent=2, exclude_none=True),
        encoding="utf-8",
    )


def test_stats_check_status_counts_snapshot_counts_verdicts(tmp_path) -> None:
    artifacts_root = tmp_path / "artifacts"
    report = StatsReport(
        doc_id="doc-001",
        run_id="run-001",
        checks=[
            StatCheckEntry(
                check_id="c1",
                test_type="t-test",
                code="print('ok')",
                outputs="ok",
                verdict=VerificationStatus.VERIFIED,
            ),
            StatCheckEntry(
                check_id="c2",
                test_type="anova",
                code="print('ok')",
                outputs="ok",
                verdict=VerificationStatus.VERIFIED,
            ),
            StatCheckEntry(
                check_id="c3",
                test_type="chi-square",
                code="print('oops')",
                outputs="oops",
                verdict=VerificationStatus.INCONSISTENT,
            ),
        ],
    )
    _write_stats_report(artifacts_root, "paper-001", "run-001", report)

    chart = ChartRequest(
        template_id="stats_check_status_counts",
        source_ref={"source_kind": "stats_report", "paper_id": "paper-001", "run_id": "run-001"},
        field_mappings=[
            {"target_field": "status", "source_field": "status"},
            {"target_field": "value", "source_field": "count"},
        ],
    )
    snapshot = build_chart_data_snapshot(chart, artifacts_root=artifacts_root)

    assert snapshot.source_row_count == 3
    assert snapshot.rows == [
        {"status": "inconsistent", "value": 1},
        {"status": "verified", "value": 2},
    ]
    assert [column.value_kind for column in snapshot.columns] == ["text", "numeric"]
    assert snapshot.warnings == []


def test_reported_vs_computed_p_snapshot_skips_non_exact_pairs_and_warns(tmp_path) -> None:
    artifacts_root = tmp_path / "artifacts"
    report = StatsReport(
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
            StatCheckEntry(
                check_id="c3",
                test_type="chi-square",
                reported_p="0.30",
                computed_p=None,
                code="print('ok')",
                outputs="ok",
                verdict=VerificationStatus.UNVERIFIABLE,
            ),
        ],
    )
    _write_stats_report(artifacts_root, "paper-001", "run-001", report)

    chart = ChartRequest(
        template_id="reported_vs_computed_p_scatter",
        source_ref={"source_kind": "stats_report", "paper_id": "paper-001", "run_id": "run-001"},
        field_mappings=[
            {"target_field": "reported_p", "source_field": "reported_p"},
            {"target_field": "computed_p", "source_field": "computed_p"},
        ],
    )
    snapshot = build_chart_data_snapshot(chart, artifacts_root=artifacts_root)

    assert snapshot.rows == [{"reported_p": 0.05, "computed_p": 0.04}]
    assert snapshot.warnings[0].code == "stats_p_pairs_skipped"
    assert snapshot.source_row_count == 3


def test_document_table_snapshot_maps_filters_and_sorts_legacy_artifact(tmp_path) -> None:
    artifacts_root = tmp_path / "artifacts"
    document = DocumentArtifact(
        doc_id="doc-001",
        source=SourceInfo(type="pdf", ref="paper.pdf"),
        metadata=PaperMetadata(title="Legacy doc", authors=[]),
        tables=[
            TableData(
                table_id="tbl-001",
                caption="Values",
                data=[
                    ["Condition", "Value"],
                    ["A", "1"],
                    ["B", "3"],
                    ["C", "2"],
                ],
                source_page=0,
            )
        ],
    )
    _write_legacy_document_artifact(artifacts_root, "paper-001", "run-001", document)

    chart = ChartRequest(
        template_id="table_numeric_bar",
        source_ref={
            "source_kind": "document_table",
            "paper_id": "paper-001",
            "run_id": "run-001",
            "table_id": "tbl-001",
        },
        field_mappings=[
            {"target_field": "group", "source_field": "Condition"},
            {"target_field": "value", "source_field": "Value"},
        ],
        filters=[{"field": "group", "op": "neq", "value": "A"}],
        sort={"field": "value", "direction": "desc"},
    )
    snapshot = build_chart_data_snapshot(chart, artifacts_root=artifacts_root)

    assert snapshot.rows == [
        {"group": "B", "value": 3},
        {"group": "C", "value": 2},
    ]
    assert [column.value_kind for column in snapshot.columns] == ["text", "numeric"]
    assert [transform.kind for transform in snapshot.transforms] == [
        "field_mapping",
        "field_mapping",
        "filter",
        "sort",
    ]


def test_document_table_snapshot_supports_v2_artifact_payload(tmp_path) -> None:
    artifacts_root = tmp_path / "artifacts"
    document = DocumentArtifactV2(
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
    )
    _write_v2_document_artifact(artifacts_root, "paper-002", "run-002", document)

    chart = ChartRequest(
        template_id="table_numeric_line",
        source_ref={
            "source_kind": "document_table",
            "paper_id": "paper-002",
            "run_id": "run-002",
            "table_id": "tbl-002",
        },
        field_mappings=[
            {"target_field": "group", "source_field": "Group"},
            {"target_field": "measurement", "source_field": "Measurement"},
        ],
    )
    snapshot = build_chart_data_snapshot(chart, artifacts_root=artifacts_root)

    assert snapshot.rows == [
        {"group": "X", "measurement": 1.5},
        {"group": "Y", "measurement": 2},
    ]
    assert snapshot.note == "Loaded table tbl-002 with 2 data row(s)."


def test_document_table_snapshot_preserves_table_provenance(tmp_path) -> None:
    artifacts_root = tmp_path / "artifacts"
    provenance_note = "Markdown table parsed from Docling text export; inspect source before reuse."
    document = DocumentArtifactV2(
        document_id="doc-003",
        meta=ArtifactMetaV2(title="V2 doc", authors=[], source_ref="paper.pdf"),
        pages=[],
        tables=[
            TableV2(
                table_id="tbl-003",
                caption="Low-confidence values",
                data=[
                    ["Group", "Measurement"],
                    ["X", "1.5"],
                    ["Y", "2.0"],
                ],
                source_page=4,
                source_ref="paper.pdf#page=4",
                extraction_method="docling.markdown_table",
                confidence=0.45,
                provenance_note=provenance_note,
            )
        ],
    )
    _write_v2_document_artifact(artifacts_root, "paper-003", "run-003", document)

    chart = ChartRequest(
        template_id="table_numeric_bar",
        source_ref={
            "source_kind": "document_table",
            "paper_id": "paper-003",
            "run_id": "run-003",
            "table_id": "tbl-003",
        },
        field_mappings=[
            {"target_field": "group", "source_field": "Group"},
            {"target_field": "measurement", "source_field": "Measurement"},
        ],
    )
    snapshot = build_chart_data_snapshot(chart, artifacts_root=artifacts_root)

    assert snapshot.source_ref.source_page == 4
    assert snapshot.source_ref.table_source_ref == "paper.pdf#page=4"
    assert snapshot.source_ref.extraction_method == "docling.markdown_table"
    assert snapshot.source_ref.extraction_confidence == 0.45
    assert snapshot.source_ref.provenance_note == provenance_note
    assert [warning.code for warning in snapshot.warnings] == [
        "table_extraction_method",
        "low_confidence_table_extraction",
        "table_provenance_note",
    ]
