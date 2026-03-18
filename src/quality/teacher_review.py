from __future__ import annotations

import json
import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Callable

from pydantic import ValidationError

from src.json_repair import repair_and_parse_json
from src.llm_provider import LLMProvider, get_llm_provider
from src.quality.claimset_policy import enforce_claimset_evidence_policy
from src.schemas.agent_artifacts import ClaimSet, EvidenceSpan, ScientificClaim
from src.services.citation_grounding import find_text_location


SYSTEM_PROMPT = """You are a conservative teacher reviewer for scientific claim extraction.

Rules:
1. Keep only claims directly supported by the provided source snippets.
2. Every kept claim must include at least one evidence span with verbatim source text.
3. Reuse the provided chunk_id and page when possible.
4. If support is weak or ambiguous, delete the claim instead of guessing.
5. Output JSON only. No markdown, no commentary.
"""


_WORD_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{3,}")
_PAGE_RE = re.compile(r"page[_ -]?(\d+)", re.IGNORECASE)


@dataclass(frozen=True)
class BundleChunk:
    chunk_id: str
    text: str
    section_name: str
    page_hint: int | None
    ordinal: int


@dataclass(frozen=True)
class TeacherBundle:
    bundle_dir: Path
    manifest: dict[str, Any]
    prior_output: dict[str, Any]
    tables: list[dict[str, Any]]
    chunks: list[BundleChunk]

    @property
    def paper_id(self) -> str:
        return str(self.manifest.get("paper_id") or "").strip()

    @property
    def expected_doc_id(self) -> str:
        prior_claimset = self.prior_output.get("claimset_json")
        if isinstance(prior_claimset, dict):
            doc_id = str(prior_claimset.get("doc_id") or "").strip()
            if doc_id:
                return doc_id
        return self.paper_id or "unknown_doc"


def load_teacher_bundle(bundle_dir: Path) -> TeacherBundle:
    bundle_dir = bundle_dir.expanduser().resolve()
    manifest = _load_json(bundle_dir / "manifest.json")
    prior_output = _load_json(bundle_dir / "prior_output.json")
    tables = _load_json(bundle_dir / "tables.json")
    if not isinstance(tables, list):
        tables = []

    chunks: list[BundleChunk] = []
    input_chunks_path = bundle_dir / "input_chunks.jsonl"
    if input_chunks_path.exists():
        for idx, row in enumerate(_load_jsonl(input_chunks_path), start=1):
            if not isinstance(row, dict):
                continue
            text = str(row.get("text") or "").strip()
            if not text:
                continue
            section_name = str(row.get("section_name") or "unknown")
            chunks.append(
                BundleChunk(
                    chunk_id=str(row.get("chunk_id") or f"chunk-{idx}"),
                    text=text,
                    section_name=section_name,
                    page_hint=_page_hint(section_name),
                    ordinal=idx,
                )
            )

    return TeacherBundle(
        bundle_dir=bundle_dir,
        manifest=manifest if isinstance(manifest, dict) else {},
        prior_output=prior_output if isinstance(prior_output, dict) else {},
        tables=[item for item in tables if isinstance(item, dict)],
        chunks=chunks,
    )


