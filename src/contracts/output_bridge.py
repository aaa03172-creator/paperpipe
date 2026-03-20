from __future__ import annotations

from typing import Any

from src.schemas.skills import (
    build_stable_claim_id,
    build_stable_evidence_id,
    SkillClaimCard,
    SkillClaimEvidence,
    SkillEvidenceLocator,
)


def normalize_claimset_payload(payload: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(payload, dict):
        return None
    nested = payload.get("claimset") or payload.get("ClaimSet")
    if isinstance(nested, dict):
        payload = nested
    claims = payload.get("claims")
    if isinstance(claims, list):
        return payload
    return None


def claim_cards_from_claimset_payload(payload: dict[str, Any]) -> list[SkillClaimCard]:
    cards: list[SkillClaimCard] = []
    seen_claim_ids: set[str] = set()
    for idx, raw in enumerate(payload.get("claims") or [], start=1):
        if not isinstance(raw, dict):
            continue
        claim_text = str(raw.get("statement") or raw.get("claim") or "Unnamed claim").strip()
        claim_type = str(raw.get("type") or raw.get("claim_type") or "claim").strip()
        source_claim_id = str(raw.get("claim_id") or raw.get("id") or "").strip() or None
        claim_id = build_stable_claim_id(claim_text, claim_type)
        if claim_id in seen_claim_ids:
            claim_id = build_stable_claim_id(claim_text, claim_type, idx)
        seen_claim_ids.add(claim_id)

        evidence_entries: list[SkillClaimEvidence] = []
        seen_evidence_ids: set[str] = set()
        for evidence in raw.get("evidence_spans") or raw.get("evidence") or []:
            if not isinstance(evidence, dict):
                continue
            text = str(evidence.get("quote") or evidence.get("raw_text") or "").strip()
            if not text:
                continue
            locator = SkillEvidenceLocator(
                page=evidence.get("page"),
                span=_coerce_int_list(evidence.get("source_span")),
                section=str(evidence.get("section") or "").strip() or None,
                chunk_id=str(evidence.get("chunk_id") or "").strip() or None,
                char_start=evidence.get("char_start"),
                char_end=evidence.get("char_end"),
                bbox_pdf=_coerce_float_list(evidence.get("bbox_pdf")),
                bbox_pct=(dict(evidence.get("bbox_pct")) if isinstance(evidence.get("bbox_pct"), dict) else None),
                table_id=str(evidence.get("table_id") or "").strip() or None,
                cell_id=str(evidence.get("cell_id") or "").strip() or None,
                source=str(evidence.get("highlight_source") or evidence.get("source") or "").strip() or None,
            )
            evidence_id = build_stable_evidence_id(
                claim_id,
                text,
                locator.page,
                ",".join(str(item) for item in locator.span),
                locator.section,
                locator.chunk_id,
                locator.char_start,
                locator.char_end,
                locator.table_id,
                locator.cell_id,
            )
            if evidence_id in seen_evidence_ids:
                evidence_id = build_stable_evidence_id(
                    claim_id,
                    text,
                    locator.page,
                    locator.section,
                    idx,
                    len(evidence_entries) + 1,
                )
            seen_evidence_ids.add(evidence_id)
            evidence_entries.append(
                SkillClaimEvidence(
                    id=evidence_id,
                    claim_id=claim_id,
                    text=text,
                    page=evidence.get("page"),
                    section=locator.section,
                    source=locator.source,
                    grounded=evidence.get("grounded"),
                    resolution=str(evidence.get("resolution") or "").strip() or None,
                    locator=locator,
                )
            )
        outcomes = [claim_type] if claim_type else []
        cards.append(
            SkillClaimCard(
                id=claim_id,
                source_claim_id=source_claim_id,
                claim=claim_text,
                evidence_ids=[entry.id for entry in evidence_entries if entry.id],
                evidence=evidence_entries,
                confidence=raw.get("confidence"),
                tags=[claim_type] if claim_type else [],
                outcomes=outcomes,
            )
        )
    return cards


def bind_claim_cards_to_run(claim_cards: list[SkillClaimCard], run_id: str) -> list[SkillClaimCard]:
    bound: list[SkillClaimCard] = []
    for card in claim_cards:
        evidence_entries = [
            evidence.model_copy(
                update={
                    "claim_id": card.id,
                    "run_id": run_id,
                }
            )
            for evidence in card.evidence
        ]
        bound.append(
            SkillClaimCard.model_validate(
                {
                    **card.model_dump(),
                    "run_id": run_id,
                    "evidence_ids": [entry.id for entry in evidence_entries if entry.id],
                    "evidence": [entry.model_dump() for entry in evidence_entries],
                }
            )
        )
    return bound


def _coerce_int_list(value: Any) -> list[int]:
    if not isinstance(value, list):
        return []
    items: list[int] = []
    for item in value:
        try:
            items.append(int(item))
        except Exception:
            continue
    return items


def _coerce_float_list(value: Any) -> list[float] | None:
    if not isinstance(value, list):
        return None
    parsed: list[float] = []
    for item in value:
        try:
            parsed.append(float(item))
        except Exception:
            return None
    return parsed or None
