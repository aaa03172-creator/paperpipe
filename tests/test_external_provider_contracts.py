import logging
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

from src.downloader.providers.unpaywall import fetch_unpaywall_candidate
from src.fetch.arxiv import ArXivFetcher
from src.fetch.openalex import OpenAlexFetcher
from src.fetch.pubmed import PubMedFetcher
import src.fetchers as legacy_fetchers


def _pubmed_fetcher() -> PubMedFetcher:
    return PubMedFetcher(SimpleNamespace(system=SimpleNamespace(unpaywall_email=None)))


def _arxiv_fetcher(*, backfill_limit_days: int = 7) -> ArXivFetcher:
    return ArXivFetcher(SimpleNamespace(system=SimpleNamespace(backfill_limit_days=backfill_limit_days)))


class _Response:
    def __init__(self, *, status_code: int = 200, payload=None, json_error: Exception | None = None):
        self.status_code = status_code
        self._payload = payload or {}
        self._json_error = json_error

    def json(self):
        if self._json_error is not None:
            raise self._json_error
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


def test_pubmed_fetcher_parses_realistic_efetch_article_contract(monkeypatch):
    fetcher = _pubmed_fetcher()
    monkeypatch.setattr(fetcher, "_esearch", lambda _query, _max_results: ["12345678", "99999999"])
    monkeypatch.setattr(
        fetcher,
        "_efetch",
        lambda _ids: b"""
        <PubmedArticleSet>
          <PubmedArticle>
            <MedlineCitation>
              <PMID>12345678</PMID>
              <Article>
                <Journal>
                  <JournalIssue>
                    <PubDate>
                      <Year>2024</Year>
                      <Month>Apr</Month>
                      <Day>07</Day>
                    </PubDate>
                  </JournalIssue>
                </Journal>
                <ArticleTitle>Contract study of extracellular vesicles</ArticleTitle>
                <Abstract>
                  <AbstractText Label="Background">First abstract sentence.</AbstractText>
                  <AbstractText>Second abstract sentence.</AbstractText>
                </Abstract>
                <AuthorList>
                  <Author><LastName>Smith</LastName><Initials>AB</Initials></Author>
                  <Author><LastName>Lee</LastName><Initials>C</Initials></Author>
                </AuthorList>
                <ELocationID EIdType="doi">10.1000/pubmed.contract</ELocationID>
              </Article>
            </MedlineCitation>
            <PubmedData>
              <ArticleIdList>
                <ArticleId IdType="pubmed">12345678</ArticleId>
              </ArticleIdList>
            </PubmedData>
          </PubmedArticle>
          <PubmedArticle>
            <PubmedData><ArticleIdList /></PubmedData>
          </PubmedArticle>
        </PubmedArticleSet>
        """,
    )

    papers = fetcher.fetch("extracellular vesicles", max_results=2)

    assert len(papers) == 1
    paper = papers[0]
    assert paper.id == "10.1000/pubmed.contract"
    assert paper.doi == "10.1000/pubmed.contract"
    assert paper.title == "Contract study of extracellular vesicles"
    assert paper.authors == ["Smith AB", "Lee C"]
    assert paper.published == "2024-04-07"
    assert paper.source == "PubMed"
    assert paper.link == "https://pubmed.ncbi.nlm.nih.gov/12345678/"
    assert "First abstract sentence." in paper.summary
    assert "Second abstract sentence." in paper.summary


def test_pubmed_fetcher_uses_article_id_doi_and_medline_date_fallback(monkeypatch):
    fetcher = _pubmed_fetcher()
    monkeypatch.setattr(fetcher, "_esearch", lambda _query, _max_results: ["222"])
    monkeypatch.setattr(
        fetcher,
        "_efetch",
        lambda _ids: b"""
        <PubmedArticleSet>
          <PubmedArticle>
            <MedlineCitation>
              <PMID>222</PMID>
              <Article>
                <Journal>
                  <JournalIssue>
                    <PubDate><MedlineDate>2001 Spring</MedlineDate></PubDate>
                  </JournalIssue>
                </Journal>
                <ArticleTitle>Medline dated article</ArticleTitle>
              </Article>
            </MedlineCitation>
            <PubmedData>
              <ArticleIdList>
                <ArticleId IdType="doi">10.1000/article-id-doi</ArticleId>
              </ArticleIdList>
            </PubmedData>
          </PubmedArticle>
        </PubmedArticleSet>
        """,
    )

    papers = fetcher.fetch("medline date", max_results=1)

    assert len(papers) == 1
    assert papers[0].id == "10.1000/article-id-doi"
    assert papers[0].doi == "10.1000/article-id-doi"
    assert papers[0].published == "2001-01-01"


