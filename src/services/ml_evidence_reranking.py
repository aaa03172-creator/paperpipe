from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import re

from src.schemas.ml_evidence_reranking import (
    EvidenceRerankCandidatePool,
    EvidenceRerankCandidateSpan,
    EvidenceRerankPilotReport,
)
from src.schemas.ml_training_examples import EvidenceRerankExample


_TOKEN_RE = re.compile(r"[a-zA-Z0-9]+")


def _tokens(value: str) -> set[str]:
    return {token.lower() for token in _TOKEN_RE.findall(value)}


def heuristic_evidence_rerank_score(claim_text: str, candidate_text: str) -> float:
    claim_tokens = _tokens(claim_text)
    candidate_tokens = _tokens(candidate_text)
    if not claim_tokens or not candidate_tokens:
        return 0.0
    overlap = len(claim_tokens & candidate_tokens)
    coverage = overlap / float(len(claim_tokens))
    density = overlap / float(len(candidate_tokens))
    return round((coverage * 2.0) + density, 6)


def build_evidence_rerank_candidate_pool(
    example: EvidenceRerankExample,
    *,
    candidate_text_by_span_id: dict[str, str],
    created_at: datetime | None = None,
) -> EvidenceRerankCandidatePool:
    candidates: list[EvidenceRerankCandidateSpan] = []
    for index, source_span in enumerate(example.source_spans, start=1):
        text = candidate_text_by_span_id.get(source_span.span_id)
        if text is None:
            continue
        candidates.append(
            EvidenceRerankCandidateSpan(
                span_id=source_span.span_id,
                text=text,
                source_span=source_span,
                original_rank=index,
                heuristic_score=heuristic_evidence_rerank_score(example.claim_text, text),
                is_positive=source_span.span_id in example.positive_span_ids,
                is_hard_negative=source_span.span_id in example.hard_negative_span_ids,
            )
        )
    return EvidenceRerankCandidatePool(
        example_id=example.example_id,
        paper_id=example.paper_id,
        run_id=example.run_id,
        claim_id=example.claim_id,
        claim_text=example.claim_text,
        payload_class=example.payload_class,
        candidates=candidates,
        created_at=created_at or datetime.now(timezone.utc),
    )


def reranked_candidates(pool: EvidenceRerankCandidatePool) -> list[EvidenceRerankCandidateSpan]:
    return sorted(
        pool.candidates,
        key=lambda candidate: (
            -candidate.heuristic_score,
            candidate.original_rank,
            candidate.span_id,
        ),
    )


def build_evidence_rerank_pilot_report(
    pools: list[EvidenceRerankCandidatePool],
    *,
    evaluated_at: datetime | None = None,
) -> EvidenceRerankPilotReport:
    if not pools:
        raise ValueError("at least one candidate pool is required")
    payload_class = pools[0].payload_class
    warnings: list[str] = []
    if any(pool.payload_class != payload_class for pool in pools):
        warnings.append("mixed_payload_classes")

    original_top_hits = 0
    reranked_top_hits = 0
    original_mrr_total = 0.0
    reranked_mrr_total = 0.0
    hard_negative_top_hits = 0
    candidate_count = 0

    for pool in pools:
        original = sorted(pool.candidates, key=lambda candidate: (candidate.original_rank, candidate.span_id))
        reranked = reranked_candidates(pool)
        candidate_count += len(pool.candidates)
        if original and original[0].is_positive:
            original_top_hits += 1
        if reranked and reranked[0].is_positive:
            reranked_top_hits += 1
        if reranked and reranked[0].is_hard_negative:
            hard_negative_top_hits += 1
        original_mrr_total += _mrr(original)
        reranked_mrr_total += _mrr(reranked)

    example_count = len(pools)
    return EvidenceRerankPilotReport(
        evaluated_at=evaluated_at or datetime.now(timezone.utc),
        payload_class=payload_class,
        example_count=example_count,
        candidate_count=candidate_count,
        original_top_1_hit_rate=round(original_top_hits / example_count, 6),
        reranked_top_1_hit_rate=round(reranked_top_hits / example_count, 6),
        original_mrr=round(original_mrr_total / example_count, 6),
        reranked_mrr=round(reranked_mrr_total / example_count, 6),
        hard_negative_top_1_rate=round(hard_negative_top_hits / example_count, 6),
        warnings=warnings,
    )


def write_evidence_rerank_candidate_pool(pool: EvidenceRerankCandidatePool, out: Path) -> Path:
    out = Path(out).expanduser().resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(pool.model_dump_json(indent=2), encoding="utf-8")
    return out


def write_evidence_rerank_pilot_report(report: EvidenceRerankPilotReport, out: Path) -> Path:
    out = Path(out).expanduser().resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    return out


def _mrr(candidates: list[EvidenceRerankCandidateSpan]) -> float:
    for index, candidate in enumerate(candidates, start=1):
        if candidate.is_positive:
            return 1.0 / float(index)
    return 0.0
