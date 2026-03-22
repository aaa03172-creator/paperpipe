from __future__ import annotations

from datetime import datetime, timezone

import pytest

import src.chart_packs.store as chart_pack_store
from src.chart_packs.store import (
    chart_pack_data_csv_path,
    chart_pack_json_path,
    chart_pack_markdown_path,
    chart_pack_spec_json_path,
    list_chart_pack_ids,
    load_chart_pack,
    load_chart_pack_data_csv,
    load_chart_pack_markdown,
    load_chart_pack_spec,
    save_chart_pack_bundle,
)
from src.schemas.chart_pack import ChartPack


def _sample_chart_pack(title: str = "Chart pack demo") -> ChartPack:
    return ChartPack(
        chart_pack_id="chartpack_20260320T120000Z_demo",
        title=title,
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
                "field_mappings": [{"target_field": "status", "source_field": "verdict"}],
                "data_snapshot_ref": {"kind": "data_csv", "path": "data/chart_1.csv"},
                "spec_ref": {"kind": "spec_json", "path": "specs/chart_1.json"},
            }
        ],
    )


def test_chart_pack_store_roundtrip_creates_expected_layout(tmp_path) -> None:
    root = tmp_path / "chart_packs"
    chart_pack = _sample_chart_pack()
    markdown = "# Chart Pack\n"
    data_snapshots = {"chart_1": "status,count\nverified,4\n"}
    specs = {"chart_1": {"type": "bar", "x": "status", "y": "count"}}

    result = save_chart_pack_bundle(
        chart_pack,
        markdown,
        data_snapshots=data_snapshots,
        specs=specs,
        root=root,
    )
    loaded = load_chart_pack(chart_pack.chart_pack_id, root)
    loaded_markdown = load_chart_pack_markdown(chart_pack.chart_pack_id, root)
    loaded_csv = load_chart_pack_data_csv(chart_pack.chart_pack_id, "chart_1", root)
    loaded_spec = load_chart_pack_spec(chart_pack.chart_pack_id, "chart_1", root)

    assert result["json"] == chart_pack_json_path(chart_pack.chart_pack_id, root)
    assert result["markdown"] == chart_pack_markdown_path(chart_pack.chart_pack_id, root)
    assert result["data:chart_1"] == chart_pack_data_csv_path(chart_pack.chart_pack_id, "chart_1", root)
    assert result["spec:chart_1"] == chart_pack_spec_json_path(chart_pack.chart_pack_id, "chart_1", root)
    assert loaded.chart_pack_id == chart_pack.chart_pack_id
    assert loaded.title == chart_pack.title
    assert loaded_markdown == markdown
    assert loaded_csv == data_snapshots["chart_1"]
    assert loaded_spec == specs["chart_1"]
    assert list_chart_pack_ids(root) == [chart_pack.chart_pack_id]


def test_chart_pack_store_overwrites_same_id_without_duplicate_dump(tmp_path) -> None:
    root = tmp_path / "chart_packs"
    original = _sample_chart_pack(title="First title")
    save_chart_pack_bundle(
        original,
        "# First\n",
        data_snapshots={"chart_1": "status,count\nverified,1\n"},
        specs={"chart_1": {"type": "bar"}},
        root=root,
    )

    updated = _sample_chart_pack(title="Updated title")
    save_chart_pack_bundle(
        updated,
        "# Updated\n",
        data_snapshots={"chart_1": "status,count\nverified,2\n"},
        specs={"chart_1": {"type": "line"}},
        root=root,
    )

    loaded = load_chart_pack(updated.chart_pack_id, root)
    loaded_markdown = load_chart_pack_markdown(updated.chart_pack_id, root)
    loaded_csv = load_chart_pack_data_csv(updated.chart_pack_id, "chart_1", root)
    loaded_spec = load_chart_pack_spec(updated.chart_pack_id, "chart_1", root)

    assert loaded.title == "Updated title"
    assert loaded_markdown == "# Updated\n"
    assert loaded_csv == "status,count\nverified,2\n"
    assert loaded_spec == {"type": "line"}


def test_chart_pack_store_rejects_unknown_snapshot_chart_ids(tmp_path) -> None:
    root = tmp_path / "chart_packs"
    chart_pack = _sample_chart_pack()

    with pytest.raises(ValueError, match="Unknown chart_id"):
        save_chart_pack_bundle(
            chart_pack,
            "# Demo\n",
            data_snapshots={"missing_chart": "a,b\n"},
            root=root,
        )


