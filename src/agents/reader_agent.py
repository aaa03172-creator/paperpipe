
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Any, Optional

from pydantic import ValidationError

from src.agents.adapter import OllamaModelAdapter
from src.contracts.artifact_views import get_artifact_header, iter_text_sections
from src.contracts.document_artifact_v2 import DocumentArtifactV2
from src.json_repair import repair_and_parse_json
from src.quality.claimset_policy import enforce_claimset_evidence_policy
from src.schemas.agent_artifacts import ClaimSet, DocumentArtifact, EvidenceSpan, ScientificClaim
from src.services.citation_grounding import find_text_location
from src.services.identity import make_chunk_id
from src.timeout_policy import is_timeout_exception

logger = logging.getLogger(__name__)


_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")
_STAT_CUE_RE = re.compile(
    r"\b(p\s*[<=>]\s*0?\.\d+|n\s*=\s*\d+|\d+(?:\.\d+)?\s*%|95%\s*CI|odds\s+ratio|hazard\s+ratio)\b",
    re.IGNORECASE,
)
_RESULT_CUE_RE = re.compile(
    r"\b(significant(?:ly)?|increase[sd]?|decrease[sd]?|improv(?:e|ed|ement)|reduc(?:e|ed|tion)|"
    r"compared|versus|associated|correlated|higher|lower|effect)\b",
    re.IGNORECASE,
)
READER_CHUNK_SIZE = 1000
READER_CHUNK_OVERLAP = 200
_LIMITATION_STOPWORDS = {
    "the",
    "and",
    "with",
    "without",
    "from",
    "that",
    "this",
    "these",
    "those",
    "into",
    "onto",
    "than",
    "then",
    "were",
    "was",
    "are",
    "is",
    "our",
    "their",
    "study",
    "paper",
    "result",
    "results",
}
_EVIDENCE_STOPWORDS = _LIMITATION_STOPWORDS | {
    "compound",
    "compounds",
    "effect",
    "effects",
    "activity",
    "activities",
    "treatment",
}


@dataclass(frozen=True)
class _SectionRecord:
    name: str
    text: str
    page: int | None


@dataclass(frozen=True)
class _ChunkRecord:
    chunk_id: str
    section: str
    page: int | None
    text: str
    char_start: int
    char_end: int


