from __future__ import annotations

from datetime import datetime, timedelta
from types import SimpleNamespace

from src.fetch.arxiv import ArXivFetcher


def _config() -> SimpleNamespace:
    return SimpleNamespace(system=SimpleNamespace(backfill_limit_days=7))


def _entry(**overrides) -> SimpleNamespace:
    published = datetime.now() - timedelta(days=1)
    payload = {
        "link": "http://arxiv.org/abs/2401.12345v1",
        "published_parsed": published.timetuple(),
        "title": "ArXiv fixture paper",
        "authors": [SimpleNamespace(name="A. Author")],
        "summary": "Fixture summary",
    }
    payload.update(overrides)
    return SimpleNamespace(**payload)


def test_arxiv_fetcher_does_not_store_arxiv_id_as_doi(monkeypatch):
    monkeypatch.setattr(
        "src.fetch.arxiv.feedparser.parse",
        lambda _url: SimpleNamespace(bozo=False, entries=[_entry()]),
    )

    papers = ArXivFetcher(_config()).fetch("fixture", max_results=1)

    assert len(papers) == 1
    assert papers[0].id == "2401.12345v1"
    assert papers[0].doi is None
    assert papers[0].pdf_link == "http://arxiv.org/pdf/2401.12345v1"


def test_arxiv_fetcher_uses_real_doi_when_present(monkeypatch):
    monkeypatch.setattr(
        "src.fetch.arxiv.feedparser.parse",
        lambda _url: SimpleNamespace(
            bozo=False,
            entries=[_entry(arxiv_doi="10.48550/arXiv.2401.12345")],
        ),
    )

    papers = ArXivFetcher(_config()).fetch("fixture", max_results=1)

    assert papers[0].id == "2401.12345v1"
    assert papers[0].doi == "10.48550/arXiv.2401.12345"


def test_arxiv_fetcher_skips_entry_with_missing_published_date(monkeypatch):
    monkeypatch.setattr(
        "src.fetch.arxiv.feedparser.parse",
        lambda _url: SimpleNamespace(bozo=False, entries=[_entry(published_parsed=None)]),
    )

    papers = ArXivFetcher(_config()).fetch("fixture", max_results=1)

    assert papers == []


def test_arxiv_fetcher_strips_pubmed_field_tags_before_query(monkeypatch):
    captured = {}

    def fake_parse(url):
        captured["url"] = url
        return SimpleNamespace(bozo=False, entries=[])

    monkeypatch.setattr("src.fetch.arxiv.feedparser.parse", fake_parse)

    ArXivFetcher(_config()).fetch('"TGF beta"[Title/Abstract] AND fibrosis[MeSH Terms]', max_results=1)

    assert "%5BTitle" not in captured["url"]
    assert "%5BMeSH" not in captured["url"]
    assert "TGF%20beta" in captured["url"]
    assert "fibrosis" in captured["url"]
