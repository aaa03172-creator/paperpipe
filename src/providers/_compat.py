from __future__ import annotations

import warnings

_WARNED = False


def warn_legacy_provider_import() -> None:
    global _WARNED
    if _WARNED:
        return
    _WARNED = True
    warnings.warn(
        "src.providers is deprecated; import downloader providers from "
        "src.downloader.providers instead.",
        DeprecationWarning,
        stacklevel=3,
    )