def test_pubmed_fetcher_returns_empty_list_for_malformed_efetch_xml(monkeypatch, caplog):
    fetcher = _pubmed_fetcher()
    monkeypatch.setattr(fetcher, "_esearch", lambda _query, _max_results: ["123"])
    monkeypatch.setattr(fetcher, "_efetch", lambda _ids: b"<PubmedArticleSet><PubmedArticle>")

    with caplog.at_level(logging.ERROR):
        papers = fetcher.fetch("malformed", max_results=1)

    assert papers == []
    assert "Critical Error in PubMedFetcher" in caplog.text


def test_pubmed_fetcher_esearch_keeps_special_characters_in_term_param(monkeypatch):
    fetcher = PubMedFetcher(SimpleNamespace(system=SimpleNamespace(unpaywall_email="ops@example.org")))
    captured: dict[str, object] = {}

    def fake_get(url: str, *, params: dict[str, object], timeout: int):
        captured["url"] = url
        captured["params"] = params
        captured["timeout"] = timeout
        return _Response(payload={"esearchresult": {"idlist": ["123"]}})

    monkeypatch.setattr("src.fetch.pubmed.requests.get", fake_get)

    ids = fetcher._esearch("TGF-beta & Smad #signal", max_results=7)

    assert ids == ["123"]
    assert captured["url"] == "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
    assert captured["params"] == {
        "db": "pubmed",
        "tool": "paperpipe",
        "email": "ops@example.org",
        "term": "TGF-beta & Smad #signal",
        "retmode": "json",
        "retmax": 7,
        "sort": "date",
    }
    assert captured["timeout"] == 10


def test_legacy_pubmed_esearch_keeps_special_characters_in_term_param(monkeypatch):
    captured: dict[str, object] = {}

    def fake_get(url: str, *, params: dict[str, object], timeout: int):
        captured["url"] = url
        captured["params"] = params
        captured["timeout"] = timeout
        return _Response(payload={"esearchresult": {"idlist": ["456"]}})

    monkeypatch.setattr("src.fetch.pubmed.requests.get", fake_get)

    with pytest.warns(DeprecationWarning, match="src.fetchers is deprecated"):
        ids = legacy_fetchers._esearch_pubmed("R&D TGF-beta & Smad", max_results=3)

    assert ids == ["456"]
    assert captured["url"] == "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
    assert captured["params"] == {
        "db": "pubmed",
        "tool": "paperpipe",
        "term": "R&D TGF-beta & Smad",
        "retmode": "json",
        "retmax": 3,
        "sort": "date",
    }
    assert captured["timeout"] == 10


def test_pubmed_fetcher_efetch_uses_params_and_contact_metadata(monkeypatch):
    fetcher = PubMedFetcher(SimpleNamespace(system=SimpleNamespace(unpaywall_email="ops@example.org")))
    captured: dict[str, object] = {}

    def fake_get(url: str, *, params: dict[str, object], timeout: int):
        captured["url"] = url
        captured["params"] = params
        captured["timeout"] = timeout
        response = _Response()
        response.content = b"<PubmedArticleSet />"
        return response

    monkeypatch.setattr("src.fetch.pubmed.requests.get", fake_get)

    assert fetcher._efetch(["123", "456"]) == b"<PubmedArticleSet />"
    assert captured["url"] == "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
    assert captured["params"] == {
        "db": "pubmed",
        "tool": "paperpipe",
        "email": "ops@example.org",
        "id": "123,456",
        "retmode": "xml",
    }
    assert captured["timeout"] == 15


