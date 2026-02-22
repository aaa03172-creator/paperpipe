from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Callable

import requests

from src.downloader.router_support import ProviderHttpPolicy
from src.schemas.core import DownloadAttempt, DownloadFailure


def is_valid_pdf_file(filepath: Path) -> bool:
    """Validate local file via PDF magic bytes."""
    if not filepath.exists() or not filepath.is_file():
        return False
    try:
        with filepath.open("rb") as file_handle:
            return file_handle.read(4) == b"%PDF"
    except OSError:
        return False


def download_pdf_file(
    url: str,
    filepath: Path,
    policy: ProviderHttpPolicy,
    logger: logging.Logger,
) -> bool:
    """Download URL in streaming mode and validate content type + PDF header."""
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

    return True


def download_with_rate_limit_retries(
    *,
    url: str,
    filepath: Path,
    provider_name: str,
    paper_id: str,
    attempts: list[DownloadAttempt],
    max_rate_limit_retries: int,
    rate_limit_backoff_seconds: float,
    download_file_fn: Callable[[str, Path, str], bool],
    map_http_failure_fn: Callable[[requests.exceptions.HTTPError], DownloadFailure],
    logger: logging.Logger,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> bool:
    retry_count = 0
    while True:
        try:
            return download_file_fn(url, filepath, provider_name)
        except requests.exceptions.HTTPError as exc:
            fail_status = map_http_failure_fn(exc)
            can_retry = fail_status == DownloadFailure.RATE_LIMIT and retry_count < max_rate_limit_retries
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
                delay_seconds = rate_limit_backoff_seconds * (2**retry_count)
                logger.warning(
                    "[%s] Rate limited via %s. Retrying in %.2fs (retry %s/%s).",
                    paper_id,
                    provider_name,
                    delay_seconds,
                    retry_count + 1,
                    max_rate_limit_retries,
                )
                retry_count += 1
                if delay_seconds > 0:
                    sleep_fn(delay_seconds)
                continue
            raise
