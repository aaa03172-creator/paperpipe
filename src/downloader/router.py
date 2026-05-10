from __future__ import annotations

import logging
import re
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import requests

from src.config import AppConfig
from src.downloader.providers.base import DownloadProvider, DownloadResult
from src.downloader.providers.base import DownloadCandidate
from src.downloader.providers.arxiv import ArxivProvider
from src.downloader.providers.direct import DirectLinkProvider
from src.downloader.providers.pmc import PmcProvider
from src.downloader.providers.unpaywall import UnpaywallProvider
from src.schemas.core import DownloadAttempt, DownloadFailure, Paper

logger = logging.getLogger(__name__)


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
    "arxiv": ProviderHttpPolicy(
        timeout_seconds=20.0,
        headers={"User-Agent": "PaperPipe/1.0 (+arXiv OA)"},
    ),
    "pmc": ProviderHttpPolicy(
        timeout_seconds=20.0,
        headers={"User-Agent": "PaperPipe/1.0 (+PMC OA)"},
    ),
}


def _sanitize_filename(name: str) -> str:
    """Sanitize file names for safe writes."""
    name = re.sub(r'[\\/:*?"<>|]', "_", name)
    return name[:200]


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
            ArxivProvider(),
            PmcProvider(),
            UnpaywallProvider(email=config.system.unpaywall_email),
        ]
        self.max_rate_limit_retries = max(0, max_rate_limit_retries)
        self.rate_limit_backoff_seconds = max(0.0, rate_limit_backoff_seconds)
        self.candidate_cache_ttl_seconds = max(0.0, candidate_cache_ttl_seconds)
        self.candidate_cache_max_entries = max(1, candidate_cache_max_entries)
        self._candidate_cache: dict[str, tuple[float, Optional[DownloadCandidate]]] = {}
        self._provider_policies: dict[str, ProviderHttpPolicy] = {
            name: ProviderHttpPolicy(timeout_seconds=policy.timeout_seconds, headers=dict(policy.headers))
            for name, policy in DEFAULT_PROVIDER_POLICIES.items()
        }
        for name, timeout in (provider_timeouts or {}).items():
            policy = self._provider_policies.setdefault(name, ProviderHttpPolicy())
            policy.timeout_seconds = max(0.1, float(timeout))
        for name, headers in (provider_headers or {}).items():
            policy = self._provider_policies.setdefault(name, ProviderHttpPolicy())
            policy.headers.update({str(k): str(v) for k, v in (headers or {}).items()})

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
        storage_root = getattr(self.config.paths, "pdf_storage_dir", None) or getattr(self.config.paths, "upload_dir", None)
        if not storage_root:
            logger.warning("[%s] No download destination configured, skipping download.", paper.id)
            return DownloadResult(
                success=False,
                final_status=DownloadFailure.TEMP_FAIL,
                message="download_destination_not_configured",
            )

        storage_path = Path(storage_root)
        storage_path.mkdir(parents=True, exist_ok=True)

        filename = _sanitize_filename(paper.id) + ".pdf"
        filepath = storage_path / filename

        if filepath.exists():
            logger.info("[%s] PDF already exists at %s, skipping download.", paper.id, filepath)
            return DownloadResult(success=True, local_pdf_path=filepath, pdf_link=paper.pdf_link)

        upload_dir = getattr(self.config.paths, "upload_dir", None)
        if upload_dir:
            upload_filepath = Path(upload_dir) / filename
            if upload_filepath.exists():
                try:
                    if upload_filepath.resolve() != filepath.resolve():
                        shutil.copy2(upload_filepath, filepath)
                    logger.info("[%s] Reused existing upload PDF at %s", paper.id, upload_filepath)
                    return DownloadResult(success=True, local_pdf_path=filepath, pdf_link=paper.pdf_link)
                except FileNotFoundError:
                    pass

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
        if not self._candidate_cache:
            return
        if self.candidate_cache_ttl_seconds > 0:
            expired_keys = [
                key
                for key, (cached_at, _candidate) in self._candidate_cache.items()
                if now - cached_at > self.candidate_cache_ttl_seconds
            ]
            for key in expired_keys:
                self._candidate_cache.pop(key, None)
        while len(self._candidate_cache) > self.candidate_cache_max_entries:
            oldest_key = min(self._candidate_cache.items(), key=lambda item: item[1][0])[0]
            self._candidate_cache.pop(oldest_key, None)

    def _download_file_with_retries(
        self,
        url: str,
        filepath: Path,
        provider_name: str,
        paper_id: str,
        attempts: list[DownloadAttempt],
    ) -> bool:
        retry_count = 0
        while True:
            try:
                return self._download_file(url, filepath, provider_name=provider_name)
            except requests.exceptions.HTTPError as exc:
                fail_status = self._map_http_failure(exc)
                can_retry = fail_status == DownloadFailure.RATE_LIMIT and retry_count < self.max_rate_limit_retries
                attempts.append(
                    DownloadAttempt(
                        provider=provider_name,
                        status=fail_status,
                        candidate_url=url,
                        message=str(exc),
                        retry_no=retry_count,
                        will_retry=can_retry,
                    )
                )
                if can_retry:
                    delay_seconds = self.rate_limit_backoff_seconds * (2**retry_count)
                    logger.warning(
                        "[%s] Rate limited via %s. Retrying in %.2fs (retry %s/%s).",
                        paper_id,
                        provider_name,
                        delay_seconds,
                        retry_count + 1,
                        self.max_rate_limit_retries,
                    )
                    retry_count += 1
                    if delay_seconds > 0:
                        time.sleep(delay_seconds)
                    continue
                raise

    def _map_http_failure(self, error: requests.exceptions.HTTPError) -> DownloadFailure:
        status_code = error.response.status_code if error.response else 0
        if status_code == 429:
            return DownloadFailure.RATE_LIMIT
        if 400 <= status_code < 500:
            return DownloadFailure.PERM_FAIL
        return DownloadFailure.TEMP_FAIL

    def _policy_for_provider(self, provider_name: str) -> ProviderHttpPolicy:
        return self._provider_policies.get(provider_name, ProviderHttpPolicy())

    def _download_file(self, url: str, filepath: Path, provider_name: str = "unknown") -> bool:
        """Download URL in streaming mode and validate content type + PDF header."""
        policy = self._policy_for_provider(provider_name)
        response = requests.get(
            url,
            stream=True,
            timeout=policy.timeout_seconds,
            headers=policy.headers,
        )
        response.raise_for_status()

        content_type = response.headers.get("Content-Type", "").lower()
        if "text/html" in content_type:
            logger.warning("Downloaded content is HTML, not PDF (likely paywall/login page): %s", url)
            return False

        with filepath.open("wb") as file_handle:
            for chunk in response.iter_content(chunk_size=8192):
                file_handle.write(chunk)

        with filepath.open("rb") as file_handle:
            header = file_handle.read(4)
            if header != b"%PDF":
                logger.warning("File magic bytes indicate invalid PDF (%s) at %s", header, filepath)
                filepath.unlink(missing_ok=True)
                return False

        self._copy_to_upload_dir(filepath)

        return True

    def _copy_to_upload_dir(self, filepath: Path) -> None:
        upload_dir = getattr(self.config.paths, "upload_dir", None)
        if not upload_dir:
            return

        upload_path = Path(upload_dir)
        upload_path.mkdir(parents=True, exist_ok=True)
        destination = upload_path / filepath.name
        if destination.resolve() == filepath.resolve():
            return
        if destination.exists():
            return
        shutil.copy2(filepath, destination)


def download_paper(paper: Paper, config: AppConfig) -> Paper:
    """Compatibility adapter that executes the router."""
    return DownloadRouter(config).execute(paper)
