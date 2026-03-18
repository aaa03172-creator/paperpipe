from __future__ import annotations

from dataclasses import dataclass

from src.schemas.agent_artifacts import ClaimSet, EvidenceSpan, IndexArtifact, ScientificClaim


@dataclass(frozen=True)
class _ResolvedMatch:
    chunk_id: str
    section_name: str
    page_hint: int | None
    char_start: int
    char_end: int
    resolution: str


def resolve_claimset_grounding(claimset: ClaimSet, index_artifact: IndexArtifact) -> ClaimSet:
    chunks = list(index_artifact.chunks or [])
    chunks_by_id = {chunk.chunk_id: chunk for chunk in chunks if str(chunk.chunk_id).strip()}

    updated_claims: list[ScientificClaim] = []
    for claim in claimset.claims:
        updated_spans = [
            _resolve_evidence_span(span.model_copy(deep=True), chunks=chunks, chunks_by_id=chunks_by_id)
            for span in claim.evidence_spans
        ]
        updated_claims.append(claim.model_copy(update={"evidence_spans": updated_spans}, deep=True))
    return ClaimSet(doc_id=claimset.doc_id, claims=updated_claims)


def find_text_location(haystack: str, needle: str) -> tuple[int, int, str] | None:
    return _find_text_location(haystack, needle)


def _resolve_evidence_span(
    span: EvidenceSpan,
    *,
    chunks: list,
    chunks_by_id: dict[str, object],
) -> EvidenceSpan:
    candidates = _candidate_texts(span)
    if not candidates:
        span.grounded = False
        span.resolution = "FAILED_MATCH"
        return span

    if span.chunk_id:
        preferred_chunk = chunks_by_id.get(span.chunk_id)
        if preferred_chunk is not None:
            preferred_match = _find_match_in_chunk(preferred_chunk, candidates)
            if preferred_match is not None:
                _apply_match(span, preferred_match)
                return span

    match = _find_unique_match(chunks, candidates)
    if match is None:
        span.grounded = False
        span.resolution = "FAILED_MATCH"
        return span
    if match == "AMBIGUOUS":
        span.grounded = False
        span.resolution = "AMBIGUOUS_MATCH"
        return span

    _apply_match(span, match)
    return span


def _candidate_texts(span: EvidenceSpan) -> list[str]:
    texts: list[str] = []
    for raw in (span.quote, span.raw_text):
        text = str(raw or "").strip()
        if text and text not in texts:
            texts.append(text)
    return sorted(texts, key=len, reverse=True)


def _find_match_in_chunk(chunk: object, candidates: list[str]) -> _ResolvedMatch | None:
    chunk_text = getattr(chunk, "text", "")
    for text in candidates:
        found = _find_text_location(chunk_text, text)
        if found is None:
            continue
        return _ResolvedMatch(
            chunk_id=str(getattr(chunk, "chunk_id", "") or ""),
            section_name=str(getattr(chunk, "section_name", "") or ""),
            page_hint=getattr(chunk, "page_hint", None),
            char_start=found[0],
            char_end=found[1],
            resolution=found[2],
        )
    return None


def _find_unique_match(chunks: list, candidates: list[str]) -> _ResolvedMatch | str | None:
    for text in candidates:
        matches: dict[str, _ResolvedMatch] = {}
        for chunk in chunks:
            found = _find_text_location(getattr(chunk, "text", ""), text)
            if found is None:
                continue
            matches[str(chunk.chunk_id)] = _ResolvedMatch(
                chunk_id=str(chunk.chunk_id),
                section_name=str(getattr(chunk, "section_name", "") or ""),
                page_hint=getattr(chunk, "page_hint", None),
                char_start=found[0],
                char_end=found[1],
                resolution=found[2],
            )
        if len(matches) == 1:
            return next(iter(matches.values()))
        if len(matches) > 1:
            return "AMBIGUOUS"
    return None


def _apply_match(span: EvidenceSpan, match: _ResolvedMatch) -> None:
    span.chunk_id = match.chunk_id
    if match.section_name:
        span.section = match.section_name
    if isinstance(match.page_hint, int) and match.page_hint > 0:
        span.page = match.page_hint - 1
    span.char_start = match.char_start
    span.char_end = match.char_end
    span.source_span = [match.char_start, match.char_end]
    if not (span.highlight_source or "").strip():
        span.highlight_source = "text_match"
    span.grounded = True
    span.resolution = match.resolution


def _find_text_location(haystack: str, needle: str) -> tuple[int, int, str] | None:
    if not haystack or not needle:
        return None

    direct_idx = haystack.find(needle)
    if direct_idx >= 0:
        return (direct_idx, direct_idx + len(needle), "OK")

    normalized_haystack, mapping = _normalize_with_mapping(haystack)
    normalized_needle = _normalize_lookup(needle)
    if not normalized_haystack or not normalized_needle:
        return None
    idx = normalized_haystack.find(normalized_needle)
    if idx < 0:
        return None
    end_idx = idx + len(normalized_needle) - 1
    if idx >= len(mapping) or end_idx >= len(mapping):
        return None
    start = mapping[idx]
    end = mapping[end_idx] + 1
    return (start, end, "NORMALIZED_MATCH")


def _normalize_with_mapping(text: str) -> tuple[str, list[int]]:
    text = _canonicalize_text(text)
    chars: list[str] = []
    mapping: list[int] = []
    prev_space = True
    idx = 0
    while idx < len(text):
        ch = text[idx]
        if ch == "-" and idx + 1 < len(text) and text[idx + 1].isspace():
            j = idx + 1
            while j < len(text) and text[j].isspace():
                j += 1
            if j < len(text) and text[j].isalnum():
                idx = j
                continue
        if ch.isspace():
            if not prev_space:
                chars.append(" ")
                mapping.append(idx)
            prev_space = True
            idx += 1
            continue
        chars.append(ch.lower())
        mapping.append(idx)
        prev_space = False
        idx += 1

    while chars and chars[0] == " ":
        chars.pop(0)
        mapping.pop(0)
    while chars and chars[-1] == " ":
        chars.pop()
        mapping.pop()
    return ("".join(chars), mapping)


def _normalize_lookup(text: str) -> str:
    normalized, _ = _normalize_with_mapping(text)
    return normalized


def _canonicalize_text(text: str) -> str:
    return (
        str(text or "")
        .replace("\u2018", "'")
        .replace("\u2019", "'")
        .replace("\u201c", '"')
        .replace("\u201d", '"')
        .replace("\u2013", "-")
        .replace("\u2014", "-")
        .replace("\ufb01", "fi")
        .replace("\ufb02", "fl")
        .replace("\ufb03", "ffi")
        .replace("\ufb04", "ffl")
    )
