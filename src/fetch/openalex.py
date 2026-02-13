
import requests
import logging
from typing import Dict, Optional, Any
from datetime import datetime
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)

class OpenAlexFetcher:
    """
    OpenAlex API wrapper to fetch bibliometric data.
    """
    BASE_URL = "https://api.openalex.org/works"
    
    def __init__(self, email: Optional[str] = None):
        self.email = email
        
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def fetch_metadata(self, doi: str) -> Dict[str, Any]:
        """
        Fetch metadata for a given DOI.
        Returns a dict with: citation_count, publication_year, venue_name, sjr_proxy, etc.
        """
        if not doi:
            return {}
            
        # Clean DOI
        doi_clean = doi.replace("https://doi.org/", "").strip()
        url = f"{self.BASE_URL}/doi:{doi_clean}"
        
        params = {}
        if self.email:
            params['mailto'] = self.email
            
        try:
            resp = requests.get(url, params=params, timeout=10)
            if resp.status_code == 404:
                logger.debug(f"DOI not found in OpenAlex: {doi}")
                return {}
            resp.raise_for_status()
            data = resp.json()
            
            # Extract relevant fields
            metadata = {
                "citation_count": data.get("cited_by_count", 0),
                "publication_year": data.get("publication_year"),
                "venue_name": None,
                "is_oa": data.get("open_access", {}).get("is_oa", False),
                "journal_issn_l": None
            }
            
            # Venue Info
            if data.get("primary_location") and data["primary_location"].get("source"):
                source = data["primary_location"]["source"]
                metadata["venue_name"] = source.get("display_name")
                metadata["journal_issn_l"] = source.get("issn_l")
                
                # Retrieve impact metrics if available (OpenAlex doesn't give SJR directly, but gives 'cited_by_count' for venue)
                # For now, we rely on the paper's citation count mainly.
            
            return metadata
            
        except Exception as e:
            logger.warning(f"OpenAlex API error for {doi}: {e}")
            return {}

    def fetch_bulk_metadata(self, dois: list[str]) -> Dict[str, Dict]:
        """
        Future optimization: Fetch multiple DOIs in one go (using filter=doi:A|B|C).
        For V1, we stick to sequential fetch with retry for robustness.
        """
        # Placeholder for future optimization
        pass
