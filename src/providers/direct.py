from src.providers._compat import warn_legacy_provider_import
from src.downloader.providers.direct import DirectLinkProvider

warn_legacy_provider_import()

__all__ = ["DirectLinkProvider"]
