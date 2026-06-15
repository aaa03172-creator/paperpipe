from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

from src.schemas.agent_artifacts import ClaimSet, EvidenceSpan, ScientificClaim
from src.schemas.evidence_grounding_scorecard import EvidenceGroundingGoldScoredMetrics, EvidenceGroundingMetric
from src.schemas.paper_understanding_gold import (
    PaperUnderstandingGold,
    PaperUnderstandingGoldEvidenceLocator,
    PaperUnderstandingGoldStatement,
)


_TEXT_MATCH_THRESHOLD = 0.30


@dataclass(frozen=True)
class _GoldMatch:
    statement: PaperUnderstandingGoldStatement
    score: float


@dataclass(frozen=True)
class EvidenceGroundingGoldScoreResult:
    metrics: EvidenceGroundingGoldScoredMetrics
    failure_counts_by_code: dict[str, int]


def score_claimset_against_paper_understanding_gold(
    *,
    claimset: ClaimSet,
    gold: PaperUnderstandingGold,
) -> EvidenceGroundingGoldScoredMetrics:
    return score_claimset_against_paper_understanding_gold_with_failures(
        claimset=claimset,
        gold=gold,
    ).metrics


def score_claimset_against_paper_understanding_gold_with_failures(
    *,
    claimset: ClaimSet,
    gold: PaperUnderstandingGold,
) -> EvidenceGroundingGoldScoreResult:
    """Compute conservative eval-only grounding metrics from a claimset and a gold record.

    The scorer is deliberately bounded: it only marks metrics available when the
    existing gold schema has enough signal. It does not mutate runtime state or
    promote the scorecard into canonical truth.
    """

    claims = list(claimset.claims)
    gold_statements = list(gold.iter_statements())
    gold_claim_like = list(gold.gold_claims) + list(gold.gold_results)
    gold_limitations = list(gold.gold_limitations)
    gold_gaps = list(gold.gold_gaps)

    matches = [_best_gold_match(claim, gold_statements) for claim in claims]
    claim_like_matches = [_best_gold_match(claim, gold_claim_like) for claim in claims]
    matched_claim_count = sum(1 for match in claim_like_matches if match is not None)
    claim_recovery = _statement_recovery_summary(claims, gold_claim_like)
    gap_recovery = _statement_recovery_summary(claims, gold_gaps)
    evidence_support = _evidence_support_summary(claims, matches)
    locator = _locator_summary(claims, matches)
    limitation_recovery = _limitation_recovery_summary(claims, gold_limitations)
    boundary_confusion = _method_result_confusion_summary(claims, matches)
    figure_reference = _figure_reference_summary(claims, matches)
    table_reference = _table_reference_summary(claims, matches)
    table_cell_locator = _table_cell_locator_summary(claims, matches)
    overstatement = _overstatement_summary(claims, matches, gold_statements)
    contradiction = _contradiction_summary(
        claims=claims,
        matches=matches,
        gold_statements=gold_statements,
    )

    metrics = EvidenceGroundingGoldScoredMetrics()
    metrics.claim_precision = _available(
        _ratio(matched_claim_count, len(claims)),
        source="paper_understanding_gold + claimset.resolved",
        detail="Statement-level match against gold claims/results using bounded lexical overlap.",
    )
    metrics.claim_recall = _recall_metric(
        recovered=claim_recovery["recovered"],
        total=claim_recovery["total"],
        source="paper_understanding_gold.gold_claims/results + claimset.resolved",
        detail="Gold claims/results recovered by system claims using bounded lexical/evidence overlap.",
    )
    metrics.unsupported_claim_rate = _available(
        _ratio(len(claims) - matched_claim_count, len(claims)),
        source="paper_understanding_gold + claimset.resolved",
        detail="System claims not matched to gold claims/results. Review required for borderline paraphrases.",
    )
    metrics.evidence_support_precision = _available(
        _ratio(evidence_support["correct"], evidence_support["total"]),
        source="paper_understanding_gold.evidence_refs + claimset.evidence_spans",
        detail="Evidence support is counted when system evidence text or locator matches a matched gold statement.",
    )
    metrics.locator_precision = _available(
        _ratio(locator["correct"], locator["total"]),
        source="paper_understanding_gold.evidence_refs + claimset.evidence_spans",
        detail="Locator precision counts page/chunk/table/cell/figure locator agreement for matched evidence.",
    )
    metrics.limitation_recall = _available(
        _ratio(limitation_recovery["recovered"], limitation_recovery["total"]),
        source="paper_understanding_gold.gold_limitations + claimset",
        detail="Gold limitations found in claim statements or claim limitation text.",
    )
    metrics.gap_recall = _recall_metric(
        recovered=gap_recovery["recovered"],
        total=gap_recovery["total"],
        source="paper_understanding_gold.gold_gaps + claimset",
        detail="Gold future-work gaps recovered by system claims/limitations/evidence using bounded lexical overlap.",
    )
    metrics.method_result_confusion_rate = _available(
        _ratio(boundary_confusion["confused"], boundary_confusion["total"]),
        source="paper_understanding_gold.statement.kind + claimset.claims[].type",
        detail="Counts method/result boundary mismatches among claims matched to method or result gold statements.",
    )
    metrics.figure_reference_precision = _available(
        _ratio(figure_reference["correct"], figure_reference["total"]),
        source="paper_understanding_gold.evidence_refs.figure_id + claimset text/evidence",
        detail="Figure reference precision is available only for explicit figure IDs detectable in claim/evidence text.",
    )
    metrics.table_reference_precision = _available(
        _ratio(table_reference["correct"], table_reference["total"]),
        source="paper_understanding_gold.evidence_refs.table_id + claimset.evidence_spans",
        detail="Table reference precision counts explicit table_id agreement.",
    )
    metrics.table_cell_locator_precision = _available(
        _ratio(table_cell_locator["correct"], table_cell_locator["total"]),
        source="paper_understanding_gold.evidence_refs.cell_id + claimset.evidence_spans",
        detail="Table cell locator precision counts explicit table_id+cell_id agreement.",
    )
    metrics.figure_caption_link_accuracy = _available(
        _ratio(figure_reference["correct"], figure_reference["total"]),
        source="paper_understanding_gold.evidence_refs.figure_id + claimset text/evidence",
        detail="Proxy for caption-to-claim link accuracy using explicit figure reference agreement.",
    )
    if overstatement["total"] > 0:
        metrics.overstatement_rate = _available(
            _ratio(overstatement["overstated"], overstatement["total"]),
            source="paper_understanding_gold.review_failure_codes + claimset.resolved",
            detail="Available only for gold/eval fixtures with explicit OVERSTATED_RESULT review labels.",
        )
    else:
        metrics.overstatement_rate = EvidenceGroundingMetric(
            status="not_available",
            source="paper_understanding_gold.review_failure_codes",
            detail="Requires explicit OVERSTATED_RESULT labels or structured human review.",
        )
    if contradiction["total"] > 0:
        metrics.contradiction_rate = _available(
            _ratio(contradiction["contradicted"], contradiction["total"]),
            source="paper_understanding_gold.review_failure_codes/direct_text_polarity + claimset.resolved",
            detail=(
                "Available for explicit CONTRADICTED_RESULT review labels or bounded direct "
                "text-polarity contradictions between matched gold and system statements."
            ),
        )
    else:
        metrics.contradiction_rate = EvidenceGroundingMetric(
            status="not_available",
            source="paper_understanding_gold.review_failure_codes",
            detail="Requires explicit CONTRADICTED_RESULT labels or structured human review.",
        )
    failure_counts = {
        "UNSUPPORTED_CLAIM": len(claims) - matched_claim_count,
        "MISSING_CLAIM": claim_recovery["total"] - claim_recovery["recovered"],
        "WRONG_EVIDENCE": evidence_support["total"] - evidence_support["correct"],
        "WRONG_LOCATOR": locator["total"] - locator["correct"],
        "LIMITATION_MISSED": limitation_recovery["total"] - limitation_recovery["recovered"],
        "GAP_MISSED": gap_recovery["total"] - gap_recovery["recovered"],
        "METHOD_AS_RESULT": boundary_confusion["method_as_result"],
        "RESULT_AS_METHOD": boundary_confusion["result_as_method"],
        "FIGURE_CAPTION_MISLINKED": figure_reference["total"] - figure_reference["correct"],
        "OVERSTATED_RESULT": overstatement["overstated"],
        "CONTRADICTED_RESULT": contradiction["contradicted"],
        "TABLE_PARSE_FAILED": 0,
    }
    return EvidenceGroundingGoldScoreResult(
        metrics=metrics,
        failure_counts_by_code={code: count for code, count in failure_counts.items() if count > 0},
    )


