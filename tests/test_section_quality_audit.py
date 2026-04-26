from src.schemas.agent_artifacts import Section

from scripts.eval.audit_section_quality import (
    classify_low_ratio_page,
    classify_page_text_coverage,
    collapse_sections_by_page,
    collect_section_text_by_page,
)


def test_collapse_sections_by_page_splits_multi_page_ranges_evenly() -> None:
    sections = [
        Section(
            name="methods",
            text="a" * 10,
            char_start=0,
            char_end=10,
            page_start=2,
            page_end=3,
        )
    ]

    result = collapse_sections_by_page(sections)

    assert result == {2: 5, 3: 5}


def test_collect_section_text_by_page_duplicates_multi_page_section_text_for_review() -> None:
    sections = [
        Section(
            name="results",
            text="Figure 2 shows effect sizes.",
            char_start=0,
            char_end=28,
            page_start=5,
            page_end=6,
        )
    ]

    result = collect_section_text_by_page(sections)

    assert result[5] == "Figure 2 shows effect sizes."
    assert result[6] == "Figure 2 shows effect sizes."


def test_classify_low_ratio_page_marks_table_heavy_when_table_page_signal_exists() -> None:
    result = classify_low_ratio_page(
        page=8,
        baseline_text="row1 col1 row1 col2",
        candidate_text="caption only",
        baseline_table_pages=[8],
        candidate_table_pages=[],
    )

    assert result["review_bucket"] == "table_heavy_page"
    assert "baseline_table_page" in result["review_signals"]


def test_classify_low_ratio_page_marks_figure_heavy_on_figure_cues() -> None:
    result = classify_low_ratio_page(
        page=5,
        baseline_text="Figure 4: Forest plot with 95% CI and study weights.",
        candidate_text="Figure 4 caption only.",
        baseline_table_pages=[],
        candidate_table_pages=[],
    )

    assert result["review_bucket"] == "figure_heavy_page"
    assert "baseline_figure_cue" in result["review_signals"]


def test_classify_low_ratio_page_marks_figure_heavy_on_image_and_scale_bar_cues() -> None:
    result = classify_low_ratio_page(
        page=25,
        baseline_text="Representative images of stained tissue. Scale bar, 50 um.",
        candidate_text="Bipolar cell Article",
        baseline_table_pages=[],
        candidate_table_pages=[],
    )

    assert result["review_bucket"] == "figure_heavy_page"
    assert "baseline_figure_cue" in result["review_signals"]


def test_classify_low_ratio_page_marks_numeric_dense_page_without_table_or_figure_cues() -> None:
    result = classify_low_ratio_page(
        page=7,
        baseline_text="AUC 0.91 CI95 0.84 0.97 n=247 p=0.003 fold-change 12.8",
        candidate_text="legend on next page",
        baseline_table_pages=[],
        candidate_table_pages=[],
    )

    assert result["review_bucket"] == "numeric_dense_page"
    assert "baseline_numeric_dense" in result["review_signals"]
    assert result["baseline_digit_ratio"] >= 0.2


def test_classify_low_ratio_page_marks_overlap_when_table_and_figure_signals_both_exist() -> None:
    result = classify_low_ratio_page(
        page=8,
        baseline_text="Figure 3 with table rows and study values.",
        candidate_text="Figure 3 caption only.",
        baseline_table_pages=[8],
        candidate_table_pages=[],
    )

    assert result["review_bucket"] == "table_and_figure_heavy_page"
    assert "baseline_table_page" in result["review_signals"]
    assert "baseline_figure_cue" in result["review_signals"]


def test_classify_page_text_coverage_marks_preserved_when_ratios_hold() -> None:
    baseline_pages = {1: 120, 2: 240}
    candidate_pages = {1: 96, 2: 180}

    result = classify_page_text_coverage(
        baseline_pages,
        candidate_pages,
        baseline_table_pages=[2],
        baseline_section_count=2,
        candidate_section_count=2,
        min_page_text_ratio=0.4,
        min_total_text_ratio=0.5,
        min_substantive_page_chars=80,
    )

    assert result["page_coverage_preserved"] is True
    assert result["missing_substantive_pages"] == []
    assert result["low_page_text_ratio_pages"] == []
    assert result["low_total_text_ratio"] is False
    assert result["section_collapse"] is False


def test_classify_page_text_coverage_flags_missing_page_and_section_collapse() -> None:
    baseline_pages = {1: 140, 2: 160, 3: 170}
    candidate_pages = {1: 470}

    result = classify_page_text_coverage(
        baseline_pages,
        candidate_pages,
        baseline_section_count=3,
        candidate_section_count=1,
        min_page_text_ratio=0.4,
        min_total_text_ratio=0.5,
        min_substantive_page_chars=80,
    )

    assert result["page_coverage_preserved"] is False
    assert result["missing_substantive_pages"] == [2, 3]
    assert result["section_collapse"] is True


def test_classify_page_text_coverage_ignores_short_baseline_page_but_flags_low_ratio() -> None:
    baseline_pages = {1: 60, 2: 200}
    candidate_pages = {1: 0, 2: 50}

    result = classify_page_text_coverage(
        baseline_pages,
        candidate_pages,
        baseline_table_pages=[2],
        baseline_section_count=2,
        candidate_section_count=2,
        min_page_text_ratio=0.4,
        min_total_text_ratio=0.5,
        min_substantive_page_chars=80,
    )

    assert result["missing_substantive_pages"] == []
    assert result["low_page_text_ratio_pages"][0]["page"] == 2
    assert result["low_page_text_ratio_pages"][0]["ratio"] == 0.25
    assert result["low_page_text_ratio_pages"][0]["review_bucket"] == "table_heavy_page"
    assert result["low_total_text_ratio"] is True
