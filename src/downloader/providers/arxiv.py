from __future__ import annotations

import re
from typing import Optional

from src.downloader.providers.base import DownloadCandidate, DownloadProvider
from src.schemas.core import Paper

_ARXIV_ID_RE = re.compile(r"^(?:arxiv:)?([0-9]{4}\.[0-9]{4,5}(?:v\d+)?)$", re.IGNORECASE)


class ArxivProvider(DownloadProvider):
    """Resolves OA PDF URLs from arXiv identifiers/links."""

    @property
    def provider_name(self) -> str:
        return "arxiv"

    def resolve_pdf(self, paper: Paper) -> Optional[DownloadCandidate]:
        arxiv_id = self._extract_arxiv_id(paper)
        if not arxiv_id:
            return None

        return DownloadCandidate(
            url=f"https://arxiv.org/pdf/{arxiv_id}.pdf",
            source_name=self.provider_name,
            is_oa=True,
            confidence=1.0,
            meta={"resolver": "arxiv_id"},
        )

    def _extract_arxiv_id(self, paper: Paper) -> Optional[str]:
        for raw in [paper.id, paper.doi or ""]:
            candidate = (raw or "").strip()
            match = _ARXIV_ID_RE.match(candidate)
            if match:
                return match.group(1)

        if "arxiv.org/abs/" in (paper.link or ""):
            return paper.link.rstrip("/").split("/abs/")[-1]
        return None