def test_chart_pack_store_rolls_back_bundle_if_spec_write_fails(tmp_path, monkeypatch) -> None:
    root = tmp_path / "chart_packs"
    original = _sample_chart_pack(title="First title")
    save_chart_pack_bundle(
        original,
        "# First\n",
        data_snapshots={"chart_1": "status,count\nverified,1\n"},
        specs={"chart_1": {"type": "bar"}},
        root=root,
    )

    updated = _sample_chart_pack(title="Updated title")
    original_atomic_write_text = chart_pack_store._atomic_write_text
    call_count = {"value": 0}

    def fail_on_fourth_write(path, content):
        call_count["value"] += 1
        if call_count["value"] == 4:
            raise IOError("boom")
        return original_atomic_write_text(path, content)

    monkeypatch.setattr(chart_pack_store, "_atomic_write_text", fail_on_fourth_write)

    with pytest.raises(OSError):
        save_chart_pack_bundle(
            updated,
            "# Updated\n",
            data_snapshots={"chart_1": "status,count\nverified,2\n"},
            specs={"chart_1": {"type": "line"}},
            root=root,
        )

    loaded = load_chart_pack(updated.chart_pack_id, root)
    loaded_markdown = load_chart_pack_markdown(updated.chart_pack_id, root)
    loaded_csv = load_chart_pack_data_csv(updated.chart_pack_id, "chart_1", root)
    loaded_spec = load_chart_pack_spec(updated.chart_pack_id, "chart_1", root)
    assert loaded.title == "First title"
    assert loaded_markdown == "# First\n"
    assert loaded_csv == "status,count\nverified,1\n"
    assert loaded_spec == {"type": "bar"}


def test_chart_pack_store_does_not_leave_partial_new_bundle_if_write_fails(tmp_path, monkeypatch) -> None:
    root = tmp_path / "chart_packs"
    chart_pack = _sample_chart_pack()
    original_atomic_write_text = chart_pack_store._atomic_write_text
    call_count = {"value": 0}

    def fail_on_third_write(path, content):
        call_count["value"] += 1
        if call_count["value"] == 3:
            raise IOError("boom")
        return original_atomic_write_text(path, content)

    monkeypatch.setattr(chart_pack_store, "_atomic_write_text", fail_on_third_write)

    with pytest.raises(OSError):
        save_chart_pack_bundle(
            chart_pack,
            "# First\n",
            data_snapshots={"chart_1": "status,count\nverified,1\n"},
            specs={"chart_1": {"type": "bar"}},
            root=root,
        )

    assert list_chart_pack_ids(root) == []


def test_chart_pack_store_removes_stale_snapshot_and_spec_files_on_overwrite(tmp_path) -> None:
    root = tmp_path / "chart_packs"
    original = ChartPack(
        chart_pack_id="chartpack_20260320T120000Z_demo",
        title="Chart pack demo",
        created_at=datetime(2026, 3, 20, 12, 0, tzinfo=timezone.utc),
        charts=[
            {
                "chart_id": "chart_a",
                "title": "A",
                "template_id": "stats_check_status_counts",
                "source_ref": {
                    "source_kind": "stats_report",
                    "paper_id": "paper-001",
                    "run_id": "run-001",
                },
                "field_mappings": [{"target_field": "status", "source_field": "status"}],
            },
            {
                "chart_id": "chart_b",
                "title": "B",
                "template_id": "stats_check_status_counts",
                "source_ref": {
                    "source_kind": "stats_report",
                    "paper_id": "paper-001",
                    "run_id": "run-001",
                },
                "field_mappings": [{"target_field": "status", "source_field": "status"}],
            },
        ],
    )
    save_chart_pack_bundle(
        original,
        "# First\n",
        data_snapshots={"chart_a": "a\n", "chart_b": "b\n"},
        specs={"chart_a": {"type": "bar"}, "chart_b": {"type": "line"}},
        root=root,
    )

    updated = ChartPack(
        chart_pack_id="chartpack_20260320T120000Z_demo",
        title="Chart pack demo",
        created_at=datetime(2026, 3, 20, 12, 0, tzinfo=timezone.utc),
        charts=[
            {
                "chart_id": "chart_a",
                "title": "A",
                "template_id": "stats_check_status_counts",
                "source_ref": {
                    "source_kind": "stats_report",
                    "paper_id": "paper-001",
                    "run_id": "run-001",
                },
                "field_mappings": [{"target_field": "status", "source_field": "status"}],
            }
        ],
    )
    save_chart_pack_bundle(
        updated,
        "# Updated\n",
        data_snapshots={"chart_a": "a2\n"},
        specs={"chart_a": {"type": "area"}},
        root=root,
    )

    pack_dir = root / updated.chart_pack_id
    assert sorted(str(path.relative_to(pack_dir)) for path in pack_dir.rglob("*") if path.is_file()) == [
        "chart_pack.json",
        "chart_pack.md",
        "data/chart_a.csv",
        "specs/chart_a.json",
    ]
