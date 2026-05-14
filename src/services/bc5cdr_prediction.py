from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


_ENTITY_TYPE_MAP = {
    "chemical": "chemical",
    "chem": "chemical",
    "compound": "chemical",
    "drug": "chemical",
    "medication": "chemical",
    "disease": "disease",
    "condition": "disease",
    "disorder": "disease",
}

_RELATION_TYPE_MAP = {
    "chemical_induced_disease": "chemical_induced_disease",
    "chemical induced disease": "chemical_induced_disease",
    "cid": "chemical_induced_disease",
}


def load_manifest(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    documents = payload.get("documents") if isinstance(payload, dict) else None
    if not isinstance(documents, list):
        raise RuntimeError(f"manifest_missing_documents={path}")
    return [doc for doc in documents if isinstance(doc, dict)]


def resolve_manifest_entry_path(manifest_path: Path, raw_path: str) -> Path:
    candidate = Path(str(raw_path or "").strip()).expanduser()
    if not candidate.is_absolute():
        candidate = (manifest_path.parent / candidate).resolve()
    else:
        candidate = candidate.resolve()
    return candidate


def load_json_object(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"invalid_json_object={path}")
    return payload


def extract_document_texts(document_artifact_path: Path, max_pages: int = 2) -> list[str]:
    payload = load_json_object(document_artifact_path)
    pages = payload.get("pages") if isinstance(payload, dict) else None
    if isinstance(pages, list):
        return [_join_page_lines(page) for page in pages[:max_pages] if isinstance(page, dict)]

    sections = payload.get("sections") if isinstance(payload, dict) else None
    if not isinstance(sections, list):
        return []

    extracted: list[str] = []
    for section in sections[: max_pages + 1]:
        if not isinstance(section, dict):
            continue
        text = str(section.get("text") or "").strip()
        if text:
            extracted.append(text)
    return extracted


def build_bc5cdr_prediction_inputs(
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
        "abstract": abstract[:4000],
    }


def build_bc5cdr_prediction_prompt(*, paper: dict[str, str], schema_json: str) -> str:
    return f"""
You are a biomedical relation extraction engine.
Extract ONLY chemical mentions, disease mentions, and chemical-induced-disease relations from the abstract text below.
Return STRICT JSON matching the provided schema. Do not add markdown, commentary, or extra keys.

Schema:
{schema_json}

Rules:
- Use `doc_id` = `{paper.get("doc_id", "")}`.
- Mentions must use only `chemical` or `disease` for `entity_type`.
- `char_start` and `char_end` must be zero-based character offsets over the exact `Abstract Text` string below.
- `char_end` is exclusive.
- Mention `text` must exactly match the substring at those offsets.
- Only emit `chemical_induced_disease` relations.
- If a relation is emitted, its chemical and disease mention ids must both exist in `mentions`.
- If a normalized id is unknown, set it to null.
- Prefer fewer high-confidence mentions over speculative ones.

Title: {paper.get("title", "")}
Abstract Text:
<<<
{paper.get("abstract", "")}
>>>
"""


def repair_bc5cdr_prediction_payload(
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
    text_key_to_mention_id: dict[tuple[str, str], str] = {}
    used_ids: set[str] = set()
    used_spans_by_entity: dict[tuple[str, str], set[tuple[int, int]]] = {}

    for idx, raw in enumerate(mentions_raw, start=1):
        raw_dict = raw if isinstance(raw, dict) else {"text": raw}
        mention_text = str(raw_dict.get("text") or raw_dict.get("mention_text") or "").strip()
        if not mention_text:
            continue

        entity_type = _normalize_entity_type(raw_dict.get("entity_type") or raw_dict.get("type"))
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
            prefix=entity_type,
            used_ids=used_ids,
        )
        original_id = str(raw_dict.get("mention_id") or raw_dict.get("id") or "").strip()
        if original_id:
            original_id_to_mention_id[original_id] = mention_id
        text_key_to_mention_id[(entity_type, _normalize_lookup_key(mention_text))] = mention_id

        normalized_id = str(raw_dict.get("normalized_id") or "").strip() or None
        mentions.append(
            {
                "mention_id": mention_id,
                "entity_type": entity_type,
                "text": abstract_text[char_start:char_end] if abstract_text else mention_text,
                "char_start": char_start,
                "char_end": char_end,
                "normalized_id": normalized_id,
            }
        )

    relations: list[dict[str, Any]] = []
    used_relation_ids: set[str] = set()
    for idx, raw in enumerate(relations_raw, start=1):
        if not isinstance(raw, dict):
            continue
        relation_type = _normalize_relation_type(raw.get("relation_type") or raw.get("type"))
        if relation_type is None:
            continue

        chemical_id = _resolve_relation_endpoint(
            raw=raw,
            primary_keys=("chemical_mention_id", "chemical_id", "head_id", "source_id"),
            text_keys=("chemical", "chemical_text", "head_text", "source_text"),
            entity_type="chemical",
            original_id_to_mention_id=original_id_to_mention_id,
            text_key_to_mention_id=text_key_to_mention_id,
        )
        disease_id = _resolve_relation_endpoint(
            raw=raw,
            primary_keys=("disease_mention_id", "disease_id", "tail_id", "target_id"),
            text_keys=("disease", "disease_text", "tail_text", "target_text"),
            entity_type="disease",
            original_id_to_mention_id=original_id_to_mention_id,
            text_key_to_mention_id=text_key_to_mention_id,
        )
        if not chemical_id or not disease_id:
            continue

        relation_id = _coerce_unique_id(
            candidate=str(raw.get("relation_id") or raw.get("id") or f"relation-{idx}"),
            prefix="relation",
            used_ids=used_relation_ids,
        )
        relations.append(
            {
                "relation_id": relation_id,
                "relation_type": relation_type,
                "chemical_mention_id": chemical_id,
                "disease_mention_id": disease_id,
            }
        )

    return {
        "doc_id": paper_id,
        "title": str(repaired.get("title") or default_title or paper_id),
        "abstract": str(repaired.get("abstract") or abstract_text),
        "mentions": mentions,
        "relations": relations,
    }


def safe_file_stem(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9._-]+", "_", str(value or "").strip()).strip("_") or "document"


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


def _join_page_lines(page: dict[str, Any]) -> str:
    lines: list[str] = []
    for block in page.get("blocks", []) or []:
        if not isinstance(block, dict):
            continue
        for line in block.get("lines", []) or []:
            if not isinstance(line, dict):
                continue
            text = str(line.get("text") or "").strip()
            if text:
                lines.append(text)
    return "\n".join(lines)


def _normalize_entity_type(value: Any) -> str | None:
    token = _normalize_lookup_key(value)
    return _ENTITY_TYPE_MAP.get(token)


def _normalize_relation_type(value: Any) -> str | None:
    token = _normalize_lookup_key(value)
    if not token:
        return "chemical_induced_disease"
    return _RELATION_TYPE_MAP.get(token)


def _normalize_lookup_key(value: Any) -> str:
    text = str(value or "").strip().lower()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_")
    return text


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

    span = _find_unused_match(text, needle, used_spans=used_spans, ignore_case=True)
    if span is not None:
        return span
    return None


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
    primary_keys: tuple[str, ...],
    text_keys: tuple[str, ...],
    entity_type: str,
    original_id_to_mention_id: dict[str, str],
    text_key_to_mention_id: dict[tuple[str, str], str],
) -> str | None:
    for key in primary_keys:
        value = str(raw.get(key) or "").strip()
        if value and value in original_id_to_mention_id:
            return original_id_to_mention_id[value]
        if value:
            normalized = safe_file_stem(value)
            if normalized in original_id_to_mention_id:
                return original_id_to_mention_id[normalized]
            if normalized.startswith(f"{entity_type}-"):
                return normalized

    for key in text_keys:
        value = str(raw.get(key) or "").strip()
        if not value:
            continue
        candidate = text_key_to_mention_id.get((entity_type, _normalize_lookup_key(value)))
        if candidate:
            return candidate
    return None
