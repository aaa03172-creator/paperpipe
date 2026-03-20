from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.contracts.output_bridge import (
    bind_claim_cards_to_run,
    claim_cards_from_claimset_payload,
    normalize_claimset_payload,
)
from src.schemas.chat import ChatEvidenceRef, ChatLocator
from src.schemas.method_comparison import ComparisonCell, ComparisonRow, MethodComparisonFieldId
from src.schemas.skills import SkillClaimCard, SkillClaimEvidence
from src.services.runtime_paths import artifacts_root as default_artifacts_root
from src.services.runtime_paths import preferred_artifact_paper_dir


_METHOD_VALUE_LABEL_PATTERNS: dict[MethodComparisonFieldId, tuple[re.Pattern[str], ...]] = {
    "intervention": (
        re.compile(r"\bintervention(?:\s+group)?\s*(?:was|were|:)\s*(?P<value>[^.;\n]+)", re.IGNORECASE),
        re.compile(r"\btreatment(?:\s+group)?\s*(?:was|were|:)\s*(?P<value>[^.;\n]+)", re.IGNORECASE),
    ),
    "comparator": (
        re.compile(r"\bcomparator\s*(?:was|were|:)\s*(?P<value>[^.;\n]+)", re.IGNORECASE),
        re.compile(r"\bcontrol(?:\s+group)?\s*(?:was|were|:)\s*(?P<value>[^.;\n]+)", re.IGNORECASE),
    ),
    "duration_or_timepoint": (
        re.compile(r"\bduration(?:\s+or\s+timepoint)?\s*(?:was|were|:)\s*(?P<value>[^.;\n]+)", re.IGNORECASE),
        re.compile(r"\btimepoint\s*(?:was|were|:)\s*(?P<value>[^.;\n]+)", re.IGNORECASE),
        re.compile(r"\bfor\s+(?P<value>\d+\s*(?:day|days|week|weeks|month|months|year|years))\b", re.IGNORECASE),
        re.compile(
            r"\bat\s+(?P<value>(?:week|day|month|year)\s*\d+|baseline|follow-?up)\b",
            re.IGNORECASE,
        ),
        re.compile(r"\bafter\s+(?P<value>\d+\s*(?:day|days|week|weeks|month|months|year|years))\b", re.IGNORECASE),
    ),
    "primary_readout": (
        re.compile(
            r"\bprimary\s+(?:readout|endpoint|outcome)\s*(?:was|were|:)?\s*(?P<value>[^.;\n]+)",
            re.IGNORECASE,
        ),
    ),
    "sample_size": (
        re.compile(r"\bsample\s+size\s*(?:was|were|:)?\s*(?P<value>\d+)\b", re.IGNORECASE),
        re.compile(r"\bn\s*=\s*(?P<value>\d+)\b", re.IGNORECASE),
    ),
}
_PAIR_PATTERN = re.compile(
    r"(?P<left>[^.;\n]{2,120}?)\s+(?:versus|vs\.?|compared with)\s+(?P<right>[^.;\n]{2,120}?)(?:[.;,\n]|$)",
    re.IGNORECASE,
)
_LEADING_CONTEXT_RE = re.compile(
    r"^(?:participants|patients|subjects|mice|rats|the participants|the patients|the subjects)\s+"
    r"(?:received|were treated with|were given|treated with|given|assigned to)\s+",
    re.IGNORECASE,
)
_VALUE_ARTICLE_RE = re.compile(r"^(?:the|an|a)\s+", re.IGNORECASE)
_TRAILING_GROUP_RE = re.compile(r"\s+group$", re.IGNORECASE)
_MULTISPACE_RE = re.compile(r"\s+")

_STRUCTURED_FIELD_ALIASES: dict[MethodComparisonFieldId, tuple[str, ...]] = {
    "intervention": ("intervention", "exposure", "treatment", "intervention_name"),
    "comparator": ("comparator", "control", "comparison", "control_condition"),
    "duration_or_timepoint": (
        "duration_or_timepoint",
        "duration",
        "timepoint",
        "follow_up",
        "followup",
        "duration_weeks",
        "timepoint_weeks",
    ),
    "primary_readout": ("primary_readout", "primary_endpoint", "primary_outcome", "endpoint", "readout"),
    "sample_size": ("sample_size", "n"),
}


