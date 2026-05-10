from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from src.services.bc5cdr_prediction import (
    extract_document_texts,
    load_manifest,
    resolve_manifest_entry_path,
    safe_file_stem,
)

_ENTITY_TYPE_MAP = {
    "geneorgeneproduct": "GeneOrGeneProduct",
    "gene_or_gene_product": "GeneOrGeneProduct",
    "gene": "GeneOrGeneProduct",
    "geneproduct": "GeneOrGeneProduct",
    "protein": "GeneOrGeneProduct",
    "geneprotein": "GeneOrGeneProduct",
    "sequencevariant": "SequenceVariant",
    "sequence_variant": "SequenceVariant",
    "variant": "SequenceVariant",
    "genevariant": "SequenceVariant",
    "chemicalentity": "ChemicalEntity",
    "chemical_entity": "ChemicalEntity",
    "chemical": "ChemicalEntity",
    "drug": "ChemicalEntity",
    "compound": "ChemicalEntity",
    "diseaseorphenotypicfeature": "DiseaseOrPhenotypicFeature",
    "disease_or_phenotypic_feature": "DiseaseOrPhenotypicFeature",
    "disease": "DiseaseOrPhenotypicFeature",
    "phenotype": "DiseaseOrPhenotypicFeature",
    "phenotypicfeature": "DiseaseOrPhenotypicFeature",
    "condition": "DiseaseOrPhenotypicFeature",
    "disorder": "DiseaseOrPhenotypicFeature",
    "organismtaxon": "OrganismTaxon",
    "organism_taxon": "OrganismTaxon",
    "organism": "OrganismTaxon",
    "taxon": "OrganismTaxon",
    "species": "OrganismTaxon",
    "cellline": "CellLine",
    "cell_line": "CellLine",
}

_RELATION_TYPE_MAP = {
    "positive_correlation": "Positive_Correlation",
    "positivecorrelation": "Positive_Correlation",
    "positive_correlation_relation": "Positive_Correlation",
    "positive_relation": "Positive_Correlation",
    "negative_correlation": "Negative_Correlation",
    "negativecorrelation": "Negative_Correlation",
    "negative_correlation_relation": "Negative_Correlation",
    "negative_relation": "Negative_Correlation",
    "association": "Association",
    "associated_with": "Association",
    "associate": "Association",
    "bind": "Bind",
    "binding": "Bind",
    "binds": "Bind",
    "cotreatment": "Cotreatment",
    "co_treatment": "Cotreatment",
    "co_treated": "Cotreatment",
    "drug_interaction": "Drug_Interaction",
    "druginteraction": "Drug_Interaction",
    "ddi": "Drug_Interaction",
    "comparison": "Comparison",
    "compare": "Comparison",
    "conversion": "Conversion",
    "convert": "Conversion",
}

_ENTITY_PREFIX_MAP = {
    "GeneOrGeneProduct": "gene",
    "SequenceVariant": "variant",
    "ChemicalEntity": "chemical",
    "DiseaseOrPhenotypicFeature": "disease",
    "OrganismTaxon": "organism",
    "CellLine": "cellline",
}

_SUPPORTED_ENTITY_TYPES = (
    "GeneOrGeneProduct",
    "SequenceVariant",
    "ChemicalEntity",
    "DiseaseOrPhenotypicFeature",
    "OrganismTaxon",
    "CellLine",
)

_SUPPORTED_RELATION_TYPES = (
    "Positive_Correlation",
    "Negative_Correlation",
    "Association",
    "Bind",
    "Cotreatment",
    "Drug_Interaction",
    "Comparison",
    "Conversion",
)


