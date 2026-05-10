from __future__ import annotations

import logging
from typing import Optional

import requests

from src.downloader.providers.base import DownloadCandidate, DownloadProvider
from src.schemas.core import Paper

logger = logging.getLogger(__name__)


def _normalize_doi(raw_doi: str) -> str:
    clean_doi = raw_doi.strip()
    for prefix in ["https://doi.org/", "http://doi.org/", "doi.org/", "doi:", "DOI:"]:
        if clean_doi.lower().startswith(prefix.lower()):
            clean_doi = clean_doi[len(prefix) :]
            break
    return clean_doi


def fetch_unpaywall_candidate(doi: Optional[str], email: Optional[str]) -> Optional[DownloadCandidate]:
    """Fetch a best-effort OA candidate from Unpaywall for a DOI string."""
    if not email:
        logger.debug("Unpaywall email not configured. Skipping Unpaywall check.")
        return None

    if not doi:
        return None

    clean_doi = _normalize_doi(doi)
    if not clean_doi:
        return None

    url = f"https://api.unpaywall.org/v2/{clean_doi}?email={email}"
    try:
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            best_loc = data.get("best_oa_location", {})
            pdf_url = best_loc.get("url_for_pdf")
            if best_loc and pdf_url:
                return DownloadCandidate(
                    url=pdf_url,
                    source_name="unpaywall",
                    is_oa=True,
                    confidence=0.9,
                    license=best_loc.get("license"),
                    meta={"is_best": True, "host_type": best_loc.get("host_type")},
                )
            return None
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
    except requests.exceptions.RequestException as exc:
        logger.warning("Unpaywall query failed for %s: %s", doi, exc)
    except ValueError:
        logger.warning("Unpaywall returned invalid JSON for %s", doi)

    return None


class UnpaywallProvider(DownloadProvider):
    """Queries the Unpaywall API using DOI to locate OA PDFs."""

    def __init__(self, email: Optional[str]):
        self.email = email

    @property
    def provider_name(self) -> str:
        return "unpaywall"

    def resolve_pdf(self, paper: Paper) -> Optional[DownloadCandidate]:
        doi = paper.doi or paper.id
        candidate = fetch_unpaywall_candidate(doi=doi, email=self.email)
        if candidate:
            candidate.source_name = self.provider_name
        return candidate
