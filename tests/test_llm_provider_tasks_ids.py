from __future__ import annotations

import logging

from src.llm_provider_tasks import extract_trial_data_with_provider


class _FakeProvider:
    entity_aliases = {}

    def _make_request(self, *_args, **_kwargs):
        return '{"study_design": {}}'

    def _extract_json(self, _content):
        return {"study_design": {}}


def test_trial_extraction_fallback_uses_canonical_doi_id():
    provider = _FakeProvider()
    logger = logging.getLogger("test")
    paper = {
        "doi": "10.1234/ABC",
        "title": "Example",
        "authors": ["Kim"],
        "published": "2024-01-01",
        "source": "PubMed",
        "link": "https://example.org",
    }

    result = extract_trial_data_with_provider(provider, paper, methods_snippet="", logger=logger)
    assert result is not None
    assert result.paper_id == "doi:10.1234/abc"


def test_trial_extraction_fallback_prefers_existing_paper_id_when_no_doi():
    provider = _FakeProvider()
    logger = logging.getLogger("test")
    paper = {
        "paper_id": "legacy:paper-123",
        "title": "No DOI",
        "authors": ["Lee"],
        "published": "2024-01-01",
        "source": "Local",
        "link": "file:///tmp/no-doi.pdf",
    }

    result = extract_trial_data_with_provider(provider, paper, methods_snippet="", logger=logger)
    assert result is not None
    assert result.paper_id == "legacy:paper-123"