def _best_gold_match(
    claim: ScientificClaim,
    gold_statements: list[PaperUnderstandingGoldStatement],
) -> _GoldMatch | None:
    if not gold_statements:
        return None
    claim_text = _text_for_claim_match(claim)
    best: _GoldMatch | None = None
    for statement in gold_statements:
        score = max(
            _token_jaccard(claim_text, statement.text),
            _best_evidence_text_overlap(claim.evidence_spans, statement.evidence_refs),
        )
        if best is None or score > best.score:
            best = _GoldMatch(statement=statement, score=score)
    if best is None or best.score < _TEXT_MATCH_THRESHOLD:
        return None
    return best


def _evidence_support_precision(claims: list[ScientificClaim], matches: list[_GoldMatch | None]) -> float:
    summary = _evidence_support_summary(claims, matches)
    return _ratio(summary["correct"], summary["total"])


def _evidence_support_summary(claims: list[ScientificClaim], matches: list[_GoldMatch | None]) -> dict[str, int]:
    spans_with_signal = [
        (span, match)
        for claim, match in zip(claims, matches, strict=False)
        for span in claim.evidence_spans
        if _span_has_support_signal(span)
    ]
    if not spans_with_signal:
        return {"total": 0, "correct": 0}
    supported = sum(
        1
        for span, match in spans_with_signal
        if match is not None and _span_matches_any_gold_evidence(span, match.statement.evidence_refs)
    )
    return {"total": len(spans_with_signal), "correct": supported}


