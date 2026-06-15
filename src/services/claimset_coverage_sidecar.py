from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import re
from pathlib import Path
from typing import Any

from src.contracts.artifact_views import get_artifact_header, iter_text_sections
from src.schemas.agent_artifacts import ClaimSet, IndexArtifact, ScientificClaim
from src.schemas.claimset_coverage import (
    ClaimsetCoverageDuplicateWarning,
    ClaimsetCoverageEvidenceSummary,
    ClaimsetCoverageMetrics,
    ClaimsetCoveragePageSummary,
    ClaimsetCoverageSidecar,
    ClaimsetCoverageStatus,
    ClaimsetCoverageTopicSignal,
)
from src.schemas.figure_captions import FigureCaptionSidecar
from src.skills.storage import atomic_write_text

_TOKEN_RE = re.compile(r"[A-Za-z0-9]+")
_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "has",
    "have",
    "in",
    "into",
    "is",
    "it",
    "may",
    "of",
    "on",
    "or",
    "that",
    "the",
    "their",
    "this",
    "to",
    "was",
    "were",
    "with",
    "without",
}
_DUPLICATE_JACCARD_THRESHOLD = 0.58


@dataclass(frozen=True)
class _TopicSignalDef:
    key: str
    label: str
    keywords: tuple[str, ...]


_REVIEW_TOPIC_SIGNALS: tuple[_TopicSignalDef, ...] = (
    _TopicSignalDef(
        key="translation_gap",
        label="Animal-to-human translation and clinical relevance",
        keywords=("animal", "preclinical", "translation", "clinical trial", "human physiology"),
    ),
    _TopicSignalDef(
        key="human_cellular_systems",
        label="Human cellular systems",
        keywords=("primary human cell", "ipsc", "stem cell", "cell line"),
    ),
    _TopicSignalDef(
        key="organoids_chips_mps",
        label="Organoids, organ chips, and microphysiological systems",
        keywords=("organoid", "organ-on-chip", "organs-on-chips", "microphysiological", "mps"),
    ),
    _TopicSignalDef(
        key="ai_computational",
        label="AI and computational methods",
        keywords=("ai", "artificial intelligence", "machine learning", "active learning", "foundation model"),
    ),
    _TopicSignalDef(
        key="regulatory_validation",
        label="Regulatory validation and qualification",
        keywords=("regulatory", "fda", "oecd", "context of use", "qualification", "benchmark"),
    ),
    _TopicSignalDef(
        key="ethics_governance",
        label="Ethics, governance, and operational adoption",
        keywords=("ethic", "consent", "privacy", "federated", "workforce", "workforce training"),
    ),
)


def build_claimset_coverage_sidecar(
    *,
    paper_id: str,
    run_id: str,
    document_artifact: Any,
    index_artifact: IndexArtifact,
    resolved_claimset: ClaimSet,
    figure_captions: FigureCaptionSidecar | None = None,
    doc_id: str | None = None,
) -> ClaimsetCoverageSidecar:
    sections = list(iter_text_sections(document_artifact))
    page_count = _document_page_count(document_artifact, sections)
    chunk_page_by_id = {
        chunk.chunk_id: page_hint
        for chunk in index_artifact.chunks
        for page_hint in [_chunk_page_hint(chunk)]
        if page_hint
    }
    covered_pages = sorted(
        {
            page
            for claim in resolved_claimset.claims
            for span in claim.evidence_spans
            for page in [_span_page_1_indexed(span, chunk_page_by_id)]
            if page is not None
        }
    )
    grounded_pages = sorted(
        {
            page
            for claim in resolved_claimset.claims
            for span in claim.evidence_spans
            if span.grounded is True
            for page in [_span_page_1_indexed(span, chunk_page_by_id)]
            if page is not None
        }
    )
    section_names = {
        _normalize_section_name(span.section)
        for claim in resolved_claimset.claims
        for span in claim.evidence_spans
        if _normalize_section_name(span.section)
    }
    if not section_names:
        section_names = {
            _normalize_section_name(chunk.section_name)
            for claim in resolved_claimset.claims
            for span in claim.evidence_spans
            if span.chunk_id in chunk_page_by_id
            for chunk in index_artifact.chunks
            if chunk.chunk_id == span.chunk_id
        }

    evidence_span_count = sum(len(claim.evidence_spans) for claim in resolved_claimset.claims)
    grounded_span_count = sum(
        1 for claim in resolved_claimset.claims for span in claim.evidence_spans if span.grounded is True
    )
    unresolved_span_count = sum(
        1 for claim in resolved_claimset.claims for span in claim.evidence_spans if span.grounded is False
    )
    grounded_ratio = _ratio(grounded_span_count, evidence_span_count)
    duplicates = _duplicate_warnings(resolved_claimset.claims)
    topic_signals = _topic_signals(
        sections=sections,
        claims=resolved_claimset.claims,
        figure_captions=figure_captions,
        chunk_page_by_id=chunk_page_by_id,
    )
    missing_topic_count = sum(1 for signal in topic_signals if signal.present_in_document and not signal.covered_by_claimset)

    metrics = ClaimsetCoverageMetrics(
        claim_count=len(resolved_claimset.claims),
        evidence_span_count=evidence_span_count,
        grounded_span_count=grounded_span_count,
        unresolved_span_count=unresolved_span_count,
        grounded_evidence_ratio=grounded_ratio,
        document_page_count=page_count,
        covered_page_count=len(covered_pages),
        page_coverage_ratio=_ratio(len(covered_pages), page_count),
        unique_section_count=len(section_names),
        duplicate_cluster_count=len(duplicates),
        missing_topic_signal_count=missing_topic_count,
    )
    page_summary = ClaimsetCoveragePageSummary(
        covered_pages=covered_pages,
        missing_page_ranges=_ranges([page for page in range(1, page_count + 1) if page not in set(covered_pages)]),
        undercovered_page_ranges=_undercovered_ranges(page_count=page_count, covered_pages=covered_pages),
    )
    evidence_summary = ClaimsetCoverageEvidenceSummary(
        total_spans=evidence_span_count,
        grounded_spans=grounded_span_count,
        unresolved_spans=unresolved_span_count,
        grounded_ratio=grounded_ratio,
        pages_with_grounded_evidence=grounded_pages,
    )
    status, reason_codes = _coverage_status(metrics)
    return ClaimsetCoverageSidecar(
        paper_id=paper_id,
        doc_id=(doc_id or get_artifact_header(document_artifact).doc_id),
        run_id=run_id,
        source_artifacts=_source_artifacts(figure_captions),
        generated_at=datetime.now(timezone.utc),
        coverage_status=status,
        metrics=metrics,
        page_summary=page_summary,
        topic_signals=topic_signals,
        duplicate_warnings=duplicates,
        evidence_summary=evidence_summary,
        recommended_next_action=_recommended_action(status),
        reason_codes=reason_codes,
    )


