from collections import Counter
from pathlib import Path

from scripts.eval.audit_same_page_table_rescue_candidates import (
    build_same_page_table_rescue_candidate_payloads,
    render_report,
)


def test_same_page_table_rescue_candidates_classifies_patch() -> None:
    details = {
        "run_id": "table_audit_test",
        "baseline_backend": "fitz_pdfplumber",
        "candidate_backend": "docling",
        "documents": [
            {
                "pdf_path": "/tmp/paper.pdf",
                "baseline_backend": "fitz_pdfplumber",
                "candidate_backend": "docling",
                "classification": {
                    "missing_cells_by_page": {"8": {"amyloidunknowntauunknown": 1}},
                },
            }
        ],
    }

    def load_page_counters(
        pdf_path: Path, baseline_backend: str, candidate_backend: str
    ) -> tuple[dict[int, Counter[str]], dict[int, Counter[str]]]:
        assert str(pdf_path) == "/tmp/paper.pdf"
        assert baseline_backend == "fitz_pdfplumber"
        assert candidate_backend == "docling"
        return (
            {8: Counter({"amyloidunknowntauunknown": 1, "sharedrow": 3})},
            {8: Counter({"amyloidunknowntau": 1, "sharedrow": 3})},
        )

    summary, candidate_details = build_same_page_table_rescue_candidate_payloads(
        table_merge_details=details,
        table_merge_details_path=Path("/tmp/details.json"),
        run_id="same_page_rescue_test",
        page_counter_loader=load_page_counters,
    )

    assert summary["runtime_change_approved"] is False
    assert summary["candidate_page_count"] == 1
    assert summary["action_counts"] == {"patch": 1}
    candidate = candidate_details["candidates"][0]
    assert candidate["current_runtime_behavior"] == "same_page_fallback_skipped"
    assert candidate["action"] == "patch"
    assert candidate["reason"] == "fallback_covers_candidate_prefix_truncation"
    assert candidate["candidate_prefix_truncation_repairs"][0]["missing_suffix"] == "unknown"


def test_same_page_table_rescue_candidates_skips_non_same_page_candidate() -> None:
    details = {
        "run_id": "table_audit_test",
        "baseline_backend": "fitz_pdfplumber",
        "candidate_backend": "docling",
        "documents": [
            {
                "pdf_path": "/tmp/paper.pdf",
                "classification": {
                    "missing_cells_by_page": {"4": {"missingrow": 1}},
                },
            }
        ],
    }

    def load_page_counters(
        _pdf_path: Path, _baseline_backend: str, _candidate_backend: str
    ) -> tuple[dict[int, Counter[str]], dict[int, Counter[str]]]:
        return ({4: Counter({"missingrow": 1, "sharedrow": 2})}, {})

    summary, candidate_details = build_same_page_table_rescue_candidate_payloads(
        table_merge_details=details,
        table_merge_details_path=Path("/tmp/details.json"),
        run_id="same_page_rescue_test",
        page_counter_loader=load_page_counters,
    )

    assert summary["action_counts"] == {"skip_not_same_page_candidate": 1}
    candidate = candidate_details["candidates"][0]
    assert candidate["current_runtime_behavior"] == "not_same_page_rescue_candidate"
    assert candidate["action"] == "skip_not_same_page_candidate"
    assert candidate["reason"] == "candidate_has_no_table_counter_on_missing_cell_page"


def test_same_page_table_rescue_report_states_review_only() -> None:
    summary = {
        "run_id": "same_page_rescue_test",
        "candidate_page_count": 1,
        "runtime_change_approved": False,
        "recommended_runtime_posture": "keep_same_page_fallback_skip_until_runtime_rescue_is_approved",
        "action_counts": {"patch": 1},
    }
    details = {
        "candidates": [
            {
                "page": 8,
                "action": "patch",
                "reason": "fallback_covers_candidate_prefix_truncation",
                "overlap_ratio": 0.75,
                "pdf_path": "/tmp/paper.pdf",
            }
        ]
    }

    report = render_report(summary, details)

    assert "action `patch`" in report
    assert "review evidence only" in report