@dataclass(frozen=True)
class ClaimsetResolvedClaimEntry:
    raw_claim: dict[str, Any]
    claim_card: SkillClaimCard


@dataclass(frozen=True)
class ClaimsetResolvedSource:
    paper_id: str
    run_id: str
    claimset_path: Path
    claimset_doc_id: str | None
    entries: tuple[ClaimsetResolvedClaimEntry, ...]


@dataclass(frozen=True)
class _FieldSupport:
    value: str | int
    normalized_value: str | int
    status: str
    evidence_refs: tuple[ChatEvidenceRef, ...]


def load_claimset_resolved_source(
    paper_id: str,
    *,
    root: Path | None = None,
) -> ClaimsetResolvedSource:
    artifacts_path = (root or default_artifacts_root()).expanduser().resolve()
    paper_dir = preferred_artifact_paper_dir(paper_id, root=artifacts_path)
    if not paper_dir.exists() or not paper_dir.is_dir():
        raise FileNotFoundError(f"Artifacts directory not found for paper_id={paper_id}")

    run_dirs = [
        path
        for path in paper_dir.iterdir()
        if path.is_dir() and (path / "claimset.resolved.json").exists()
    ]
    if not run_dirs:
        raise FileNotFoundError(f"claimset.resolved.json not found for paper_id={paper_id}")

    run_dirs.sort(key=lambda path: (path.stat().st_mtime, path.name), reverse=True)
    run_dir = run_dirs[0]
    claimset_path = run_dir / "claimset.resolved.json"

    try:
        payload = json.loads(claimset_path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ValueError(f"Failed to parse {claimset_path}: {exc}") from exc

    normalized = normalize_claimset_payload(payload)
    if normalized is None:
        raise ValueError(f"claimset.resolved.json did not contain a valid claimset payload: {claimset_path}")

    raw_claims = [claim for claim in normalized.get("claims") or [] if isinstance(claim, dict)]
    claim_cards = bind_claim_cards_to_run(
        claim_cards_from_claimset_payload({"claims": raw_claims}),
        run_dir.name,
    )
    entries = tuple(
        ClaimsetResolvedClaimEntry(raw_claim=raw_claim, claim_card=claim_card)
        for raw_claim, claim_card in zip(raw_claims, claim_cards)
    )
    doc_id = normalized.get("doc_id")
    return ClaimsetResolvedSource(
        paper_id=paper_id,
        run_id=run_dir.name,
        claimset_path=claimset_path,
        claimset_doc_id=str(doc_id).strip() or None if doc_id is not None else None,
        entries=entries,
    )


def build_claimset_comparison_cells(
    source: ClaimsetResolvedSource,
    field_ids: list[MethodComparisonFieldId],
    *,
    paper_slug: str,
) -> list[ComparisonCell]:
    return [_build_claimset_field_cell(source, field_id, paper_slug=paper_slug) for field_id in field_ids]


def build_claimset_comparison_row(
    source: ClaimsetResolvedSource,
    field_ids: list[MethodComparisonFieldId],
    *,
    paper_slug: str,
    title: str | None = None,
    citekey: str | None = None,
) -> ComparisonRow:
    return ComparisonRow(
        paper_id=source.paper_id,
        paper_slug=paper_slug,
        citekey=citekey,
        title=(title or source.claimset_doc_id or source.paper_id),
        cells=build_claimset_comparison_cells(source, field_ids, paper_slug=paper_slug),
    )


def _build_claimset_field_cell(
    source: ClaimsetResolvedSource,
    field_id: MethodComparisonFieldId,
    *,
    paper_slug: str,
) -> ComparisonCell:
    supports: list[_FieldSupport] = []
    for entry in source.entries:
        supports.extend(_extract_supports_for_entry(entry, field_id, paper_slug=paper_slug))

    if not supports:
        return ComparisonCell(
            field_id=field_id,
            status="missing",
            note="No evidence-backed support found in claimset.resolved.json.",
        )

    grouped: dict[str, dict[str, Any]] = {}
    for support in supports:
        group_key = _support_group_key(support.normalized_value)
        bucket = grouped.setdefault(
            group_key,
            {
                "value": support.value,
                "normalized_value": support.normalized_value,
                "has_explicit": False,
                "evidence_refs": [],
            },
        )
        if support.status == "explicit":
            bucket["has_explicit"] = True
        bucket["evidence_refs"] = _dedupe_evidence_refs(
            [*bucket["evidence_refs"], *support.evidence_refs],
        )

    if len(grouped) == 1:
        only_bucket = next(iter(grouped.values()))
        status = "explicit" if only_bucket["has_explicit"] else "inferred"
        note = None
        if status == "inferred":
            note = "Derived from claimset evidence quote; the field was not explicitly stated in the claim text."
        return ComparisonCell(
            field_id=field_id,
            value=only_bucket["value"],
            normalized_value=only_bucket["normalized_value"],
            status=status,
            note=note,
            evidence_refs=only_bucket["evidence_refs"],
        )

    conflict_values = [bucket["value"] for bucket in grouped.values()]
    joined = " | ".join(str(value) for value in conflict_values)
    conflict_refs: list[ChatEvidenceRef] = []
    for bucket in grouped.values():
        conflict_refs = _dedupe_evidence_refs([*conflict_refs, *bucket["evidence_refs"]])
    return ComparisonCell(
        field_id=field_id,
        value=joined,
        normalized_value=joined.lower(),
        status="conflict",
        note=f"Conflicting values from claimset.resolved.json: {joined}",
        evidence_refs=conflict_refs,
    )


def _extract_supports_for_entry(
    entry: ClaimsetResolvedClaimEntry,
    field_id: MethodComparisonFieldId,
    *,
    paper_slug: str,
) -> list[_FieldSupport]:
    supports: list[_FieldSupport] = []
    claim_refs = tuple(_claim_evidence_refs(entry.claim_card, paper_slug=paper_slug))

    structured_value = _extract_structured_value(entry.raw_claim, field_id)
    if structured_value is not None and claim_refs:
        supports.append(
            _FieldSupport(
                value=structured_value,
                normalized_value=_normalize_field_value(field_id, structured_value),
                status="explicit",
                evidence_refs=claim_refs,
            )
        )

    if claim_refs:
        for extracted in _extract_values_from_text(field_id, entry.claim_card.claim):
            supports.append(
                _FieldSupport(
                    value=extracted,
                    normalized_value=_normalize_field_value(field_id, extracted),
                    status="explicit",
                    evidence_refs=claim_refs,
                )
            )

    for evidence in entry.claim_card.evidence:
        evidence_ref = _evidence_ref(evidence, paper_slug=paper_slug)
        for extracted in _extract_values_from_text(field_id, evidence.text):
            supports.append(
                _FieldSupport(
                    value=extracted,
                    normalized_value=_normalize_field_value(field_id, extracted),
                    status="inferred",
                    evidence_refs=(evidence_ref,),
                )
            )
    return supports


def _extract_structured_value(
    raw_claim: dict[str, Any],
    field_id: MethodComparisonFieldId,
) -> str | int | None:
    containers = [raw_claim]
    for key in ("method_facts", "method", "metadata"):
        nested = raw_claim.get(key)
        if isinstance(nested, dict):
            containers.append(nested)

    aliases = _STRUCTURED_FIELD_ALIASES[field_id]
    for container in containers:
        for alias in aliases:
            if alias not in container:
                continue
            value = _coerce_structured_value(field_id, alias, container.get(alias))
            if value is not None:
                return value

    hard_tags = raw_claim.get("hard_tags")
    if field_id == "sample_size" and isinstance(hard_tags, dict):
        value = _coerce_structured_value(field_id, "sample_size", hard_tags.get("sample_size"))
        if value is not None:
            return value

    return None


def _coerce_structured_value(
    field_id: MethodComparisonFieldId,
    alias: str,
    value: Any,
) -> str | int | None:
    if value is None:
        return None
    if field_id == "sample_size":
        return _coerce_int_value(value)

    if alias in {"duration_weeks", "timepoint_weeks"}:
        weeks = _coerce_int_value(value)
        if weeks is None:
            return None
        return f"{weeks} weeks"

    if isinstance(value, list):
        parts = [_clean_method_value(str(item)) for item in value if str(item).strip()]
        joined = "; ".join(part for part in parts if part)
        return joined or None

    text = _clean_method_value(str(value))
    return text or None


def _extract_values_from_text(
    field_id: MethodComparisonFieldId,
    text: str | None,
) -> list[str | int]:
    if not text:
        return []

    values: list[str | int] = []
    if field_id in {"intervention", "comparator"}:
        match = _PAIR_PATTERN.search(text)
        if match:
            raw_value = match.group("left" if field_id == "intervention" else "right")
            cleaned = _clean_method_value(raw_value)
            if cleaned:
                values.append(cleaned)

    for pattern in _METHOD_VALUE_LABEL_PATTERNS[field_id]:
        for match in pattern.finditer(text):
            raw_value = match.group("value")
            if field_id == "sample_size":
                parsed = _coerce_int_value(raw_value)
                if parsed is not None:
                    values.append(parsed)
                continue
            cleaned = _clean_method_value(raw_value)
            if cleaned:
                values.append(cleaned)

    deduped: list[str | int] = []
    seen: set[str] = set()
    for value in values:
        key = _support_group_key(_normalize_field_value(field_id, value))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(value)
    return deduped


def _normalize_field_value(
    field_id: MethodComparisonFieldId,
    value: str | int,
) -> str | int:
    if field_id == "sample_size":
        parsed = _coerce_int_value(value)
        return parsed if parsed is not None else 0
    return _clean_method_value(str(value)).lower()


def _claim_evidence_refs(claim_card: SkillClaimCard, *, paper_slug: str) -> list[ChatEvidenceRef]:
    refs: list[ChatEvidenceRef] = []
    for evidence in claim_card.evidence:
        refs.append(_evidence_ref(evidence, paper_slug=paper_slug, claim_id=claim_card.id))
    return _dedupe_evidence_refs(refs)


def _evidence_ref(
    evidence: SkillClaimEvidence,
    *,
    paper_slug: str,
    claim_id: str | None = None,
) -> ChatEvidenceRef:
    locator = evidence.locator
    return ChatEvidenceRef(
        paper_slug=paper_slug,
        claim_id=claim_id or evidence.claim_id,
        evidence_id=evidence.id,
        run_id=evidence.run_id,
        locator=(
            ChatLocator(
                page=locator.page,
                span=list(locator.span),
                section=locator.section,
                chunk_id=locator.chunk_id,
                char_start=locator.char_start,
                char_end=locator.char_end,
                bbox_pdf=list(locator.bbox_pdf) if locator.bbox_pdf else None,
                bbox_pct=dict(locator.bbox_pct) if locator.bbox_pct else None,
                table_id=locator.table_id,
                cell_id=locator.cell_id,
                source=locator.source,
            )
            if locator is not None
            else None
        ),
    )


def _dedupe_evidence_refs(refs: list[ChatEvidenceRef]) -> list[ChatEvidenceRef]:
    deduped: list[ChatEvidenceRef] = []
    seen: set[tuple[Any, ...]] = set()
    for ref in refs:
        locator = ref.locator
        key = (
            ref.paper_slug,
            ref.claim_id,
            ref.evidence_id,
            ref.run_id,
            getattr(locator, "page", None),
            tuple(getattr(locator, "span", []) or []),
            getattr(locator, "section", None),
            getattr(locator, "chunk_id", None),
            getattr(locator, "char_start", None),
            getattr(locator, "char_end", None),
            tuple(getattr(locator, "bbox_pdf", []) or []),
            tuple(sorted((getattr(locator, "bbox_pct", {}) or {}).items())),
            getattr(locator, "table_id", None),
            getattr(locator, "cell_id", None),
            getattr(locator, "source", None),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(ref)
    return deduped


def _coerce_int_value(value: Any) -> int | None:
    text = str(value).strip()
    if not text:
        return None
    try:
        return int(text)
    except Exception:
        return None


def _clean_method_value(value: str) -> str:
    cleaned = _MULTISPACE_RE.sub(" ", value or "").strip().strip(" .,;:")
    cleaned = _LEADING_CONTEXT_RE.sub("", cleaned)
    cleaned = _VALUE_ARTICLE_RE.sub("", cleaned)
    cleaned = _TRAILING_GROUP_RE.sub("", cleaned)
    return cleaned.strip()


def _support_group_key(value: str | int) -> str:
    if isinstance(value, int):
        return f"int:{value}"
    return f"text:{value}"
