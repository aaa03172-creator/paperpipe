from __future__ import annotations

import importlib
import sys
import warnings


def _forget_legacy_provider_modules() -> None:
    for name in list(sys.modules):
        if name == "src.providers" or name.startswith("src.providers."):
            sys.modules.pop(name, None)


def test_legacy_provider_package_reexports_with_deprecation_warning() -> None:
    _forget_legacy_provider_modules()

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", DeprecationWarning)
        module = importlib.import_module("src.providers")

    messages = [str(item.message) for item in caught if issubclass(item.category, DeprecationWarning)]
    assert any("src.providers is deprecated" in message for message in messages)
    assert module.BaseDownloader is module.DownloadProvider


def test_legacy_provider_unpaywall_preserves_requests_patch_surface() -> None:
    _forget_legacy_provider_modules()

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", DeprecationWarning)
        module = importlib.import_module("src.providers.unpaywall")

    from src.downloader.providers.unpaywall import UnpaywallProvider

    messages = [str(item.message) for item in caught if issubclass(item.category, DeprecationWarning)]
    assert any("src.providers is deprecated" in message for message in messages)
    assert module.UnpaywallProvider is UnpaywallProvider
    assert hasattr(module, "requests")
