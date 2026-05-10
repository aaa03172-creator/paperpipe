from pathlib import Path

from src.ingest.cloud_table_fallback import CloudTableFallbackExtractor


def test_evaluate_table_quality_flags_low_coverage() -> None:
    extractor = CloudTableFallbackExtractor(api_key="")
    sparse_rows = [
        ["1", "", "", ""],
        ["", "2", "", ""],
        ["", "", "3", ""],
        ["", "", "", "4"],
        ["5", "", "", ""],
        ["", "6", "", ""],
        ["", "", "7", ""],
        ["", "", "", "8"],
    ]
    valid, failures = extractor._evaluate_table_quality(
        [
            ["A", "B", "C", "D"],
            *sparse_rows,
        ]
    )
    assert valid is False
    assert "CELL_COVERAGE_LOW" in failures


def test_evaluate_table_quality_flags_overlap() -> None:
    extractor = CloudTableFallbackExtractor(api_key="")
    valid, failures = extractor._evaluate_table_quality(
        [
            ["A", "B"],
            ["1", "2"],
            ["1", "2"],
            ["1", "2"],
        ]
    )
    assert valid is False
    assert "CELL_OVERLAP_HIGH" in failures


def test_extract_tables_records_quality_taxonomy_when_invalid(monkeypatch, tmp_path: Path) -> None:
    pdf = tmp_path / "dummy.pdf"
    pdf.write_bytes(b"%PDF-1.4\n%fake\n")

    extractor = CloudTableFallbackExtractor(api_key="")
    extractor.client = object()  # bypass NO_API guard

    monkeypatch.setattr(extractor, "_select_candidate_pages", lambda _p, _b: [1])
    monkeypatch.setattr(extractor, "_extract_page_text", lambda _p, _n: "table text")
    sparse_rows = [
        ["1", "", "", ""],
        ["", "2", "", ""],
        ["", "", "3", ""],
        ["", "", "", "4"],
        ["5", "", "", ""],
        ["", "6", "", ""],
        ["", "", "7", ""],
        ["", "", "", "8"],
    ]
    monkeypatch.setattr(
        extractor,
        "_extract_page_tables_with_llm",
        lambda _t, _n: [
            [
                ["A", "B", "C", "D"],
                *sparse_rows,
            ]
        ],
    )

    result = extractor.extract_tables(pdf, page_budget=1)
    assert result.tables == []
    assert "CELL_COVERAGE_LOW" in result.diagnostics.table_failure_taxonomy
    assert "LOW_ACCURACY" in result.diagnostics.table_failure_taxonomy


def test_extract_tables_skips_llm_when_preflight_blocks(monkeypatch, tmp_path: Path) -> None:
    pdf = tmp_path / "dummy.pdf"
    pdf.write_bytes(b"%PDF-1.4\n%fake\n")

    extractor = CloudTableFallbackExtractor(api_key="", preflight_callback=lambda _text, _page: False)
    extractor.client = object()  # bypass NO_API guard

    monkeypatch.setattr(extractor, "_select_candidate_pages", lambda _p, _b: [1])
    monkeypatch.setattr(extractor, "_extract_page_text", lambda _p, _n: "table text")

    def fail_if_called(_text: str, _page: int):
        raise AssertionError("LLM extraction should not run when preflight blocks")

    monkeypatch.setattr(extractor, "_extract_page_tables_with_llm", fail_if_called)

    result = extractor.extract_tables(pdf, page_budget=1)

    assert result.tables == []
    assert "PRIVACY_PREFLIGHT_BLOCKED" in result.diagnostics.table_failure_taxonomy
