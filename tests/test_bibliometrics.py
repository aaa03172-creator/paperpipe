
import logging
from src.schemas import Paper
from src.ranking import BibliometricScorer
from src.fetch.openalex import OpenAlexFetcher

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_openalex_fetch():
    print("\n--- Test 1: OpenAlex Fetch (Network) ---")
    # This test actually hits the API. If it fails due to network, we might want to skip it, 
    # but for verification it's good to know.
    fetcher = OpenAlexFetcher(email="test@example.com")
    
    # Use a known high-impact paper DOI
    doi_high = "10.1126/science.1072994" # Science, 2002
    
    try:
        meta = fetcher.fetch_metadata(doi_high)
        print(f"DOI: {doi_high}")
        print(f"Metadata: {meta}")
        
        if meta.get("citation_count", 0) > 1000:
            print("✅ High impact paper has many citations.")
        else:
            print("❌ Citations count seems low or fetch failed.")
    except Exception as e:
        print(f"⚠️ Network test failed: {e}")

def test_ranking_logic():
    print("\n--- Test 2: Ranking Logic (Mocked) ---")
    
    # Define Mock Config locally to ensure test isolation
    class MockWeights:
        enabled = True
        weights = {"novelty": 0.4, "impact": 0.4, "venue": 0.2}

    class MockRanking:
        bibliometrics = MockWeights()

    class MockConfig:
        system = type('obj', (object,), {'unpaywall_email': 'test@example.com'})
        ranking = MockRanking()

    # Initialize Scorer with Mock Config
    scorer = BibliometricScorer(MockConfig())

    # --- MOCK FETCHER ---
    def mock_fetch(doi):
        if doi == "doi_high":
            # High impact: 5 years old, 5000 cites -> 1000/yr
            return {"citation_count": 5000, "publication_year": 2020, "venue_name": "Nature"}
        elif doi == "doi_new":
             # New: 0 years old (2024), 5 cites -> High potential relevance
            return {"citation_count": 5, "publication_year": 2024, "venue_name": "Cell"}
        elif doi == "doi_low":
            # Low: 14 years old, 10 cites -> <1/yr
            return {"citation_count": 10, "publication_year": 2010, "venue_name": "Unknown"}
        return {}
    
    # Inject Mock Fetcher
    scorer.fetcher.fetch_metadata = mock_fetch

    # Mock Papers
    p_high = Paper(id="p1", title="High Impact Paper", authors=[], published="2020-01-01", source="Journal A", summary="", link="", doi="doi_high")
    p_new = Paper(id="p2", title="Brand New Paper", authors=[], published="2024-01-01", source="Journal B", summary="", link="", doi="doi_new")
    p_low = Paper(id="p3", title="Low Impact Old Paper", authors=[], published="2010-01-01", source="Journal C", summary="", link="", doi="doi_low")
    
    papers = [p_low, p_new, p_high] 
    print(f"Initial Order: {[p.title for p in papers]}")
    
    # Run Ranking
    ranked = scorer.calculate_scores(papers)
    
    print("\nRanking Results:")
    for p in ranked:
        print(f"Title: {p.title} | Score: {p.manual_rank_score} | Cites: {p.citation_count}")

    # Expected: High Impact should be top.
    if len(ranked) > 0 and ranked[0].title == "High Impact Paper":
        print("✅ High Impact paper is #1.")
    else:
        print(f"❌ Ranking mismatch. #1 is {ranked[0].title if ranked else 'None'}")

if __name__ == "__main__":
    test_openalex_fetch()
    test_ranking_logic()
