from __future__ import annotations

from dataclasses import dataclass

from src.fetch.openalex import OpenAlexFetcher
from src.ranking import BibliometricScorer
from src.schemas import Paper


@dataclass
class _MockResponse:
    status_code: int
    payload: dict

    def raise_for_status(self) -> None:
        if self.status_code >= 400 and self.status_code != 404:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self) -> dict:
        return self.payload


def test_openalex_fetch_metadata_parses_expected_fields(monkeypatch):
    fetcher = OpenAlexFetcher(email="test@example.com")

    def _fake_get(url, params, timeout):  # noqa: ARG001
        assert "doi:10.1126/science.1072994" in url
        assert params == {"mailto": "test@example.com"}
        return _MockResponse(
            status_code=200,
            payload={
                "cited_by_count": 4321,
                "publication_year": 2002,
                "open_access": {"is_oa": True},
                "primary_location": {
                    "source": {"display_name": "Science", "issn_l": "0036-8075"}
                },
            },
        )

    monkeypatch.setattr("src.fetch.openalex.requests.get", _fake_get)

    meta = fetcher.fetch_metadata("10.1126/science.1072994")
    assert meta["citation_count"] == 4321
    assert meta["publication_year"] == 2002
    assert meta["is_oa"] is True
    assert meta["venue_name"] == "Science"
    assert meta["journal_issn_l"] == "0036-8075"


def test_openalex_fetch_metadata_returns_empty_for_404(monkeypatch):
    fetcher = OpenAlexFetcher(email="test@example.com")

    def _fake_get(url, params, timeout):  # noqa: ARG001
        return _MockResponse(status_code=404, payload={})

    monkeypatch.setattr("src.fetch.openalex.requests.get", _fake_get)

    assert fetcher.fetch_metadata("10.0000/not-found") == {}


def test_ranking_logic_orders_by_manual_rank_score():
    class MockWeights:
        enabled = True
        weights = {"novelty": 0.4, "impact": 0.4, "venue": 0.2}

    class MockRanking:
        bibliometrics = MockWeights()

    class MockConfig:
        system = type("obj", (object,), {"unpaywall_email": "test@example.com"})
        ranking = MockRanking()

    scorer = BibliometricScorer(MockConfig())

    def mock_fetch(doi):
        if doi == "doi_high":
            return {"citation_count": 5000, "publication_year": 2020, "venue_name": "Nature"}
        if doi == "doi_new":
            return {"citation_count": 5, "publication_year": 2024, "venue_name": "Cell"}
        if doi == "doi_low":
            return {"citation_count": 10, "publication_year": 2010, "venue_name": "Unknown"}
        return {}

    scorer.fetcher.fetch_metadata = mock_fetch

    p_high = Paper(
        id="p1",
        title="High Impact Paper",
        authors=[],
        published="2020-01-01",
        source="Journal A",
        summary="",
        link="",
        doi="doi_high",
    )
    p_new = Paper(
        id="p2",
        title="Brand New Paper",
        authors=[],
        published="2024-01-01",
        source="Journal B",
        summary="",
        link="",
        doi="doi_new",
    )
    p_low = Paper(
        id="p3",
        title="Low Impact Old Paper",
        authors=[],
        published="2010-01-01",
        source="Journal C",
        summary="",
        link="",
        doi="doi_low",
    )

    ranked = scorer.calculate_scores([p_low, p_new, p_high])

    assert len(ranked) == 3
    assert ranked[0].title == "High Impact Paper"
    assert ranked[0].manual_rank_score is not None
