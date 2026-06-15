from src.providers._compat import warn_legacy_provider_import
from src.downloader.providers.base import DownloadProvider

warn_legacy_provider_import()

BaseDownloader = DownloadProvider

__all__ = ["DownloadProvider", "BaseDownloader"]