def _locator_precision(claims: list[ScientificClaim], matches: list[_GoldMatch | None]) -> float:
    summary = _locator_summary(claims, matches)
    return _ratio(summary["correct"], summary["total"])


def _locator_summary(claims: list[ScientificClaim], matches: list[_GoldMatch | None]) -> dict[str, int]:
    spans_with_locator = [
        (span, match)
        for claim, match in zip(claims, matches, strict=False)
        for span in claim.evidence_spans
        if _span_has_locator(span)
    ]
    if not spans_with_locator:
        return {"total": 0, "correct": 0}
    correct = sum(
        1
        for span, match in spans_with_locator
        if match is not None and any(_locator_matches(span, ref) for ref in match.statement.evidence_refs)
    )
    return {"total": len(spans_with_locator), "correct": correct}


def _limitation_recall(claims: list[ScientificClaim], gold_limitations: list[PaperUnderstandingGoldStatement]) -> float:
    summary = _limitation_recovery_summary(claims, gold_limitations)
    return _ratio(summary["recovered"], summary["total"])


def _limitation_recovery_summary(
    claims: list[ScientificClaim],
    gold_limitations: list[PaperUnderstandingGoldStatement],
) -> dict[str, int]:
    if not gold_limitations:
        return {"total": 0, "recovered": 0}
    system_texts = [claim.statement for claim in claims] + [limitation for claim in claims for limitation in claim.limitations]
    recovered = sum(
        1
        for limitation in gold_limitations
        if any(_token_jaccard(system_text, limitation.text) >= _TEXT_MATCH_THRESHOLD for system_text in system_texts)
        or any(
            _token_jaccard(system_text, ref.quote) >= _TEXT_MATCH_THRESHOLD
            for system_text in system_texts
            for ref in limitation.evidence_refs
        )
    )
    return {"total": len(gold_limitations), "recovered": recovered}


