from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

ReasoningPersonaId = Literal["librarian", "researcher", "extractor_reviewer"]


@dataclass(frozen=True)
class ReasoningPersonaDefinition:
    id: ReasoningPersonaId
    title: str
    notes: str
    prompt_hint: str


@dataclass(frozen=True)
class PersonaSelection:
    persona_id: str
    reasoning_persona: ReasoningPersonaId | None = None
    profile_id: str | None = None


_REASONING_PERSONA_CATALOG: tuple[ReasoningPersonaDefinition, ...] = (
    ReasoningPersonaDefinition(
        id="librarian",
        title="Librarian",
        notes="Search-first intake with source coverage, provenance checks, and explicit retrieval gaps.",
        prompt_hint=(
            "reasoning_persona=librarian\n"
            "decision_rules=prioritize source coverage, metadata fidelity, retrieval recall, and explicit gaps before synthesis\n"
            "evidence_policy=avoid overclaiming when metadata, source quality, or coverage is incomplete"
        ),
    ),
    ReasoningPersonaDefinition(
        id="researcher",
        title="Researcher",
        notes="Interpretive synthesis with mechanistic framing, tradeoffs, and uncertainty made explicit.",
        prompt_hint=(
            "reasoning_persona=researcher\n"
            "decision_rules=prioritize study interpretation, synthesis across findings, mechanism hypotheses, and uncertainty tracking\n"
            "evidence_policy=link conclusions to concrete evidence and surface conflicting or missing evidence"
        ),
    ),
    ReasoningPersonaDefinition(
        id="extractor_reviewer",
        title="Extractor / Reviewer",
        notes="Structured extraction and conservative review for evidence-ready outputs and QA checks.",
        prompt_hint=(
            "reasoning_persona=extractor_reviewer\n"
            "decision_rules=prioritize extraction completeness, schema fidelity, review checkpoints, and conservative claim promotion\n"
            "evidence_policy=keep unresolved spans or review-only claims clearly separated from extraction-ready facts"
        ),
    ),
)

_REASONING_PERSONA_MAP = {definition.id: definition for definition in _REASONING_PERSONA_CATALOG}


def list_reasoning_personas() -> tuple[ReasoningPersonaDefinition, ...]:
    return _REASONING_PERSONA_CATALOG


def is_reasoning_persona(value: str | None) -> bool:
    normalized = str(value or "").strip()
    return normalized in _REASONING_PERSONA_MAP


def normalize_persona_selection(
    *,
    persona_id: str | None = None,
    reasoning_persona: str | None = None,
    profile_id: str | None = None,
) -> PersonaSelection:
    legacy_persona_id = str(persona_id or "").strip()
    resolved_reasoning = _normalize_reasoning_persona(reasoning_persona)
    resolved_profile = str(profile_id or "").strip() or None

    if resolved_reasoning is None and is_reasoning_persona(legacy_persona_id):
        resolved_reasoning = _normalize_reasoning_persona(legacy_persona_id)
    if resolved_profile is None and legacy_persona_id and legacy_persona_id != "default" and not is_reasoning_persona(legacy_persona_id):
        resolved_profile = legacy_persona_id

    compatibility_persona_id = legacy_persona_id
    if not compatibility_persona_id or compatibility_persona_id == "default":
        compatibility_persona_id = resolved_profile or resolved_reasoning or "default"

    return PersonaSelection(
        persona_id=compatibility_persona_id,
        reasoning_persona=resolved_reasoning,
        profile_id=resolved_profile,
    )


def resolve_reasoning_persona_hint(reasoning_persona: str | None) -> str | None:
    definition = _REASONING_PERSONA_MAP.get(str(reasoning_persona or "").strip())
    if not definition:
        return None
    return definition.prompt_hint


def _normalize_reasoning_persona(value: str | None) -> ReasoningPersonaId | None:
    normalized = str(value or "").strip()
    if normalized in _REASONING_PERSONA_MAP:
        return normalized  # type: ignore[return-value]
    return None
