from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import requests

from src.config import AppConfig, PathsConfig, SystemConfig
from src.downloader import ArxivProvider, DownloadRouter, DirectLinkProvider, PmcProvider, UnpaywallProvider
from src.downloader.providers.base import DownloadCandidate, DownloadProvider
from src.schemas.core import DownloadFailure, Paper


@pytest.fixture
def mock_config(tmp_path):
    return AppConfig(
        system=SystemConfig(unpaywall_email="test@example.com"),
        paths=PathsConfig(
            zotero_base_dir=tmp_path,
            obsidian_vault=tmp_path,
            upload_dir=tmp_path / "uploads",
        ),
        search={"slots": {}},
        llm={"features": {"trial_extraction": {}, "slot_classification": {}, "one_liner": {}}},
    )


@pytest.fixture
def dummy_paper():
    return Paper(
        id="test-paper-123",
        title="Test Paper",
        authors=[],
        published="2024",
        source="pubmed",
        summary="A test paper summary.",
        link="https://pubmed.ncbi.nlm.nih.gov/12345/",
    )


def test_provider_ordering_default(mock_config):
    router = DownloadRouter(mock_config)
    assert [provider.provider_name for provider in router.providers] == ["direct_link", "unpaywall"]


def test_direct_link_provider_resolves():
    provider = DirectLinkProvider()
    paper = Paper(
        id="1",
        title="x",
        authors=[],
        published="2024",
        source="x",
        summary="x",
        link="x",
        pdf_link="http://example.com/test.pdf",
    )
    candidate = provider.resolve_pdf(paper)

    assert candidate is not None
    assert candidate.url == "http://example.com/test.pdf"
    assert candidate.source_name == "direct_link"
    assert candidate.is_oa is True


def test_router_skips_when_pdf_exists(mock_config, dummy_paper):
    router = DownloadRouter(mock_config)
    upload_dir = Path(mock_config.paths.upload_dir)
    upload_dir.mkdir(parents=True)

    fake_pdf = upload_dir / "test-paper-123.pdf"
    fake_pdf.write_text("dummy")

    result = router.execute(dummy_paper)

    assert result.local_pdf_path == fake_pdf
    assert len(result.download_attempts) == 0


@patch("src.downloader.router.DownloadRouter._download_file")
@patch("src.downloader.providers.unpaywall.requests.get")
def test_router_sequence_unpaywall_fallback(mock_get, mock_download, mock_config, dummy_paper):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"best_oa_location": {"url_for_pdf": "http://unpaywall.org/test.pdf"}}
    mock_get.return_value = mock_resp

    mock_download.return_value = True

    router = DownloadRouter(mock_config)
    result = router.execute(dummy_paper)

    assert result.local_pdf_path is not None
    assert result.pdf_link == "http://unpaywall.org/test.pdf"
    assert len(result.download_attempts) == 1
    assert result.download_attempts[0].provider == "direct_link"
    assert result.download_attempts[0].status == DownloadFailure.NO_LINK


@patch("src.downloader.router.DownloadRouter._download_file")
def test_router_bad_content_handling(mock_download, mock_config, dummy_paper):
    dummy_paper.pdf_link = "http://example.com/bad.pdf"
    mock_download.return_value = False

    router = DownloadRouter(mock_config)

    with patch("src.downloader.providers.unpaywall.UnpaywallProvider.resolve_pdf", return_value=None):
        result = router.execute(dummy_paper)

    assert result.local_pdf_path is None
    assert len(result.download_attempts) == 2
    assert result.download_attempts[0].provider == "direct_link"
    assert result.download_attempts[0].status == DownloadFailure.BAD_CONTENT
    assert result.download_attempts[1].provider == "unpaywall"
    assert result.download_attempts[1].status == DownloadFailure.NO_LINK


