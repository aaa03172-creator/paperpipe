from __future__ import annotations

import re

from src.schemas.cloud_paper import (
    CloudPaperPageArtifactPublic,
    CloudPaperPayloadClass,
    CloudPaperSummaryResponse,
    CloudPaperSummarySourceBlock,
    CloudPaperWarning,
)


_SENTENCE_END_RE = re.compile(r"(?<=[.!?])\s+")


def build_cloud_paper_summary(
    page_artifact: CloudPaperPageArtifactPublic,
    *,
    max_blocks: int = 3,
    snippet_limit: int = 320,
) -> CloudPaperSummaryResponse:
    source_blocks = [
        _source_block_from_page_block(block, snippet_limit=snippet_limit)
        for block in page_artifact.blocks
        if block.text
    ][:max_blocks]
    warnings = list(page_artifact.warnings)
    if not source_blocks:
        warnings.append(
            CloudPaperWarning(
                code="CLOUD_PAGE_SUMMARY_NO_TEXT_BLOCKS",
                message="No readable text blocks were available in the cloud page artifact.",
                severity="low",
            )
        )

    return CloudPaperSummaryResponse(
        paper_id=page_artifact.paper_id,
        run_id=page_artifact.run_id,
        payload_class=_strictest_payload_class([block.payload_class for block in source_blocks]),
        summary_text=_summary_text_from_source_blocks(source_blocks),
        source_blocks=source_blocks,
        warnings=warnings,
        provenance_summary=page_artifact.provenance_summary,
    )


def _source_block_from_page_block(block, *, snippet_limit: int) -> CloudPaperSummarySourceBlock:
    text = _truncate_text(block.text or "", limit=snippet_limit)
    return CloudPaperSummarySourceBlock(
        block_id=block.block_id,
        page=block.page,
        kind=block.kind,
        text_snippet=text,
        payload_class=block.payload_class,
        metadata=block.metadata,
    )


def _summary_text_from_source_blocks(source_blocks: list[CloudPaperSummarySourceBlock]) -> str:
    if not source_blocks:
        return "No readable cloud page text is available for a draft summary."

    summary_sentences = [_first_sentence(block.text_snippet) for block in source_blocks]
    return " ".join(sentence for sentence in summary_sentences if sentence).strip()


def _first_sentence(text: str) -> str:
    cleaned = " ".join(str(text or "").split())
    if not cleaned:
        return ""
    return _SENTENCE_END_RE.split(cleaned, maxsplit=1)[0].strip()


def _truncate_text(text: str, *, limit: int) -> str:
    cleaned = " ".join(str(text or "").split())
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 1].rstrip() + "..."


def _strictest_payload_class(payload_classes: list[CloudPaperPayloadClass]) -> CloudPaperPayloadClass:
    if not payload_classes:
        return "local_only"
    if "local_only" in payload_classes:
        return "local_only"
    if "lab_allowed" in payload_classes:
        return "lab_allowed"
    return "external_allowed"
