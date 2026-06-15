from __future__ import annotations

import warnings

def warn_legacy_provider_import() -> None:
    warnings.warn(
        "src.providers is deprecated; import downloader providers from "
        "src.downloader.providers instead.",
        DeprecationWarning,
        stacklevel=3,
    )