def build_biored_prediction_inputs(
    document_artifact_path: Path,
    *,
    paper_id: str,
    max_pages: int = 2,
) -> dict[str, str]:
    pages = extract_document_texts(document_artifact_path, max_pages=max_pages)
    title = _extract_title(pages, fallback=paper_id)
    abstract_parts: list[str] = []
    for idx, page_text in enumerate(pages):
        if not page_text:
            continue
        if idx == 0:
            stripped = _strip_title_prefix(page_text, title=title)
            if stripped:
                abstract_parts.append(stripped)
            continue
        abstract_parts.append(page_text)
    abstract = "\n\n".join(part for part in abstract_parts if part).strip()
    return {
        "paper_id": paper_id,
        "doc_id": paper_id,
        "title": title,
        "abstract": abstract[:5000],
    }


def build_biored_prediction_prompt(*, paper: dict[str, str], schema_json: str) -> str:
    entity_types = ", ".join(_SUPPORTED_ENTITY_TYPES)
    relation_types = ", ".join(_SUPPORTED_RELATION_TYPES)
    return f"""
You are a biomedical document relation extraction engine.
Extract ONLY BioRED-style biomedical entity mentions and relations from the abstract text below.
Return STRICT JSON matching the provided schema. Do not add markdown, commentary, or extra keys.

Schema:
{schema_json}

Rules:
- Use `doc_id` = `{paper.get("doc_id", "")}`.
- Mentions must use only these entity types: {entity_types}.
- Relations must use only these relation types: {relation_types}.
- `char_start` and `char_end` must be zero-based character offsets over the exact `Abstract Text` string below.
- `char_end` is exclusive.
- Mention `text` must exactly match the substring at those offsets.
- `normalized_ids` must be a list of strings; use an empty list when unknown.
- `entity_id` is optional and may be null.
- Every relation must reference mention ids that exist in `mentions`.
- `novelty` must be one of `novel`, `background`, or `unknown`.
- If the same surface text appears multiple times, use the correct distinct offsets for each mention you emit.
- Prefer fewer high-confidence mentions and relations over speculative coverage.

Title: {paper.get("title", "")}
Abstract Text:
<<<
{paper.get("abstract", "")}
>>>
"""


