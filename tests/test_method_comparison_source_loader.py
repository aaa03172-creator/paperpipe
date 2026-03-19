from __future__ import annotations

import json
import os

import pytest

from src.method_comparisons.source_loader import (
    build_claimset_comparison_row,
    load_claimset_resolved_source,
)
from src.services.identity import artifact_paper_segment


def _write_claimset(run_dir, payload) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "claimset.resolved.json").write_text(json.dumps(payload), encoding="utf-8")


def _cell_map(row):
    return {cell.field_id: cell for cell in row.cells}


def test_load_claimset_resolved_source_picks_latest_run_with_resolved_claimset(tmp_path) -> None:
    root = tmp_path / "artifacts"
    paper_id = "doi:10.1000/test-paper"
    paper_dir = root / artifact_paper_segment(paper_id)
    old_run = paper_dir / "run_old"
    selected_run = paper_dir / "run_selected"
    newest_without_resolved = paper_dir / "run_newest"

    _write_claimset(
        old_run,
        {
            "doc_id": paper_id,
            "claims": [{"statement": "old claim", "evidence_spans": [{"quote": "old evidence", "page": 0}]}],
        },
    )
    _write_claimset(
        selected_run,
        {
            "doc_id": paper_id,
            "claims": [{"statement": "selected claim", "evidence_spans": [{"quote": "selected evidence", "page": 1}]}],
        },
    )
    newest_without_resolved.mkdir(parents=True, exist_ok=True)

    os.utime(old_run, (1000, 1000))
    os.utime(selected_run, (2000, 2000))
    os.utime(newest_without_resolved, (3000, 3000))

    source = load_claimset_resolved_source(paper_id, root=root)

    assert source.run_id == "run_selected"
    assert source.claimset_path == selected_run / "claimset.resolved.json"
    assert len(source.entries) == 1


def test_load_claimset_resolved_source_raises_when_missing(tmp_path) -> None:
    root = tmp_path / "artifacts"
    paper_id = "paper-missing"
    (root / paper_id / "run_001").mkdir(parents=True, exist_ok=True)

    with pytest.raises(FileNotFoundError):
        load_claimset_resolved_source(paper_id, root=root)


def test_build_claimset_comparison_row_extracts_explicit_values_from_claimset(tmp_path) -> None:
    root = tmp_path / "artifacts"
    paper_id = "paper-001"
    run_dir = root / paper_id / "run_001"
    _write_claimset(
        run_dir,
        {
            "doc_id": paper_id,
            "claims": [
                {
                    "claim_id": "CLM-001",
                    "type": "methods",
                    "statement": (
                        "Intervention: Ketone ester. Comparator: Placebo. "
                        "Primary outcome: ADAS-Cog score. Duration: 12 weeks."
                    ),
                    "sample_size": 48,
                    "evidence_spans": [
                        {
                            "quote": (
                                "Intervention: Ketone ester. Comparator: Placebo. "
                                "Primary outcome: ADAS-Cog score. Duration: 12 weeks. Sample size: 48."
                            ),
                            "page": 2,
                            "section": "Methods",
                            "chunk_id": "p02_c01",
                        }
                    ],
                }
            ],
        },
    )

    source = load_claimset_resolved_source(paper_id, root=root)
    row = build_claimset_comparison_row(
        source,
        ["intervention", "comparator", "primary_readout", "duration_or_timepoint", "sample_size"],
        paper_slug="paper-001-slug",
        title="Paper 001",
    )
    cells = _cell_map(row)

    assert row.paper_id == paper_id
    assert row.paper_slug == "paper-001-slug"
    assert row.title == "Paper 001"
    assert cells["intervention"].value == "Ketone ester"
    assert cells["intervention"].status == "explicit"
    assert cells["comparator"].value == "Placebo"
    assert cells["primary_readout"].value == "ADAS-Cog score"
    assert cells["duration_or_timepoint"].value == "12 weeks"
    assert cells["sample_size"].value == 48
    assert cells["sample_size"].evidence_refs[0].run_id == "run_001"
    assert cells["sample_size"].evidence_refs[0].paper_slug == "paper-001-slug"


def test_build_claimset_comparison_row_marks_inferred_when_value_only_in_evidence(tmp_path) -> None:
    root = tmp_path / "artifacts"
    paper_id = "paper-002"
    run_dir = root / paper_id / "run_001"
    _write_claimset(
        run_dir,
        {
            "doc_id": paper_id,
            "claims": [
                {
                    "claim_id": "CLM-002",
                    "type": "efficacy",
                    "statement": "The treatment improved cognition during follow-up.",
                    "evidence_spans": [
                        {
                            "quote": (
                                "Intervention: Ketone ester. Comparator: Placebo. "
                                "Primary endpoint: Memory composite score. Timepoint: week 24."
                            ),
                            "page": 4,
                            "section": "Methods",
                        }
                    ],
                }
            ],
        },
    )

    source = load_claimset_resolved_source(paper_id, root=root)
    row = build_claimset_comparison_row(
        source,
        ["intervention", "comparator", "primary_readout", "duration_or_timepoint"],
        paper_slug="paper-002-slug",
    )
    cells = _cell_map(row)

    assert cells["intervention"].status == "inferred"
    assert cells["intervention"].value == "Ketone ester"
    assert cells["intervention"].note.startswith("Derived from claimset evidence quote")
    assert cells["comparator"].value == "Placebo"
    assert cells["primary_readout"].value == "Memory composite score"
    assert cells["duration_or_timepoint"].value == "week 24"


def test_build_claimset_comparison_row_marks_conflict_for_distinct_supported_values(tmp_path) -> None:
    root = tmp_path / "artifacts"
    paper_id = "paper-003"
    run_dir = root / paper_id / "run_001"
    _write_claimset(
        run_dir,
        {
            "doc_id": paper_id,
            "claims": [
                {
                    "claim_id": "CLM-003A",
                    "statement": "Intervention: Ketone ester.",
                    "evidence_spans": [{"quote": "Intervention: Ketone ester.", "page": 1}],
                },
                {
                    "claim_id": "CLM-003B",
                    "statement": "Intervention: Medium-chain triglycerides.",
                    "evidence_spans": [{"quote": "Intervention: Medium-chain triglycerides.", "page": 2}],
                },
            ],
        },
    )

    source = load_claimset_resolved_source(paper_id, root=root)
    row = build_claimset_comparison_row(source, ["intervention"], paper_slug="paper-003-slug")
    cell = row.cells[0]

    assert cell.status == "conflict"
    assert cell.value == "Ketone ester | Medium-chain triglycerides"
    assert "Ketone ester" in (cell.note or "")
    assert "Medium-chain triglycerides" in (cell.note or "")
    assert len(cell.evidence_refs) == 2


def test_build_claimset_comparison_row_keeps_missing_without_evidence_backing(tmp_path) -> None:
    root = tmp_path / "artifacts"
    paper_id = "paper-004"
    run_dir = root / paper_id / "run_001"
    _write_claimset(
        run_dir,
        {
            "doc_id": paper_id,
            "claims": [
                {
                    "claim_id": "CLM-004",
                    "statement": "Intervention: Ketone ester.",
                    "evidence_spans": [],
                }
            ],
        },
    )

    source = load_claimset_resolved_source(paper_id, root=root)
    row = build_claimset_comparison_row(source, ["intervention"], paper_slug="paper-004-slug")
    cell = row.cells[0]

    assert cell.status == "missing"
    assert cell.value is None
    assert cell.evidence_refs == []
    assert cell.note == "No evidence-backed support found in claimset.resolved.json."
