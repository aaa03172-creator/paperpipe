
import logging
import math
from datetime import datetime
from typing import List, Dict
from src.schemas import Paper
from src.config import AppConfig
from src.fetch.openalex import OpenAlexFetcher

logger = logging.getLogger(__name__)

class BibliometricScorer:
    def __init__(self, config: AppConfig):
        self.config = config
        self.fetcher = OpenAlexFetcher(email=config.system.unpaywall_email)
        self.weights = config.ranking.bibliometrics
        self.current_year = datetime.now().year

    def calculate_scores(self, papers: List[Paper]) -> List[Paper]:
        """
        Fetch metrics and update paper scores in-place.
        Returns the list sorted by manual_rank_score descending.
        """
        if not self.weights.enabled:
            return papers

        logger.info(f"📊 Calculating Bibliometric Scores for {len(papers)} papers...")
        
        for paper in papers:
            # 1. Fetch Metadata (Skip if no DOI)
            if not paper.doi:
                continue
                
            meta = self.fetcher.fetch_metadata(paper.doi)
            if not meta:
                continue
            
            # Update fields
            paper.citation_count = meta.get("citation_count", 0)
            pub_year = meta.get("publication_year", self.current_year)
            
            # 2. Calculate Novelty Score (0.0 - 1.0)
            # Decay: 1.0 (0-1 yr), 0.8 (2-3 yr), 0.5 (>3 yr)
            age = max(0, self.current_year - pub_year)
            novelty_score = 1.0 / (1.0 + (0.5 * age)) # Hyperbolic decay
            
            # 3. Calculate Impact Score (Velocity)
            # Velocity = Citations / Age (min 1 year to avoid div/0)
            eff_age = max(1, age)
            velocity = paper.citation_count / eff_age
            # Log normalize: log10(v+1) -> 0 (v=0), 1 (v=9), 2 (v=99)
            # Cap at 100 cites/year => score 1.0
            impact_raw = math.log10(velocity + 1)
            impact_score = min(1.0, impact_raw / 2.0) # Normalize to ~0-1 range (assuming 100 cites/yr is huge)
            
            # 4. Venue Score (Placeholder)
            # Todo: Map ISSN to SJR list if available
            venue_score = 0.5 
            
            # 5. Weighted Sum
            # w_n * N + w_i * I + w_v * V
            final_score = (
                (self.weights.weights["novelty"] * novelty_score) + 
                (self.weights.weights["impact"] * impact_score) +
                (self.weights.weights["venue"] * venue_score)
            )
            
            paper.manual_rank_score = round(final_score, 3)
            logger.debug(f"   - {paper.title[:30]}... | Citations: {paper.citation_count} (V={velocity:.1f}) | Score: {final_score:.3f}")

        # Sort descending
        papers.sort(key=lambda p: p.manual_rank_score or 0.0, reverse=True)
        return papers