class ReaderAgent:
    """
    Agent responsible for critical scientific reading and claim extraction.
    Uses a 'Senior Postdoc' persona and structured JSON output.
    """

    def __init__(
        self,
        model_name: str = "llama3:latest",
        persona_hint: Optional[str] = None,
        min_claims: int = 1,
        max_context_chars: int = 16000,
    ):
        self.model_name = model_name
        self.adapter = OllamaModelAdapter(model_name=model_name)
        self.min_claims = max(1, int(min_claims))
        self.max_context_chars = max(6000, int(max_context_chars))

        self.output_schema = ClaimSet.model_json_schema()
        self.system_prompt = """You are a highly analytical and rigorous Senior Postdoc researcher in a Biomedical Convergence and Cognitive Science laboratory. Your role is to mentor and assist the Lead Researcher by critically deep-reading papers. 

Your goal is NOT to summarize the paper. Your goal is to extract verifiable claims with grounded evidence only.

Follow these strict directives:
1. Extract claims only when directly supported by provided text evidence.
2. Every claim MUST include evidence_spans with quote/raw_text and a location hint (page or source_span).
3. If uncertain, set unknown=true and keep confidence <= 0.5.
4. Never invent numbers, p-values, effect sizes, or sample sizes.
5. Output strictly valid JSON object matching the ClaimSet schema.
6. Do not include limitations unless the limitation wording is directly supported by the provided source text.
"""
        if persona_hint:
            self.system_prompt += f"\n\nPersona override:\n{persona_hint}\n"

    def analyze(self, doc: DocumentArtifact | DocumentArtifactV2) -> Optional[ClaimSet]:
        """
        Analyzes the DocumentArtifact and returns a ClaimSet.
        """
        header = get_artifact_header(doc)
        sections = self._collect_sections(doc)
        chunks = self._collect_chunks(sections)
        table_context = self._build_table_context(doc)

        example_claim = ScientificClaim(
            claim_id="CLM-001",
            type="efficacy",
            statement="Caffeine increases coding speed by 20%.",
            evidence_spans=[
                EvidenceSpan(
                    page=2,
                    chunk_id="p03_c01",
                    raw_text="Speed increased by 20% compared to placebo...",
                    quote="Speed increased by 20%",
                    rationale="The results section explicitly states the percentage increase derived from the t-test.",
                    section="page_3",
                    source_span=[0, 26],
                )
            ],
            limitations=[],
            confidence=0.9
        )
        example_set = ClaimSet(doc_id="doi:10.1234/ex", claims=[example_claim])
        example_json = example_set.model_dump_json(indent=2)

        logger.info("Reader Agent analyzing: %s", header.title)
        attempts = self._build_attempt_contexts(sections=sections)
        best_claimset: ClaimSet | None = None

        for attempt_idx, context in enumerate(attempts, start=1):
            if not context.strip():
                continue
            prompt = self._build_extraction_prompt(
                doc_id=header.doc_id,
                title=header.title,
                authors=header.authors,
                paper_context=context,
                table_context=table_context,
                example_json=example_json,
                min_claims=self.min_claims,
                attempt_idx=attempt_idx,
            )

            try:
                result = self.adapter.generate(prompt, format="json")
            except Exception as exc:
                if is_timeout_exception(exc):
                    raise
                logger.error("Reader attempt %s failed: %s", attempt_idx, exc)
                continue

            parsed = self._parse_claimset_payload(result.text, expected_doc_id=header.doc_id, chunks=chunks)
            if parsed is None:
                logger.warning("Reader attempt %s: JSON/schema parse failed", attempt_idx)
                continue

            parsed = enforce_claimset_evidence_policy(parsed)
            if best_claimset is None or len(parsed.claims) > len(best_claimset.claims):
                best_claimset = parsed

            if len(parsed.claims) >= self.min_claims:
                logger.info("Reader attempt %s succeeded with %s claims", attempt_idx, len(parsed.claims))
                return parsed

        if best_claimset is not None and best_claimset.claims:
            logger.info("Reader returning best non-empty claimset from retries: %s claims", len(best_claimset.claims))
            return best_claimset

        heuristic_claims = self._build_heuristic_claims(chunks=chunks, max_claims=max(3, self.min_claims))
        if heuristic_claims:
            logger.warning("Reader fallback heuristic applied: %s claims", len(heuristic_claims))
            fallback = ClaimSet(doc_id=header.doc_id, claims=heuristic_claims)
            return enforce_claimset_evidence_policy(fallback)

        if best_claimset is not None:
            return best_claimset
        return ClaimSet(doc_id=header.doc_id, claims=[])

    def _collect_sections(self, doc: DocumentArtifact | DocumentArtifactV2) -> list[_SectionRecord]:
        records: list[_SectionRecord] = []
        page_by_name: dict[str, int | None] = {}

        if isinstance(doc, DocumentArtifact):
            for section in doc.sections:
                page_value = section.page_start if isinstance(section.page_start, int) and section.page_start >= 0 else None
                page_by_name[section.name] = page_value

        for section in iter_text_sections(doc):
            text = (section.text or "").strip()
            if not text:
                continue
            parsed_from_name = self._page_from_section_name(section.name)
            page = page_by_name.get(section.name, parsed_from_name)
            records.append(_SectionRecord(name=section.name, text=text, page=page))
        return records

    @staticmethod
    def _page_from_section_name(name: str) -> int | None:
        match = re.match(r"^page_(\d+)$", (name or "").strip().lower())
        if not match:
            return None
        page_1_indexed = int(match.group(1))
        if page_1_indexed <= 0:
            return None
        return page_1_indexed - 1

    def _build_attempt_contexts(self, *, sections: list[_SectionRecord]) -> list[str]:
        chunks = self._collect_chunks(sections)
        primary = self._render_chunk_context(chunks, char_budget=self.max_context_chars)

        focused_sections = [s for s in sections if self._is_priority_section(s.name)]
        focused = self._render_chunk_context(
            self._collect_chunks(focused_sections if focused_sections else sections),
            char_budget=min(self.max_context_chars, 12000),
        )

        sentence_focus = self._render_sentence_focus_context(chunks, max_sentences=18)
        return [primary, focused, sentence_focus]

    @staticmethod
    def _is_priority_section(name: str) -> bool:
        lowered = (name or "").strip().lower()
        keywords = ("abstract", "result", "discussion", "conclusion", "finding")
        return any(k in lowered for k in keywords)

    def _render_chunk_context(self, chunks: list[_ChunkRecord], *, char_budget: int) -> str:
        if not chunks:
            return ""

        def _priority_key(record: _ChunkRecord) -> tuple[int, int]:
            name = record.section.lower()
            if "abstract" in name:
                return (0, 0)
            if "result" in name:
                return (1, 0)
            if "discussion" in name or "conclusion" in name:
                return (2, 0)
            if "method" in name:
                return (3, 0)
            return (4, 0)

        ordered = sorted(chunks, key=_priority_key)
        pieces: list[str] = []
        used = 0
        for rec in ordered:
            page_label = rec.page if rec.page is not None else "unknown"
            text = rec.text
            if len(text) > 2500:
                text = text[:2500] + "\n...[truncated]"
            piece = f"[CHUNK {rec.chunk_id} | section={rec.section} | page={page_label}]\n{text}\n"
            projected = used + len(piece)
            if projected > char_budget and pieces:
                break
            if projected > char_budget:
                remain = max(char_budget - used, 0)
                if remain <= 120:
                    break
                piece = piece[:remain]
            pieces.append(piece)
            used += len(piece)
            if used >= char_budget:
                break
        return "\n".join(pieces)

    def _render_sentence_focus_context(self, chunks: list[_ChunkRecord], *, max_sentences: int) -> str:
        candidates = self._select_candidate_sentences(chunks, max_sentences=max_sentences)
        if not candidates:
            return self._render_chunk_context(chunks, char_budget=min(self.max_context_chars, 8000))

        lines: list[str] = []
        for idx, item in enumerate(candidates, start=1):
            lines.append(
                f"{idx}. [chunk_id={item['chunk_id']}, section={item['section']}, page={item['page']}] {item['sentence']}"
            )
        return "\n".join(lines)

    def _build_table_context(self, doc: DocumentArtifact | DocumentArtifactV2) -> str:
        tables = list(getattr(doc, "tables", []) or [])
        if not tables:
            return ""

        snippets: list[str] = []
        for idx, table in enumerate(tables[:3], start=1):
            if isinstance(table, dict):
                table_id = str(table.get("table_id") or f"T{idx}")
                caption = str(table.get("caption") or "")
                data = table.get("data") or []
                source_page = table.get("source_page")
            else:
                table_id = str(getattr(table, "table_id", f"T{idx}") or f"T{idx}")
                caption = str(getattr(table, "caption", "") or "")
                data = getattr(table, "data", []) or []
                source_page = getattr(table, "source_page", None)

            row_preview = []
            for row in data[:3]:
                if isinstance(row, list):
                    row_preview.append(" | ".join(str(cell) for cell in row[:8]))
            preview_text = "; ".join(row_preview) if row_preview else "no table rows parsed"
            snippets.append(
                f"[TABLE {table_id} | page={source_page}] caption={caption}\nrows={preview_text}"
            )
        return "\n".join(snippets)

    def _build_extraction_prompt(
        self,
        *,
        doc_id: str,
        title: str,
        authors: list[str],
        paper_context: str,
        table_context: str,
        example_json: str,
        min_claims: int,
        attempt_idx: int,
    ) -> str:
        return f"""
{self.system_prompt}

TASK:
Extract scientific claims from the provided paper snippets.

STRICT ACCURACY RULES:
1. Use only evidence that appears verbatim in the provided snippets.
2. Every claim must include at least one evidence_spans item with raw_text/quote and location info.
3. Copy numbers exactly as written in evidence text.
4. If confidence is low, set unknown=true and unknown_reason.
5. Do not output an empty claims array unless there is truly no claim-like result in the snippets.
6. When a text snippet includes a CHUNK id, reuse that exact chunk_id. Do not invent placeholder ids.
7. Do not include a limitation unless the supporting wording appears in the provided snippets.

ATTEMPT: {attempt_idx}
TARGET_MIN_CLAIMS: {min_claims}

PAPER:
- doc_id: "{doc_id}"
- title: "{title}"
- authors: "{", ".join(authors)}"

TEXT SNIPPETS:
{paper_context}

TABLE SNIPPETS:
{table_context if table_context else "N/A"}

EXAMPLE OUTPUT FORMAT:
{example_json}

Output requirements:
- Return JSON object only.
- Root keys: doc_id, claims.
- doc_id must be exactly "{doc_id}".
"""

    def _parse_claimset_payload(self, raw_text: str, *, expected_doc_id: str, chunks: list[_ChunkRecord]) -> ClaimSet | None:
        cleaned = (raw_text or "").strip()
        if not cleaned:
            return None

        try:
            payload = repair_and_parse_json(cleaned)
        except json.JSONDecodeError:
            logger.debug("Reader parse failed for payload prefix: %s", cleaned[:200])
            return None

        claimset_payload = self._unwrap_claimset(payload)
        if not isinstance(claimset_payload, dict):
            return None

        raw_claims = claimset_payload.get("claims")
        if not isinstance(raw_claims, list):
            raw_claims = []

        normalized_claims: list[dict[str, Any]] = []
        for idx, item in enumerate(raw_claims, start=1):
            normalized = self._normalize_claim_payload(item, fallback_claim_id=f"CLM-{idx:03d}", chunks=chunks)
            if normalized is not None:
                normalized_claims.append(normalized)

        normalized_payload = {
            "doc_id": expected_doc_id,
            "claims": normalized_claims,
        }
        try:
            return ClaimSet.model_validate(normalized_payload)
        except ValidationError:
            valid_claims: list[ScientificClaim] = []
            for item in normalized_claims:
                try:
                    valid_claims.append(ScientificClaim.model_validate(item))
                except ValidationError:
                    continue
            return ClaimSet(doc_id=expected_doc_id, claims=valid_claims)

    @staticmethod
    def _unwrap_claimset(payload: dict[str, Any]) -> dict[str, Any]:
        if isinstance(payload.get("claims"), list):
            return payload
        nested = payload.get("ClaimSet")
        if isinstance(nested, dict) and isinstance(nested.get("claims"), list):
            return nested
        nested = payload.get("claimset")
        if isinstance(nested, dict) and isinstance(nested.get("claims"), list):
            return nested
        return payload

    def _normalize_claim_payload(self, claim: Any, *, fallback_claim_id: str, chunks: list[_ChunkRecord]) -> dict[str, Any] | None:
        if not isinstance(claim, dict):
            return None
        statement = str(claim.get("statement") or "").strip()
        if not statement:
            return None

        claim_id = str(claim.get("claim_id") or fallback_claim_id)
        claim_type = str(claim.get("type") or "finding").strip() or "finding"
        confidence = self._coerce_confidence(claim.get("confidence"))
        evidence_spans_raw = claim.get("evidence_spans")
        evidence_spans = self._normalize_evidence_spans(
            evidence_spans_raw if isinstance(evidence_spans_raw, list) else [],
            statement=statement,
            chunks=chunks,
        )
        limitations_raw = claim.get("limitations") if isinstance(claim.get("limitations"), list) else []
        limitations = self._normalize_limitations(limitations_raw, evidence_spans=evidence_spans, chunks=chunks)

        unknown = bool(claim.get("unknown", False))
        unknown_reason = claim.get("unknown_reason")
        if unknown_reason is not None:
            unknown_reason = str(unknown_reason).strip() or None

        return {
            "claim_id": claim_id,
            "type": claim_type,
            "statement": statement,
            "evidence_spans": evidence_spans,
            "limitations": limitations,
            "confidence": confidence,
            "unknown": unknown,
            "unknown_reason": unknown_reason,
        }

    def _normalize_limitations(
        self,
        limitations_raw: list[Any],
        *,
        evidence_spans: list[dict[str, Any]],
        chunks: list[_ChunkRecord],
    ) -> list[str]:
        limitations = [str(item).strip() for item in limitations_raw if str(item).strip()]
        if not limitations:
            return []

        source_texts: list[str] = []
        for span in evidence_spans:
            raw_text = self._normalize_match_text(str(span.get("raw_text") or ""))
            quote = self._normalize_match_text(str(span.get("quote") or ""))
            if raw_text:
                source_texts.append(raw_text)
            if quote:
                source_texts.append(quote)

        for chunk in chunks:
            normalized = self._normalize_match_text(chunk.text)
            if normalized:
                source_texts.append(normalized)

        filtered: list[str] = []
        for limitation in limitations:
            if self._limitation_has_source_support(limitation, source_texts):
                filtered.append(limitation)
            else:
                logger.info("Reader dropped unsupported limitation: %s", limitation)
        return filtered

    @staticmethod
    def _normalize_match_text(text: str) -> str:
        lowered = (text or "").lower()
        lowered = re.sub(r"[^a-z0-9]+", " ", lowered)
        return " ".join(lowered.split())

    @classmethod
    def _limitation_has_source_support(cls, limitation: str, source_texts: list[str]) -> bool:
        normalized = cls._normalize_match_text(limitation)
        if not normalized:
            return False
        if any(normalized in text for text in source_texts):
            return True

        tokens = [
            token
            for token in normalized.split()
            if len(token) >= 4 and token not in _LIMITATION_STOPWORDS
        ]
        if not tokens:
            return False

        for text in source_texts:
            words = set(text.split())
            if all(token in words for token in tokens):
                return True
        return False

    def _normalize_evidence_spans(self, spans: list[Any], *, statement: str, chunks: list[_ChunkRecord]) -> list[dict[str, Any]]:
        normalized: list[dict[str, Any]] = []
        known_chunk_ids = {chunk.chunk_id for chunk in chunks}
        for idx, span in enumerate(spans, start=1):
            if not isinstance(span, dict):
                continue
            raw_text = str(span.get("raw_text") or "").strip()
            quote = str(span.get("quote") or "").strip()
            if not raw_text and quote:
                raw_text = quote
            if not raw_text:
                continue

            page = self._coerce_int(span.get("page"))
            bbox_pdf = self._normalize_bbox_pdf(span.get("bbox_pdf") or span.get("bboxPdf"))
            bbox_pct = self._normalize_bbox_pct(span.get("bbox_pct") or span.get("bboxPct"))
            highlight_source = self._normalize_highlight_source(
                span.get("highlight_source") or span.get("highlightSource"),
                bbox_pdf=bbox_pdf,
                bbox_pct=bbox_pct,
                has_text=bool(raw_text or quote),
            )
            matched_chunk = self._match_chunk_record(
                text_candidates=[quote, raw_text],
                page=self._coerce_int(span.get("page")),
                declared_chunk_id=str(span.get("chunk_id") or "").strip() or None,
                chunks=chunks,
            )
            if matched_chunk is not None:
                supporting_excerpt = self._select_supporting_excerpt(statement=statement, chunk_text=matched_chunk["text"])
                if supporting_excerpt and not self._source_contains_text(matched_chunk["text"], quote):
                    raw_text = supporting_excerpt
                    quote = self._best_supported_quote(statement=statement, source_text=supporting_excerpt)
                current_score = self._support_overlap_score(statement, f"{raw_text} {quote}".strip())
                excerpt_score = self._support_overlap_score(statement, supporting_excerpt)
                if supporting_excerpt and excerpt_score > current_score:
                    raw_text = supporting_excerpt
                    quote = self._best_supported_quote(statement=statement, source_text=supporting_excerpt)
            source_span = span.get("source_span")
            if matched_chunk is not None:
                excerpt_text = quote or raw_text
                excerpt_loc = find_text_location(matched_chunk["text"], excerpt_text)
                if excerpt_loc is None and raw_text:
                    excerpt_loc = find_text_location(matched_chunk["text"], raw_text)
                if excerpt_loc is not None:
                    source_span = [excerpt_loc[0], excerpt_loc[1]]
                else:
                    source_span = [matched_chunk["char_start"], matched_chunk["char_end"]]
            else:
                if not (isinstance(source_span, list) and len(source_span) >= 2):
                    source_span = [0, min(len(raw_text), 160)]
                source_span = [
                    self._coerce_int(source_span[0], default=0),
                    self._coerce_int(source_span[1], default=min(len(raw_text), 160)),
                ]

            chunk_id = str(span.get("chunk_id") or "").strip() or None
            if chunk_id not in known_chunk_ids:
                chunk_id = matched_chunk["chunk_id"] if matched_chunk is not None else "unknown"
            page = self._coerce_int(span.get("page"))
            if matched_chunk is not None:
                page = matched_chunk["page"]
            section_name = str(span.get("section") or "").strip() or None
            if matched_chunk is not None:
                section_name = matched_chunk["section"]

            normalized.append(
                {
                    "page": page,
                    "chunk_id": chunk_id,
                    "raw_text": raw_text,
                    "quote": quote or self._truncate_words(raw_text, 24),
                    "rationale": str(span.get("rationale") or "Direct evidence snippet from source text."),
                    "section": section_name or "unknown",
                    "source_span": source_span,
                    "char_start": source_span[0],
                    "char_end": source_span[1],
                    "bbox_pdf": bbox_pdf,
                    "bbox_pct": bbox_pct,
                    "highlight_source": highlight_source,
                    "table_id": span.get("table_id"),
                    "cell_id": span.get("cell_id"),
                }
            )

        if normalized:
            return normalized

        # If model omitted evidence but gave a statement, keep conservative one-span fallback.
        return [
            {
                "page": inferred["page"] if inferred is not None else None,
                "chunk_id": inferred["chunk_id"] if inferred is not None else "unknown",
                "raw_text": statement,
                "quote": self._truncate_words(statement, 24),
                "rationale": "Fallback evidence created from claim statement due missing model span.",
                "section": inferred["section"] if inferred is not None else "unknown",
                "source_span": (
                    [inferred["char_start"], inferred["char_end"]]
                    if inferred is not None
                    else [0, min(len(statement), 160)]
                ),
                "char_start": inferred["char_start"] if inferred is not None else 0,
                "char_end": inferred["char_end"] if inferred is not None else min(len(statement), 160),
                "highlight_source": "approx",
            }
            for inferred in [self._match_chunk_record(text_candidates=[statement], page=None, declared_chunk_id=None, chunks=chunks)]
        ]

    @staticmethod
    def _coerce_int(value: Any, default: int | None = None) -> int | None:
        if isinstance(value, int):
            return value
        if isinstance(value, float) and value.is_integer():
            return int(value)
        if isinstance(value, str) and value.strip().isdigit():
            return int(value.strip())
        return default

    @staticmethod
    def _normalize_bbox_pdf(value: Any) -> list[float] | None:
        if not isinstance(value, list) or len(value) != 4:
            return None
        parsed: list[float] = []
        for item in value:
            if not isinstance(item, (int, float)):
                return None
            parsed.append(float(item))
        return parsed

    @staticmethod
    def _normalize_bbox_pct(value: Any) -> dict[str, float] | None:
        if not isinstance(value, dict):
            return None
        required = ("left", "top", "width", "height")
        out: dict[str, float] = {}
        for key in required:
            parsed = value.get(key)
            if not isinstance(parsed, (int, float)):
                return None
            out[key] = float(parsed)
        return out

    @staticmethod
    def _normalize_highlight_source(
        value: Any,
        *,
        bbox_pdf: list[float] | None,
        bbox_pct: dict[str, float] | None,
        has_text: bool,
    ) -> str:
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"bbox", "text_match", "approx"}:
                return normalized
        if bbox_pdf or bbox_pct:
            return "bbox"
        if has_text:
            return "text_match"
        return "approx"

    @staticmethod
    def _coerce_confidence(value: Any) -> float:
        if isinstance(value, (int, float)):
            return float(max(0.0, min(1.0, value)))
        if isinstance(value, str):
            try:
                parsed = float(value.strip())
                return float(max(0.0, min(1.0, parsed)))
            except ValueError:
                return 0.5
        return 0.5

    def _build_heuristic_claims(self, *, chunks: list[_ChunkRecord], max_claims: int) -> list[ScientificClaim]:
        candidates = self._select_candidate_sentences(chunks, max_sentences=max_claims * 3)
        if not candidates:
            return []

        claims: list[ScientificClaim] = []
        used_statements: set[str] = set()
        for idx, candidate in enumerate(candidates, start=1):
            sentence = candidate["sentence"]
            key = " ".join(sentence.lower().split())
            if key in used_statements:
                continue
            used_statements.add(key)

            page = candidate["page"]
            score = int(candidate["score"])
            confidence = min(0.62, 0.45 + score * 0.03)
            claim_type = self._infer_claim_type(sentence)

            evidence = EvidenceSpan(
                page=page,
                chunk_id=str(candidate["chunk_id"] or "unknown"),
                raw_text=sentence,
                quote=self._truncate_words(sentence, 24),
                rationale="Heuristic fallback: sentence selected from source text by statistical/result cue.",
                section=str(candidate["section"]),
                source_span=[candidate["char_start"], candidate["char_end"]],
                char_start=candidate["char_start"],
                char_end=candidate["char_end"],
                highlight_source="text_match",
            )
            claims.append(
                ScientificClaim(
                    claim_id=f"CLM-H{idx:03d}",
                    type=claim_type,
                    statement=sentence,
                    evidence_spans=[evidence],
                    limitations=["Heuristic fallback extraction; manual review recommended."],
                    confidence=confidence,
                    unknown=True,
                    unknown_reason="HEURISTIC_BACKFILL",
                )
            )
            if len(claims) >= max_claims:
                break
        return claims

    def _select_candidate_sentences(self, chunks: list[_ChunkRecord], *, max_sentences: int) -> list[dict[str, Any]]:
        candidates: list[dict[str, Any]] = []
        for chunk in chunks:
            for sentence in _SENTENCE_SPLIT_RE.split(chunk.text):
                normalized = " ".join(sentence.strip().split())
                if len(normalized) < 35:
                    continue
                score = self._score_sentence(normalized)
                if score <= 0:
                    continue
                loc = find_text_location(chunk.text, normalized)
                if loc is None:
                    continue
                candidates.append(
                    {
                        "sentence": normalized,
                        "section": chunk.section,
                        "page": chunk.page,
                        "chunk_id": chunk.chunk_id,
                        "char_start": loc[0],
                        "char_end": loc[1],
                        "score": score,
                    }
                )

        candidates.sort(key=lambda item: (item["score"], len(item["sentence"])), reverse=True)
        return candidates[:max_sentences]

    @staticmethod
    def _score_sentence(sentence: str) -> int:
        score = 0
        if _STAT_CUE_RE.search(sentence):
            score += 4
        if _RESULT_CUE_RE.search(sentence):
            score += 3
        if any(ch.isdigit() for ch in sentence):
            score += 1
        if 45 <= len(sentence) <= 320:
            score += 1
        return score

    @staticmethod
    def _infer_claim_type(sentence: str) -> str:
        lowered = sentence.lower()
        if any(token in lowered for token in ("adverse", "toxicity", "safety", "side effect")):
            return "safety"
        if any(token in lowered for token in ("pathway", "mechanism", "protein", "gene", "receptor")):
            return "mechanism"
        if any(token in lowered for token in ("method", "protocol", "assay")):
            return "methods"
        return "efficacy"

    @staticmethod
    def _truncate_words(text: str, limit: int) -> str:
        words = str(text or "").split()
        if len(words) <= limit:
            return " ".join(words)
        return " ".join(words[:limit])

    @classmethod
    def _support_overlap_score(cls, statement: str, candidate_text: str) -> int:
        statement_tokens = cls._support_tokens(statement)
        if not statement_tokens:
            return 0
        candidate_tokens = set(cls._support_tokens(candidate_text))
        return sum(1 for token in statement_tokens if token in candidate_tokens)

    @classmethod
    def _support_tokens(cls, text: str) -> list[str]:
        normalized = cls._normalize_match_text(text)
        tokens: list[str] = []
        for token in normalized.split():
            if len(token) < 4 or token in _EVIDENCE_STOPWORDS:
                continue
            tokens.append(cls._support_token_root(token))
        return tokens

    @staticmethod
    def _support_token_root(token: str) -> str:
        if token.startswith("direct"):
            return "direct"
        if token.startswith("inhibit"):
            return "inhibit"
        if token.startswith("chang"):
            return "change"
        if token.startswith("protein"):
            return "protein"
        if token.startswith("activit"):
            return "activity"
        return token

    @classmethod
    def _select_supporting_excerpt(cls, *, statement: str, chunk_text: str) -> str:
        chunk_text = str(chunk_text or "").strip()
        if not chunk_text:
            return ""
        support_tokens = cls._support_tokens(statement)
        if not support_tokens:
            return ""

        sentences = [segment.strip() for segment in _SENTENCE_SPLIT_RE.split(chunk_text) if segment.strip()]
        if not sentences:
            return ""

        scored: list[tuple[int, int]] = []
        support_token_set = set(support_tokens)
        for idx, sentence in enumerate(sentences):
            score = cls._support_overlap_score(statement, sentence)
            if score > 0:
                scored.append((idx, score))
        if not scored:
            return ""

        scored.sort(key=lambda item: (item[1], len(sentences[item[0]])), reverse=True)
        best_idx, _ = scored[0]
        chosen_indices = {best_idx}
        covered = set(cls._support_tokens(sentences[best_idx]))

        for neighbor_idx in (best_idx - 1, best_idx + 1):
            if not (0 <= neighbor_idx < len(sentences)):
                continue
            neighbor_tokens = set(cls._support_tokens(sentences[neighbor_idx]))
            if (neighbor_tokens & support_token_set) - covered:
                chosen_indices.add(neighbor_idx)
                covered |= neighbor_tokens

        ordered = [sentences[idx] for idx in sorted(chosen_indices)]
        return " ".join(ordered)

    @classmethod
    def _best_supported_quote(cls, *, statement: str, source_text: str) -> str:
        source_text = str(source_text or "").strip()
        if not source_text:
            return ""
        sentences = [segment.strip() for segment in _SENTENCE_SPLIT_RE.split(source_text) if segment.strip()]
        if not sentences:
            return cls._truncate_words(source_text, 32)
        scored = sorted(
            ((sentence, cls._support_overlap_score(statement, sentence)) for sentence in sentences),
            key=lambda item: (item[1], len(item[0])),
            reverse=True,
        )
        best_sentence, best_score = scored[0]
        if best_score <= 0:
            return cls._truncate_words(source_text, 32)
        return best_sentence

    @classmethod
    def _source_contains_text(cls, source_text: str, candidate_text: str) -> bool:
        source_norm = cls._normalize_match_text(source_text)
        candidate_norm = cls._normalize_match_text(candidate_text)
        return bool(source_norm and candidate_norm and candidate_norm in source_norm)

    def _collect_chunks(self, sections: list[_SectionRecord]) -> list[_ChunkRecord]:
        chunks: list[_ChunkRecord] = []
        for section_ordinal, section in enumerate(sections, start=1):
            page_hint = section.page + 1 if isinstance(section.page, int) and section.page >= 0 else None
            for chunk_ordinal, chunk in enumerate(
                self._chunk_text_with_offsets(section.text, chunk_size=READER_CHUNK_SIZE, overlap=READER_CHUNK_OVERLAP),
                start=1,
            ):
                chunks.append(
                    _ChunkRecord(
                        chunk_id=make_chunk_id(
                            page_hint=page_hint,
                            section_ordinal=section_ordinal,
                            chunk_ordinal=chunk_ordinal,
                        ),
                        section=section.name,
                        page=section.page,
                        text=chunk["text"],
                        char_start=chunk["start"],
                        char_end=chunk["end"],
                    )
                )
        return chunks

    def _match_chunk_record(
        self,
        *,
        text_candidates: list[str],
        page: int | None,
        declared_chunk_id: str | None,
        chunks: list[_ChunkRecord],
    ) -> dict[str, Any] | None:
        preferred_chunks = [chunk for chunk in chunks if declared_chunk_id and chunk.chunk_id == declared_chunk_id]
        if preferred_chunks:
            matched = self._locate_in_chunks(preferred_chunks, text_candidates)
            if matched is not None:
                return matched

        if isinstance(page, int):
            page_chunks = [chunk for chunk in chunks if chunk.page == page]
            matched = self._locate_in_chunks(page_chunks, text_candidates)
            if matched is not None:
                return matched

        return self._locate_in_chunks(chunks, text_candidates, require_unique=True)

    def _locate_in_chunks(
        self,
        chunks: list[_ChunkRecord],
        text_candidates: list[str],
        *,
        require_unique: bool = False,
    ) -> dict[str, Any] | None:
        candidates = [str(text or "").strip() for text in text_candidates if str(text or "").strip()]
        candidates.sort(key=len, reverse=True)
        for text in candidates:
            matches: list[dict[str, Any]] = []
            for chunk in chunks:
                location = find_text_location(chunk.text, text)
                if location is None:
                    continue
                matches.append(
                    {
                        "chunk_id": chunk.chunk_id,
                        "section": chunk.section,
                        "page": chunk.page,
                        "text": chunk.text,
                        "char_start": location[0],
                        "char_end": location[1],
                    }
                )
            if not matches:
                continue
            if require_unique and len(matches) != 1:
                continue
            return matches[0]
        return None

    @staticmethod
    def _chunk_text_with_offsets(text: str, *, chunk_size: int, overlap: int) -> list[dict[str, Any]]:
        if not text:
            return []
        chunks: list[dict[str, Any]] = []
        start = 0
        text_len = len(text)
        while start < text_len:
            end = min(start + chunk_size, text_len)
            chunk_text = text[start:end]
            chunks.append({"start": start, "end": end, "text": chunk_text})
            if end == text_len:
                break
            start += chunk_size - overlap
        return chunks
