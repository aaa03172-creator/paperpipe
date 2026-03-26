from collections import Counter

from scripts.eval.audit_table_merge_semantics import classify_page_cell_coverage


def test_classify_page_cell_coverage_marks_semantic_merge_preserved() -> None:
    baseline_pages = {
        7: Counter({"rehacom100": 1, "modifiedstorymemory": 1, "large": 2}),
    }
    candidate_pages = {
        7: Counter({"rehacom100": 1, "modifiedstorymemory": 1, "large": 2, "restorativeapproaches": 1}),
    }

    result = classify_page_cell_coverage(baseline_pages, candidate_pages)

    assert result["semantic_merge_preserved"] is True
    assert result["missing_pages"] == []
    assert result["missing_cells_total"] == 0
    assert result["extra_cells_total"] == 1


def test_classify_page_cell_coverage_flags_missing_cells() -> None:
    baseline_pages = {
        8: Counter({"amyloidpositive": 2, "highlyunlikely": 3}),
    }
    candidate_pages = {
        8: Counter({"amyloidpositive": 2}),
    }

    result = classify_page_cell_coverage(baseline_pages, candidate_pages)

    assert result["semantic_merge_preserved"] is False
    assert result["missing_pages"] == []
    assert result["missing_cells_total"] == 3
    assert result["missing_cells_by_page"]["8"]["highlyunlikely"] == 3


def test_classify_page_cell_coverage_flags_missing_page() -> None:
    baseline_pages = {
        4: Counter({"amyloidpositive": 1}),
    }
    candidate_pages = {}

    result = classify_page_cell_coverage(baseline_pages, candidate_pages)

    assert result["semantic_merge_preserved"] is False
    assert result["missing_pages"] == [4]
    assert result["missing_cells_total"] == 1