def _statement_recovery_summary(
    claims: list[ScientificClaim],
    gold_statements: list[PaperUnderstandingGoldStatement],
) -> dict[str, int]:
    if not gold_statements:
        return {"total": 0, "recovered": 0}
    recovered = sum(
        1
        for statement in gold_statements
        if any(_claim_recovers_statement(claim, statement) for claim in claims)
    )
    return {"total": len(gold_statements), "recovered": recovered}


def _claim_recovers_statement(claim: ScientificClaim, statement: PaperUnderstandingGoldStatement) -> bool:
    return (
        _token_jaccard(_text_for_statement_recall(claim), statement.text) >= _TEXT_MATCH_THRESHOLD
        or _best_evidence_text_overlap(claim.evidence_spans, statement.evidence_refs) >= _TEXT_MATCH_THRESHOLD
        or any(_locator_matches(span, ref) for span in claim.evidence_spans for ref in statement.evidence_refs)
    )


def _method_result_confusion_rate(claims: list[ScientificClaim], matches: list[_GoldMatch | None]) -> float:
    summary = _method_result_confusion_summary(claims, matches)
    return _ratio(summary["confused"], summary["total"])


def _method_result_confusion_summary(claims: list[ScientificClaim], matches: list[_GoldMatch | None]) -> dict[str, int]:
    boundary_matches = [
        (claim, match.statement)
        for claim, match in zip(claims, matches, strict=False)
        if match is not None and match.statement.kind in {"method", "result"}
    ]
    if not boundary_matches:
        return {"total": 0, "confused": 0, "method_as_result": 0, "result_as_method": 0}
    method_as_result = sum(
        1
        for claim, statement in boundary_matches
        if statement.kind == "method" and _claim_kind_confuses_boundary(claim, statement.kind)
    )
    result_as_method = sum(
        1
        for claim, statement in boundary_matches
        if statement.kind == "result" and _claim_kind_confuses_boundary(claim, statement.kind)
    )
    return {
        "total": len(boundary_matches),
        "confused": method_as_result + result_as_method,
        "method_as_result": method_as_result,
        "result_as_method": result_as_method,
    }


def _overstatement_summary(
    claims: list[ScientificClaim],
    matches: list[_GoldMatch | None],
    gold_statements: list[PaperUnderstandingGoldStatement],
) -> dict[str, int]:
    summary = _labeled_consistency_summary(
        claims=claims,
        matches=matches,
        gold_statements=gold_statements,
        failure_code="OVERSTATED_RESULT",
    )
    return {"total": summary["total"], "overstated": summary["labeled"]}


def _labeled_consistency_summary(
    *,
    claims: list[ScientificClaim],
    matches: list[_GoldMatch | None],
    gold_statements: list[PaperUnderstandingGoldStatement],
    failure_code: str,
) -> dict[str, int]:
    labeled_statement_ids = {
        statement.statement_id
        for statement in gold_statements
        if failure_code in statement.review_failure_codes
    }
    if not labeled_statement_ids:
        return {"total": 0, "labeled": 0}
    matched_count = sum(
        1
        for match in matches
        if match is not None and match.statement.statement_id in labeled_statement_ids
    )
    return {"total": len(claims), "labeled": matched_count}


def _contradiction_summary(
    *,
    claims: list[ScientificClaim],
    matches: list[_GoldMatch | None],
    gold_statements: list[PaperUnderstandingGoldStatement],
) -> dict[str, int]:
    explicit = _labeled_consistency_summary(
        claims=claims,
        matches=matches,
        gold_statements=gold_statements,
        failure_code="CONTRADICTED_RESULT",
    )
    explicit_statement_ids = {
        statement.statement_id
        for statement in gold_statements
        if "CONTRADICTED_RESULT" in statement.review_failure_codes
    }
    explicit_claim_indexes = {
        index
        for index, match in enumerate(matches)
        if match is not None and match.statement.statement_id in explicit_statement_ids
    }
    direct_adjudicated_indexes: set[int] = set()
    direct_contradicted_indexes: set[int] = set()
    for index, (claim, match) in enumerate(zip(claims, matches, strict=False)):
        if match is None or match.statement.kind not in {"claim", "result"}:
            continue
        if match.statement.statement_id in explicit_statement_ids:
            continue
        direct_status = _direct_text_polarity_contradiction(claim.statement, match.statement.text)
        if direct_status is None:
            continue
        direct_adjudicated_indexes.add(index)
        if direct_status:
            direct_contradicted_indexes.add(index)

    if explicit["total"] > 0:
        contradicted_indexes = explicit_claim_indexes | direct_contradicted_indexes
        return {"total": len(claims), "contradicted": len(contradicted_indexes)}
    return {
        "total": len(direct_adjudicated_indexes),
        "contradicted": len(direct_contradicted_indexes),
    }