def review_teacher_bundle(
    *,
    bundle_dir: Path,
    provider: LLMProvider | None = None,
    llm_callable: Callable[[str, str], str | None] | None = None,
    output_name: str = "teacher_output.json",
    meta_name: str = "teacher_output.meta.json",
    max_claims: int = 6,
    max_chunks: int = 18,
    max_chars: int = 18000,
    attempts: int = 2,
) -> dict[str, Any]:
    bundle = load_teacher_bundle(bundle_dir)
    provider_obj = provider
    if provider_obj is None and llm_callable is None:
        from src.config import load_config

        cfg = load_config()
        provider_obj = get_llm_provider(cfg.llm, getattr(cfg, "entity_aliases", None))
        if provider_obj is None or not provider_obj.is_available():
            raise RuntimeError("local_llm_unavailable")

    selected_chunks = select_context_chunks(bundle, max_chunks=max_chunks, max_chars=max_chars)
    prompt = build_teacher_review_prompt(bundle, selected_chunks, max_claims=max_claims)

    last_error = ""
    raw_response = ""
    claimset: ClaimSet | None = None

    for attempt in range(1, max(1, attempts) + 1):
        if llm_callable is not None:
            response = llm_callable(prompt, SYSTEM_PROMPT)
        else:
            assert provider_obj is not None
            response = provider_obj.review_claimset_bundle(prompt=prompt, system_prompt=SYSTEM_PROMPT)
        raw_response = str(response or "")
        parsed = _parse_teacher_claimset(raw_response, expected_doc_id=bundle.expected_doc_id, max_claims=max_claims)
        if parsed is None:
            last_error = "parse_failed"
            continue
        parsed = _augment_locations(parsed, bundle, selected_chunks)
        parsed = _filter_supported_claims(parsed)
        if parsed.claims:
            claimset = parsed
            break
        last_error = "no_supported_claims"

    output_path = bundle.bundle_dir / output_name
    meta_path = bundle.bundle_dir / meta_name
    raw_path = bundle.bundle_dir / "teacher_output.raw.txt"

    raw_path.write_text(raw_response, encoding="utf-8")
    if claimset is None:
        raise RuntimeError(f"teacher_review_failed={last_error}")

    output_path.write_text(json.dumps(claimset.model_dump(), ensure_ascii=False, indent=2), encoding="utf-8")

    model_name = "unknown"
    if provider_obj is not None and hasattr(provider_obj, "_get_model"):
        try:
            model_name = str(provider_obj._get_model("teacher_review"))  # type: ignore[attr-defined]
        except Exception:
            model_name = "unknown"

    meta_payload = {
        "schema_version": "teacher_review.v1",
        "bundle_dir": str(bundle.bundle_dir),
        "paper_id": bundle.paper_id,
        "doc_id": claimset.doc_id,
        "output_path": str(output_path),
        "raw_output_path": str(raw_path),
        "provider": type(provider_obj).__name__ if provider_obj is not None else "callable",
        "model": model_name,
        "selected_chunk_count": len(selected_chunks),
        "selected_chunk_ids": [chunk.chunk_id for chunk in selected_chunks],
        "selected_chunk_pages": [chunk.page_hint for chunk in selected_chunks],
        "tables_count": len(bundle.tables),
        "claim_count": len(claimset.claims),
        "prompt_version": "teacher_local_v1",
    }
    meta_path.write_text(json.dumps(meta_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    return {
        "bundle": bundle,
        "claimset": claimset,
        "output_path": output_path,
        "meta_path": meta_path,
        "raw_path": raw_path,
        "selected_chunks": selected_chunks,
        "meta": meta_payload,
    }


def select_context_chunks(
    bundle: TeacherBundle,
    *,
    max_chunks: int = 18,
    max_chars: int = 18000,
) -> list[BundleChunk]:
    if not bundle.chunks:
        return []

    keywords = _bundle_keywords(bundle)
    target_pages = _target_pages(bundle)

    scored: list[tuple[int, int, BundleChunk]] = []
    for chunk in bundle.chunks:
        text_norm = _normalize_lookup(chunk.text)
        score = 0
        if chunk.ordinal <= 2:
            score += 3
        if chunk.page_hint is not None and chunk.page_hint in target_pages:
            score += 8
        hits = 0
        for token in keywords:
            if token in text_norm:
                hits += 1
        score += min(hits, 8)
        if score > 0:
            scored.append((score, -chunk.ordinal, chunk))

    if not scored:
        scored = [(1, -chunk.ordinal, chunk) for chunk in bundle.chunks[:max_chunks]]

    picked: list[BundleChunk] = []
    used_ids: set[str] = set()
    total_chars = 0
    for _, _, chunk in sorted(scored, reverse=True):
        if chunk.chunk_id in used_ids:
            continue
        if len(picked) >= max_chunks:
            break
        if picked and total_chars + len(chunk.text) > max_chars:
            continue
        picked.append(chunk)
        used_ids.add(chunk.chunk_id)
        total_chars += len(chunk.text)

    if not picked:
        return bundle.chunks[: min(max_chunks, len(bundle.chunks))]
    return sorted(picked, key=lambda item: item.ordinal)


def build_teacher_review_prompt(bundle: TeacherBundle, chunks: list[BundleChunk], *, max_claims: int = 6) -> str:
    prior_summary = str(bundle.prior_output.get("summary") or "").strip()
    prior_claimset = bundle.prior_output.get("claimset_json")
    if isinstance(prior_claimset, dict):
        prior_claimset_json = json.dumps(prior_claimset, ensure_ascii=False, indent=2)
    else:
        prior_claimset_json = "{}"

    chunk_blocks = []
    for idx, chunk in enumerate(chunks, start=1):
        chunk_blocks.append(
            "\n".join(
                [
                    f"[SOURCE {idx}]",
                    f"chunk_id: {chunk.chunk_id}",
                    f"section_name: {chunk.section_name}",
                    f"page: {chunk.page_hint if chunk.page_hint is not None else 'unknown'}",
                    chunk.text,
                ]
            )
        )
    sources_text = "\n\n".join(chunk_blocks) if chunk_blocks else "No text snippets available."

    tables_text = json.dumps(bundle.tables[:3], ensure_ascii=False, indent=2) if bundle.tables else "[]"
    schema_example = {
        "doc_id": bundle.expected_doc_id,
        "claims": [
            {
                "claim_id": "CLM-001",
                "type": "finding",
                "statement": "Supported claim text.",
                "evidence_spans": [
                    {
                        "page": 1,
                        "chunk_id": chunks[0].chunk_id if chunks else "chunk-1",
                        "raw_text": "Exact supporting sentence from the snippets.",
                        "quote": "Exact supporting sentence",
                        "rationale": "Why the sentence supports the claim.",
                    }
                ],
                "limitations": [],
                "confidence": 0.78,
            }
        ],
    }

    return f"""Review and correct the prior claim extraction using ONLY the provided sources.

Expected doc_id: {bundle.expected_doc_id}
Maximum claims to keep: {max_claims}

Prior summary:
{prior_summary if prior_summary else "N/A"}

Prior claimset:
{prior_claimset_json}

Tables:
{tables_text}

Source snippets:
{sources_text}

Output contract:
- Return a JSON object with root keys: doc_id, claims.
- doc_id must be exactly "{bundle.expected_doc_id}".
- Keep only claims that are directly supported by the source snippets.
- Each evidence span must copy source text verbatim into raw_text.
- Reuse chunk_id/page from the labeled sources when possible.
- Do not invent locations, statistics, or study results.
- Prefer fewer, better-supported claims over broader coverage.

Example format:
{json.dumps(schema_example, ensure_ascii=False, indent=2)}
"""


def build_prediction_row(result: dict[str, Any]) -> dict[str, Any]:
    bundle: TeacherBundle = result["bundle"]
    claimset: ClaimSet = result["claimset"]
    return {
        "paper_id": bundle.paper_id,
        "teacher_output": claimset.model_dump(),
        "summary": str(bundle.prior_output.get("summary") or ""),
        "prior_output": bundle.prior_output,
        "bundle_dir": str(bundle.bundle_dir),
        "teacher_output_path": str(result["output_path"]),
        "teacher_meta_path": str(result["meta_path"]),
    }


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_jsonl(path: Path) -> list[Any]:
    rows: list[Any] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def _page_hint(section_name: str) -> int | None:
    match = _PAGE_RE.search(section_name or "")
    if not match:
        return None
    try:
        return int(match.group(1))
    except ValueError:
        return None


def _bundle_keywords(bundle: TeacherBundle) -> set[str]:
    tokens: set[str] = set()
    prior_claimset = bundle.prior_output.get("claimset_json")
    if isinstance(prior_claimset, dict):
        for claim in prior_claimset.get("claims", []) or []:
            if not isinstance(claim, dict):
                continue
            for source in (
                claim.get("statement"),
                " ".join(str(item) for item in claim.get("limitations", []) or []),
            ):
                tokens.update(_tokenize(source))
            for span in claim.get("evidence_spans", []) or []:
                if isinstance(span, dict):
                    tokens.update(_tokenize(span.get("raw_text")))
                    tokens.update(_tokenize(span.get("quote")))
    tokens.update(_tokenize(bundle.prior_output.get("summary")))
    return {token for token in tokens if len(token) >= 4}


def _target_pages(bundle: TeacherBundle) -> set[int]:
    pages: set[int] = set()
    prior_claimset = bundle.prior_output.get("claimset_json")
    if not isinstance(prior_claimset, dict):
        return pages
    for claim in prior_claimset.get("claims", []) or []:
        if not isinstance(claim, dict):
            continue
        for span in claim.get("evidence_spans", []) or []:
            if not isinstance(span, dict):
                continue
            page = span.get("page")
            if isinstance(page, int) and page >= 0:
                pages.add(page)
            section = str(span.get("section") or "")
            page_hint = _page_hint(section)
            if page_hint is not None:
                pages.add(page_hint)
    return pages


def _tokenize(text: Any) -> set[str]:
    return {match.group(0).lower() for match in _WORD_RE.finditer(str(text or ""))}


def _parse_teacher_claimset(raw_text: str, *, expected_doc_id: str, max_claims: int) -> ClaimSet | None:
    cleaned = (raw_text or "").strip()
    if not cleaned:
        return None

    try:
        payload = repair_and_parse_json(cleaned)
    except json.JSONDecodeError:
        return None

    if not isinstance(payload, dict):
        return None

    if isinstance(payload.get("ClaimSet"), dict):
        payload = payload["ClaimSet"]
    elif isinstance(payload.get("claimset"), dict):
        payload = payload["claimset"]

    raw_claims = payload.get("claims")
    if not isinstance(raw_claims, list):
        return None

    normalized_claims: list[ScientificClaim] = []
    for idx, item in enumerate(raw_claims[:max_claims], start=1):
        normalized = _normalize_claim(item, fallback_claim_id=f"CLM-{idx:03d}")
        if normalized is None:
            continue
        normalized_claims.append(normalized)

    try:
        return ClaimSet.model_validate({"doc_id": expected_doc_id, "claims": normalized_claims})
    except ValidationError:
        if not normalized_claims:
            return None
        return ClaimSet(doc_id=expected_doc_id, claims=normalized_claims)


def _normalize_claim(item: Any, *, fallback_claim_id: str) -> ScientificClaim | None:
    if not isinstance(item, dict):
        return None
    statement = str(item.get("statement") or "").strip()
    if not statement:
        return None

    evidence_items = item.get("evidence_spans")
    if not isinstance(evidence_items, list):
        evidence_items = []
    evidence_spans: list[EvidenceSpan] = []
    for idx, span in enumerate(evidence_items, start=1):
        normalized = _normalize_evidence_span(span, fallback_chunk_id=f"ev-{idx}", fallback_statement=statement)
        if normalized is not None:
            evidence_spans.append(normalized)

    if not evidence_spans:
        return None

    limitations = item.get("limitations")
    if not isinstance(limitations, list):
        limitations = []
    limitation_text = [str(entry).strip() for entry in limitations if str(entry).strip()]

    return ScientificClaim(
        claim_id=str(item.get("claim_id") or fallback_claim_id),
        type=str(item.get("type") or "finding"),
        statement=statement,
        evidence_spans=evidence_spans,
        limitations=limitation_text,
        confidence=_clamp_confidence(item.get("confidence")),
        unknown=bool(item.get("unknown", False)),
        unknown_reason=(str(item.get("unknown_reason")).strip() or None) if item.get("unknown_reason") is not None else None,
    )


def _normalize_evidence_span(span: Any, *, fallback_chunk_id: str, fallback_statement: str) -> EvidenceSpan | None:
    if not isinstance(span, dict):
        return None
    raw_text = str(span.get("raw_text") or "").strip()
    quote = str(span.get("quote") or "").strip()
    if not raw_text and quote:
        raw_text = quote
    if not raw_text:
        return None

    payload = {
        "page": _coerce_int(span.get("page")),
        "chunk_id": str(span.get("chunk_id") or fallback_chunk_id),
        "char_start": _coerce_int(span.get("char_start")),
        "char_end": _coerce_int(span.get("char_end")),
        "raw_text": raw_text,
        "quote": quote or _truncate_words(raw_text, 24),
        "rationale": str(span.get("rationale") or "Direct evidence from provided source text."),
        "section": str(span.get("section") or "").strip() or None,
        "source_span": span.get("source_span"),
        "highlight_source": span.get("highlight_source") or span.get("highlightSource"),
        "table_id": span.get("table_id"),
        "cell_id": span.get("cell_id"),
    }
    try:
        return EvidenceSpan.model_validate(payload)
    except ValidationError:
        try:
            fallback_payload = {
                "page": _coerce_int(span.get("page")),
                "chunk_id": str(span.get("chunk_id") or fallback_chunk_id),
                "raw_text": raw_text,
                "quote": quote or _truncate_words(raw_text, 24),
                "rationale": str(span.get("rationale") or "Direct evidence from provided source text."),
                "section": str(span.get("section") or "").strip() or "unknown",
                "source_span": [0, min(len(raw_text), 200)],
                "highlight_source": "text_match",
            }
            return EvidenceSpan.model_validate(fallback_payload)
        except ValidationError:
            if fallback_statement == raw_text:
                return None
            return None


def _augment_locations(claimset: ClaimSet, bundle: TeacherBundle, selected_chunks: list[BundleChunk]) -> ClaimSet:
    prior_lookup = _prior_evidence_lookup(bundle)
    updated_claims: list[ScientificClaim] = []
    for claim in claimset.claims:
        updated_spans: list[EvidenceSpan] = []
        for span in claim.evidence_spans:
            updated = span.model_copy(deep=True)
            _apply_best_location(updated, claim.statement, selected_chunks, prior_lookup)
            updated_spans.append(updated)
        updated_claims.append(claim.model_copy(update={"evidence_spans": updated_spans}, deep=True))

    updated_claimset = ClaimSet(doc_id=claimset.doc_id, claims=updated_claims)
    return enforce_claimset_evidence_policy(updated_claimset)


def _filter_supported_claims(claimset: ClaimSet) -> ClaimSet:
    kept: list[ScientificClaim] = []
    for claim in claimset.claims:
        if claim.unknown:
            continue
        if not claim.evidence_spans:
            continue
        if not any(_span_has_meaningful_location(span) for span in claim.evidence_spans):
            continue
        kept.append(claim)
    return ClaimSet(doc_id=claimset.doc_id, claims=kept)


def _span_has_meaningful_location(span: EvidenceSpan) -> bool:
    if isinstance(span.page, int) and span.page >= 0:
        return True
    if isinstance(span.section, str) and span.section.strip():
        return True
    if isinstance(span.source_span, list) and len(span.source_span) >= 2:
        return True
    if span.char_start is not None and span.char_end is not None:
        return True
    return False


def _apply_best_location(
    span: EvidenceSpan,
    statement: str,
    chunks: list[BundleChunk],
    prior_lookup: dict[str, list[dict[str, Any]]],
) -> None:
    match = _find_chunk_match(span, chunks)
    if match is None:
        match = _find_prior_match(span, statement, prior_lookup)
    if match is None:
        return

    if span.page is None and match.get("page") is not None:
        span.page = match["page"]
    if match.get("chunk_id"):
        span.chunk_id = match["chunk_id"]
    if match.get("section"):
        span.section = match["section"]

    source_span = match.get("source_span")
    if isinstance(source_span, list) and len(source_span) >= 2:
        span.source_span = [int(source_span[0]), int(source_span[1])]
        if span.char_start is None:
            span.char_start = int(source_span[0])
        if span.char_end is None:
            span.char_end = int(source_span[1])

    if not (span.highlight_source or "").strip():
        span.highlight_source = "text_match"


def _find_chunk_match(span: EvidenceSpan, chunks: list[BundleChunk]) -> dict[str, Any] | None:
    texts = [str(span.quote or "").strip(), str(span.raw_text or "").strip()]
    if span.chunk_id:
        for chunk in chunks:
            if chunk.chunk_id == span.chunk_id:
                for text in texts:
                    loc = _find_text_location(chunk.text, text)
                    if loc is not None:
                        return {
                            "page": chunk.page_hint,
                            "chunk_id": chunk.chunk_id,
                            "section": chunk.section_name,
                            "source_span": [loc[0], loc[1]],
                        }

    for text in sorted({candidate for candidate in texts if candidate}, key=len, reverse=True):
        for chunk in chunks:
            loc = _find_text_location(chunk.text, text)
            if loc is not None:
                return {
                    "page": chunk.page_hint,
                    "chunk_id": chunk.chunk_id,
                    "section": chunk.section_name,
                    "source_span": [loc[0], loc[1]],
                }
    return None


def _find_prior_match(
    span: EvidenceSpan,
    statement: str,
    prior_lookup: dict[str, list[dict[str, Any]]],
) -> dict[str, Any] | None:
    candidates = [str(span.quote or "").strip(), str(span.raw_text or "").strip()]
    for text in sorted({candidate for candidate in candidates if candidate}, key=len, reverse=True):
        key = _normalize_lookup(text)
        matches = prior_lookup.get(key)
        if matches:
            return matches[0]

    statement_key = _normalize_lookup(statement)
    best: tuple[float, dict[str, Any]] | None = None
    for prior_statement_key, matches in prior_lookup.items():
        ratio = SequenceMatcher(None, statement_key, prior_statement_key).ratio()
        if ratio < 0.86:
            continue
        if best is None or ratio > best[0]:
            best = (ratio, matches[0])
    if best is not None:
        return best[1]
    return None


def _prior_evidence_lookup(bundle: TeacherBundle) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {}
    prior_claimset = bundle.prior_output.get("claimset_json")
    if not isinstance(prior_claimset, dict):
        return out

    for claim in prior_claimset.get("claims", []) or []:
        if not isinstance(claim, dict):
            continue
        statement = str(claim.get("statement") or "").strip()
        evidence_spans = claim.get("evidence_spans")
        if not isinstance(evidence_spans, list):
            evidence_spans = []
        for span in evidence_spans:
            if not isinstance(span, dict):
                continue
            raw_text = str(span.get("raw_text") or span.get("quote") or "").strip()
            if not raw_text:
                continue
            record = {
                "page": _coerce_int(span.get("page")),
                "chunk_id": str(span.get("chunk_id") or "").strip() or None,
                "section": str(span.get("section") or "").strip() or None,
                "source_span": span.get("source_span") if isinstance(span.get("source_span"), list) else None,
            }
            for key in {_normalize_lookup(raw_text), _normalize_lookup(statement)}:
                if key:
                    out.setdefault(key, []).append(record)
    return out


def _find_text_location(haystack: str, needle: str) -> tuple[int, int] | None:
    found = find_text_location(haystack, needle)
    if found is None:
        return None
    return (found[0], found[1])


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
    )


def _coerce_int(value: Any) -> int | None:
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    return None


def _clamp_confidence(value: Any) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except Exception:
        return 0.5


def _truncate_words(text: str, limit: int) -> str:
    words = str(text or "").split()
    return " ".join(words[:limit])
