from src.fetch.openalex import OpenAlexFetcher
from src.ranking import BibliometricScorer
from src.schemas import Paper


class _Response:
    def __init__(self, payload: dict, status_code: int = 200):
        self._payload = payload
        self.status_code = status_code

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


def test_openalex_fetch_metadata_maps_response_contract(monkeypatch):
    captured = {}

    def fake_get(url, params, timeout):
        captured.update({"url": url, "params": params, "timeout": timeout})
        return _Response(
            {
                "cited_by_count": 1500,
                "publication_year": 2002,
                "open_access": {"is_oa": True},
                "primary_location": {
                    "source": {
                        "display_name": "Science",
                        "issn_l": "0036-8075",
                    }
                },
            }
        )

    monkeypatch.setattr("src.fetch.openalex.requests.get", fake_get)

    meta = OpenAlexFetcher(email="test@example.com").fetch_metadata("https://doi.org/10.1126/science.1072994")

    assert captured == {
        "url": "https://api.openalex.org/works/doi:10.1126/science.1072994",
        "params": {"mailto": "test@example.com"},
        "timeout": 10,
    }
    assert meta == {
        "citation_count": 1500,
        "publication_year": 2002,
        "venue_name": "Science",
        "is_oa": True,
        "journal_issn_l": "0036-8075",
    }


def test_bibliometric_scorer_ranks_by_deterministic_metadata():
    class MockWeights:
        enabled = True
        weights = {"novelty": 0.4, "impact": 0.4, "venue": 0.2}

    class MockRanking:
        bibliometrics = MockWeights()

    class MockConfig:
        system = type("obj", (object,), {"unpaywall_email": "test@example.com"})
        ranking = MockRanking()

    scorer = BibliometricScorer(MockConfig())
    scorer.current_year = 2026

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
    p_without_doi = Paper(
        id="p4",
        title="No DOI Paper",
        authors=[],
        published="2024-01-01",
        source="Journal D",
        summary="",
        link="",
    )

    ranked = scorer.calculate_scores([p_low, p_without_doi, p_new, p_high])

    assert [paper.title for paper in ranked] == [
        "High Impact Paper",
        "Brand New Paper",
        "Low Impact Old Paper",
        "No DOI Paper",
    ]
    assert p_high.citation_count == 5000
    assert p_high.manual_rank_score == 0.6
    assert p_new.citation_count == 5
    assert p_new.manual_rank_score == 0.409
    assert p_low.citation_count == 10
    assert p_low.manual_rank_score == 0.187
    assert p_without_doi.citation_count is None
    assert p_without_doi.manual_rank_score is None
