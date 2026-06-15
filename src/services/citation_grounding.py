from __future__ import annotations

from dataclasses import dataclass
import difflib
import re
from typing import Any

from src.contracts.document_artifact_v2 import DocumentArtifactV2

from src.schemas.agent_artifacts import ClaimSet, EvidenceSpan, IndexArtifact, ScientificClaim


@dataclass(frozen=True)
class _ResolvedMatch:
    chunk_id: str
    section_name: str
    page_hint: int | None
    char_start: int
    char_end: int
    resolution: str


@dataclass(frozen=True)
class _ResolvedDocumentBlockMatch:
    page_index: int
    section_name: str
    bbox_pdf: list[float] | None
    resolution: str


@dataclass(frozen=True)
class _TokenPosition:
    token: str
    start: int
    end: int


def resolve_claimset_grounding(
    claimset: ClaimSet,
    index_artifact: IndexArtifact,
    document_artifact: DocumentArtifactV2 | None = None,
) -> ClaimSet:
    chunks = list(index_artifact.chunks or [])
    chunks_by_id = {chunk.chunk_id: chunk for chunk in chunks if str(chunk.chunk_id).strip()}
    pages_by_index = _build_pages_by_index(document_artifact)

    updated_claims: list[ScientificClaim] = []
    for claim in claimset.claims:
        updated_spans = [
            _resolve_evidence_span(
                span.model_copy(deep=True),
                claim_statement=str(claim.statement or ""),
                chunks=chunks,
                chunks_by_id=chunks_by_id,
                pages_by_index=pages_by_index,
            )
            for span in claim.evidence_spans
        ]
        updated_claims.append(claim.model_copy(update={"evidence_spans": updated_spans}, deep=True))
    return ClaimSet(doc_id=claimset.doc_id, claims=updated_claims)


def find_text_location(haystack: str, needle: str) -> tuple[int, int, str] | None:
    return _find_text_location(haystack, needle)


def _resolve_evidence_span(
    span: EvidenceSpan,
    *,
    claim_statement: str,
    chunks: list,
    chunks_by_id: dict[str, object],
    pages_by_index: dict[int, object],
) -> EvidenceSpan:
    candidates = _candidate_texts(span)
    bbox_candidates = _bbox_candidate_texts(span, claim_statement=claim_statement)
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
                _apply_document_bbox(span, candidates=bbox_candidates, pages_by_index=pages_by_index)
                return span

    match = _find_unique_match(chunks, candidates)
    if match is None or match == "AMBIGUOUS":
        document_match = _find_unique_document_block_match(pages_by_index, candidates)
        if document_match is not None:
            _apply_document_only_match(span, document_match)
            return span

    if match is None:
        span.grounded = False
        span.resolution = "FAILED_MATCH"
        return span
    if match == "AMBIGUOUS":
        span.grounded = False
        span.resolution = "AMBIGUOUS_MATCH"
        return span

    _apply_match(span, match)
    _apply_document_bbox(span, candidates=bbox_candidates, pages_by_index=pages_by_index)
    return span


def _candidate_texts(span: EvidenceSpan) -> list[str]:
    texts: list[str] = []
    for raw in (span.quote, span.raw_text):
        text = str(raw or "").strip()
        if text and text not in texts:
            texts.append(text)
        stripped = _strip_terminal_punctuation(text)
        if stripped and stripped not in texts:
            texts.append(stripped)
        hyphen_variants = _expand_internal_hyphen_variants(text)
        for variant in hyphen_variants:
            if variant and variant not in texts:
                texts.append(variant)
        for variant in _expand_internal_hyphen_variants(stripped):
            if variant and variant not in texts:
                texts.append(variant)
        numeric_variants = _expand_numeric_unit_spacing_variants(text)
        for variant in numeric_variants:
            if variant and variant not in texts:
                texts.append(variant)
        for variant in _expand_numeric_unit_spacing_variants(stripped):
            if variant and variant not in texts:
                texts.append(variant)
        for variant in hyphen_variants:
            for numeric_variant in _expand_numeric_unit_spacing_variants(variant):
                if numeric_variant and numeric_variant not in texts:
                    texts.append(numeric_variant)
    return sorted(texts, key=len, reverse=True)


