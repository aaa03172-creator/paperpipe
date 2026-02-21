from __future__ import annotations

from typing import Optional

from src.downloader.providers.base import DownloadCandidate, DownloadProvider
from src.schemas.core import Paper


class DirectLinkProvider(DownloadProvider):
    """Uses `paper.pdf_link` when already present."""

    @property
    def provider_name(self) -> str:
        return "direct_link"

    def resolve_pdf(self, paper: Paper) -> Optional[DownloadCandidate]:
        if not paper.pdf_link:
            return None

        return DownloadCandidate(
            url=paper.pdf_link,
            source_name=self.provider_name,
            is_oa=True,
            confidence=1.0,
            meta={"note": "Resolved from paper.pdf_link"},
        )
