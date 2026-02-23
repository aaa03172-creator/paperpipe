from typing import Optional

from src.downloader.providers.base import DownloadCandidate, DownloadProvider, DownloadResult
from src.downloader.providers.arxiv import ArxivProvider
from src.downloader.providers.direct import DirectLinkProvider
from src.downloader.providers.pmc import PmcProvider
from src.downloader.providers.unpaywall import UnpaywallProvider, fetch_unpaywall_candidate
from src.downloader.router import DownloadRouter, download_paper


def _fetch_oa_link(doi: str, email: Optional[str]) -> Optional[str]:
    """Backward-compatible helper used by CLI smoke command."""
    candidate = fetch_unpaywall_candidate(doi=doi, email=email)
    return candidate.url if candidate else None


__all__ = [
    "DownloadCandidate",
    "DownloadProvider",
    "DownloadResult",
    "ArxivProvider",
    "DirectLinkProvider",
    "PmcProvider",
    "UnpaywallProvider",
    "DownloadRouter",
    "download_paper",
    "_fetch_oa_link",
]
