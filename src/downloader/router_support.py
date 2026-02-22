from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

import requests

from src.downloader.providers.base import DownloadCandidate
from src.schemas.core import DownloadFailure


@dataclass
class ProviderHttpPolicy:
    timeout_seconds: float = 30.0
    headers: dict[str, str] = field(default_factory=dict)


DEFAULT_PROVIDER_POLICIES: dict[str, ProviderHttpPolicy] = {
    "direct_link": ProviderHttpPolicy(
        timeout_seconds=20.0,
        headers={"User-Agent": "PaperPipe/1.0 (+OA Downloader)"},
    ),
    "unpaywall": ProviderHttpPolicy(
        timeout_seconds=25.0,
        headers={"User-Agent": "PaperPipe/1.0 (+Unpaywall OA)"},
    ),
}


def sanitize_filename(name: str) -> str:
    """Sanitize file names for safe writes."""
    name = re.sub(r'[\\/:*?"<>|]', "_", name)
    return name[:200]


def build_provider_policies(
    provider_timeouts: Optional[dict[str, float]],
    provider_headers: Optional[dict[str, dict[str, str]]],
) -> dict[str, ProviderHttpPolicy]:
    policies: dict[str, ProviderHttpPolicy] = {
        name: ProviderHttpPolicy(timeout_seconds=policy.timeout_seconds, headers=dict(policy.headers))
        for name, policy in DEFAULT_PROVIDER_POLICIES.items()
    }
    for name, timeout in (provider_timeouts or {}).items():
        policy = policies.setdefault(name, ProviderHttpPolicy())
        policy.timeout_seconds = max(0.1, float(timeout))
    for name, headers in (provider_headers or {}).items():
        policy = policies.setdefault(name, ProviderHttpPolicy())
        policy.headers.update({str(k): str(v) for k, v in (headers or {}).items()})
    return policies


def map_http_failure(error: requests.exceptions.HTTPError) -> DownloadFailure:
    status_code = error.response.status_code if error.response else 0
    if status_code == 429:
        return DownloadFailure.RATE_LIMIT
    if 400 <= status_code < 500:
        return DownloadFailure.PERM_FAIL
    return DownloadFailure.TEMP_FAIL


def prune_candidate_cache(
    candidate_cache: dict[str, tuple[float, Optional[DownloadCandidate]]],
    now: float,
    ttl_seconds: float,
    max_entries: int,
) -> None:
    if not candidate_cache:
        return
    if ttl_seconds > 0:
        expired_keys = [
            key
            for key, (cached_at, _candidate) in candidate_cache.items()
            if now - cached_at > ttl_seconds
        ]
        for key in expired_keys:
            candidate_cache.pop(key, None)
    while len(candidate_cache) > max_entries:
        oldest_key = min(candidate_cache.items(), key=lambda item: item[1][0])[0]
        candidate_cache.pop(oldest_key, None)
