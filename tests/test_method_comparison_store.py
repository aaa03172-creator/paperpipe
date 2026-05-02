from __future__ import annotations

from datetime import datetime, timezone

import pytest

import src.method_comparisons.store as method_comparison_store
from src.method_comparisons.store import (
    list_method_comparison_ids,
    load_method_comparison,
    load_method_comparison_csv,
    load_method_comparison_markdown,
    method_comparison_csv_path,
    method_comparison_json_path,
    method_comparison_markdown_path,
    save_method_comparison_bundle,
)
from src.schemas.method_comparison import MethodComparison, build_method_comparison_columns


def _sample_comparison(title: str = "Method comparison") -> MethodComparison:
    return MethodComparison(
        comparison_id="methodcmp_20260318T120000Z_demo",
        title=title,
        created_at=datetime(2026, 3, 18, 12, 0, tzinfo=timezone.utc),
        readiness="evidence_backed",
        freshness="unknown",
        paper_ids=["paper-001"],
        columns=build_method_comparison_columns(["intervention", "primary_readout"]),
        rows=[
            {
                "paper_id": "paper-001",
                "title": "Demo paper",
                "cells": [
                    {"field_id": "intervention", "value": "Ketone ester", "status": "explicit"},
                    {"field_id": "primary_readout", "value": "Memory score", "status": "explicit"},
                ],
            }
        ],
    )


def test_method_comparison_store_roundtrip_creates_expected_layout(tmp_path):
    root = tmp_path / "method_comparisons"
    comparison = _sample_comparison()
    csv_text = "paper_id,intervention\npaper-001,Ketone ester\n"
    markdown = "# Comparison\n"

    json_path, csv_path, md_path = save_method_comparison_bundle(comparison, csv_text, markdown, root)
    loaded = load_method_comparison(comparison.comparison_id, root)
    loaded_csv = load_method_comparison_csv(comparison.comparison_id, root)
    loaded_markdown = load_method_comparison_markdown(comparison.comparison_id, root)

    assert json_path == method_comparison_json_path(comparison.comparison_id, root)
    assert csv_path == method_comparison_csv_path(comparison.comparison_id, root)
    assert md_path == method_comparison_markdown_path(comparison.comparison_id, root)
    assert loaded.comparison_id == comparison.comparison_id
    assert loaded.title == comparison.title
    assert loaded.layer == "user_facing_artifact"
    assert loaded.canonical_status == "non_canonical"
    assert loaded.readiness == "evidence_backed"
    assert loaded.freshness == "unknown"
    assert loaded_csv == csv_text
    assert loaded_markdown == markdown
    assert list_method_comparison_ids(root) == [comparison.comparison_id]


def test_method_comparison_store_overwrites_same_id_without_duplicate_dump(tmp_path):
    root = tmp_path / "method_comparisons"
    comparison = _sample_comparison(title="First title")
    save_method_comparison_bundle(comparison, "a,b\n", "# First", root)

    updated = _sample_comparison(title="Updated title")
    save_method_comparison_bundle(updated, "c,d\n", "# Updated", root)

    loaded = load_method_comparison(updated.comparison_id, root)
    loaded_csv = load_method_comparison_csv(updated.comparison_id, root)
    loaded_markdown = load_method_comparison_markdown(updated.comparison_id, root)

    assert loaded.title == "Updated title"
    assert loaded_csv == "c,d\n"
    assert loaded_markdown == "# Updated"
    assert len(list((root / updated.comparison_id).iterdir())) == 3


def test_method_comparison_store_rolls_back_bundle_if_markdown_write_fails(tmp_path, monkeypatch):
    root = tmp_path / "method_comparisons"
    original = _sample_comparison(title="First title")
    save_method_comparison_bundle(original, "a,b\n", "# First", root)

    updated = _sample_comparison(title="Updated title")
    original_atomic_write_text = method_comparison_store._atomic_write_text
    call_count = {"value": 0}

    def fail_on_third_write(path, content):
        call_count["value"] += 1
        if call_count["value"] == 3:
            raise IOError("boom")
        return original_atomic_write_text(path, content)

    monkeypatch.setattr(method_comparison_store, "_atomic_write_text", fail_on_third_write)

    with pytest.raises(OSError):
        save_method_comparison_bundle(updated, "c,d\n", "# Updated", root)

    loaded = load_method_comparison(updated.comparison_id, root)
    loaded_csv = load_method_comparison_csv(updated.comparison_id, root)
    loaded_markdown = load_method_comparison_markdown(updated.comparison_id, root)
    assert loaded.title == "First title"
    assert loaded_csv == "a,b\n"
    assert loaded_markdown == "# First"


def test_method_comparison_store_does_not_leave_partial_new_bundle_if_write_fails(tmp_path, monkeypatch):
    root = tmp_path / "method_comparisons"
    comparison = _sample_comparison()
    original_atomic_write_text = method_comparison_store._atomic_write_text
    call_count = {"value": 0}

    def fail_on_second_write(path, content):
        call_count["value"] += 1
        if call_count["value"] == 2:
            raise IOError("boom")
        return original_atomic_write_text(path, content)

    monkeypatch.setattr(method_comparison_store, "_atomic_write_text", fail_on_second_write)

    with pytest.raises(OSError):
        save_method_comparison_bundle(comparison, "a,b\n", "# First", root)

    assert list_method_comparison_ids(root) == []
