from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Optional

import requests

from src.config import AppConfig
from src.downloader.providers.base import DownloadProvider, DownloadResult
from src.downloader.providers.direct import DirectLinkProvider
from src.downloader.providers.unpaywall import UnpaywallProvider
from src.schemas.core import DownloadAttempt, DownloadFailure, Paper

logger = logging.getLogger(__name__)


def _sanitize_filename(name: str) -> str:
    """Sanitize file names for safe writes."""
    name = re.sub(r'[\\/:*?"<>|]', "_", name)
    return name[:200]


class DownloadRouter:
    """Routes OA download attempts across providers with fail-safe semantics."""

    def __init__(self, config: AppConfig, providers: Optional[list[DownloadProvider]] = None):
        self.config = config
        self.providers: list[DownloadProvider] = providers or [
            DirectLinkProvider(),
            UnpaywallProvider(email=config.system.unpaywall_email),
        ]

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
                candidate = provider.resolve_pdf(paper)
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
                is_valid_pdf = self._download_file(candidate.url, filepath)
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
                fail_status = self._map_http_failure(exc)
                logger.warning("[%s] HTTP Error during download via %s: %s", paper.id, provider_name, exc)
                attempts.append(
                    DownloadAttempt(
                        provider=provider_name,
                        status=fail_status,
                        candidate_url=candidate.url,
                        message=str(exc),
                    )
                )
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

    def _map_http_failure(self, error: requests.exceptions.HTTPError) -> DownloadFailure:
        status_code = error.response.status_code if error.response else 0
        if status_code == 429:
            return DownloadFailure.RATE_LIMIT
        if 400 <= status_code < 500:
            return DownloadFailure.PERM_FAIL
        return DownloadFailure.TEMP_FAIL

    def _download_file(self, url: str, filepath: Path) -> bool:
        """Download URL in streaming mode and validate content type + PDF header."""
        response = requests.get(url, stream=True, timeout=30)
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

        return True


def download_paper(paper: Paper, config: AppConfig) -> Paper:
    """Compatibility adapter that executes the router."""
    return DownloadRouter(config).execute(paper)
