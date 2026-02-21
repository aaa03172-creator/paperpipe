from src.downloader.providers.base import DownloadCandidate, DownloadProvider, DownloadResult
from src.downloader.providers.arxiv import ArxivProvider
from src.downloader.providers.direct import DirectLinkProvider
from src.downloader.providers.pmc import PmcProvider
from src.downloader.providers.unpaywall import UnpaywallProvider

__all__ = [
    "DownloadCandidate",
    "DownloadProvider",
    "DownloadResult",
    "ArxivProvider",
    "DirectLinkProvider",
    "PmcProvider",
    "UnpaywallProvider",
]
