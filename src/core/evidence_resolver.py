from __future__ import annotations

import re
from typing import Optional

from src.schemas.agent_artifacts import ClaimSet, IndexArtifact


_WS_RE = re.compile(r"\s+")
_QUOTE_RE = re.compile(r"[“”‘’`]")
_CHUNK_ID_PAGE_RE = re.compile(r"^p(\d+)_c\d+$")


def normalize_text(text: str) -> str:
    if not text:
        return ""
    text = _QUOTE_RE.sub('"', text)
    text = text.replace("-\n", "")
    text = text.replace("\n", " ")
    text = _WS_RE.sub(" ", text)
    return text.strip()


def parse_page_from_chunk_id(chunk_id: str) -> Optional[int]:
    if not chunk_id:
        return None
    m = _CHUNK_ID_PAGE_RE.match(chunk_id.strip())
    if not m:
        return None
    try:
        page = int(m.group(1))
    except ValueError:
        return None
    return page if page > 0 else None


def resolve_claimset_evidence(claim_set: ClaimSet, index_artifact: IndexArtifact) -> ClaimSet:
    chunk_map = {chunk.chunk_id: chunk for chunk in index_artifact.chunks}

    for claim in claim_set.claims:
        for span in claim.evidence_spans:
            chunk_id = (span.chunk_id or "").strip()
            quote = (span.quote or "").strip()
            if not quote:
                quote = (span.raw_text or "").strip()
                if quote:
                    span.quote = quote

            if not chunk_id or chunk_id == "unknown":
                span.grounded = False
                span.resolution = "MISSING_CHUNK"
                span.confidence_band = "hold"
                continue

            chunk = chunk_map.get(chunk_id)
            if chunk is None:
                span.grounded = False
                span.resolution = "MISSING_CHUNK"
                span.confidence_band = "hold"
                continue

            if span.page is None or span.page <= 0:
                parsed_page = parse_page_from_chunk_id(chunk_id)
                if parsed_page is not None:
                    span.page = parsed_page

            chunk_text = chunk.text or ""
            if quote and quote in chunk_text:
                span.grounded = True
                span.resolution = "OK"
                span.confidence_band = "certain"
                continue

            norm_quote = normalize_text(quote)
            norm_chunk = normalize_text(chunk_text)
            if norm_quote and norm_quote in norm_chunk:
                span.grounded = True
                span.resolution = "AMBIGUOUS_MATCH"
                span.confidence_band = "estimated"
                continue

            span.grounded = False
            span.resolution = "FAILED_MATCH"
            span.confidence_band = "hold"

    return claim_set
