
import requests
import logging
from typing import Dict, Optional, Any, List
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

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def fetch_work(self, identifier: str) -> Dict[str, Any]:
        """
        Fetch a single OpenAlex work by DOI/OpenAlex ID.
        """
        if not identifier:
            return {}

        normalized = identifier.strip()
        if normalized.startswith("https://doi.org/"):
            normalized = normalized.replace("https://doi.org/", "", 1)

        if normalized.lower().startswith("doi:"):
            target = normalized
        elif normalized.upper().startswith("W"):
            target = normalized
        elif "/W" in normalized and "openalex.org" in normalized:
            target = normalized.rstrip("/").split("/")[-1]
        else:
            target = f"doi:{normalized}"

        url = f"{self.BASE_URL}/{target}"
        params: Dict[str, str] = {}
        if self.email:
            params["mailto"] = self.email

        try:
            resp = requests.get(url, params=params, timeout=10)
            if resp.status_code == 404:
                logger.debug("OpenAlex work not found: %s", identifier)
                return {}
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:
            logger.warning("OpenAlex work fetch error for %s: %s", identifier, exc)
            return {}

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def fetch_related_works(self, seed: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Fetch related works from both backward references and forward citations.
        Returns normalized candidate dictionaries.
        """
        if not seed:
            return []

        seed_work = self.fetch_work(seed)
        if not seed_work:
            return []

        per_direction = max(1, limit // 2)
        params: Dict[str, Any] = {"per-page": per_direction}
        if self.email:
            params["mailto"] = self.email

        candidates: List[Dict[str, Any]] = []

        # Backward expansion (referenced works IDs).
        for wid in (seed_work.get("referenced_works") or [])[:per_direction]:
            work = self.fetch_work(str(wid))
            if work:
                candidates.append(self._normalize_related_work(work, relation="referenced"))

        # Forward expansion (works that cite seed).
        cited_by_api_url = seed_work.get("cited_by_api_url")
        if cited_by_api_url:
            try:
                resp = requests.get(cited_by_api_url, params=params, timeout=10)
                resp.raise_for_status()
                payload = resp.json()
                for work in (payload.get("results") or [])[:per_direction]:
                    candidates.append(self._normalize_related_work(work, relation="cited_by"))
            except Exception as exc:
                logger.warning("OpenAlex cited_by fetch error for %s: %s", seed, exc)

        dedup: Dict[str, Dict[str, Any]] = {}
        for item in candidates:
            key = (
                str(item.get("doi") or "").lower().strip()
                or str(item.get("openalex_id") or "").strip()
                or str(item.get("title") or "").lower().strip()
            )
            if not key:
                continue
            if key in dedup:
                if dedup[key].get("relation") != "referenced":
                    dedup[key]["relation"] = item.get("relation", dedup[key].get("relation"))
                continue
            dedup[key] = item

        results = list(dedup.values())
        results.sort(key=lambda x: int(x.get("cited_by_count") or 0), reverse=True)
        return results[:limit]

    def _normalize_related_work(self, work: Dict[str, Any], relation: str) -> Dict[str, Any]:
        source = ((work.get("primary_location") or {}).get("source") or {})
        doi = str(work.get("doi") or "").strip()
        if doi.startswith("https://doi.org/"):
            doi = doi.replace("https://doi.org/", "", 1)
        return {
            "openalex_id": work.get("id"),
            "doi": doi or None,
            "title": work.get("display_name") or "Untitled",
            "year": work.get("publication_year"),
            "venue": source.get("display_name"),
            "cited_by_count": int(work.get("cited_by_count") or 0),
            "is_oa": bool((work.get("open_access") or {}).get("is_oa")),
            "relation": relation,
            "source_url": work.get("id"),
        }
