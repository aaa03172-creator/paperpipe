from src.agents.ingest_agent import IngestAgent


def test_safe_parse_year_handles_invalid_creation_date():
    assert IngestAgent._safe_parse_year("th No") == 0
    assert IngestAgent._safe_parse_year(None) == 0


def test_safe_parse_year_parses_pdf_style_date():
    assert IngestAgent._safe_parse_year("D:20181201093000") == 2018


def test_safe_parse_year_fallback_regex():
    assert IngestAgent._safe_parse_year("created at 2024-03-11") == 2024
