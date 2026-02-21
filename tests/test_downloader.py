from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.config import AppConfig, PathsConfig, SystemConfig
from src.downloader import DownloadRouter, DirectLinkProvider, UnpaywallProvider
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
