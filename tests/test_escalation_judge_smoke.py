from __future__ import annotations

from pathlib import Path

from scripts.check_escalation_judge_smoke import _load_fixture, _summarize


FIXTURE_PATH = Path(__file__).resolve().parent / "fixtures" / "escalation_judge_case" / "cases.json"


def test_load_fixture_reads_representative_cases() -> None:
    cases = _load_fixture(FIXTURE_PATH)

    assert len(cases) >= 6
    assert cases[0]["case_id"] == "approve_mci_mct_rct"
    assert isinstance(cases[0]["paper"], dict)


def test_summarize_counts_invalid_and_mismatch_cases() -> None:
    summary = _summarize(
        [
            {"case_id": "a", "valid_output": True, "matched": True, "approved": True},
            {"case_id": "b", "valid_output": True, "matched": False, "approved": False},
            {"case_id": "c", "valid_output": False, "matched": False, "approved": None},
        ],
        model_name="llama3:latest",
    )

    assert summary["model"] == "llama3:latest"
    assert summary["total_cases"] == 3
    assert summary["valid_output_count"] == 2
    assert summary["invalid_output_count"] == 1
    assert summary["mismatch_count"] == 1
    assert summary["approved_count"] == 1