class _BlockedProvider(DownloadProvider):
    @property
    def provider_name(self) -> str:
        return "blocked_provider"

    def resolve_pdf(self, paper: Paper):
        return DownloadCandidate(
            url="https://example.com/paywalled.pdf",
            source_name=self.provider_name,
            is_oa=False,
            confidence=1.0,
        )


class _CrashProvider(DownloadProvider):
    @property
    def provider_name(self) -> str:
        return "crash_provider"

    def resolve_pdf(self, paper: Paper):
        raise RuntimeError("provider exploded")


class _GoodProvider(DownloadProvider):
    @property
    def provider_name(self) -> str:
        return "good_provider"

    def resolve_pdf(self, paper: Paper):
        return DownloadCandidate(
            url="https://example.com/good.pdf",
            source_name=self.provider_name,
            is_oa=True,
            confidence=1.0,
        )


def test_router_policy_block(mock_config, dummy_paper):
    router = DownloadRouter(mock_config, providers=[_BlockedProvider()])
    result = router.execute(dummy_paper)

    assert result.local_pdf_path is None
    assert len(result.download_attempts) == 1
    assert result.download_attempts[0].status == DownloadFailure.POLICY_BLOCK


@patch("src.downloader.router.DownloadRouter._download_file", return_value=True)
def test_router_fail_safe_continues_after_provider_exception(_mock_download, mock_config, dummy_paper):
    router = DownloadRouter(mock_config, providers=[_CrashProvider(), _GoodProvider()])
    result = router.execute(dummy_paper)

    assert result.local_pdf_path is not None
    assert len(result.download_attempts) == 1
    assert result.download_attempts[0].provider == "crash_provider"
    assert result.download_attempts[0].status == DownloadFailure.TEMP_FAIL


@patch("src.downloader.router.requests.get")
def test_download_file_rejects_html_content_type(mock_get, mock_config, tmp_path):
    response = MagicMock()
    response.headers = {"Content-Type": "text/html; charset=utf-8"}
    response.iter_content.return_value = [b"<html>nope</html>"]
    response.raise_for_status.return_value = None
    mock_get.return_value = response

    router = DownloadRouter(mock_config)
    file_path = tmp_path / "paper.pdf"

    assert router._download_file("https://example.com/not-pdf", file_path) is False
    assert not file_path.exists()


@patch("src.downloader.router.requests.get")
def test_download_file_uses_provider_policy_defaults(mock_get, mock_config, tmp_path):
    response = MagicMock()
    response.headers = {"Content-Type": "application/pdf"}
    response.iter_content.return_value = [b"%PDF-1.4\n"]
    response.raise_for_status.return_value = None
    mock_get.return_value = response

    router = DownloadRouter(mock_config)
    file_path = tmp_path / "paper.pdf"

    assert router._download_file("https://example.com/file.pdf", file_path, provider_name="unpaywall") is True
    mock_get.assert_called_once()
    kwargs = mock_get.call_args.kwargs
    assert kwargs["timeout"] == 25.0
    assert "User-Agent" in kwargs["headers"]


@patch("src.downloader.router.requests.get")
def test_download_file_uses_provider_policy_overrides(mock_get, mock_config, tmp_path):
    response = MagicMock()
    response.headers = {"Content-Type": "application/pdf"}
    response.iter_content.return_value = [b"%PDF-1.7\n"]
    response.raise_for_status.return_value = None
    mock_get.return_value = response

    router = DownloadRouter(
        mock_config,
        provider_timeouts={"custom_provider": 5.0},
        provider_headers={"custom_provider": {"X-Test": "1"}},
    )
    file_path = tmp_path / "paper.pdf"

    assert router._download_file("https://example.com/file.pdf", file_path, provider_name="custom_provider") is True
    kwargs = mock_get.call_args.kwargs
    assert kwargs["timeout"] == 5.0
    assert kwargs["headers"]["X-Test"] == "1"