def _direct_text_polarity_contradiction(claim_text: str, gold_text: str) -> bool | None:
    if _core_token_jaccard(claim_text, gold_text) < 0.4:
        return None
    claim_negated = _has_negation_signal(claim_text)
    gold_negated = _has_negation_signal(gold_text)
    if not claim_negated and not gold_negated:
        return None
    return claim_negated != gold_negated


def _has_negation_signal(text: str) -> bool:
    return bool(
        re.search(
            r"\b(no|not|neither|nor|without|lack(?:ed|ing|s)?|fail(?:ed|s|ure)?|"
            r"absence|absent|unchanged|insufficient)\b"
            r"|non[-\s]?significant",
            str(text or "").lower(),
        )
    )


def _core_token_jaccard(left: str, right: str) -> float:
    left_tokens = set(_tokens_without_negation(left))
    right_tokens = set(_tokens_without_negation(right))
    if not left_tokens or not right_tokens:
        return 0.0
    return len(left_tokens & right_tokens) / len(left_tokens | right_tokens)


def _tokens_without_negation(text: str) -> list[str]:
    negation_tokens = {
        "no",
        "not",
        "neither",
        "nor",
        "without",
        "lack",
        "lacked",
        "lacking",
        "lacks",
        "fail",
        "failed",
        "fails",
        "failure",
        "absence",
        "absent",
        "unchanged",
        "insufficient",
        "non",
        "nonsignificant",
        "did",
        "does",
        "figure",
        "fig",
    }
    return [token for token in _tokens(text) if token not in negation_tokens]


def _figure_reference_precision(claims: list[ScientificClaim], matches: list[_GoldMatch | None]) -> float:
    summary = _figure_reference_summary(claims, matches)
    return _ratio(summary["correct"], summary["total"])


def _figure_reference_summary(claims: list[ScientificClaim], matches: list[_GoldMatch | None]) -> dict[str, int]:
    figure_refs = [
        (figure_id, claim, match)
        for claim, match in zip(claims, matches, strict=False)
        for figure_id in _figure_ids_from_claim(claim)
    ]
    if not figure_refs:
        return {"total": 0, "correct": 0}
    correct = sum(
        1
        for figure_id, claim, match in figure_refs
        if match is not None and _figure_reference_matches_claim(figure_id, claim, match.statement.evidence_refs)
    )
    return {"total": len(figure_refs), "correct": correct}


def _table_reference_precision(claims: list[ScientificClaim], matches: list[_GoldMatch | None]) -> float:
    summary = _table_reference_summary(claims, matches)
    return _ratio(summary["correct"], summary["total"])


def _table_reference_summary(claims: list[ScientificClaim], matches: list[_GoldMatch | None]) -> dict[str, int]:
    table_refs = [
        (span, match)
        for claim, match in zip(claims, matches, strict=False)
        for span in claim.evidence_spans
        if span.table_id
    ]
    if not table_refs:
        return {"total": 0, "correct": 0}
    correct = sum(
        1
        for span, match in table_refs
        if match is not None and any(
            _table_reference_matches_span(span, ref, require_cell=False)
            for ref in match.statement.evidence_refs
        )
    )
    return {"total": len(table_refs), "correct": correct}


def _table_cell_locator_precision(claims: list[ScientificClaim], matches: list[_GoldMatch | None]) -> float:
    summary = _table_cell_locator_summary(claims, matches)
    return _ratio(summary["correct"], summary["total"])