def _bbox_candidate_texts(span: EvidenceSpan, *, claim_statement: str) -> list[str]:
    texts = list(_candidate_texts(span))
    statement = str(claim_statement or "").strip()
    if not statement:
        return texts
    for candidate in [
        statement,
        _strip_terminal_punctuation(statement),
        *_expand_internal_hyphen_variants(statement),
        *_expand_numeric_unit_spacing_variants(statement),
        *_expand_claim_statement_bbox_variants(statement),
    ]:
        value = str(candidate or "").strip()
        if value and value not in texts:
            texts.append(value)
    return sorted(texts, key=len, reverse=True)


def _expand_claim_statement_bbox_variants(statement: str) -> list[str]:
    text = str(statement or "").strip()
    if not text:
        return []
    variants: list[str] = []
    match = re.match(r"^(.+?)\s+is\s+(?:a|an)\s+condition\s+characterized\s+by\s+(.+)$", text, flags=re.IGNORECASE)
    if match is not None:
        tail = str(match.group(2) or "").strip()
        if tail:
            variants.append(tail)
    return variants


def _find_match_in_chunk(chunk: object, candidates: list[str]) -> _ResolvedMatch | None:
    chunk_text = getattr(chunk, "text", "")
    for allow_token_overlap in (False, True):
        for text in candidates:
            found = _find_text_location(chunk_text, text, allow_token_overlap=allow_token_overlap)
            if found is None:
                continue
            return _ResolvedMatch(
                chunk_id=str(getattr(chunk, "chunk_id", "") or ""),
                section_name=str(getattr(chunk, "section_name", "") or ""),
                page_hint=_chunk_page_hint(chunk),
                char_start=found[0],
                char_end=found[1],
                resolution=found[2],
            )
    return None


def _find_unique_match(chunks: list, candidates: list[str]) -> _ResolvedMatch | str | None:
    for allow_token_overlap in (False, True):
        for text in candidates:
            matches: dict[str, _ResolvedMatch] = {}
            for chunk in chunks:
                found = _find_text_location(getattr(chunk, "text", ""), text, allow_token_overlap=allow_token_overlap)
                if found is None:
                    continue
                matches[str(chunk.chunk_id)] = _ResolvedMatch(
                    chunk_id=str(chunk.chunk_id),
                    section_name=str(getattr(chunk, "section_name", "") or ""),
                    page_hint=_chunk_page_hint(chunk),
                    char_start=found[0],
                    char_end=found[1],
                    resolution=found[2],
                )
            if len(matches) == 1:
                return next(iter(matches.values()))
            if len(matches) > 1:
                return "AMBIGUOUS"
    return None


def _chunk_page_hint(chunk: object) -> int | None:
    page_hint = getattr(chunk, "page_hint", None)
    if isinstance(page_hint, int) and page_hint > 0:
        return page_hint
    section_name = str(getattr(chunk, "section_name", "") or "").strip()
    match = re.fullmatch(r"page_(\d+)", section_name, flags=re.IGNORECASE)
    if match is None:
        return None
    parsed = int(match.group(1))
    return parsed if parsed > 0 else None


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


def _apply_document_only_match(span: EvidenceSpan, match: _ResolvedDocumentBlockMatch) -> None:
    span.page = match.page_index
    span.section = match.section_name
    if match.bbox_pdf is not None:
        span.bbox_pdf = match.bbox_pdf
        span.highlight_source = "bbox"
    elif not (span.highlight_source or "").strip():
        span.highlight_source = "text_match"
    span.grounded = True
    span.resolution = match.resolution


def _build_pages_by_index(document_artifact: DocumentArtifactV2 | None) -> dict[int, object]:
    if not isinstance(document_artifact, DocumentArtifactV2):
        return {}
    pages_by_index: dict[int, object] = {}
    for page in document_artifact.pages:
        page_index = getattr(page, "page_index", None)
        if isinstance(page_index, int) and page_index >= 0:
            pages_by_index[page_index] = page
    return pages_by_index


def _apply_document_bbox(
    span: EvidenceSpan,
    *,
    candidates: list[str],
    pages_by_index: dict[int, object],
) -> None:
    if span.bbox_pdf or span.bbox_pct:
        return
    if not isinstance(span.page, int) or span.page < 0:
        return
    page = pages_by_index.get(span.page)
    if page is None:
        return
    bbox_pdf = _find_unique_block_bbox(page, candidates)
    if bbox_pdf is None:
        return
    span.bbox_pdf = bbox_pdf
    bbox_pct = _to_bbox_pct(
        bbox_pdf,
        page_width=_coerce_positive_float(getattr(page, "width", None)),
        page_height=_coerce_positive_float(getattr(page, "height", None)),
    )
    if bbox_pct is not None:
        span.bbox_pct = bbox_pct
    span.highlight_source = "bbox"


