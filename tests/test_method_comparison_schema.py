from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from src.schemas.chat import ChatEvidenceRef, ChatLocator
from src.schemas.method_comparison import (
    METHOD_COMPARISON_FIELD_MAP,
    MethodComparison,
    MethodComparisonRequest,
    build_method_comparison_columns,
    method_comparison_field_specs,
)


def test_method_comparison_field_registry_matches_expected_allowlist() -> None:
    specs = method_comparison_field_specs()

    assert [spec.field_id for spec in specs] == [
        "intervention",
        "comparator",
        "duration_or_timepoint",
        "primary_readout",
        "sample_size",
    ]
    assert METHOD_COMPARISON_FIELD_MAP["sample_size"].value_kind == "numeric"


def test_method_comparison_request_dedupes_papers_and_fields_preserving_order() -> None:
    request = MethodComparisonRequest(
        paper_ids=["paper-1", "paper-2", "paper-1"],
        field_ids=["intervention", "primary_readout", "intervention"],
    )

    assert request.paper_ids == ["paper-1", "paper-2"]
    assert request.field_ids == ["intervention", "primary_readout"]


def test_build_method_comparison_columns_uses_registry_metadata() -> None:
    columns = build_method_comparison_columns(["intervention", "sample_size"])

    assert [column.field_id for column in columns] == ["intervention", "sample_size"]
    assert [column.label for column in columns] == ["Intervention", "Sample Size"]
    assert [column.value_kind for column in columns] == ["text", "numeric"]


def test_method_comparison_schema_accepts_paper_slug_distinct_from_paper_id() -> None:
    comparison = MethodComparison(
        comparison_id="methodcmp_20260318T120000Z_demo",
        title="Method comparison demo",
        created_at=datetime(2026, 3, 18, 12, 0, tzinfo=timezone.utc),
        paper_ids=["doi:10.1000/test"],
        columns=build_method_comparison_columns(["intervention"]),
        rows=[
            {
                "paper_id": "doi:10.1000/test",
                "paper_slug": "wenzelShortchainFattyAcids2020",
                "title": "Demo paper",
                "cells": [
                    {
                        "field_id": "intervention",
                        "value": "Ketone ester",
                        "status": "explicit",
                        "evidence_refs": [
                            ChatEvidenceRef(
                                paper_slug="wenzelShortchainFattyAcids2020",
                                claim_id="claim_123",
                                evidence_id="evidence_123",
                                run_id="run_123",
                                locator=ChatLocator(page=1),
                            )
                        ],
                    }
                ],
            }
        ],
    )

    assert comparison.rows[0].paper_id == "doi:10.1000/test"
    assert comparison.rows[0].paper_slug == "wenzelShortchainFattyAcids2020"
    assert comparison.rows[0].cells[0].evidence_refs[0].paper_slug == "wenzelShortchainFattyAcids2020"
    assert comparison.layer == "user_facing_artifact"
    assert comparison.canonical_status == "non_canonical"


def test_method_comparison_cell_requires_value_when_not_missing() -> None:
    with pytest.raises(ValidationError):
        MethodComparison(
            comparison_id="methodcmp_20260318T120000Z_demo",
            title="Method comparison demo",
            created_at=datetime(2026, 3, 18, 12, 0, tzinfo=timezone.utc),
            paper_ids=["paper-1"],
            columns=build_method_comparison_columns(["intervention"]),
            rows=[
                {
                    "paper_id": "paper-1",
                    "title": "Demo paper",
                    "cells": [{"field_id": "intervention", "status": "explicit"}],
                }
            ],
        )


def test_method_comparison_row_rejects_duplicate_field_ids() -> None:
    with pytest.raises(ValidationError):
        MethodComparison(
            comparison_id="methodcmp_20260318T120000Z_demo",
            title="Method comparison demo",
            created_at=datetime(2026, 3, 18, 12, 0, tzinfo=timezone.utc),
            paper_ids=["paper-1"],
            columns=build_method_comparison_columns(["intervention"]),
            rows=[
                {
                    "paper_id": "paper-1",
                    "title": "Demo paper",
                    "cells": [
                        {"field_id": "intervention", "value": "A", "status": "explicit"},
                        {"field_id": "intervention", "value": "B", "status": "conflict"},
                    ],
                }
            ],
        )