def _table_cell_locator_summary(claims: list[ScientificClaim], matches: list[_GoldMatch | None]) -> dict[str, int]:
    cell_refs = [
        (span, match)
        for claim, match in zip(claims, matches, strict=False)
        for span in claim.evidence_spans
        if span.table_id and span.cell_id
    ]
    if not cell_refs:
        return {"total": 0, "correct": 0}
    correct = sum(
        1
        for span, match in cell_refs
        if match is not None and any(
            _table_reference_matches_span(span, ref, require_cell=True)
            for ref in match.statement.evidence_refs
        )
    )
    return {"total": len(cell_refs), "correct": correct}


def _figure_reference_matches_claim(
    figure_id: str,
    claim: ScientificClaim,
    refs: list[PaperUnderstandingGoldEvidenceLocator],
) -> bool:
    for ref in refs:
        if not ref.figure_id or _normalize_figure_id(ref.figure_id) != figure_id:
            continue
        if _locator_context_required(ref):
            return any(_locator_context_matches(span, ref) for span in claim.evidence_spans)
        return True
    return False


def _table_reference_matches_span(
    span: EvidenceSpan,
    ref: PaperUnderstandingGoldEvidenceLocator,
    *,
    require_cell: bool,
) -> bool:
    if not span.table_id or not ref.table_id:
        return False
    if _normalize_id(span.table_id) != _normalize_id(ref.table_id):
        return False
    if require_cell:
        if not span.cell_id or not ref.cell_id:
            return False
        if _normalize_id(span.cell_id) != _normalize_id(ref.cell_id):
            return False
    return _locator_context_matches(span, ref)


def _locator_context_required(ref: PaperUnderstandingGoldEvidenceLocator) -> bool:
    return bool(ref.page is not None or ref.chunk_id or ref.quote)


def _locator_context_matches(span: EvidenceSpan, ref: PaperUnderstandingGoldEvidenceLocator) -> bool:
    if ref.page is not None and span.page != ref.page:
        return False
    if ref.chunk_id and (not span.chunk_id or _normalize_id(span.chunk_id) != _normalize_id(ref.chunk_id)):
        return False
    if ref.quote and not _evidence_text_matches(span, ref):
        return False
    return True


def _span_matches_any_gold_evidence(span: EvidenceSpan, refs: list[PaperUnderstandingGoldEvidenceLocator]) -> bool:
    return any(_evidence_text_matches(span, ref) or _locator_matches(span, ref) for ref in refs)


def _locator_matches(span: EvidenceSpan, ref: PaperUnderstandingGoldEvidenceLocator) -> bool:
    if span.page is not None and ref.page is not None and span.page == ref.page:
        return True
    if span.chunk_id and ref.chunk_id and _normalize_id(span.chunk_id) == _normalize_id(ref.chunk_id):
        return True
    if span.table_id and ref.table_id and _normalize_id(span.table_id) == _normalize_id(ref.table_id):
        if span.cell_id and ref.cell_id:
            return _normalize_id(span.cell_id) == _normalize_id(ref.cell_id)
        return True
    return False


def _evidence_text_matches(span: EvidenceSpan, ref: PaperUnderstandingGoldEvidenceLocator) -> bool:
    text = " ".join(value for value in (span.quote, span.raw_text, span.rationale) if value)
    if not text:
        return False
    return (
        _token_jaccard(text, ref.quote) >= _TEXT_MATCH_THRESHOLD
        or _token_coverage(ref.quote, text) >= 0.8
    )


def _span_has_support_signal(span: EvidenceSpan) -> bool:
    return bool(span.quote or span.raw_text or span.rationale or span.table_id or span.cell_id)


def _span_has_locator(span: EvidenceSpan) -> bool:
    return bool(span.page is not None or span.chunk_id or span.table_id or span.cell_id or span.bbox_pdf or span.bbox_pct)


def _text_for_claim_match(claim: ScientificClaim) -> str:
    parts = [claim.statement]
    for span in claim.evidence_spans:
        parts.extend(value for value in (span.quote, span.raw_text, span.rationale) if value)
    return "\n".join(parts)