def _find_unique_document_block_match(
    pages_by_index: dict[int, object],
    candidates: list[str],
) -> _ResolvedDocumentBlockMatch | None:
    for allow_token_overlap in (False, True):
        for text in candidates:
            matches: dict[str, _ResolvedDocumentBlockMatch] = {}
            for page_index, page in pages_by_index.items():
                blocks = list(getattr(page, "blocks", []) or [])
                for idx, block in enumerate(blocks, start=1):
                    block_text = _block_text(block)
                    if not block_text:
                        continue
                    found = _find_text_location(block_text, text, allow_token_overlap=allow_token_overlap)
                    if found is None:
                        continue
                    block_id = str(getattr(block, "block_id", "") or f"page-{page_index}-block-{idx}")
                    matches[block_id] = _ResolvedDocumentBlockMatch(
                        page_index=page_index,
                        section_name=f"page_{page_index + 1}",
                        bbox_pdf=_coerce_bbox_pdf(getattr(block, "bbox_pdf", None)),
                        resolution=found[2],
                    )
            if len(matches) == 1:
                return next(iter(matches.values()))
    return None


def _find_unique_block_bbox(page: object, candidates: list[str]) -> list[float] | None:
    blocks = list(getattr(page, "blocks", []) or [])
    for allow_token_overlap in (False, True):
        for text in candidates:
            matches: dict[str, list[float]] = {}
            for idx, block in enumerate(blocks, start=1):
                bbox_pdf = _coerce_bbox_pdf(getattr(block, "bbox_pdf", None))
                if bbox_pdf is None:
                    continue
                block_text = _block_text(block)
                if not block_text:
                    continue
                if _find_text_location(block_text, text, allow_token_overlap=allow_token_overlap) is None:
                    continue
                block_id = str(getattr(block, "block_id", "") or f"block-{idx}")
                matches[block_id] = bbox_pdf
            if len(matches) == 1:
                return next(iter(matches.values()))
    return None


def _block_text(block: object) -> str:
    lines = list(getattr(block, "lines", []) or [])
    texts: list[str] = []
    for line in lines:
        text = str(getattr(line, "text", "") or "").strip()
        if text:
            texts.append(text)
    return "\n".join(texts).strip()


def _coerce_bbox_pdf(value: Any) -> list[float] | None:
    if not isinstance(value, list) or len(value) != 4:
        return None
    parsed: list[float] = []
    for item in value:
        if not isinstance(item, (int, float)):
            return None
        parsed.append(float(item))
    x0, y0, x1, y1 = parsed
    if min(x0, y0, x1, y1) < 0:
        return None
    if x1 <= x0 or y1 <= y0:
        return None
    return parsed


def _coerce_positive_float(value: Any) -> float | None:
    if not isinstance(value, (int, float)):
        return None
    parsed = float(value)
    if parsed <= 0:
        return None
    return parsed


def _to_bbox_pct(bbox_pdf: list[float], *, page_width: float | None, page_height: float | None) -> dict[str, float] | None:
    if page_width is None or page_height is None:
        return None
    x0, y0, x1, y1 = bbox_pdf
    return {
        "left": round((x0 / page_width) * 100, 4),
        "top": round((y0 / page_height) * 100, 4),
        "width": round(((x1 - x0) / page_width) * 100, 4),
        "height": round(((y1 - y0) / page_height) * 100, 4),
    }


def _find_text_location(haystack: str, needle: str, *, allow_token_overlap: bool = True) -> tuple[int, int, str] | None:
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
    if idx >= 0:
        end_idx = idx + len(normalized_needle) - 1
        if idx >= len(mapping) or end_idx >= len(mapping):
            return None
        start = mapping[idx]
        end = mapping[end_idx] + 1
        return (start, end, "NORMALIZED_MATCH")

    if allow_token_overlap:
        token_match = _find_token_overlap_location(normalized_haystack, normalized_needle, mapping)
        if token_match is not None:
            return token_match
    return None


