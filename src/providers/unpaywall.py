import requests

from src.providers._compat import warn_legacy_provider_import
from src.downloader.providers.unpaywall import UnpaywallProvider

warn_legacy_provider_import()

__all__ = ["UnpaywallProvider", "requests"]
