from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from backend import main as api_main
from src.contracts.document_artifact_v2 import ArtifactMetaV2, DocumentArtifactV2, TableV2
from src.schemas.agent_artifacts import StatCheckEntry, StatsReport, VerificationStatus
from src.services.runtime_paths import preferred_artifact_paper_dir


def _write_stats_report(root: Path, paper_id: str, run_id: str, report: StatsReport) -> None:
    run_dir = preferred_artifact_paper_dir(paper_id, root=root) / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "stats_report.json").write_text(
        report.model_dump_json(indent=2, exclude_none=True),
        encoding="utf-8",
    )


def _write_v2_document_artifact(root: Path, paper_id: str, run_id: str, document: DocumentArtifactV2) -> None:
    run_dir = preferred_artifact_paper_dir(paper_id, root=root) / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "document_artifact_v2.json").write_text(
        document.model_dump_json(indent=2, exclude_none=True),
        encoding="utf-8",
    )


def test_chart_packs_api_generate_roundtrip_and_exports(tmp_path, monkeypatch) -> None:
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

    monkeypatch.setenv("PAPERPIPE_ARTIFACTS_DIR", str(artifacts_root))
    monkeypatch.setenv("PAPERPIPE_CHART_PACKS_DIR", str(chart_root))
    monkeypatch.delenv("LATTICE_API_KEY", raising=False)
    monkeypatch.delenv("PAPERPIPE_API_KEY", raising=False)

    client = TestClient(api_main.app)
    created = client.post(
        "/chart-packs/generate",
        json={
            "chart_pack_id": "chartpack_api_demo",
            "title": "Research figures",
            "charts": [
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
        },
    )
    assert created.status_code == 200
    payload = created.json()

    assert payload["chart_pack"]["chart_pack_id"] == "chartpack_api_demo"
    assert payload["chart_pack"]["title"] == "Research figures"
    assert [chart["chart_id"] for chart in payload["chart_pack"]["charts"]] == [
        "chart_01_reported-vs-computed-p-scatter",
        "chart_02_table-numeric-line",
    ]
    assert payload["specs"]["chart_01_reported-vs-computed-p-scatter"]["mark"] == "point"
    assert "reported_p,computed_p" in payload["data_snapshots"]["chart_01_reported-vs-computed-p-scatter"]
    assert (chart_root / "chartpack_api_demo" / "chart_pack.json").exists()
    assert (chart_root / "chartpack_api_demo" / "chart_pack.md").exists()

    fetched = client.get("/chart-packs/chartpack_api_demo")
    assert fetched.status_code == 200
    assert fetched.json()["chart_pack"]["chart_pack_id"] == "chartpack_api_demo"

    listed = client.get("/chart-packs")
    assert listed.status_code == 200
    list_payload = listed.json()
    assert list_payload["total"] == 1
    assert list_payload["items"][0]["chart_pack_id"] == "chartpack_api_demo"
    assert list_payload["items"][0]["chart_count"] == 2

    csv_export = client.get(
        "/chart-packs/chartpack_api_demo/charts/chart_01_reported-vs-computed-p-scatter/data.csv"
    )
    assert csv_export.status_code == 200
    assert csv_export.headers["content-type"].startswith("text/csv")
    assert (
        csv_export.headers["content-disposition"]
        == 'attachment; filename="chartpack_api_demo_chart_01_reported-vs-computed-p-scatter.csv"'
    )
    assert "reported_p,computed_p" in csv_export.text

    spec_export = client.get("/chart-packs/chartpack_api_demo/charts/chart_02_table-numeric-line/spec.json")
    assert spec_export.status_code == 200
    assert spec_export.headers["content-type"].startswith("application/json")
    assert (
        spec_export.headers["content-disposition"]
        == 'attachment; filename="chartpack_api_demo_chart_02_table-numeric-line.json"'
    )
    assert spec_export.json()["encoding"] == {"x": "group", "y": "measurement"}


def test_chart_packs_api_lists_recent_first(tmp_path, monkeypatch) -> None:
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

    monkeypatch.setenv("PAPERPIPE_ARTIFACTS_DIR", str(artifacts_root))
    monkeypatch.setenv("PAPERPIPE_CHART_PACKS_DIR", str(chart_root))
    monkeypatch.delenv("LATTICE_API_KEY", raising=False)
    monkeypatch.delenv("PAPERPIPE_API_KEY", raising=False)

    client = TestClient(api_main.app)
    older = client.post(
        "/chart-packs/generate",
        json={
            "chart_pack_id": "chartpack_api_older",
            "title": "Older pack",
            "charts": [
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
            ],
        },
    )
    newer = client.post(
        "/chart-packs/generate",
        json={
            "chart_pack_id": "chartpack_api_newer",
            "title": "Newer pack",
            "charts": [
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
            ],
        },
    )
    assert older.status_code == 200
    assert newer.status_code == 200

    listed = client.get("/chart-packs")
    assert listed.status_code == 200
    payload = listed.json()

    assert payload["total"] == 2
    assert [item["chart_pack_id"] for item in payload["items"]] == [
        "chartpack_api_newer",
        "chartpack_api_older",
    ]
    assert payload["items"][0]["title"] == "Newer pack"
    assert payload["items"][0]["chart_count"] == 1


def test_chart_packs_api_returns_404_when_pack_missing(tmp_path, monkeypatch) -> None:
    chart_root = tmp_path / "chart_packs"
    monkeypatch.setenv("PAPERPIPE_CHART_PACKS_DIR", str(chart_root))
    monkeypatch.delenv("LATTICE_API_KEY", raising=False)
    monkeypatch.delenv("PAPERPIPE_API_KEY", raising=False)

    client = TestClient(api_main.app)

    assert client.get("/chart-packs/chartpack_missing").status_code == 404
    assert client.get("/chart-packs/chartpack_missing/charts/chart_01/data.csv").status_code == 404
    assert client.get("/chart-packs/chartpack_missing/charts/chart_01/spec.json").status_code == 404