def write_claimset_coverage_sidecar(sidecar: ClaimsetCoverageSidecar, artifact_dir: Path) -> Path:
    path = artifact_dir / "claimset_coverage.json"
    atomic_write_text(path, sidecar.model_dump_json(indent=2))
    return path


def _document_page_count(document_artifact: Any, sections: list) -> int:
    pages = getattr(document_artifact, "pages", None)
    if isinstance(pages, list) and pages:
        return len(pages)
    hinted_pages = [section.page_hint for section in sections if section.page_hint]
    if hinted_pages:
        return max(hinted_pages)
    return 0


def _span_page_1_indexed(span: Any, chunk_page_by_id: dict[str, int]) -> int | None:
    if isinstance(span.page, int) and span.page >= 0:
        return span.page + 1
    chunk_id = str(span.chunk_id or "")
    page_hint = chunk_page_by_id.get(chunk_id)
    return page_hint if isinstance(page_hint, int) and page_hint > 0 else None


def _chunk_page_hint(chunk: Any) -> int | None:
    page_hint = getattr(chunk, "page_hint", None)
    if isinstance(page_hint, int) and page_hint > 0:
        return page_hint
    section_name = str(getattr(chunk, "section_name", "") or "").strip()
    match = re.fullmatch(r"page_(\d+)", section_name, flags=re.IGNORECASE)
    if match is None:
        return None
    parsed = int(match.group(1))
    return parsed if parsed > 0 else None


def _normalize_section_name(value: object) -> str:
    return " ".join(str(value or "").strip().lower().split())


