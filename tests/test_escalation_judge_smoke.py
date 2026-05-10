from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from scripts.check_escalation_judge_smoke import _evaluate_case, _load_fixture, _summarize
from src.llm_provider import LLMProvider


FIXTURE_PATH = Path(__file__).resolve().parent / "fixtures" / "escalation_judge_case" / "cases.json"
REAL_FIXTURE_PATH = Path(__file__).resolve().parent / "fixtures" / "escalation_judge_case" / "real_cases_20260327.json"
REAL_EXTENDED_FIXTURE_PATH = Path(__file__).resolve().parent / "fixtures" / "escalation_judge_case" / "real_cases_extended_20260327.json"


class _PolicyOnlyProvider(LLMProvider):
    def _initialize(self) -> None:
        self.client = True

    def _make_request(self, *args, **kwargs):
        return '{"approved": false, "new_confidence": 0.0, "reason": "Stub fallback"}'

    def get_embedding(self, text: str):
        return None


def _provider() -> _PolicyOnlyProvider:
    return _PolicyOnlyProvider(SimpleNamespace(features=None, default_model=None))


def _assert_fixture_matches_current_policy(path: Path) -> None:
    cases = _load_fixture(path)
    provider = _provider()
    results = [_evaluate_case(provider, case) for case in cases]
    summary = _summarize(results, model_name="policy-only-stub")
    expected_approved = sum(1 for case in cases if case.get("expected_approved") is True)

    assert summary["invalid_output_count"] == 0
    assert summary["mismatch_count"] == 0
    assert summary["approved_count"] == expected_approved


def test_load_fixture_reads_representative_cases() -> None:
    cases = _load_fixture(FIXTURE_PATH)

    assert len(cases) >= 6
    assert cases[0]["case_id"] == "approve_mci_mct_rct"
    assert isinstance(cases[0]["paper"], dict)


def test_summarize_counts_invalid_and_mismatch_cases() -> None:
    summary = _summarize(
        [
            {
                "case_id": "a",
                "valid_output": True,
                "matched": True,
                "approved": True,
                "final_route": "FAST_LANE_APPROVE",
                "in_biomedical_scope": True,
                "reason_codes": ["FASTLANE_GUIDANCE"],
            },
            {
                "case_id": "b",
                "valid_output": True,
                "matched": False,
                "approved": False,
                "final_route": "QUEUE_HUMAN_REVIEW",
                "in_biomedical_scope": True,
                "reason_codes": ["MODEL_REVIEW_REQUIRED"],
            },
            {
                "case_id": "c",
                "valid_output": False,
                "matched": False,
                "approved": None,
                "final_route": "QUEUE_HUMAN_REVIEW",
                "in_biomedical_scope": False,
                "reason_codes": ["JUDGE_ERROR"],
            },
        ],
        model_name="llama3:latest",
    )

    assert summary["model"] == "llama3:latest"
    assert summary["total_cases"] == 3
    assert summary["valid_output_count"] == 2
    assert summary["invalid_output_count"] == 1
    assert summary["mismatch_count"] == 1
    assert summary["approved_count"] == 1
    assert summary["route_counts"] == {"FAST_LANE_APPROVE": 1, "QUEUE_HUMAN_REVIEW": 2}
    assert summary["biomedical_scope_counts"] == {"in_scope": 2, "out_of_scope": 1}
    assert summary["top_reason_codes"] == ["FASTLANE_GUIDANCE", "JUDGE_ERROR", "MODEL_REVIEW_REQUIRED"]


def test_evaluate_case_marks_judge_error_as_invalid() -> None:
    class _BrokenProvider:
        def evaluate_escalation(self, paper):
            return {
                "approved": False,
                "reason": "Judge Error",
                "final_route": "QUEUE_HUMAN_REVIEW",
                "in_biomedical_scope": True,
                "reason_codes": ["JUDGE_ERROR"],
            }

    result = _evaluate_case(
        _BrokenProvider(),
        {
            "case_id": "broken",
            "expected_approved": False,
            "paper": {"title": "x", "summary": "y", "tags": []},
        },
    )

    assert result["approved"] is False
    assert result["valid_output"] is False
    assert result["matched"] is False
    assert result["final_route"] == "QUEUE_HUMAN_REVIEW"
    assert result["in_biomedical_scope"] is True
    assert result["reason_codes"] == ["JUDGE_ERROR"]


def test_load_real_fixture_matches_current_policy_baseline() -> None:
    cases = _load_fixture(REAL_FIXTURE_PATH)

    approved = sum(1 for case in cases if case.get("expected_approved") is True)
    rejected = sum(1 for case in cases if case.get("expected_approved") is False)

    assert len(cases) == 10
    assert approved == 4
    assert rejected == 6


def test_real_fixture_replays_against_current_policy_without_llm() -> None:
    _assert_fixture_matches_current_policy(REAL_FIXTURE_PATH)


def test_load_extended_real_fixture_matches_current_policy_baseline() -> None:
    cases = _load_fixture(REAL_EXTENDED_FIXTURE_PATH)

    approved = sum(1 for case in cases if case.get("expected_approved") is True)
    rejected = sum(1 for case in cases if case.get("expected_approved") is False)

    assert len(cases) == 22
    assert approved == 10
    assert rejected == 12


def test_extended_real_fixture_replays_against_current_policy_without_llm() -> None:
    _assert_fixture_matches_current_policy(REAL_EXTENDED_FIXTURE_PATH)
