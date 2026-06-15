from src.providers._compat import warn_legacy_provider_import
from src.downloader.providers.arxiv import ArxivProvider

warn_legacy_provider_import()

__all__ = ["ArxivProvider"]