def test_arxiv_provider_resolves_from_link():
    provider = ArxivProvider()
    paper = Paper(
        id="ignore",
        title="x",
        authors=[],
        published="2024",
        source="ArXiv",
        summary="x",
        link="https://arxiv.org/abs/2401.01234v2",
    )
    candidate = provider.resolve_pdf(paper)
    assert candidate is not None
    assert candidate.url == "https://arxiv.org/pdf/2401.01234v2.pdf"
    assert candidate.is_oa is True


def test_pmc_provider_resolves_from_link():
    provider = PmcProvider()
    paper = Paper(
        id="ignore",
        title="x",
        authors=[],
        published="2024",
        source="PubMed",
        summary="x",
        link="https://pmc.ncbi.nlm.nih.gov/articles/PMC1234567/",
    )
    candidate = provider.resolve_pdf(paper)
    assert candidate is not None
    assert candidate.url == "https://pmc.ncbi.nlm.nih.gov/articles/PMC1234567/pdf/"
    assert candidate.is_oa is True


class _CountedProvider(DownloadProvider):
    def __init__(self):
        self.calls = 0

    @property
    def provider_name(self) -> str:
        return "counted_provider"

    def resolve_pdf(self, paper: Paper):
        self.calls += 1
        return DownloadCandidate(
            url="https://example.com/cached.pdf",
            source_name=self.provider_name,
            is_oa=True,
            confidence=1.0,
        )


@patch("src.downloader.router.DownloadRouter._download_file", return_value=False)
def test_router_candidate_cache_reuses_provider_resolution(_mock_download, mock_config, dummy_paper):
    provider = _CountedProvider()
    router = DownloadRouter(mock_config, providers=[provider])

    router.execute(dummy_paper)
    router.execute(dummy_paper)

    assert provider.calls == 1


@patch("src.downloader.router.DownloadRouter._download_file", return_value=False)
@patch("src.downloader.router.time.time")
def test_router_candidate_cache_ttl_expires(mock_time, _mock_download, mock_config, dummy_paper):
    provider = _CountedProvider()
    router = DownloadRouter(
        mock_config,
        providers=[provider],
        candidate_cache_ttl_seconds=1.0,
        candidate_cache_max_entries=16,
    )
    mock_time.side_effect = [1000.0, 1002.1]

    router.execute(dummy_paper)
    router.execute(dummy_paper)

    assert provider.calls == 2


@patch("src.downloader.router.DownloadRouter._download_file", return_value=False)
def test_router_candidate_cache_size_is_bounded(_mock_download, mock_config, dummy_paper):
    provider = _CountedProvider()
    router = DownloadRouter(
        mock_config,
        providers=[provider],
        candidate_cache_ttl_seconds=3600.0,
        candidate_cache_max_entries=1,
    )
    paper_two = dummy_paper.model_copy(update={"id": "test-paper-456"})

    router.execute(dummy_paper)
    router.execute(paper_two)
    router.execute(dummy_paper)

    assert provider.calls == 3


@patch("src.downloader.router.time.sleep", return_value=None)
@patch("src.downloader.router.DownloadRouter._download_file")
def test_rate_limit_retry_is_bounded(mock_download, _mock_sleep, mock_config, dummy_paper):
    response = MagicMock()
    response.status_code = 429
    http_error = requests.exceptions.HTTPError("429 too many requests", response=response)
    mock_download.side_effect = [http_error, http_error, http_error]

    router = DownloadRouter(
        mock_config,
        providers=[_GoodProvider()],
        max_rate_limit_retries=2,
        rate_limit_backoff_seconds=0,
    )
    result = router.execute(dummy_paper)

    assert result.local_pdf_path is None
    assert len(result.download_attempts) == 3
    assert all(attempt.status == DownloadFailure.RATE_LIMIT for attempt in result.download_attempts)
    assert [attempt.retry_no for attempt in result.download_attempts] == [0, 1, 2]
    assert [attempt.will_retry for attempt in result.download_attempts] == [True, True, False]
