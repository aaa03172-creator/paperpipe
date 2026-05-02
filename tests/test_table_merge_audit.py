from collections import Counter

from scripts.eval.audit_table_merge_semantics import classify_page_cell_coverage, classify_same_page_table_rescue_pair


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


def test_classify_page_cell_coverage_accepts_high_similarity_cell_matches() -> None:
    baseline_pages = {
        16: Counter({"alexafluorcid2488affinipuredonkeyanti-mouseigghl": 1}),
    }
    candidate_pages = {
        16: Counter({"alexafluor488affinipuredonkeyanti-mouseigghl": 1}),
    }

    result = classify_page_cell_coverage(baseline_pages, candidate_pages)

    assert result["semantic_merge_preserved"] is True
    assert result["missing_cells_total"] == 0
    assert result["extra_cells_total"] == 0
    assert result["near_matched_cells_total"] == 1
    assert result["near_match_examples_by_page"]["16"][0]["strategy"] == "high_similarity"


def test_classify_page_cell_coverage_accepts_label_prefixed_candidate_cells() -> None:
    baseline_pages = {
        16: Counter({"638911": 1, "takara": 1}),
    }
    candidate_pages = {
        16: Counter({"identifier638911": 1, "sourcetakara": 1}),
    }

    result = classify_page_cell_coverage(baseline_pages, candidate_pages)

    assert result["semantic_merge_preserved"] is True
    assert result["missing_cells_total"] == 0
    assert result["near_matched_cells_by_page"]["16"] == {"638911": 1, "takara": 1}


def test_classify_page_cell_coverage_accepts_candidate_cell_fragments() -> None:
    baseline_pages = {
        16: Counter({"catmir2306": 1}),
    }
    candidate_pages = {
        16: Counter({"catmir": 1, "2306": 1}),
    }

    result = classify_page_cell_coverage(baseline_pages, candidate_pages)

    assert result["semantic_merge_preserved"] is True
    assert result["missing_cells_total"] == 0
    assert result["extra_cells_total"] == 0
    assert result["near_match_examples_by_page"]["16"][0]["strategy"] == "candidate_fragments_cover_baseline"


def test_classify_page_cell_coverage_accepts_generic_suffix_truncation() -> None:
    baseline_pages = {
        15: Counter({"dmemhighglucoseglutamaxsupplement": 1}),
    }
    candidate_pages = {
        15: Counter({"dmemhighglucoseglutamax": 1}),
    }

    result = classify_page_cell_coverage(baseline_pages, candidate_pages)

    assert result["semantic_merge_preserved"] is True
    assert result["missing_cells_total"] == 0
    assert result["near_match_examples_by_page"]["15"][0]["strategy"] == "generic_suffix_truncation"


def test_classify_page_cell_coverage_flags_semantic_tail_truncation() -> None:
    baseline_pages = {
        8: Counter({"amyloidunknowntauunknown": 1}),
    }
    candidate_pages = {
        8: Counter({"amyloidunknowntau": 1}),
    }

    result = classify_page_cell_coverage(baseline_pages, candidate_pages)

    assert result["semantic_merge_preserved"] is False
    assert result["missing_cells_total"] == 1
    assert result["missing_cells_by_page"]["8"]["amyloidunknowntauunknown"] == 1
    assert result["extra_cells_by_page"]["8"]["amyloidunknowntau"] == 1
    assert result["near_matched_cells_total"] == 0


def test_classify_page_cell_coverage_flags_missing_page() -> None:
    baseline_pages = {
        4: Counter({"amyloidpositive": 1}),
    }
    candidate_pages = {}

    result = classify_page_cell_coverage(baseline_pages, candidate_pages)

    assert result["semantic_merge_preserved"] is False
    assert result["missing_pages"] == [4]
    assert result["missing_cells_total"] == 1


def test_classify_same_page_table_rescue_pair_patches_prefix_truncation() -> None:
    missing = Counter({"amyloidunknowntauunknown": 1})
    candidate = Counter(
        {
            "amyloidunknowntau": 1,
            "likelihoodofalzheimersdiseaseasaprimarydiagnosis": 1,
            "furtherinvestigation": 1,
        }
    )
    fallback = Counter(
        {
            "amyloidunknowntauunknown": 1,
            "likelihoodofalzheimersdiseaseasaprimarydiagnosis": 1,
            "furtherinvestigation": 1,
        }
    )

    result = classify_same_page_table_rescue_pair(
        missing_counter=missing,
        candidate_counter=candidate,
        fallback_counter=fallback,
    )

    assert result["action"] == "patch"
    assert result["reason"] == "fallback_covers_candidate_prefix_truncation"
    assert result["covered_missing_cells"] == {"amyloidunknowntauunknown": 1}
    assert result["candidate_prefix_truncation_repairs"] == [
        {
            "missing_cell": "amyloidunknowntauunknown",
            "candidate_cell": "amyloidunknowntau",
            "missing_suffix": "unknown",
            "missing_count": 1,
            "candidate_count": 1,
        }
    ]


def test_classify_same_page_table_rescue_pair_rejects_different_same_page_table() -> None:
    result = classify_same_page_table_rescue_pair(
        missing_counter=Counter({"amyloidunknowntauunknown": 1}),
        candidate_counter=Counter({"tableaheader": 1, "tablearow": 1, "amyloidunknowntau": 1}),
        fallback_counter=Counter({"tablebheader": 1, "tablebrow": 1, "amyloidunknowntauunknown": 1}),
    )

    assert result["action"] == "skip_low_confidence"
    assert result["reason"] == "candidate_and_fallback_tables_do_not_share_enough_cells"
    assert result["overlap_ratio"] == 0.0


def test_classify_same_page_table_rescue_pair_skips_when_no_missing_cells() -> None:
    result = classify_same_page_table_rescue_pair(
        missing_counter=Counter(),
        candidate_counter=Counter({"amyloidunknowntauunknown": 1}),
        fallback_counter=Counter({"amyloidunknowntauunknown": 1}),
    )

    assert result["action"] == "skip_no_missing_cells"
    assert result["reason"] == "candidate_table_has_no_missing_cells_to_repair"


def test_classify_same_page_table_rescue_pair_replaces_when_fallback_only_adds_missing_cells() -> None:
    result = classify_same_page_table_rescue_pair(
        missing_counter=Counter({"row3": 1}),
        candidate_counter=Counter({"header": 1, "row1": 1, "row2": 1}),
        fallback_counter=Counter({"header": 1, "row1": 1, "row2": 1, "row3": 1}),
    )

    assert result["action"] == "replace"
    assert result["reason"] == "fallback_adds_missing_cells_without_unsupported_extras"
    assert result["covered_missing_cells"] == {"row3": 1}
    assert result["unsupported_fallback_extra_cells"] == {}


def test_classify_same_page_table_rescue_pair_rejects_unsupported_extra_cells() -> None:
    result = classify_same_page_table_rescue_pair(
        missing_counter=Counter({"row3": 1}),
        candidate_counter=Counter({"header": 1, "row1": 1, "row2": 1}),
        fallback_counter=Counter({"header": 1, "row1": 1, "row2": 1, "row3": 1, "otherrow": 1}),
    )

    assert result["action"] == "skip_duplicate_risk"
    assert result["reason"] == "fallback_contains_unsupported_extra_cells"
    assert result["covered_missing_cells"] == {"row3": 1}
    assert result["unsupported_fallback_extra_cells"] == {"otherrow": 1}
