from src.providers._compat import warn_legacy_provider_import

warn_legacy_provider_import()

from src.providers.base import BaseDownloader, DownloadProvider
from src.providers.arxiv import ArxivProvider
from src.providers.direct import DirectLinkProvider
from src.providers.pmc import PmcProvider
from src.providers.unpaywall import UnpaywallProvider

__all__ = [
    "BaseDownloader",
    "DownloadProvider",
    "ArxivProvider",
    "DirectLinkProvider",
    "PmcProvider",
    "UnpaywallProvider",
]
