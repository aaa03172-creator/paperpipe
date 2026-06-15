"""Deprecated compatibility wrappers for legacy fetcher imports.

New runtime code should use `src.fetch.get_fetchers` or the concrete fetchers
under `src.fetch.*`. This module remains only so older operator scripts do not
break while sharing the canonical PubMed implementation.
"""

from __future__ import annotations

import warnings
from typing import List

from src.fetch.pubmed import PubMedFetcher
from src.schemas import Paper


def _warn_legacy_fetchers() -> None:
    warnings.warn(
        "src.fetchers is deprecated; use src.fetch.pubmed.PubMedFetcher or src.fetch.get_fetchers.",
        DeprecationWarning,
        stacklevel=2,
    )


def _pubmed_fetcher() -> PubMedFetcher:
    return PubMedFetcher(config=None)  # type: ignore[arg-type]


def _esearch_pubmed(term: str, max_results: int) -> List[str]:
    """Compatibility wrapper around `PubMedFetcher._esearch`."""
    _warn_legacy_fetchers()
    return _pubmed_fetcher()._esearch(term, max_results)


def _efetch_pubmed(ids: List[str]) -> str:
    """Compatibility wrapper around `PubMedFetcher._efetch`."""
    _warn_legacy_fetchers()
    return _pubmed_fetcher()._efetch(ids)


def fetch_pubmed(keywords: List[str], max_results: int = 5) -> List[Paper]:
    """Compatibility wrapper around `PubMedFetcher.fetch`."""
    _warn_legacy_fetchers()
    term = " OR ".join(keywords)
    return _pubmed_fetcher().fetch(term, max_results)