def repair_biored_prediction_payload(
    payload: dict[str, Any],
    *,
    paper_id: str,
    abstract_text: str,
    default_title: str | None = None,
) -> dict[str, Any]:
    repaired = json.loads(json.dumps(payload))
    mentions_payload = repaired.get("mentions")
    relations_payload = repaired.get("relations")
    mentions_raw = mentions_payload if isinstance(mentions_payload, list) else []
    relations_raw = relations_payload if isinstance(relations_payload, list) else []

    mentions: list[dict[str, Any]] = []
    original_id_to_mention_id: dict[str, str] = {}
    typed_text_key_to_mention_ids: dict[tuple[str, str], list[str]] = {}
    text_key_to_mention_ids: dict[str, list[str]] = {}
    span_to_mention_id: dict[tuple[int, int], str] = {}
    mention_ids: set[str] = set()
    used_spans_by_entity: dict[tuple[str, str], set[tuple[int, int]]] = {}

    for idx, raw in enumerate(mentions_raw, start=1):
        raw_dict = raw if isinstance(raw, dict) else {"text": raw}
        mention_text = str(raw_dict.get("text") or raw_dict.get("mention_text") or raw_dict.get("value") or "").strip()
        if not mention_text:
            continue

        entity_type = _normalize_entity_type(raw_dict.get("entity_type") or raw_dict.get("type") or raw_dict.get("label"))
        if entity_type is None:
            continue

        char_start = _safe_int(raw_dict.get("char_start"))
        char_end = _safe_int(raw_dict.get("char_end"))
        if char_start is None or char_end is None or char_end <= char_start:
            inferred_span = _infer_span(
                abstract_text,
                mention_text,
                used_spans=used_spans_by_entity.setdefault(
                    (entity_type, _normalize_lookup_key(mention_text)),
                    set(),
                ),
            )
            if inferred_span is None:
                continue
            char_start, char_end = inferred_span
        used_spans_by_entity.setdefault(
            (entity_type, _normalize_lookup_key(mention_text)),
            set(),
        ).add((char_start, char_end))

        mention_id = _coerce_unique_id(
            candidate=str(raw_dict.get("mention_id") or raw_dict.get("id") or f"{entity_type}-{idx}"),
            prefix=_ENTITY_PREFIX_MAP.get(entity_type, "mention"),
            used_ids=mention_ids,
        )
        original_id = str(raw_dict.get("mention_id") or raw_dict.get("id") or "").strip()
        if original_id:
            original_id_to_mention_id[original_id] = mention_id

        normalized_text = abstract_text[char_start:char_end] if abstract_text else mention_text
        typed_text_key_to_mention_ids.setdefault(
            (entity_type, _normalize_lookup_key(normalized_text)),
            [],
        ).append(mention_id)
        text_key_to_mention_ids.setdefault(_normalize_lookup_key(normalized_text), []).append(mention_id)
        span_to_mention_id[(char_start, char_end)] = mention_id

        mentions.append(
            {
                "mention_id": mention_id,
                "entity_type": entity_type,
                "text": normalized_text,
                "char_start": char_start,
                "char_end": char_end,
                "normalized_ids": _normalize_id_list(
                    raw_dict.get("normalized_ids")
                    or raw_dict.get("normalized_id")
                    or raw_dict.get("db_ids")
                    or raw_dict.get("identifier")
                ),
                "entity_id": str(
                    raw_dict.get("entity_id")
                    or raw_dict.get("concept_id")
                    or raw_dict.get("cluster_id")
                    or ""
                ).strip()
                or None,
            }
        )

    relations: list[dict[str, Any]] = []
    relation_ids: set[str] = set()
    for idx, raw in enumerate(relations_raw, start=1):
        if not isinstance(raw, dict):
            continue
        relation_type = _normalize_relation_type(
            raw.get("relation_type") or raw.get("type") or raw.get("predicate") or raw.get("label")
        )
        if relation_type is None:
            continue

        head_id = _resolve_relation_endpoint(
            raw=raw,
            nested_keys=("head", "source", "arg1"),
            primary_keys=("head_mention_id", "head_id", "source_id", "arg1_id"),
            text_keys=("head_text", "head_mention_text", "source_text", "arg1_text"),
            entity_type_keys=("head_entity_type", "head_type", "source_entity_type", "arg1_type"),
            span_start_keys=("head_char_start", "source_char_start", "arg1_char_start"),
            span_end_keys=("head_char_end", "source_char_end", "arg1_char_end"),
            mention_ids=mention_ids,
            original_id_to_mention_id=original_id_to_mention_id,
            typed_text_key_to_mention_ids=typed_text_key_to_mention_ids,
            text_key_to_mention_ids=text_key_to_mention_ids,
            span_to_mention_id=span_to_mention_id,
        )
        tail_id = _resolve_relation_endpoint(
            raw=raw,
            nested_keys=("tail", "target", "arg2"),
            primary_keys=("tail_mention_id", "tail_id", "target_id", "arg2_id"),
            text_keys=("tail_text", "tail_mention_text", "target_text", "arg2_text"),
            entity_type_keys=("tail_entity_type", "tail_type", "target_entity_type", "arg2_type"),
            span_start_keys=("tail_char_start", "target_char_start", "arg2_char_start"),
            span_end_keys=("tail_char_end", "target_char_end", "arg2_char_end"),
            mention_ids=mention_ids,
            original_id_to_mention_id=original_id_to_mention_id,
            typed_text_key_to_mention_ids=typed_text_key_to_mention_ids,
            text_key_to_mention_ids=text_key_to_mention_ids,
            span_to_mention_id=span_to_mention_id,
        )
        if not head_id or not tail_id or head_id == tail_id:
            continue

        relation_id = _coerce_unique_id(
            candidate=str(raw.get("relation_id") or raw.get("id") or f"relation-{idx}"),
            prefix="relation",
            used_ids=relation_ids,
        )
        relations.append(
            {
                "relation_id": relation_id,
                "relation_type": relation_type,
                "head_mention_id": head_id,
                "tail_mention_id": tail_id,
                "novelty": _normalize_novelty(raw.get("novelty")),
            }
        )

    return {
        "doc_id": paper_id,
        "title": str(repaired.get("title") or default_title or paper_id),
        "abstract": str(repaired.get("abstract") or abstract_text),
        "mentions": mentions,
        "relations": relations,
    }


