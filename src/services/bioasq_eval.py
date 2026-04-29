from __future__ import annotations

import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from src.schemas.bioasq_eval import (
    BioASQEvalReport,
    BioASQQuestion,
    BioASQQuestionEval,
    BioASQRerankExperimentQuestion,
    BioASQRerankExperimentReport,
    BioASQRerankLabelRow,
)
from src.skills.storage import atomic_write_text
from src.services.identity import normalize_doi


def load_bioasq_questions(path: Path) -> list[BioASQQuestion]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        questions = payload.get("questions")
    else:
        questions = payload
    if not isinstance(questions, list):
        raise ValueError(f"BioASQ question payload must be a list or object with questions: {path}")
    return [BioASQQuestion.model_validate(item) for item in questions if isinstance(item, dict)]


def load_screening_queue(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            payload = json.loads(line)
            if isinstance(payload, dict):
                rows.append(payload)
    return rows


def load_bioasq_rerank_labels(path: Path) -> list[BioASQRerankLabelRow]:
    rows: list[BioASQRerankLabelRow] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            payload = json.loads(line)
            if isinstance(payload, dict):
                rows.append(BioASQRerankLabelRow.model_validate(payload))
    return rows


def evaluate_bioasq_screening_queue(
    *,
    questions: list[BioASQQuestion],
    screening_rows: list[dict[str, Any]],
) -> BioASQEvalReport:
    question_results: list[BioASQQuestionEval] = []
    warnings: list[str] = []

    ranked_identifier_sets = [_row_identifier_tokens(row) for row in screening_rows]
    ranked_texts = [_row_text(row) for row in screening_rows]

    for question in questions:
        gold_tokens, used_identifier_alias_fallback = _question_identifier_tokens(question)
        candidate_hit_positions, candidate_hit_count = _candidate_hit_positions_and_count(
            gold_tokens=gold_tokens,
            ranked_identifier_sets=ranked_identifier_sets,
        )
        candidate_gold_count = len(gold_tokens)
        candidate_recall = _ratio(candidate_hit_count, candidate_gold_count)
        first_candidate_hit_rank = candidate_hit_positions[0] + 1 if candidate_hit_positions else None
        candidate_reciprocal_rank = round((1.0 / first_candidate_hit_rank) if first_candidate_hit_rank else 0.0, 4)
        candidate_average_precision = _average_precision(
            relevant_positions=candidate_hit_positions,
            gold_count=candidate_gold_count,
        )
        candidate_ndcg_at_10 = _ndcg_at_k(
            relevant_positions=candidate_hit_positions,
            gold_count=candidate_gold_count,
            k=10,
        )

        snippet_gold = [snippet for snippet in question.source_snippets if str(snippet).strip()]
        snippet_hit_count = sum(1 for snippet in snippet_gold if _text_supported(snippet, ranked_texts))
        snippet_recall = _ratio(snippet_hit_count, len(snippet_gold))

        answer_aliases = [value for value in [*question.exact_answers, *question.ideal_answers] if str(value).strip()]
        answer_alias_hit = any(_text_supported(answer, ranked_texts, min_overlap_tokens=2) for answer in answer_aliases)

        result_warnings: list[str] = []
        if not gold_tokens:
            result_warnings.append("question_missing_source_candidate_ids")
        elif used_identifier_alias_fallback:
            result_warnings.append("question_identifier_alias_fallback_used")
        if not snippet_gold:
            result_warnings.append("question_missing_source_snippets")

        question_results.append(
            BioASQQuestionEval(
                question_id=question.question_id,
                candidate_gold_count=candidate_gold_count,
                candidate_hit_count=candidate_hit_count,
                candidate_recall=candidate_recall,
                first_candidate_hit_rank=first_candidate_hit_rank,
                candidate_reciprocal_rank=candidate_reciprocal_rank,
                candidate_average_precision=candidate_average_precision,
                candidate_ndcg_at_10=candidate_ndcg_at_10,
                top_1_hit=any(pos < 1 for pos in candidate_hit_positions),
                top_5_hit=any(pos < 5 for pos in candidate_hit_positions),
                top_10_hit=any(pos < 10 for pos in candidate_hit_positions),
                snippet_gold_count=len(snippet_gold),
                snippet_hit_count=snippet_hit_count,
                snippet_recall=snippet_recall,
                answer_alias_hit=answer_alias_hit,
                warnings=result_warnings,
            )
        )
        warnings.extend(f"{question.question_id}:{warning}" for warning in result_warnings)

    question_count = len(question_results)
    return BioASQEvalReport(
        evaluated_at=datetime.now(timezone.utc),
        question_count=question_count,
        candidate_macro_recall=_macro_average(item.candidate_recall for item in question_results),
        candidate_mrr=_macro_average(item.candidate_reciprocal_rank for item in question_results),
        candidate_map=_macro_average(item.candidate_average_precision for item in question_results),
        candidate_ndcg_at_10=_macro_average(item.candidate_ndcg_at_10 for item in question_results),
        snippet_macro_recall=_macro_average(item.snippet_recall for item in question_results),
        answer_alias_hit_rate=_macro_average(1.0 if item.answer_alias_hit else 0.0 for item in question_results),
        top_1_hit_rate=_macro_average(1.0 if item.top_1_hit else 0.0 for item in question_results),
        top_5_hit_rate=_macro_average(1.0 if item.top_5_hit else 0.0 for item in question_results),
        top_10_hit_rate=_macro_average(1.0 if item.top_10_hit else 0.0 for item in question_results),
        questions=question_results,
        warnings=warnings,
    )


def write_bioasq_eval_report(report: BioASQEvalReport, path: Path) -> Path:
    atomic_write_text(path, report.model_dump_json(indent=2))
    return path


def build_bioasq_rerank_labels(
    *,
    questions: list[BioASQQuestion],
    screening_rows: list[dict[str, Any]],
) -> list[BioASQRerankLabelRow]:
    labels: list[BioASQRerankLabelRow] = []
    for question in questions:
        gold_tokens, _ = _question_identifier_tokens(question)
        gold_token_set = set(gold_tokens)
        snippet_gold = [snippet for snippet in question.source_snippets if str(snippet).strip()]
        answer_aliases = [value for value in [*question.exact_answers, *question.ideal_answers] if str(value).strip()]

        for rank_index, row in enumerate(screening_rows, start=1):
            row_tokens = _row_identifier_tokens(row)
            row_text = _row_text(row)
            identifier_match = bool(gold_token_set and row_tokens & gold_token_set)
            snippet_support = any(_text_supported(snippet, [row_text]) for snippet in snippet_gold)
            answer_alias_support = any(
                _text_supported(answer, [row_text], min_overlap_tokens=2)
                for answer in answer_aliases
            )
            relevance_grade = 2 if identifier_match else 1 if (snippet_support or answer_alias_support) else 0

            labels.append(
                BioASQRerankLabelRow(
                    question_id=question.question_id,
                    question=question.question,
                    candidate_rank=rank_index,
                    candidate_id=str(row.get("candidate_id") or ""),
                    paper_id=str(row.get("paper_id") or ""),
                    doi=str(row.get("doi") or ""),
                    title=str(row.get("title") or ""),
                    summary=str(row.get("summary") or ""),
                    identifier_match=identifier_match,
                    snippet_support=snippet_support,
                    answer_alias_support=answer_alias_support,
                    relevance_grade=relevance_grade,
                    metadata={
                        "query_version": row.get("query_version"),
                        "run_id": row.get("run_id"),
                        "dna_id": row.get("dna_id"),
                        "source": row.get("source"),
                    },
                )
            )
    return labels


def write_bioasq_rerank_labels(rows: list[BioASQRerankLabelRow], path: Path) -> Path:
    atomic_write_text(
        path,
        "".join(row.model_dump_json() + "\n" for row in rows),
    )
    return path


def summarize_bioasq_rerank_labels(rows: list[BioASQRerankLabelRow]) -> dict[str, int]:
    positive_rows = sum(1 for row in rows if row.relevance_grade > 0)
    strong_positive_rows = sum(1 for row in rows if row.relevance_grade >= 2)
    return {
        "row_count": len(rows),
        "positive_row_count": positive_rows,
        "strong_positive_row_count": strong_positive_rows,
    }


def run_bioasq_rerank_experiment(rows: list[BioASQRerankLabelRow]) -> BioASQRerankExperimentReport:
    grouped_rows: dict[str, list[BioASQRerankLabelRow]] = {}
    warnings: list[str] = []
    for row in rows:
        grouped_rows.setdefault(row.question_id, []).append(row)

    question_reports: list[BioASQRerankExperimentQuestion] = []
    total_rows = 0
    for question_id, question_rows in grouped_rows.items():
        original_rows = sorted(question_rows, key=lambda row: (row.candidate_rank, row.candidate_id, row.paper_id))
        reranked_rows = sorted(
            question_rows,
            key=lambda row: (-_heuristic_rerank_score(row), row.candidate_rank, row.candidate_id, row.paper_id),
        )
        positive_count = sum(1 for row in question_rows if row.relevance_grade > 0)
        strong_positive_count = sum(1 for row in question_rows if row.relevance_grade >= 2)
        total_rows += len(question_rows)

        if positive_count == 0:
            warnings.append(f"{question_id}:question_missing_positive_labels")

        question_reports.append(
            BioASQRerankExperimentQuestion(
                question_id=question_id,
                row_count=len(question_rows),
                positive_row_count=positive_count,
                strong_positive_row_count=strong_positive_count,
                original_top_1_hit=_top_1_hit(original_rows),
                reranked_top_1_hit=_top_1_hit(reranked_rows),
                original_mrr=_binary_mrr(original_rows),
                reranked_mrr=_binary_mrr(reranked_rows),
                original_map=_binary_average_precision(original_rows),
                reranked_map=_binary_average_precision(reranked_rows),
                original_ndcg_at_10=_graded_ndcg_at_k(original_rows, k=10),
                reranked_ndcg_at_10=_graded_ndcg_at_k(reranked_rows, k=10),
            )
        )

    return BioASQRerankExperimentReport(
        evaluated_at=datetime.now(timezone.utc),
        question_count=len(question_reports),
        row_count=total_rows,
        original_top_1_hit_rate=_macro_average(1.0 if item.original_top_1_hit else 0.0 for item in question_reports),
        reranked_top_1_hit_rate=_macro_average(1.0 if item.reranked_top_1_hit else 0.0 for item in question_reports),
        original_mrr=_macro_average(item.original_mrr for item in question_reports),
        reranked_mrr=_macro_average(item.reranked_mrr for item in question_reports),
        original_map=_macro_average(item.original_map for item in question_reports),
        reranked_map=_macro_average(item.reranked_map for item in question_reports),
        original_ndcg_at_10=_macro_average(item.original_ndcg_at_10 for item in question_reports),
        reranked_ndcg_at_10=_macro_average(item.reranked_ndcg_at_10 for item in question_reports),
        questions=question_reports,
        warnings=warnings,
    )


def write_bioasq_rerank_experiment_report(report: BioASQRerankExperimentReport, path: Path) -> Path:
    atomic_write_text(path, report.model_dump_json(indent=2))
    return path


def _normalize_identifier(value: Any) -> str | None:
    if value is None:
        return None
    raw = str(value).strip()
    if not raw:
        return None
    lowered = raw.lower()

    normalized_doi = normalize_doi(raw)
    if normalized_doi and (
        lowered.startswith("doi:")
        or lowered.startswith("10.")
        or "doi.org/" in lowered
    ):
        return normalized_doi

    if lowered.startswith("pmid:"):
        pmid_value = raw.split(":", 1)[1].strip()
        return f"pmid:{pmid_value}" if pmid_value else None

    if lowered.startswith("pmcid:"):
        pmcid_value = raw.split(":", 1)[1].strip().lower()
        return f"pmcid:{pmcid_value}" if pmcid_value.startswith("pmc") else None

    if lowered.startswith("pmc") and lowered[3:].isdigit():
        return f"pmcid:{lowered}"

    if raw.isdigit():
        return f"pmid:{raw}"

    if "://" in raw:
        parsed = urlparse(raw)
        host = parsed.netloc.lower()
        path = parsed.path.strip("/")

        if "doi.org" in host:
            return normalized_doi or None

        if host in {"pubmed.ncbi.nlm.nih.gov", "www.ncbi.nlm.nih.gov"}:
            if path.isdigit():
                return f"pmid:{path}"
            if path.lower().startswith("pubmed/"):
                pmid_candidate = path.split("/", 1)[1].strip("/")
                if pmid_candidate.isdigit():
                    return f"pmid:{pmid_candidate}"
            if path.lower().startswith("pmc/articles/"):
                pmcid_candidate = path.split("/", 2)[2].strip("/").lower()
                if pmcid_candidate.startswith("pmc") and pmcid_candidate[3:].isdigit():
                    return f"pmcid:{pmcid_candidate}"

        if host == "pmc.ncbi.nlm.nih.gov" and path.lower().startswith("articles/"):
            pmcid_candidate = path.split("/", 1)[1].strip("/").lower()
            if pmcid_candidate.startswith("pmc") and pmcid_candidate[3:].isdigit():
                return f"pmcid:{pmcid_candidate}"

    return lowered


def _row_identifier_tokens(row: dict[str, Any]) -> set[str]:
    tokens: set[str] = set()
    metadata = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
    alias_values = [
        *list(_iter_identifier_values(row.get("identifier_aliases"))),
        *list(_iter_identifier_values(row.get("candidate_aliases"))),
        *list(_iter_identifier_values(metadata.get("identifier_aliases"))),
        *list(_iter_identifier_values(metadata.get("candidate_aliases"))),
        *list(_iter_identifier_values(metadata.get("paper_id_aliases"))),
    ]
    for value in (
        row.get("candidate_id"),
        row.get("paper_id"),
        row.get("doi"),
        row.get("id"),
        row.get("link"),
        row.get("url"),
        row.get("source_url"),
        *alias_values,
    ):
        normalized = _normalize_identifier(value)
        if normalized:
            tokens.add(normalized)
    return tokens


def _question_identifier_tokens(question: BioASQQuestion) -> tuple[list[str], bool]:
    primary_tokens = _deduped_identifiers(question.source_candidate_ids)
    if primary_tokens:
        return primary_tokens, False

    metadata = question.metadata if isinstance(question.metadata, dict) else {}
    alias_tokens = _deduped_identifiers(
        [
            *question.source_candidate_aliases,
            *list(_iter_identifier_values(metadata.get("source_candidate_aliases"))),
            *list(_iter_identifier_values(metadata.get("identifier_aliases"))),
            *list(_iter_identifier_values(metadata.get("candidate_aliases"))),
        ]
    )
    return alias_tokens, bool(alias_tokens)


def _candidate_hit_positions_and_count(
    *,
    gold_tokens: list[str],
    ranked_identifier_sets: list[set[str]],
) -> tuple[list[int], int]:
    gold_token_set = set(gold_tokens)
    if not gold_token_set:
        return [], 0

    seen_hits: set[str] = set()
    hit_positions: list[int] = []
    for idx, row_tokens in enumerate(ranked_identifier_sets):
        new_hits = (row_tokens & gold_token_set) - seen_hits
        if not new_hits:
            continue
        hit_positions.append(idx)
        seen_hits.update(new_hits)
        if len(seen_hits) >= len(gold_token_set):
            break
    return hit_positions, len(seen_hits)


def _deduped_identifiers(values: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for value in values:
        normalized = _normalize_identifier(value)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(normalized)
    return deduped


def _iter_identifier_values(value: Any):
    if isinstance(value, str):
        text = value.strip()
        if text:
            yield text
        return
    if isinstance(value, (list, tuple, set)):
        for item in value:
            if isinstance(item, str):
                text = item.strip()
                if text:
                    yield text


def _row_text(row: dict[str, Any]) -> str:
    title = str(row.get("title") or "").strip()
    summary = str(row.get("summary") or "").strip()
    return _normalize_text(" ".join(part for part in (title, summary) if part))


def _normalize_text(value: Any) -> str:
    text = str(value or "").strip().lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _text_supported(
    reference_text: str,
    ranked_texts: list[str],
    *,
    min_overlap_tokens: int = 3,
) -> bool:
    normalized_reference = _normalize_text(reference_text)
    if not normalized_reference:
        return False

    reference_tokens = [token for token in normalized_reference.split(" ") if token]
    if not reference_tokens:
        return False

    for row_text in ranked_texts:
        if not row_text:
            continue
        if normalized_reference in row_text:
            return True

        row_tokens = set(row_text.split(" "))
        overlap = len(set(reference_tokens) & row_tokens)
        required = max(min_overlap_tokens, math.ceil(0.6 * len(reference_tokens)))
        if overlap >= required:
            return True
    return False


def _ratio(hit_count: int, total: int) -> float:
    return round((hit_count / total) if total else 0.0, 4)


def _heuristic_rerank_score(row: BioASQRerankLabelRow) -> float:
    question_tokens = set(_normalize_text(row.question).split())
    title_tokens = set(_normalize_text(row.title).split())
    summary_tokens = set(_normalize_text(row.summary).split())
    overlap = len(question_tokens & (title_tokens | summary_tokens))
    title_overlap = len(question_tokens & title_tokens)
    return (
        float(title_overlap) * 3.0
        + float(overlap)
        + (0.5 if row.doi else 0.0)
        + (0.25 if row.paper_id or row.candidate_id else 0.0)
    )


def _top_1_hit(rows: list[BioASQRerankLabelRow]) -> bool:
    return bool(rows) and rows[0].relevance_grade > 0


def _binary_mrr(rows: list[BioASQRerankLabelRow]) -> float:
    for index, row in enumerate(rows, start=1):
        if row.relevance_grade > 0:
            return round(1.0 / float(index), 4)
    return 0.0


def _binary_average_precision(rows: list[BioASQRerankLabelRow]) -> float:
    positive_total = sum(1 for row in rows if row.relevance_grade > 0)
    if positive_total <= 0:
        return 0.0

    precision_sum = 0.0
    positives_seen = 0
    for index, row in enumerate(rows, start=1):
        if row.relevance_grade <= 0:
            continue
        positives_seen += 1
        precision_sum += positives_seen / float(index)
    return round(precision_sum / float(positive_total), 4)


def _graded_ndcg_at_k(rows: list[BioASQRerankLabelRow], *, k: int) -> float:
    if not rows or k <= 0:
        return 0.0

    dcg = 0.0
    for index, row in enumerate(rows[:k], start=1):
        gain = float(row.relevance_grade)
        if gain <= 0.0:
            continue
        dcg += gain / math.log2(index + 1.0)

    ideal_rows = sorted(rows, key=lambda row: (-row.relevance_grade, row.candidate_rank))
    ideal_dcg = 0.0
    for index, row in enumerate(ideal_rows[:k], start=1):
        gain = float(row.relevance_grade)
        if gain <= 0.0:
            continue
        ideal_dcg += gain / math.log2(index + 1.0)

    if ideal_dcg <= 0.0:
        return 0.0
    return round(dcg / ideal_dcg, 4)


def _average_precision(*, relevant_positions: list[int], gold_count: int) -> float:
    if not relevant_positions or gold_count <= 0:
        return 0.0

    precision_sum = 0.0
    for rank_index, position in enumerate(relevant_positions, start=1):
        precision_sum += rank_index / float(position + 1)
    return round(precision_sum / float(gold_count), 4)


def _ndcg_at_k(*, relevant_positions: list[int], gold_count: int, k: int) -> float:
    if not relevant_positions or gold_count <= 0 or k <= 0:
        return 0.0

    dcg = 0.0
    for position in relevant_positions:
        rank = position + 1
        if rank > k:
            continue
        dcg += 1.0 / math.log2(rank + 1.0)

    ideal_hits = min(gold_count, k)
    if ideal_hits <= 0:
        return 0.0
    ideal_dcg = sum(1.0 / math.log2(rank + 1.0) for rank in range(1, ideal_hits + 1))
    if ideal_dcg <= 0.0:
        return 0.0
    return round(dcg / ideal_dcg, 4)


def _macro_average(values) -> float:
    values = list(values)
    if not values:
        return 0.0
    return round(sum(float(value) for value in values) / len(values), 4)
