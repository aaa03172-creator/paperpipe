from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from src.method_comparisons.service import generate_method_comparison
from src.schemas.method_comparison import MethodComparisonRequest


FIXTURE_ROOT = Path(__file__).resolve().parent / "fixtures" / "method_comparison_case"


def _cell_map(row):
    return {cell.field_id: cell for cell in row.cells}


def test_method_comparison_fixture_hardening_generates_repeatable_saved_artifact(tmp_path) -> None:
    output_root = tmp_path / "method_comparisons"
    request = MethodComparisonRequest(
        comparison_id="methodcmp_fixture_case",
        paper_ids=["doi:10.1000/alpha", "doi:10.1000/beta", "doi:10.1000/gamma"],
        field_ids=["intervention", "comparator", "primary_readout", "duration_or_timepoint"],
    )
    fixed_now = datetime(2026, 3, 18, 18, 0, 0, tzinfo=timezone.utc)

    first = generate_method_comparison(
        request=request,
        root=output_root,
        artifacts_root=FIXTURE_ROOT / "artifacts",
        vault_path=FIXTURE_ROOT / "vault",
        now=fixed_now,
    )
    second = generate_method_comparison(
        request=request,
        root=output_root,
        artifacts_root=FIXTURE_ROOT / "artifacts",
        vault_path=FIXTURE_ROOT / "vault",
        now=fixed_now,
    )

    assert first.csv_text == second.csv_text
    assert first.markdown == second.markdown
    assert (output_root / "methodcmp_fixture_case" / "comparison.json").exists()
    assert (output_root / "methodcmp_fixture_case" / "comparison.csv").exists()
    assert (output_root / "methodcmp_fixture_case" / "comparison.md").exists()

    rows = {row.paper_slug: row for row in first.comparison.rows}
    alpha = _cell_map(rows["paper-alpha"])
    beta = _cell_map(rows["paper-beta"])
    gamma = _cell_map(rows["paper-gamma"])

    assert alpha["intervention"].status == "explicit"
    assert alpha["intervention"].value == "Ketone ester"
    assert alpha["duration_or_timepoint"].value == "12 weeks"

    assert beta["intervention"].status == "inferred"
    assert beta["intervention"].value == "MCT oil"
    assert beta["primary_readout"].value == "Memory composite score"

    assert gamma["intervention"].status == "conflict"
    assert gamma["intervention"].value == "Medium-chain triglyceride | Ketone ester"
    assert gamma["comparator"].status == "missing"
    assert gamma["duration_or_timepoint"].status == "missing"

    assert "paper-alpha" in first.csv_text
    assert "paper-beta" in first.csv_text
    assert "paper-gamma" in first.csv_text
    assert "Gamma Conflict Study" in first.markdown
    assert "Medium-chain triglyceride | Ketone ester (conflict)" in first.markdown
