from src.downloader.providers.base import DownloadCandidate, DownloadProvider, DownloadResult
from src.downloader.providers.direct import DirectLinkProvider
from src.downloader.providers.unpaywall import UnpaywallProvider

__all__ = [
    "DownloadCandidate",
    "DownloadProvider",
    "DownloadResult",
    "DirectLinkProvider",
    "UnpaywallProvider",
]
