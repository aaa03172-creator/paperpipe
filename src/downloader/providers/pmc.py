from __future__ import annotations

import re
from typing import Optional

from src.downloader.providers.base import DownloadCandidate, DownloadProvider
from src.schemas.core import Paper

_PMC_ID_RE = re.compile(r"^(PMC\d+)$", re.IGNORECASE)


class PmcProvider(DownloadProvider):
    """Resolves OA PDF URLs from PubMed Central article ids/links."""

    @property
    def provider_name(self) -> str:
        return "pmc"

    def resolve_pdf(self, paper: Paper) -> Optional[DownloadCandidate]:
        pmc_id = self._extract_pmc_id(paper)
        if not pmc_id:
            return None

        return DownloadCandidate(
            url=f"https://pmc.ncbi.nlm.nih.gov/articles/{pmc_id}/pdf/",
            source_name=self.provider_name,
            is_oa=True,
            confidence=1.0,
            meta={"resolver": "pmc_id"},
        )

    def _extract_pmc_id(self, paper: Paper) -> Optional[str]:
        for raw in [paper.id, paper.doi or ""]:
            candidate = (raw or "").strip()
            match = _PMC_ID_RE.match(candidate)
            if match:
                return match.group(1).upper()

        link = paper.link or ""
        marker = "/articles/"
        if "pmc.ncbi.nlm.nih.gov" in link and marker in link:
            segment = link.split(marker, 1)[1].strip("/").split("/")[0]
            match = _PMC_ID_RE.match(segment)
            if match:
                return match.group(1).upper()
        return None