def _ratio(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round(numerator / denominator, 4)


def _meaningful_tokens(text: str) -> set[str]:
    tokens = {token.lower() for token in _TOKEN_RE.findall(str(text or ""))}
    return {token for token in tokens if len(token) > 2 and token not in _STOPWORDS}


def _duplicate_warnings(claims: list[ScientificClaim]) -> list[ClaimsetCoverageDuplicateWarning]:
    warnings: list[ClaimsetCoverageDuplicateWarning] = []
    tokens_by_id = {claim.claim_id: _meaningful_tokens(claim.statement) for claim in claims}
    for idx, claim in enumerate(claims):
        left = tokens_by_id[claim.claim_id]
        if not left:
            continue
        for other in claims[idx + 1 :]:
            right = tokens_by_id[other.claim_id]
            if not right:
                continue
            similarity = len(left & right) / len(left | right)
            if similarity >= _DUPLICATE_JACCARD_THRESHOLD:
                warnings.append(
                    ClaimsetCoverageDuplicateWarning(
                        claim_ids=[claim.claim_id, other.claim_id],
                        similarity=round(similarity, 4),
                        reason="claim_statements_have_high_token_overlap",
                    )
                )
    return warnings


def _topic_signals(
    *,
    sections: list,
    claims: list[ScientificClaim],
    figure_captions: FigureCaptionSidecar | None,
    chunk_page_by_id: dict[str, int],
) -> list[ClaimsetCoverageTopicSignal]:
    document_text = "\n".join(str(section.text or "") for section in sections)
    figure_text = "\n".join(figure.caption for figure in (figure_captions.figures if figure_captions else []))
    document_haystack = f"{document_text}\n{figure_text}".lower()
    claim_text_by_signal_source = _claim_text_by_signal_source(claims)
    signals: list[ClaimsetCoverageTopicSignal] = []
    for signal in _REVIEW_TOPIC_SIGNALS:
        present = any(_keyword_present(document_haystack, keyword) for keyword in signal.keywords)
        covered = any(_keyword_present(claim_text_by_signal_source, keyword) for keyword in signal.keywords)
        pages = _evidence_pages_for_keywords(claims=claims, keywords=signal.keywords, chunk_page_by_id=chunk_page_by_id)
        signals.append(
            ClaimsetCoverageTopicSignal(
                key=signal.key,
                label=signal.label,
                keywords=list(signal.keywords),
                present_in_document=present,
                covered_by_claimset=covered,
                evidence_pages=pages,
            )
        )
    return signals


def _claim_text_by_signal_source(claims: list[ScientificClaim]) -> str:
    parts: list[str] = []
    for claim in claims:
        parts.append(claim.statement)
        parts.extend(str(span.raw_text or "") for span in claim.evidence_spans)
        parts.extend(str(span.quote or "") for span in claim.evidence_spans)
    return "\n".join(parts).lower()


def _keyword_present(haystack: str, keyword: str) -> bool:
    needle = keyword.lower()
    if len(needle) <= 3 and needle.isalnum():
        return re.search(rf"\b{re.escape(needle)}\b", haystack) is not None
    return needle in haystack


def _evidence_pages_for_keywords(
    *,
    claims: list[ScientificClaim],
    keywords: tuple[str, ...],
    chunk_page_by_id: dict[str, int],
) -> list[int]:
    pages: set[int] = set()
    for claim in claims:
        claim_text = claim.statement.lower()
        claim_matches = any(_keyword_present(claim_text, keyword) for keyword in keywords)
        for span in claim.evidence_spans:
            evidence_text = f"{span.raw_text or ''}\n{span.quote or ''}".lower()
            if claim_matches or any(_keyword_present(evidence_text, keyword) for keyword in keywords):
                page = _span_page_1_indexed(span, chunk_page_by_id)
                if page is not None:
                    pages.add(page)
    return sorted(pages)


def _ranges(pages: list[int]) -> list[str]:
    if not pages:
        return []
    ranges: list[str] = []
    start = prev = pages[0]
    for page in pages[1:]:
        if page == prev + 1:
            prev = page
            continue
        ranges.append(_format_range(start, prev))
        start = prev = page
    ranges.append(_format_range(start, prev))
    return ranges


def _format_range(start: int, end: int) -> str:
    return str(start) if start == end else f"{start}-{end}"


def _undercovered_ranges(*, page_count: int, covered_pages: list[int]) -> list[str]:
    if page_count <= 0 or not covered_pages:
        return _ranges(list(range(1, page_count + 1)))
    if len(covered_pages) == page_count:
        return []
    first = min(covered_pages)
    last = max(covered_pages)
    outside_cluster = [page for page in range(1, page_count + 1) if page < first or page > last]
    return _ranges(outside_cluster)


def _coverage_status(metrics: ClaimsetCoverageMetrics) -> tuple[ClaimsetCoverageStatus, list[str]]:
    reasons: list[str] = []
    if metrics.claim_count == 0:
        reasons.append("no_claims")
    if metrics.evidence_span_count == 0:
        reasons.append("no_evidence_spans")
    if metrics.evidence_span_count > 0 and metrics.grounded_evidence_ratio < 0.5:
        reasons.append("low_grounded_evidence_ratio")
    if metrics.document_page_count >= 6 and metrics.page_coverage_ratio < 0.25:
        reasons.append("low_page_coverage")
    if metrics.claim_count >= 3 and metrics.document_page_count >= 4 and metrics.unique_section_count <= 1:
        reasons.append("low_section_diversity")
    if metrics.duplicate_cluster_count > 0 and metrics.claim_count <= 4:
        reasons.append("near_duplicate_claims")
    if metrics.missing_topic_signal_count >= 3:
        reasons.append("missing_major_topic_signals")
    if "no_claims" in reasons or "no_evidence_spans" in reasons or "low_grounded_evidence_ratio" in reasons:
        return "fail", reasons
    if reasons:
        return "warn", reasons
    return "pass", []


def _recommended_action(status: ClaimsetCoverageStatus) -> str:
    if status == "fail":
        return "review_reader_output_before_promotion"
    if status == "warn":
        return "run_focused_coverage_review_for_missing_topics"
    return "none"


def _source_artifacts(figure_captions: FigureCaptionSidecar | None) -> list[str]:
    artifacts = ["document_artifact.json", "index_artifact.json", "claimset.resolved.json"]
    if figure_captions is not None:
        artifacts.append("figure_captions.json")
    return artifacts