def test_pubmed_fetcher_chunks_efetch_requests(monkeypatch):
    fetcher = _pubmed_fetcher()
    ids = [str(idx) for idx in range(205)]
    chunks: list[list[str]] = []

    monkeypatch.setattr(fetcher, "_esearch", lambda _query, _max_results: ids)

    def fake_efetch(id_chunk: list[str]):
        chunks.append(id_chunk)
        return b"<PubmedArticleSet />"

    monkeypatch.setattr(fetcher, "_efetch", fake_efetch)

    assert fetcher.fetch("large", max_results=205) == []
    assert [len(chunk) for chunk in chunks] == [100, 100, 5]


def test_unpaywall_candidate_preserves_best_location_contract(monkeypatch):
    captured_urls: list[str] = []

    def fake_get(url: str, timeout: int):
        captured_urls.append(url)
        assert timeout == 10
        return _Response(
            payload={
                "doi": "10.1000/unpaywall.contract",
                "best_oa_location": {
                    "url_for_pdf": "https://example.org/oa.pdf",
                    "license": "cc-by",
                    "host_type": "repository",
                },
            }
        )

    monkeypatch.setattr("src.downloader.providers.unpaywall.requests.get", fake_get)

    candidate = fetch_unpaywall_candidate("https://doi.org/10.1000/unpaywall.contract", "ops@example.org")

    assert captured_urls == [
        "https://api.unpaywall.org/v2/10.1000/unpaywall.contract?email=ops@example.org"
    ]
    assert candidate is not None
    assert candidate.url == "https://example.org/oa.pdf"
    assert candidate.source_name == "unpaywall"
    assert candidate.is_oa is True
    assert candidate.confidence == pytest.approx(0.9)
    assert candidate.license == "cc-by"
    assert candidate.meta == {"is_best": True, "host_type": "repository"}


def test_unpaywall_candidate_returns_none_for_no_pdf_or_not_found(monkeypatch):
    responses = iter(
        [
            _Response(payload={"best_oa_location": {"url": "https://example.org/html-only"}}),
            _Response(status_code=404),
        ]
    )
    monkeypatch.setattr("src.downloader.providers.unpaywall.requests.get", lambda *_args, **_kwargs: next(responses))

    assert fetch_unpaywall_candidate("10.1000/no-pdf", "ops@example.org") is None
    assert fetch_unpaywall_candidate("10.1000/not-found", "ops@example.org") is None


def test_unpaywall_candidate_returns_none_for_invalid_json(monkeypatch, caplog):
    monkeypatch.setattr(
        "src.downloader.providers.unpaywall.requests.get",
        lambda *_args, **_kwargs: _Response(json_error=ValueError("not json")),
    )

    with caplog.at_level(logging.WARNING):
        candidate = fetch_unpaywall_candidate("doi:10.1000/bad-json", "ops@example.org")

    assert candidate is None
    assert "Unpaywall returned invalid JSON" in caplog.text


def test_arxiv_fetcher_parses_recent_atom_entry_contract(monkeypatch):
    fetcher = _arxiv_fetcher(backfill_limit_days=7)
    recent = datetime.now() - timedelta(days=1)
    captured_urls: list[str] = []

    def fake_parse(url: str):
        captured_urls.append(url)
        return SimpleNamespace(
            bozo=False,
            entries=[
                SimpleNamespace(
                    link="https://arxiv.org/abs/2401.01234v2",
                    title="Contract study\nfor arXiv retrieval",
                    authors=[SimpleNamespace(name="Ada Lovelace"), SimpleNamespace(name="Grace Hopper")],
                    published_parsed=recent.timetuple(),
                    summary="A realistic Atom summary.",
                )
            ],
        )

    monkeypatch.setattr("src.fetch.arxiv.feedparser.parse", fake_parse)

    papers = fetcher.fetch("machine learning", max_results=5)

    assert captured_urls == [
        "http://export.arxiv.org/api/query?search_query=all:machine%20learning&start=0&max_results=5&sortBy=submittedDate&sortOrder=descending"
    ]
    assert len(papers) == 1
    paper = papers[0]
    assert paper.id == "2401.01234v2"
    assert paper.doi is None
    assert paper.title == "Contract study for arXiv retrieval"
    assert paper.authors == ["Ada Lovelace", "Grace Hopper"]
    assert paper.link == "https://arxiv.org/abs/2401.01234v2"
    assert paper.pdf_link == "https://arxiv.org/pdf/2401.01234v2"
    assert paper.published == recent.strftime("%Y-%m-%d")
    assert paper.source == "ArXiv"
    assert paper.summary == "A realistic Atom summary."