def _extract_title(pages: list[str], *, fallback: str) -> str:
    if not pages:
        return fallback
    first_page = pages[0]
    for line in first_page.splitlines():
        candidate = line.strip()
        if candidate:
            return candidate[:240]
    return fallback


def _strip_title_prefix(page_text: str, *, title: str) -> str:
    if not page_text:
        return ""
    prefix = str(title or "").strip()
    if not prefix:
        return page_text.strip()
    if page_text.startswith(prefix):
        remainder = page_text[len(prefix):].lstrip("\n\r\t :;-")
        return remainder.strip()
    return page_text.strip()


def _normalize_entity_type(value: Any) -> str | None:
    token = _normalize_lookup_key(value)
    return _ENTITY_TYPE_MAP.get(token)


def _normalize_relation_type(value: Any) -> str | None:
    token = _normalize_lookup_key(value)
    return _RELATION_TYPE_MAP.get(token)


def _normalize_novelty(value: Any) -> str:
    token = _normalize_lookup_key(value)
    if token in {"novel", "new"}:
        return "novel"
    if token in {"background", "known", "existing", "previously_known"}:
        return "background"
    return "unknown"


def _normalize_lookup_key(value: Any) -> str:
    text = str(value or "").strip().lower()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_")
    return text


def _normalize_id_list(value: Any) -> list[str]:
    if isinstance(value, list):
        candidates = [str(item).strip() for item in value]
    elif isinstance(value, tuple):
        candidates = [str(item).strip() for item in value]
    elif isinstance(value, str):
        pieces = re.split(r"[|;,]", value)
        candidates = [piece.strip() for piece in pieces]
    elif value is None:
        candidates = []
    else:
        candidates = [str(value).strip()]

    normalized: list[str] = []
    for candidate in candidates:
        if not candidate or candidate in normalized:
            continue
        normalized.append(candidate)
    return normalized


def _safe_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _infer_span(
    text: str,
    needle: str,
    *,
    used_spans: set[tuple[int, int]] | None = None,
) -> tuple[int, int] | None:
    if not text or not needle:
        return None

    span = _find_unused_match(text, needle, used_spans=used_spans)
    if span is not None:
        return span

    return _find_unused_match(text, needle, used_spans=used_spans, ignore_case=True)


def _find_unused_match(
    text: str,
    needle: str,
    *,
    used_spans: set[tuple[int, int]] | None = None,
    ignore_case: bool = False,
) -> tuple[int, int] | None:
    flags = re.IGNORECASE if ignore_case else 0
    for match in re.finditer(re.escape(needle), text, flags=flags):
        span = (match.start(), match.end())
        if used_spans is None or span not in used_spans:
            return span
    return None


def _coerce_unique_id(*, candidate: str, prefix: str, used_ids: set[str]) -> str:
    base = safe_file_stem(candidate) or prefix
    result = base
    counter = 2
    while result in used_ids:
        result = f"{base}-{counter}"
        counter += 1
    used_ids.add(result)
    return result


