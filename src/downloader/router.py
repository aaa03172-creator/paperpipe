from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Optional

import requests

from src.config import AppConfig
from src.downloader.providers.base import DownloadProvider, DownloadResult
from src.downloader.providers.base import DownloadCandidate
from src.downloader.providers.direct import DirectLinkProvider
from src.downloader.router_io import download_pdf_file, download_with_rate_limit_retries
from src.downloader.providers.unpaywall import UnpaywallProvider
from src.downloader.router_support import (
    ProviderHttpPolicy,
    build_provider_policies,
    map_http_failure,
    prune_candidate_cache,
    sanitize_filename,
)
from src.schemas.core import DownloadAttempt, DownloadFailure, Paper

logger = logging.getLogger(__name__)


def _sanitize_filename(name: str) -> str:
    return sanitize_filename(name)


class DownloadRouter:
    """Routes OA download attempts across providers with fail-safe semantics."""

    def __init__(
        self,
        config: AppConfig,
        providers: Optional[list[DownloadProvider]] = None,
        max_rate_limit_retries: int = 2,
        rate_limit_backoff_seconds: float = 1.0,
        provider_timeouts: Optional[dict[str, float]] = None,
        provider_headers: Optional[dict[str, dict[str, str]]] = None,
        candidate_cache_ttl_seconds: float = 600.0,
        candidate_cache_max_entries: int = 1024,
    ):
        self.config = config
        self.providers: list[DownloadProvider] = providers or [
            DirectLinkProvider(),
            UnpaywallProvider(email=config.system.unpaywall_email),
        ]
        self.max_rate_limit_retries = max(0, max_rate_limit_retries)
        self.rate_limit_backoff_seconds = max(0.0, rate_limit_backoff_seconds)
        self.candidate_cache_ttl_seconds = max(0.0, candidate_cache_ttl_seconds)
        self.candidate_cache_max_entries = max(1, candidate_cache_max_entries)
        self._candidate_cache: dict[str, tuple[float, Optional[DownloadCandidate]]] = {}
        self._provider_policies = build_provider_policies(
            provider_timeouts=provider_timeouts,
            provider_headers=provider_headers,
        )

    def execute(self, paper: Paper) -> Paper:
        """Backward-compatible API that updates and returns Paper."""
        result = self.execute_with_result(paper)
        paper.download_attempts.extend(result.attempts)
        if result.local_pdf_path:
            paper.local_pdf_path = result.local_pdf_path
        if result.pdf_link and not paper.pdf_link:
            paper.pdf_link = result.pdf_link
        return paper

    def execute_with_result(self, paper: Paper) -> DownloadResult:
        upload_dir = self.config.paths.upload_dir
        if not upload_dir:
            logger.warning("[%s] Upload directory not configured, skipping download.", paper.id)
            return DownloadResult(success=False, final_status=DownloadFailure.TEMP_FAIL, message="upload_dir_not_configured")

        upload_path = Path(upload_dir)
        upload_path.mkdir(parents=True, exist_ok=True)

        filename = _sanitize_filename(paper.id) + ".pdf"
        filepath = upload_path / filename

        if filepath.exists():
            logger.info("[%s] PDF already exists at %s, skipping download.", paper.id, filepath)
            return DownloadResult(success=True, local_pdf_path=filepath, pdf_link=paper.pdf_link)

        attempts: list[DownloadAttempt] = []

        for provider in self.providers:
            provider_name = provider.provider_name
            try:
                candidate = self._resolve_candidate_with_cache(provider, paper)
            except Exception as exc:
                logger.error("[%s] Unexpected error in provider %s: %s", paper.id, provider_name, exc)
                attempts.append(
                    DownloadAttempt(
                        provider=provider_name,
                        status=DownloadFailure.TEMP_FAIL,
                        message=f"Provider exception: {exc}",
                    )
                )
                continue

            if not candidate:
                attempts.append(
                    DownloadAttempt(
                        provider=provider_name,
                        status=DownloadFailure.NO_LINK,
                        message="Provider returned no candidate.",
                    )
                )
                continue

            if not candidate.is_oa:
                attempts.append(
                    DownloadAttempt(
                        provider=provider_name,
                        status=DownloadFailure.POLICY_BLOCK,
                        candidate_url=candidate.url,
                        message="OA-only policy blocked non-OA candidate.",
                    )
                )
                continue

            logger.info("[%s] %s resolved candidate: %s", paper.id, provider_name, candidate.url)

            try:
                is_valid_pdf = self._download_file_with_retries(
                    url=candidate.url,
                    filepath=filepath,
                    provider_name=provider_name,
                    paper_id=paper.id,
                    attempts=attempts,
                )
                if not is_valid_pdf:
                    attempts.append(
                        DownloadAttempt(
                            provider=provider_name,
                            status=DownloadFailure.BAD_CONTENT,
                            candidate_url=candidate.url,
                            message="Downloaded file is not a valid PDF.",
                        )
                    )
                    continue

                logger.info("[%s] Successfully downloaded PDF via %s", paper.id, provider_name)
                return DownloadResult(
                    success=True,
                    local_pdf_path=filepath,
                    pdf_link=candidate.url,
                    attempts=attempts,
                )
            except requests.exceptions.HTTPError as exc:
                logger.warning("[%s] HTTP Error during download via %s: %s", paper.id, provider_name, exc)
            except requests.exceptions.RequestException as exc:
                logger.warning("[%s] Network Error during download via %s: %s", paper.id, provider_name, exc)
                attempts.append(
                    DownloadAttempt(
                        provider=provider_name,
                        status=DownloadFailure.TEMP_FAIL,
                        candidate_url=candidate.url,
                        message=str(exc),
                    )
                )

        logger.warning("[%s] All providers exhausted. Failed to download PDF.", paper.id)
        final_status = attempts[-1].status if attempts else DownloadFailure.NO_LINK
        return DownloadResult(
            success=False,
            attempts=attempts,
            final_status=final_status,
            message="providers_exhausted",
        )

    def _resolve_candidate_with_cache(self, provider: DownloadProvider, paper: Paper) -> Optional[DownloadCandidate]:
        cache_key = (
            f"{provider.provider_name}|{paper.id}|{paper.doi or ''}|{paper.pdf_link or ''}|{paper.link or ''}"
        )
        now = time.time()
        self._prune_candidate_cache(now)
        cached = self._candidate_cache.get(cache_key)
        if cached is not None:
            _cached_at, cached_candidate = cached
            return cached_candidate
        candidate = provider.resolve_pdf(paper)
        self._candidate_cache[cache_key] = (now, candidate)
        self._prune_candidate_cache(now)
        return candidate

    def _prune_candidate_cache(self, now: float) -> None:
        prune_candidate_cache(
            candidate_cache=self._candidate_cache,
            now=now,
            ttl_seconds=self.candidate_cache_ttl_seconds,
            max_entries=self.candidate_cache_max_entries,
        )

    def _download_file_with_retries(
        self,
        url: str,
        filepath: Path,
        provider_name: str,
        paper_id: str,
        attempts: list[DownloadAttempt],
    ) -> bool:
        return download_with_rate_limit_retries(
            url=url,
            filepath=filepath,
            provider_name=provider_name,
            paper_id=paper_id,
            attempts=attempts,
            max_rate_limit_retries=self.max_rate_limit_retries,
            rate_limit_backoff_seconds=self.rate_limit_backoff_seconds,
            download_file_fn=lambda u, f, p: self._download_file(u, f, provider_name=p),
            map_http_failure_fn=self._map_http_failure,
            logger=logger,
            sleep_fn=time.sleep,
        )

    def _map_http_failure(self, error: requests.exceptions.HTTPError) -> DownloadFailure:
        return map_http_failure(error)

    def _policy_for_provider(self, provider_name: str) -> ProviderHttpPolicy:
        return self._provider_policies.get(provider_name, ProviderHttpPolicy())

    def _download_file(self, url: str, filepath: Path, provider_name: str = "unknown") -> bool:
        policy = self._policy_for_provider(provider_name)
        return download_pdf_file(url=url, filepath=filepath, policy=policy, logger=logger)


def download_paper(paper: Paper, config: AppConfig) -> Paper:
    """Compatibility adapter that executes the router."""
    return DownloadRouter(config).execute(paper)