def test_arxiv_fetcher_filters_entries_older_than_backfill_limit(monkeypatch):
    fetcher = _arxiv_fetcher(backfill_limit_days=7)
    old = datetime.now() - timedelta(days=30)

    monkeypatch.setattr(
        "src.fetch.arxiv.feedparser.parse",
        lambda _url: SimpleNamespace(
            bozo=False,
            entries=[
                SimpleNamespace(
                    link="https://arxiv.org/abs/2301.00001",
                    title="Old paper",
                    authors=[SimpleNamespace(name="Old Author")],
                    published_parsed=old.timetuple(),
                    summary="Too old for backfill.",
                )
            ],
        ),
    )

    assert fetcher.fetch("old query", max_results=1) == []


def test_arxiv_fetcher_skips_malformed_entry_and_keeps_valid_entry(monkeypatch, caplog):
    fetcher = _arxiv_fetcher(backfill_limit_days=7)
    recent = datetime.now() - timedelta(days=1)

    monkeypatch.setattr(
        "src.fetch.arxiv.feedparser.parse",
        lambda _url: SimpleNamespace(
            bozo=False,
            entries=[
                SimpleNamespace(
                    link="https://arxiv.org/abs/bad-entry",
                    title="Malformed paper",
                    published_parsed=recent.timetuple(),
                    summary="Missing authors should be logged and skipped.",
                ),
                SimpleNamespace(
                    link="https://arxiv.org/abs/2401.99999",
                    title="Valid paper",
                    authors=[SimpleNamespace(name="Valid Author")],
                    published_parsed=recent.timetuple(),
                    summary="Still returned after the malformed entry.",
                ),
            ],
        ),
    )

    with caplog.at_level(logging.ERROR):
        papers = fetcher.fetch("mixed query", max_results=2)

    assert [paper.id for paper in papers] == ["2401.99999"]
    assert "Error parsing ArXiv entry" in caplog.text


def test_openalex_fetcher_normalizes_work_metadata_contract(monkeypatch):
    captured: list[tuple[str, dict, int]] = []

    def fake_get(url: str, params: dict, timeout: int):
        captured.append((url, params, timeout))
        return _Response(
            payload={
                "cited_by_count": 42,
                "publication_year": 2024,
                "open_access": {"is_oa": True},
                "primary_location": {
                    "source": {
                        "display_name": "Journal of Contract Tests",
                        "issn_l": "1234-5678",
                    }
                },
            }
        )

    monkeypatch.setattr("src.fetch.openalex.requests.get", fake_get)

    metadata = OpenAlexFetcher(email="ops@example.org").fetch_metadata("https://doi.org/10.1000/openalex.contract")

    assert captured == [
        (
            "https://api.openalex.org/works/doi:10.1000/openalex.contract",
            {"mailto": "ops@example.org"},
            10,
        )
    ]
    assert metadata == {
        "citation_count": 42,
        "publication_year": 2024,
        "venue_name": "Journal of Contract Tests",
        "is_oa": True,
        "journal_issn_l": "1234-5678",
    }


def test_openalex_fetcher_returns_empty_metadata_for_missing_doi_or_404(monkeypatch):
    monkeypatch.setattr("src.fetch.openalex.requests.get", lambda *_args, **_kwargs: _Response(status_code=404))
    fetcher = OpenAlexFetcher()

    assert fetcher.fetch_metadata("") == {}
    assert fetcher.fetch_metadata("10.1000/not-found") == {}


def test_openalex_fetcher_returns_empty_metadata_for_invalid_json(monkeypatch, caplog):
    monkeypatch.setattr(
        "src.fetch.openalex.requests.get",
        lambda *_args, **_kwargs: _Response(json_error=ValueError("not json")),
    )

    with caplog.at_level(logging.WARNING):
        metadata = OpenAlexFetcher().fetch_metadata("doi:10.1000/bad-json")

    assert metadata == {}
    assert "OpenAlex API error for doi:10.1000/bad-json" in caplog.text