def _find_token_overlap_location(
    normalized_haystack: str,
    normalized_needle: str,
    mapping: list[int],
) -> tuple[int, int, str] | None:
    if len(normalized_needle) < 120:
        return None
    needle_tokens = [match.group(0) for match in re.finditer(r"[a-z0-9]+", normalized_needle)]
    if len(needle_tokens) < 14:
        return None
    haystack_tokens = [
        _TokenPosition(match.group(0), match.start(), match.end())
        for match in re.finditer(r"[a-z0-9]+", normalized_haystack)
    ]
    if len(haystack_tokens) < 14:
        return None

    matcher = difflib.SequenceMatcher(
        None,
        needle_tokens,
        [position.token for position in haystack_tokens],
        autojunk=False,
    )
    matching_blocks = [block for block in matcher.get_matching_blocks() if block.size > 0]
    matched = sum(block.size for block in matching_blocks)
    if not matching_blocks:
        return None
    coverage = matched / len(needle_tokens)
    if coverage < 0.85 or matched < 14:
        return None
    first_idx = min(block.b for block in matching_blocks)
    last_idx = max(block.b + block.size - 1 for block in matching_blocks)
    start_norm = haystack_tokens[first_idx].start
    end_norm = haystack_tokens[last_idx].end - 1
    if start_norm >= len(mapping) or end_norm >= len(mapping):
        return None
    span_norm_width = haystack_tokens[last_idx].end - haystack_tokens[first_idx].start
    default_width_limit = max(len(normalized_needle) * 1.75, len(normalized_needle) + 160)
    interleaved_column_width_limit = max(len(normalized_needle) * 2.25, len(normalized_needle) + 260)
    if span_norm_width > default_width_limit and (
        coverage < 0.95 or matched < 20 or span_norm_width > interleaved_column_width_limit
    ):
        return None
    return (mapping[start_norm], mapping[end_norm] + 1, "TOKEN_OVERLAP_MATCH")


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


def _strip_terminal_punctuation(text: str) -> str:
    stripped = str(text or "").strip()
    while stripped and stripped[-1] in ".!?,;:":
        stripped = stripped[:-1].rstrip()
    return stripped


_INTERNAL_HYPHEN_RE = re.compile(r"(?<=\w)-(?=\w)")


def _expand_internal_hyphen_variants(text: str) -> list[str]:
    value = str(text or "").strip()
    if not value or "-" not in value:
        return []
    hyphen_positions = [match.start() for match in _INTERNAL_HYPHEN_RE.finditer(value)]
    if not hyphen_positions:
        return []

    variants: list[str] = []
    # Keep this bounded: enough for mixed real-paper cases without exploding candidate count.
    max_combinations = 64
    total_combinations = 1 << len(hyphen_positions)
    if total_combinations <= max_combinations:
        for mask in range(total_combinations):
            chars: list[str] = []
            hyphen_idx = 0
            for idx, ch in enumerate(value):
                if hyphen_idx < len(hyphen_positions) and idx == hyphen_positions[hyphen_idx]:
                    chars.append("" if (mask & (1 << hyphen_idx)) else " ")
                    hyphen_idx += 1
                    continue
                chars.append(ch)
            variant = "".join(chars).strip()
            if variant and variant != value and variant not in variants:
                variants.append(variant)
        return variants

    collapsed = _INTERNAL_HYPHEN_RE.sub("", value).strip()
    if collapsed and collapsed != value:
        variants.append(collapsed)
    spaced = _INTERNAL_HYPHEN_RE.sub(" ", value).strip()
    if spaced and spaced != value and spaced not in variants:
        variants.append(spaced)
    return variants


_DIGIT_ALPHA_COMPACT_RE = re.compile(r"(?<=\d)\s+(?=[A-Za-z])|(?<=[A-Za-z])\s+(?=\d)")
_DIGIT_ALPHA_INSERT_RE = re.compile(r"(?<=\d)(?=[A-Za-z])|(?<=[A-Za-z])(?=\d)")


def _expand_numeric_unit_spacing_variants(text: str) -> list[str]:
    value = str(text or "").strip()
    if not value:
        return []
    variants: list[str] = []
    compact = _DIGIT_ALPHA_COMPACT_RE.sub("", value).strip()
    if compact and compact != value:
        variants.append(compact)
    spaced = _DIGIT_ALPHA_INSERT_RE.sub(" ", value).strip()
    if spaced and spaced != value and spaced not in variants:
        variants.append(spaced)
    return variants


def _canonicalize_text(text: str) -> str:
    value = (
        str(text or "")
        .replace("\u00ad", "")
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
    return _strip_inline_reference_markers(value)


def _strip_inline_reference_markers(text: str) -> str:
    value = str(text or "")
    value = re.sub(r",\s*\d{1,3}(?=\s|[.,;:])", ",", value)
    value = re.sub(r"\)\s*\d{1,3}(?=\s|[.,;:\-])", ")", value)
    return value