def _resolve_relation_endpoint(
    *,
    raw: dict[str, Any],
    nested_keys: tuple[str, ...],
    primary_keys: tuple[str, ...],
    text_keys: tuple[str, ...],
    entity_type_keys: tuple[str, ...],
    span_start_keys: tuple[str, ...],
    span_end_keys: tuple[str, ...],
    mention_ids: set[str],
    original_id_to_mention_id: dict[str, str],
    typed_text_key_to_mention_ids: dict[tuple[str, str], list[str]],
    text_key_to_mention_ids: dict[str, list[str]],
    span_to_mention_id: dict[tuple[int, int], str],
) -> str | None:
    for key in nested_keys:
        nested = raw.get(key)
        if isinstance(nested, dict):
            resolved = _resolve_endpoint_payload(
                nested,
                primary_keys=("mention_id", "id"),
                text_keys=("text", "mention_text", "value"),
                entity_type_keys=("entity_type", "type", "label"),
                span_start_keys=("char_start",),
                span_end_keys=("char_end",),
                mention_ids=mention_ids,
                original_id_to_mention_id=original_id_to_mention_id,
                typed_text_key_to_mention_ids=typed_text_key_to_mention_ids,
                text_key_to_mention_ids=text_key_to_mention_ids,
                span_to_mention_id=span_to_mention_id,
            )
            if resolved:
                return resolved
        elif isinstance(nested, str) and nested.strip():
            resolved = _resolve_explicit_endpoint_id(
                nested.strip(),
                mention_ids=mention_ids,
                original_id_to_mention_id=original_id_to_mention_id,
            )
            if resolved:
                return resolved

    return _resolve_endpoint_payload(
        raw,
        primary_keys=primary_keys,
        text_keys=text_keys,
        entity_type_keys=entity_type_keys,
        span_start_keys=span_start_keys,
        span_end_keys=span_end_keys,
        mention_ids=mention_ids,
        original_id_to_mention_id=original_id_to_mention_id,
        typed_text_key_to_mention_ids=typed_text_key_to_mention_ids,
        text_key_to_mention_ids=text_key_to_mention_ids,
        span_to_mention_id=span_to_mention_id,
    )


def _resolve_endpoint_payload(
    payload: dict[str, Any],
    *,
    primary_keys: tuple[str, ...],
    text_keys: tuple[str, ...],
    entity_type_keys: tuple[str, ...],
    span_start_keys: tuple[str, ...],
    span_end_keys: tuple[str, ...],
    mention_ids: set[str],
    original_id_to_mention_id: dict[str, str],
    typed_text_key_to_mention_ids: dict[tuple[str, str], list[str]],
    text_key_to_mention_ids: dict[str, list[str]],
    span_to_mention_id: dict[tuple[int, int], str],
) -> str | None:
    for key in primary_keys:
        value = str(payload.get(key) or "").strip()
        if not value:
            continue
        resolved = _resolve_explicit_endpoint_id(
            value,
            mention_ids=mention_ids,
            original_id_to_mention_id=original_id_to_mention_id,
        )
        if resolved:
            return resolved

    for start_key, end_key in zip(span_start_keys, span_end_keys):
        char_start = _safe_int(payload.get(start_key))
        char_end = _safe_int(payload.get(end_key))
        if char_start is None or char_end is None:
            continue
        candidate = span_to_mention_id.get((char_start, char_end))
        if candidate:
            return candidate

    entity_type: str | None = None
    for key in entity_type_keys:
        entity_type = _normalize_entity_type(payload.get(key))
        if entity_type:
            break

    for key in text_keys:
        value = str(payload.get(key) or "").strip()
        if not value:
            continue
        lookup_key = _normalize_lookup_key(value)
        if entity_type:
            typed_candidates = typed_text_key_to_mention_ids.get((entity_type, lookup_key)) or []
            if typed_candidates:
                return typed_candidates[0]
        untyped_candidates = text_key_to_mention_ids.get(lookup_key) or []
        if untyped_candidates:
            return untyped_candidates[0]
    return None


def _resolve_explicit_endpoint_id(
    value: str,
    *,
    mention_ids: set[str],
    original_id_to_mention_id: dict[str, str],
) -> str | None:
    if value in original_id_to_mention_id:
        return original_id_to_mention_id[value]
    if value in mention_ids:
        return value
    normalized = safe_file_stem(value)
    if normalized in original_id_to_mention_id:
        return original_id_to_mention_id[normalized]
    if normalized in mention_ids:
        return normalized
    return None
