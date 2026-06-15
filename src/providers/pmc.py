from src.providers._compat import warn_legacy_provider_import
from src.downloader.providers.pmc import PmcProvider

warn_legacy_provider_import()

__all__ = ["PmcProvider"]