def _text_for_statement_recall(claim: ScientificClaim) -> str:
    parts = [_text_for_claim_match(claim)]
    parts.extend(claim.limitations)
    return "\n".join(parts)


def _best_evidence_text_overlap(
    spans: list[EvidenceSpan],
    refs: list[PaperUnderstandingGoldEvidenceLocator],
) -> float:
    best = 0.0
    for span in spans:
        text = " ".join(value for value in (span.quote, span.raw_text, span.rationale) if value)
        for ref in refs:
            best = max(best, _token_jaccard(text, ref.quote))
    return best


def _claim_kind_confuses_boundary(claim: ScientificClaim, gold_kind: str) -> bool:
    claim_type = str(claim.type or "").strip().lower()
    if gold_kind == "method":
        return claim_type in {"result", "finding", "efficacy", "safety", "outcome"}
    if gold_kind == "result":
        return claim_type in {"method", "methods", "methodology", "protocol"}
    return False


def _figure_ids_from_claim(claim: ScientificClaim) -> set[str]:
    text = _normalize_text(_text_for_claim_match(claim))
    matches = re.findall(r"\b(?:fig|figure)\.?\s+([a-z0-9_.-]+)", text)
    return {_normalize_figure_id(match) for match in matches if match}


def _gold_figure_ids(refs: Iterable[PaperUnderstandingGoldEvidenceLocator]) -> set[str]:
    return {_normalize_figure_id(ref.figure_id) for ref in refs if ref.figure_id}


def _gold_table_ids(refs: Iterable[PaperUnderstandingGoldEvidenceLocator]) -> set[str]:
    return {_normalize_id(ref.table_id) for ref in refs if ref.table_id}


def _gold_table_cell_ids(refs: Iterable[PaperUnderstandingGoldEvidenceLocator]) -> set[tuple[str, str]]:
    return {
        (_normalize_id(ref.table_id), _normalize_id(ref.cell_id))
        for ref in refs
        if ref.table_id and ref.cell_id
    }


def _normalize_figure_id(value: str | None) -> str:
    normalized = _normalize_id(value)
    normalized = normalized.removeprefix("figure_").removeprefix("fig_")
    return normalized


def _normalize_id(value: str | None) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(value or "").strip().lower()).strip("_")


def _token_jaccard(left: str, right: str) -> float:
    left_tokens = set(_tokens(left))
    right_tokens = set(_tokens(right))
    if not left_tokens or not right_tokens:
        return 0.0
    return len(left_tokens & right_tokens) / len(left_tokens | right_tokens)


def _token_coverage(query: str, target: str) -> float:
    query_tokens = set(_tokens(query))
    target_tokens = set(_tokens(target))
    if not query_tokens or not target_tokens:
        return 0.0
    return len(query_tokens & target_tokens) / len(query_tokens)


def _tokens(text: str) -> list[str]:
    tokens: list[str] = []
    for token in re.findall(r"[a-z0-9]+", str(text or "").lower()):
        if token.isdigit() or len(token) > 2:
            tokens.append(token)
    return tokens


def _normalize_text(text: str) -> str:
    return " ".join(str(text or "").lower().split())


def _available(value: float | int, *, source: str, detail: str | None = None) -> EvidenceGroundingMetric:
    return EvidenceGroundingMetric(value=value, status="available", source=source, detail=detail)


def _not_available(*, source: str, detail: str | None = None) -> EvidenceGroundingMetric:
    return EvidenceGroundingMetric(status="not_available", source=source, detail=detail)


def _recall_metric(*, recovered: int, total: int, source: str, detail: str) -> EvidenceGroundingMetric:
    if total <= 0:
        return _not_available(
            source=source,
            detail=f"{detail} Requires at least one gold label.",
        )
    return _available(_ratio(recovered, total), source=source, detail=detail)


def _ratio(numerator: int | float, denominator: int | float) -> float:
    if denominator <= 0:
        return 0.0
    return round(float(numerator) / float(denominator), 4)
