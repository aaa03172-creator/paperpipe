from __future__ import annotations

from datetime import datetime, timezone
import re
from pathlib import Path

from src.schemas.agent_artifacts import ClaimSet, IndexArtifact, ScientificClaim
from src.schemas.reader_eval import ReaderEvalClaimEntry, ReaderEvalMetrics, ReaderEvalSidecar
from src.services.citation_grounding import find_text_location

_POLICY_UNSUPPORTED_REASONS = {"EVIDENCE_MISSING", "EVIDENCE_LOCATION_MISSING"}
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
    "in",
    "into",
    "is",
    "it",
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
_TOKEN_RE = re.compile(r"[A-Za-z0-9]+")
_LOW_OVERLAP_THRESHOLD = 0.5


def build_reader_eval_sidecar(
    *,
    paper_id: str,
    run_id: str,
    claimset: ClaimSet,
    resolved_claimset: ClaimSet,
    index_artifact: IndexArtifact,
) -> ReaderEvalSidecar:
    original_by_id = {claim.claim_id: claim for claim in claimset.claims}
    chunks = list(index_artifact.chunks or [])

    entries: list[ReaderEvalClaimEntry] = []
    for resolved_claim in resolved_claimset.claims:
        original_claim = original_by_id.get(resolved_claim.claim_id, resolved_claim)
        entries.append(_build_claim_entry(original_claim=original_claim, resolved_claim=resolved_claim, chunks=chunks))

    metrics = ReaderEvalMetrics(
        claim_count=len(entries),
        supported_claim_count=sum(1 for entry in entries if entry.supported),
        unsupported_claim_count=sum(1 for entry in entries if entry.unsupported),
        unknown_claim_count=sum(1 for entry in entries if entry.unknown),
        heuristic_backfill_claim_count=sum(1 for entry in entries if entry.heuristic_backfill),
        evidence_span_count=sum(entry.evidence_span_count for entry in entries),
        grounded_span_count=sum(entry.grounded_span_count for entry in entries),
        unresolved_span_count=sum(entry.unresolved_span_count for entry in entries),
        ambiguous_span_count=sum(entry.ambiguous_span_count for entry in entries),
        failed_grounding_span_count=sum(entry.failed_grounding_span_count for entry in entries),
        limitation_count=sum(entry.limitation_count for entry in entries),
        grounded_limitation_count=sum(entry.grounded_limitation_count for entry in entries),
        low_overlap_claim_count=sum(1 for entry in entries if entry.low_statement_evidence_overlap),
    )
    return ReaderEvalSidecar(
        generated_at=datetime.now(timezone.utc),
        paper_id=paper_id,
        doc_id=resolved_claimset.doc_id,
        run_id=run_id,
        metrics=metrics,
        claims=entries,
    )


def write_reader_eval_sidecar(sidecar: ReaderEvalSidecar, artifact_dir: Path) -> Path:
    path = artifact_dir / "reader_eval.json"
    path.write_text(sidecar.model_dump_json(indent=2), encoding="utf-8")
    return path


def _build_claim_entry(*, original_claim: ScientificClaim, resolved_claim: ScientificClaim, chunks: list) -> ReaderEvalClaimEntry:
    resolutions = [str(span.resolution or "") for span in resolved_claim.evidence_spans if str(span.resolution or "").strip()]
    grounded_span_count = sum(1 for span in resolved_claim.evidence_spans if span.grounded is True)
    unresolved_span_count = sum(1 for span in resolved_claim.evidence_spans if span.grounded is False)
    ambiguous_span_count = sum(1 for span in resolved_claim.evidence_spans if span.resolution == "AMBIGUOUS_MATCH")
    failed_grounding_span_count = sum(1 for span in resolved_claim.evidence_spans if span.resolution == "FAILED_MATCH")
    unknown_reason = str(original_claim.unknown_reason or "").strip() or None
    unsupported = bool(original_claim.unknown and unknown_reason in _POLICY_UNSUPPORTED_REASONS)
    heuristic_backfill = unknown_reason == "HEURISTIC_BACKFILL"
    grounded_limitation_count = sum(1 for limitation in original_claim.limitations if _text_matches_any_chunk(limitation, chunks))
    overlap_ratio = _statement_evidence_overlap_ratio(resolved_claim)
    return ReaderEvalClaimEntry(
        claim_id=resolved_claim.claim_id,
        statement=resolved_claim.statement,
        supported=not bool(original_claim.unknown),
        unsupported=unsupported,
        unknown=bool(original_claim.unknown),
        unknown_reason=unknown_reason,
        heuristic_backfill=heuristic_backfill,
        evidence_span_count=len(resolved_claim.evidence_spans),
        grounded_span_count=grounded_span_count,
        unresolved_span_count=unresolved_span_count,
        ambiguous_span_count=ambiguous_span_count,
        failed_grounding_span_count=failed_grounding_span_count,
        grounding_resolutions=resolutions,
        limitation_count=len(original_claim.limitations),
        grounded_limitation_count=grounded_limitation_count,
        statement_evidence_overlap_ratio=overlap_ratio,
        low_statement_evidence_overlap=overlap_ratio < _LOW_OVERLAP_THRESHOLD,
    )


def _text_matches_any_chunk(text: str, chunks: list) -> bool:
    candidate = str(text or "").strip()
    if not candidate:
        return False
    for chunk in chunks:
        chunk_text = str(getattr(chunk, "text", "") or "")
        if find_text_location(chunk_text, candidate) is not None:
            return True
    return False


def _statement_evidence_overlap_ratio(claim: ScientificClaim) -> float:
    statement_tokens = _meaningful_tokens(claim.statement)
    if not statement_tokens:
        return 1.0
    evidence_text = " ".join(
        str(text or "").strip()
        for span in claim.evidence_spans
        for text in (span.quote, span.raw_text)
        if str(text or "").strip()
    )
    evidence_tokens = _meaningful_tokens(evidence_text)
    if not evidence_tokens:
        return 0.0
    overlap = len(statement_tokens & evidence_tokens)
    return round(overlap / len(statement_tokens), 4)


def _meaningful_tokens(text: str) -> set[str]:
    tokens = {token.lower() for token in _TOKEN_RE.findall(str(text or ""))}
    return {token for token in tokens if len(token) > 2 and token not in _STOPWORDS}
