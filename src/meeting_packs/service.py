from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from hashlib import sha1
import logging
from pathlib import Path
import re
from typing import Any

from src.meeting_packs.handoff_artifacts import write_meeting_pack_handoff_artifacts
from src.output_modes import resolve_meeting_pack_output_mode_family
from src.meeting_packs.evidence import build_meeting_pack_evidence_ledger
from src.meeting_packs.renderer import render_meeting_pack_markdown
from src.meeting_packs.source_resolver import (
    ResolvedMeetingPackBundle,
    ResolvedMeetingPackSource,
    ResolvedMeetingPackScreeningContext,
    resolve_meeting_pack_sources,
)
from src.meeting_packs.store import (
    list_meeting_pack_ids,
    load_meeting_pack,
    load_meeting_pack_markdown,
    save_meeting_pack_markdown,
    save_meeting_pack_bundle,
)
from src.schemas.meeting_pack import (
    MeetingPack,
    MeetingPackConsensus,
    MeetingPackConflict,
    MeetingPackExpectedQuestion,
    MeetingPackFigureCandidate,
    MeetingPackGenerateRequest,
    MeetingPackKeyPoint,
    MeetingPackListItem,
    MeetingPackListResponse,
    MeetingPackMarkdownSync,
    MeetingPackNextStep,
    MeetingPackOnePageSummary,
    MeetingPackQuestion,
    MeetingPackReadiness,
    MeetingPackRequestSnapshot,
    MeetingPackResponse,
    MeetingPackSlide,
    MeetingPackSourceItem,
    MeetingPackSpeakerNote,
    MeetingPackTraceResponse,
    MeetingPackRetrievalTraceEntry,
    MeetingPackRetrievalTraceSummary,
    MeetingPackValidation,
    MeetingPackValidationResponse,
)

logger = logging.getLogger(__name__)

MODE_SLIDE_TEMPLATES = {
    "journal_club": {
        "opening_title": "Why this paper matters",
        "opening_purpose": "Frame the paper and the discussion target",
        "context_title": "Study design and methods",
        "context_purpose": "Summarize what was studied and how",
        "limits_title": "Strengths, limits, and uncertainty",
        "limits_purpose": "Keep the discussion honest about what is and is not supported",
        "closing_title": "Discussion focus",
        "closing_purpose": "Surface strengths, limits, and what to debate",
    },
    "literature_update": {
        "opening_title": "Why this update matters",
        "opening_purpose": "Frame the current evidence movement",
        "context_title": "Topic landscape and selected sources",
        "context_purpose": "Show what evidence set this update is based on",
        "limits_title": "Convergence, divergence, and uncertainty",
        "limits_purpose": "Make agreement and disagreement visible",
        "closing_title": "Trend and open questions",
        "closing_purpose": "Highlight convergence, divergence, and gaps",
    },
    "project_progress_update": {
        "opening_title": "What changed for the project",
        "opening_purpose": "Frame the current evidence state and blockers",
        "context_title": "Current evidence and blockers",
        "context_purpose": "Separate what changed from what remains blocked",
        "limits_title": "Current blockers and uncertainty",
        "limits_purpose": "Keep blockers visible before assigning actions",
        "closing_title": "Immediate project decisions",
        "closing_purpose": "Focus the lab on next actions",
    },
    "experiment_proposal": {
        "opening_title": "Why this experiment is worth proposing",
        "opening_purpose": "Frame the rationale and prior evidence",
        "context_title": "Prior evidence and rationale",
        "context_purpose": "Show the evidence chain that motivates the experiment",
        "limits_title": "Design risks and failure modes",
        "limits_purpose": "Bound the proposal with its weakest assumptions",
        "closing_title": "Design risks and next experiment",
        "closing_purpose": "Surface failure modes before execution",
    },
}

NULL_DIRECTION_PHRASES = (
    "did not",
    "didn't",
    "no effect",
    "no change",
    "no significant difference",
    "not associated",
    "unchanged",
    "failed to",
    "without effect",
)
DECREASE_DIRECTION_TOKENS = {
    "attenuate",
    "attenuated",
    "decrease",
    "decreased",
    "lower",
    "lowered",
    "reduce",
    "reduced",
    "suppressed",
    "suppresses",
    "suppression",
}
INCREASE_DIRECTION_TOKENS = {
    "aggravate",
    "aggravated",
    "elevate",
    "elevated",
    "higher",
    "increase",
    "increased",
    "raise",
    "raised",
    "upregulate",
    "upregulated",
    "upregulation",
}
BENEFIT_DIRECTION_TOKENS = {
    "improve",
    "improved",
    "improvement",
    "protective",
    "rescued",
    "rescue",
    "benefit",
    "beneficial",
    "ameliorated",
    "ameliorate",
}
HARM_DIRECTION_TOKENS = {
    "worsen",
    "worsened",
    "worsening",
    "impair",
    "impaired",
    "impairment",
    "harmful",
    "toxicity",
    "toxic",
}
FOCUS_TERM_TOKEN_PATTERN = re.compile(r"[a-z0-9]{3,}")
FOCUS_GENERIC_TOKENS = {
    "activity",
    "change",
    "changes",
    "effect",
    "effects",
    "group",
    "intervention",
    "level",
    "levels",
    "marker",
    "markers",
    "outcome",
    "outcomes",
    "pathway",
    "response",
    "responses",
    "signal",
    "signals",
    "signaling",
    "study",
    "treatment",
}
FOCUS_ROOT_ALIASES = {
    "funct": "function",
    "glucose": "glycem",
    "learn": "cognit",
    "memory": "cognit",
}
FOCUS_DERIVED_FAMILIES = {
    "glycemic_family": (
        {"glycem"},
        {"sugar"},
    ),
    "safety_family": (
        {"safety"},
        {"tolerabil"},
        {"adverse", "event"},
    ),
}
HIGHER_IS_BETTER_ROOTS = {
    "cognit",
    "function",
    "perform",
    "safety",
    "safety_family",
    "surviv",
    "tolerabil",
    "viabil",
}
HIGHER_IS_WORSE_ROOTS = {
    "adverse",
    "burden",
    "glycem",
    "glycemic_family",
    "inflamm",
    "injur",
    "pain",
    "risk",
    "symptom",
    "toxic",
}
ROW_HIGHER_IS_BETTER_ROOTS = HIGHER_IS_BETTER_ROOTS - {"safety_family"}
ROW_HIGHER_IS_WORSE_ROOTS = HIGHER_IS_WORSE_ROOTS


def generate_meeting_pack(
    *,
    request: MeetingPackGenerateRequest,
    vault_path: Path,
    root: Path | None = None,
    profiles_path: Path | None = None,
    regenerated_from_pack_id: str | None = None,
) -> MeetingPackResponse:
    bundle = resolve_meeting_pack_sources(
        vault_path=vault_path,
        source_selectors=request.source_items,
        profiles_path=profiles_path,
    )
    ledger = build_meeting_pack_evidence_ledger(bundle)
    pack = _build_meeting_pack(
        request=request,
        bundle=bundle,
        ledger=ledger,
        regenerated_from_pack_id=regenerated_from_pack_id,
    )
    markdown = render_meeting_pack_markdown(pack)
    save_meeting_pack_bundle(pack, markdown, root)
    _write_meeting_pack_handoff_artifacts(pack=pack, root=root, markdown=markdown)
    return _meeting_pack_response(pack, markdown, markdown)


def get_meeting_pack(pack_id: str, *, root: Path | None = None) -> MeetingPackResponse:
    pack = load_meeting_pack(pack_id, root)
    stored_markdown = load_meeting_pack_markdown(pack_id, root)
    rendered_markdown = render_meeting_pack_markdown(pack)
    return _meeting_pack_response(pack, stored_markdown, rendered_markdown)


def list_meeting_packs(*, root: Path | None = None) -> MeetingPackListResponse:
    items = [
        _meeting_pack_list_item(load_meeting_pack(pack_id, root))
        for pack_id in list_meeting_pack_ids(root)
    ]
    items.sort(key=lambda item: (item.created_at, item.pack_id), reverse=True)
    return MeetingPackListResponse(
        generated_at=datetime.now(timezone.utc),
        total=len(items),
        items=items,
    )


def get_meeting_pack_trace(pack_id: str, *, root: Path | None = None) -> MeetingPackTraceResponse:
    pack = load_meeting_pack(pack_id, root)
    trace = list(pack.retrieval_trace)
    return MeetingPackTraceResponse(
        pack_id=pack.id,
        available=bool(trace),
        summary=_retrieval_trace_summary(trace),
        trace=trace,
    )


def validate_meeting_pack(
    pack_id: str,
    *,
    root: Path | None = None,
    vault_path: Path | None = None,
    profiles_path: Path | None = None,
) -> MeetingPackValidationResponse:
    pack = load_meeting_pack(pack_id, root)
    stored_markdown = load_meeting_pack_markdown(pack_id, root)
    rendered_markdown = render_meeting_pack_markdown(pack)
    markdown_sync = _markdown_sync(stored_markdown, rendered_markdown)
    request, strategy, warnings = _resolved_generation_request(pack)
    can_regenerate, strategy, availability_warnings = _validated_regenerate_availability(
        request=request,
        strategy=strategy,
        vault_path=vault_path,
        profiles_path=profiles_path,
    )
    return MeetingPackValidationResponse(
        validation=MeetingPackValidation(
            pack_id=pack.id,
            readiness=pack.readiness,
            markdown_sync=markdown_sync,
            can_regenerate=can_regenerate,
            regenerate_strategy=strategy,
            warnings=[*warnings, *availability_warnings],
        )
    )


def regenerate_meeting_pack(
    pack_id: str,
    *,
    vault_path: Path,
    root: Path | None = None,
    profiles_path: Path | None = None,
) -> MeetingPackResponse:
    pack = load_meeting_pack(pack_id, root)
    request, _strategy, _warnings = _resolved_generation_request(pack)
    if request is None:
        raise ValueError(
            "Meeting Pack cannot be regenerated safely from saved data; no deterministic request reconstruction is available."
        )
    return generate_meeting_pack(
        request=request,
        vault_path=vault_path,
        root=root,
        profiles_path=profiles_path,
        regenerated_from_pack_id=pack.id,
    )


def rerender_meeting_pack(pack_id: str, *, root: Path | None = None) -> MeetingPackResponse:
    pack = load_meeting_pack(pack_id, root)
    markdown = render_meeting_pack_markdown(pack)
    save_meeting_pack_markdown(pack.id, markdown, root)
    _write_meeting_pack_handoff_artifacts(pack=pack, root=root, markdown=markdown)
    return _meeting_pack_response(pack, markdown, markdown)


def _build_meeting_pack(
    *,
    request: MeetingPackGenerateRequest,
    bundle: ResolvedMeetingPackBundle,
    ledger,
    regenerated_from_pack_id: str | None = None,
) -> MeetingPack:
    created_at = datetime.now(timezone.utc)
    pack_id = _build_pack_id(request=request, created_at=created_at)
    secondary_note_items = _secondary_note_items(bundle.selected_items)
    screening_contexts = bundle.screening_contexts
    claim_rows: list[tuple[str, str, Any]] = []
    for source in bundle.sources:
        for claim in source.structured_state.claimset:
            claim_rows.append((source.source_item.id, source.source_item.ref, claim))

    consensus_points, conflicts = _build_cross_source_findings(
        sources=bundle.sources,
        screening_contexts=screening_contexts,
        evidence_ref_map=ledger.evidence_ref_map,
    )
    highlighted_rows = claim_rows[: max(1, request.max_slides - 4)]
    selected_ref_titles = _display_ref_titles(bundle)
    top_ref_ids = [ref.id for ref in ledger.evidence_refs[:3]]

    key_points = _build_key_points(
        request.mode,
        highlighted_rows,
        ledger.evidence_ref_map,
        secondary_note_items,
        screening_contexts,
    )
    claim_slides = _build_claim_slides(
        request.mode,
        highlighted_rows,
        ledger.evidence_ref_map,
        structured_source_count=len({source.source_item.ref for source in bundle.sources}),
    )
    overview = _build_overview(
        request.mode,
        selected_ref_titles,
        len(bundle.sources),
        len(claim_rows),
        secondary_note_items,
        screening_contexts,
    )
    uncertainties = _build_uncertainties(
        claim_rows,
        secondary_note_items,
        screening_contexts,
        conflicts,
        ledger.evidence_ref_map,
    )
    opening_slide, context_slide, limits_slide, closing_slide = _build_boundary_slides(
        request=request,
        selected_ref_titles=selected_ref_titles,
        source_count=len(bundle.sources),
        claim_count=len(claim_rows),
        top_ref_ids=top_ref_ids,
        uncertainties=uncertainties,
        secondary_note_items=secondary_note_items,
        screening_contexts=screening_contexts,
        consensus_points=consensus_points,
        conflicts=conflicts,
    )
    slides = [opening_slide, context_slide, *claim_slides, limits_slide, closing_slide][: request.max_slides]
    speaker_notes = [
        MeetingPackSpeakerNote(
            slide_index=slide_index,
            text=_speaker_note_text(request.mode, slide.slide_title),
            evidence_refs=list(slide.evidence_refs),
        )
        for slide_index, slide in enumerate(slides, start=1)
    ]

    return MeetingPack(
        id=pack_id,
        mode=request.mode,
        output_mode_family=resolve_meeting_pack_output_mode_family(request.mode),
        title=request.title or _default_title(request.mode, selected_ref_titles[0]),
        created_at=created_at,
        status="draft",
        readiness=_meeting_pack_readiness(claim_rows, ledger.evidence_ref_map),
        generation_request=MeetingPackRequestSnapshot(**request.model_dump()),
        regenerated_from_pack_id=regenerated_from_pack_id,
        source_items=_pack_source_items(bundle),
        retrieval_trace=list(bundle.retrieval_trace),
        one_page_summary=MeetingPackOnePageSummary(
            overview=overview,
            key_points=key_points[:3],
            consensus_points=consensus_points,
            conflicts=conflicts,
            uncertainties=uncertainties,
        ),
        slides=slides,
        speaker_notes=speaker_notes,
        discussion_questions=_build_discussion_questions(
            request.mode,
            key_points,
            secondary_note_items,
            screening_contexts,
        ),
        expected_questions=_build_expected_questions(
            request.mode,
            key_points,
            secondary_note_items,
            screening_contexts,
        ),
        next_steps=_build_next_steps(
            request.mode,
            key_points,
            secondary_note_items,
            screening_contexts,
        ),
        evidence_refs=ledger.evidence_refs,
    )


def _build_key_points(
    mode: str,
    highlighted_rows: list[tuple[str, str, Any]],
    evidence_ref_map: dict[tuple[str, str, str], str],
    secondary_note_items: list[MeetingPackSourceItem],
    screening_contexts: list[ResolvedMeetingPackScreeningContext],
) -> list[MeetingPackKeyPoint]:
    if not highlighted_rows:
        return [
            MeetingPackKeyPoint(
                label="Background only",
                text="No structured claim was available; treat this pack as a background-only draft until evidence is refreshed.",
                evidence_refs=[],
                uncertainty_note="No structured claim/evidence entries were available.",
            )
        ]

    key_points: list[MeetingPackKeyPoint] = []
    for index, (_source_item_id, paper_slug, claim) in enumerate(highlighted_rows, start=1):
        ref_ids = _claim_ref_ids(paper_slug, claim, evidence_ref_map)
        uncertainty_note = _merge_uncertainty_notes(
            _claim_uncertainty_note(claim, ref_ids),
            _key_point_context_note(
                mode,
                index,
                secondary_note_items,
                screening_contexts,
            ),
        )
        key_points.append(
            MeetingPackKeyPoint(
                label=_key_point_label(mode, index),
                text=claim.claim,
                evidence_refs=ref_ids,
                uncertainty_note=uncertainty_note,
            )
        )
    return key_points


def _build_claim_slides(
    mode: str,
    highlighted_rows: list[tuple[str, str, Any]],
    evidence_ref_map: dict[tuple[str, str, str], str],
    *,
    structured_source_count: int,
) -> list[MeetingPackSlide]:
    if not highlighted_rows:
        return [
            MeetingPackSlide(
                slide_title=_claim_slide_title(mode, 1),
                purpose=_claim_slide_purpose(mode),
                bullets=[
                    "No structured claim was available for this selection.",
                    "Treat this as background context until a stronger evidence state is generated.",
                ],
                evidence_refs=[],
                caution_notes=["This section is background-only and should not be presented as a defended result."],
            )
        ]

    slides: list[MeetingPackSlide] = []
    for index, (source_item_id, paper_slug, claim) in enumerate(highlighted_rows, start=1):
        ref_ids = _claim_ref_ids(paper_slug, claim, evidence_ref_map)
        slides.append(
            MeetingPackSlide(
                slide_title=_claim_slide_title(mode, index),
                purpose=_claim_slide_purpose(mode),
                bullets=[
                    claim.claim,
                    _support_summary(ref_ids),
                ],
                evidence_refs=ref_ids,
                optional_figure_candidates=[
                    MeetingPackFigureCandidate(
                        label="Primary source figure candidate",
                        source_item_id=source_item_id,
                        reason="Use the main result figure only after manual verification.",
                    )
                ]
                if index == 1
                else [],
                caution_notes=[
                    *([] if ref_ids else ["Treat this point as uncertain until source support is rechecked."]),
                    *(
                        ["This is a source-specific claim slide; do not present it as consensus across all selected papers."]
                        if structured_source_count > 1
                        else []
                    ),
                ],
            )
        )
    return slides


def _build_pack_id(*, request: MeetingPackGenerateRequest, created_at: datetime) -> str:
    source_key = "|".join(f"{item.type}:{item.ref}" for item in request.source_items)
    digest = sha1(f"{request.mode}|{source_key}".encode("utf-8")).hexdigest()[:8]
    stamp = created_at.strftime("%Y%m%dT%H%M%S%fZ")
    return f"meetingpack_{stamp}_{request.mode}_{digest}"


def _saved_generation_request(pack: MeetingPack) -> MeetingPackGenerateRequest:
    if pack.generation_request is None:
        raise ValueError(
            "Meeting Pack does not include a saved generation request; regenerate is unavailable for this pack."
        )
    return MeetingPackGenerateRequest(**pack.generation_request.model_dump())


def _resolved_generation_request(
    pack: MeetingPack,
) -> tuple[MeetingPackGenerateRequest | None, str, list[str]]:
    if pack.generation_request is not None:
        return MeetingPackGenerateRequest(**pack.generation_request.model_dump()), "saved_request", []
    return _legacy_generation_request(pack)


def _validated_regenerate_availability(
    *,
    request: MeetingPackGenerateRequest | None,
    strategy: str,
    vault_path: Path | None,
    profiles_path: Path | None,
) -> tuple[bool, str, list[str]]:
    if request is None:
        return False, "unavailable", []
    if vault_path is None:
        return (
            False,
            "unavailable",
            [
                "Regenerate availability could not be verified because the Obsidian vault path is unavailable.",
            ],
        )
    try:
        resolve_meeting_pack_sources(
            vault_path=vault_path,
            source_selectors=request.source_items,
            profiles_path=profiles_path,
        )
    except (FileNotFoundError, NotImplementedError, ValueError) as exc:
        return (
            False,
            "unavailable",
            [f"Regenerate source validation failed for {strategy}: {exc}"],
        )
    return True, strategy, []


def _legacy_generation_request(
    pack: MeetingPack,
) -> tuple[MeetingPackGenerateRequest | None, str, list[str]]:
    selector_items = _legacy_selector_items(pack.source_items)
    if not selector_items:
        return (
            None,
            "unavailable",
            [
                "Legacy pack has no deterministic selector subset in source_items; regenerate remains unavailable.",
            ],
        )
    max_slides = min(8, max(5, len(pack.slides) or 5))
    warnings = [
        "Legacy pack regenerate fell back to source_items and inferred max_slides from the saved slide count.",
    ]
    return (
        MeetingPackGenerateRequest(
            mode=pack.mode,
            title=pack.title,
            source_items=[
                {"type": item.type, "ref": item.ref}
                for item in selector_items
            ],
            max_slides=max_slides,
        ),
        "legacy_source_items",
        warnings,
    )


def _legacy_selector_items(source_items: list[MeetingPackSourceItem]) -> list[MeetingPackSourceItem]:
    explicit_selectors = [item for item in source_items if item.type != "paper_state"]
    if explicit_selectors:
        return explicit_selectors
    direct_paper_states = [item for item in source_items if item.type == "paper_state"]
    return direct_paper_states


def _meeting_pack_readiness(
    claim_rows: list[tuple[str, str, Any]],
    evidence_ref_map: dict[tuple[str, str, str], str],
) -> MeetingPackReadiness:
    if any(_claim_has_direct_support(paper_slug, claim, evidence_ref_map) for _, paper_slug, claim in claim_rows):
        return "evidence_backed"
    return "background_only"


def _meeting_pack_response(
    pack: MeetingPack,
    stored_markdown: str,
    rendered_markdown: str,
) -> MeetingPackResponse:
    return MeetingPackResponse(
        pack=pack,
        markdown=stored_markdown,
        markdown_sync=_markdown_sync(stored_markdown, rendered_markdown),
    )


def _meeting_pack_list_item(pack: MeetingPack) -> MeetingPackListItem:
    primary_source_title = pack.source_items[0].title if pack.source_items else None
    return MeetingPackListItem(
        pack_id=pack.id,
        title=pack.title,
        mode=pack.mode,
        output_mode_family=resolve_meeting_pack_output_mode_family(pack.mode, explicit_family=pack.output_mode_family),
        created_at=pack.created_at,
        readiness=pack.readiness,
        source_count=len(pack.source_items),
        slide_count=len(pack.slides),
        trace_entry_count=len(pack.retrieval_trace),
        primary_source_title=primary_source_title,
        has_generation_request=pack.generation_request is not None,
        regenerated_from_pack_id=pack.regenerated_from_pack_id,
    )


def _retrieval_trace_summary(
    trace: list[MeetingPackRetrievalTraceEntry],
) -> MeetingPackRetrievalTraceSummary:
    selector_keys: set[tuple[str, str]] = set()
    action_counts: dict[str, int] = {}
    outcome_counts: dict[str, int] = {}
    matched_paper_slugs: list[str] = []
    source_paths: list[str] = []

    for entry in trace:
        selector_keys.add((entry.selector_type, entry.selector_ref))
        action_counts[entry.action] = action_counts.get(entry.action, 0) + 1
        outcome_counts[entry.outcome] = outcome_counts.get(entry.outcome, 0) + 1
        for slug in entry.matched_paper_slugs:
            if slug not in matched_paper_slugs:
                matched_paper_slugs.append(slug)
        if entry.source_path and entry.source_path not in source_paths:
            source_paths.append(entry.source_path)

    return MeetingPackRetrievalTraceSummary(
        entry_count=len(trace),
        selector_count=len(selector_keys),
        matched_paper_count=len(matched_paper_slugs),
        source_path_count=len(source_paths),
        action_counts=action_counts,
        outcome_counts=outcome_counts,
        matched_paper_slugs=matched_paper_slugs,
        source_paths=source_paths,
    )


def _markdown_sync(stored_markdown: str, rendered_markdown: str) -> MeetingPackMarkdownSync:
    status = "in_sync" if stored_markdown == rendered_markdown else "drifted"
    note = None
    if status == "drifted":
        note = "Stored markdown differs from the deterministic render of meeting_pack.json."
    return MeetingPackMarkdownSync(
        status=status,
        stored_markdown_sha1=sha1(stored_markdown.encode("utf-8")).hexdigest(),
        rendered_markdown_sha1=sha1(rendered_markdown.encode("utf-8")).hexdigest(),
        note=note,
    )


def _write_meeting_pack_handoff_artifacts(
    *,
    pack: MeetingPack,
    root: Path | None,
    markdown: str,
) -> None:
    request, strategy, _warnings = _resolved_generation_request(pack)
    regenerate_strategy = strategy if request is not None else "unavailable"
    try:
        write_meeting_pack_handoff_artifacts(
            pack=pack,
            root=root,
            regenerate_strategy=regenerate_strategy,
            markdown_sync_status=_markdown_sync(markdown, markdown).status,
        )
    except Exception as exc:
        logger.warning("Failed to write Meeting Pack handoff artifacts for %s: %s", pack.id, exc)


def _pack_source_items(bundle: ResolvedMeetingPackBundle) -> list[MeetingPackSourceItem]:
    seen: set[tuple[str, str]] = set()
    merged: list[MeetingPackSourceItem] = []
    for item in [*bundle.selected_items, *(source.source_item for source in bundle.sources)]:
        key = (item.type, item.ref)
        if key in seen:
            continue
        seen.add(key)
        merged.append(item)
    return merged


def _display_ref_titles(bundle: ResolvedMeetingPackBundle) -> list[str]:
    primary_titles = [source.source_item.title for source in bundle.sources if source.source_item.title]
    if primary_titles:
        deduped: list[str] = []
        for title in primary_titles:
            if title not in deduped:
                deduped.append(title)
        return deduped

    fallback_titles: list[str] = []
    for item in bundle.selected_items:
        if item.title and item.title not in fallback_titles:
            fallback_titles.append(item.title)
    return fallback_titles or ["selected sources"]


def _build_overview(
    mode: str,
    selected_ref_titles: list[str],
    source_count: int,
    claim_count: int,
    secondary_note_items: list[MeetingPackSourceItem],
    screening_contexts: list[ResolvedMeetingPackScreeningContext],
) -> str:
    primary = selected_ref_titles[0] if selected_ref_titles else "selected sources"
    suffix = _overview_context_suffix(mode, secondary_note_items, screening_contexts)
    if mode == "journal_club":
        return (
            f"This draft frames {primary} for journal-club discussion and highlights {claim_count} structured claim(s) "
            f"across {source_count} evidence-linked paper source(s).{suffix}"
        )
    if mode == "literature_update":
        return (
            f"This draft summarizes the current evidence movement for {primary} using {source_count} paper source(s) "
            f"and {claim_count} structured claim(s).{suffix}"
        )
    if mode == "project_progress_update":
        return (
            f"This draft packages the current project-facing evidence state for {primary} from {source_count} paper "
            f"source(s) and {claim_count} structured claim(s).{suffix}"
        )
    return (
        f"This draft packages prior evidence for {primary} into an experiment-proposal framing built on "
        f"{claim_count} structured claim(s) across {source_count} paper source(s).{suffix}"
    )


def _build_uncertainties(
    claim_rows: list[tuple[str, str, Any]],
    secondary_note_items: list[MeetingPackSourceItem],
    screening_contexts: list[ResolvedMeetingPackScreeningContext],
    conflicts: list[MeetingPackConflict],
    evidence_ref_map: dict[tuple[str, str, str], str],
) -> list[str]:
    if not claim_rows:
        uncertainties = ["No structured claims were available; treat the pack as background-only."]
    else:
        uncertainties = []

    if any(not claim.evidence for _, _, claim in claim_rows):
        uncertainties.append(
            "One or more claims lacked explicit evidence refs and should be reviewed before presentation."
        )
    if any(
        getattr(claim, "confidence", None) is not None and float(claim.confidence) < 0.6
        for _, _, claim in claim_rows
    ):
        uncertainties.append(
            "At least one highlighted claim carries mixed confidence and should be framed cautiously."
        )
    if any(
        _claim_grounding_uncertainty_note(claim, _claim_ref_ids(paper_slug, claim, evidence_ref_map))
        for _, paper_slug, claim in claim_rows
    ):
        uncertainties.append(
            "At least one evidence-linked claim is still missing or unresolved citation-grounding metadata; re-check citation linkage before presentation."
        )
    uncertainties.append(
        "Numeric effect sizes and figure choices should still be re-verified from source text before presenting."
    )
    if secondary_note_items:
        note_titles = ", ".join(item.title for item in secondary_note_items)
        uncertainties.append(
            f"Secondary notes were included as context-only inputs ({note_titles}) and do not override structured claims."
        )
    if len(secondary_note_items) > 1:
        uncertainties.append(
            "Multiple secondary notes were selected; reconcile them manually instead of treating them as merged truth."
        )
    for context in screening_contexts:
        summary = (
            f"Screening rationale from {context.run_id}: include={context.include_count}, "
            f"exclude={context.exclude_count}, unclear={context.unclear_count}"
        )
        if context.top_reason_codes:
            summary += f"; top reasons={', '.join(context.top_reason_codes)}"
        uncertainties.append(summary + ".")
    if screening_contexts:
        uncertainties.append(
            "Screening rationale is contextual only and should not be presented as evidence for effect direction or strength."
        )
    if conflicts:
        uncertainties.append(
            "Review the structured conflict list before presenting any cross-source consensus statement."
        )

    deduped: list[str] = []
    for item in uncertainties:
        if item not in deduped:
            deduped.append(item)
    return deduped


def _build_boundary_slides(
    *,
    request: MeetingPackGenerateRequest,
    selected_ref_titles: list[str],
    source_count: int,
    claim_count: int,
    top_ref_ids: list[str],
    uncertainties: list[str],
    secondary_note_items: list[MeetingPackSourceItem],
    screening_contexts: list[ResolvedMeetingPackScreeningContext],
    consensus_points: list[MeetingPackConsensus],
    conflicts: list[MeetingPackConflict],
) -> tuple[MeetingPackSlide, MeetingPackSlide, MeetingPackSlide, MeetingPackSlide]:
    template = MODE_SLIDE_TEMPLATES[request.mode]
    consensus_summaries = _consensus_summaries(consensus_points)
    conflict_summaries = _conflict_summaries(conflicts)
    opening_bullets = [
        f"Selected source context: {', '.join(selected_ref_titles[:3])}",
        f"Structured claims available: {claim_count}",
    ]
    if secondary_note_items:
        opening_bullets.append(_opening_note_bullet(request.mode, secondary_note_items))
    if screening_contexts:
        opening_bullets.append(_opening_screening_bullet(request.mode, screening_contexts))
    opening_cautions = [] if top_ref_ids else ["No direct evidence refs were available at the opening summary layer."]
    if secondary_note_items:
        opening_cautions.append("Secondary notes are context-only inputs and do not override structured claims.")
    if len(secondary_note_items) > 1:
        opening_cautions.append("Multiple secondary notes may diverge; treat them as framing, not merged truth.")
    if screening_contexts:
        opening_cautions.append("Screening rationale is contextual only and does not override evidence-linked claims.")
    opening_cautions.extend(conflict_summaries[:2])
    opening = MeetingPackSlide(
        slide_title=template["opening_title"],
        purpose=template["opening_purpose"],
        bullets=opening_bullets,
        evidence_refs=list(top_ref_ids),
        caution_notes=opening_cautions,
    )
    context = MeetingPackSlide(
        slide_title=template["context_title"],
        purpose=template["context_purpose"],
        bullets=_context_bullets(
            request.mode,
            selected_ref_titles,
            source_count,
            secondary_note_items,
            screening_contexts,
        ),
        evidence_refs=list(top_ref_ids),
        caution_notes=(
            ["Use this slide to bound scope before discussing interpretation."]
            + (["Context notes can frame discussion but must not override evidence-linked claims."] if secondary_note_items else [])
            + (["Screening rationale can explain selection context but must not be presented as claim evidence."] if screening_contexts else [])
            + conflict_summaries[:2]
        ),
    )
    limit_bullets: list[str] = []
    limit_bullets.extend(consensus_summaries[:1])
    limit_bullets.extend(conflict_summaries[:1])
    if len(limit_bullets) < 2:
        limit_bullets.extend(uncertainties[: 2 - len(limit_bullets)])
    limits = MeetingPackSlide(
        slide_title=template["limits_title"],
        purpose=template["limits_purpose"],
        bullets=limit_bullets
        or ["No explicit uncertainty note was produced; re-check the source manually."],
        evidence_refs=list(top_ref_ids),
        caution_notes=["Do not resolve conflicting evidence silently in presentation mode."],
    )
    closing = MeetingPackSlide(
        slide_title=template["closing_title"],
        purpose=template["closing_purpose"],
        bullets=_closing_bullets(request.mode),
        evidence_refs=list(top_ref_ids),
        caution_notes=[
            "Re-check the source note before presenting any numeric or mechanistic claim.",
            *(
                ["Keep note-derived framing separate from evidence-backed claim truth."]
                if secondary_note_items
                else []
            ),
            *(
                ["Keep screening-derived rationale separate from evidence-backed claim truth."]
                if screening_contexts
                else []
            ),
        ],
    )
    return opening, context, limits, closing


def _claim_ref_ids(paper_slug: str, claim: Any, evidence_ref_map: dict[tuple[str, str, str], str]) -> list[str]:
    refs: list[str] = []
    for evidence in claim.evidence:
        key = (paper_slug, str(claim.id), str(evidence.id or ""))
        ref_id = evidence_ref_map.get(key)
        if ref_id and ref_id not in refs:
            refs.append(ref_id)
    return refs


def _claim_has_direct_support(
    paper_slug: str,
    claim: Any,
    evidence_ref_map: dict[tuple[str, str, str], str],
) -> bool:
    return bool(_claim_ref_ids(paper_slug, claim, evidence_ref_map))


def _claim_grounding_state(claim: Any) -> str:
    saw_grounding_metadata = False
    for evidence in getattr(claim, "evidence", []):
        grounded = getattr(evidence, "grounded", None)
        resolution = str(getattr(evidence, "resolution", "") or "").strip().upper()
        if grounded is True:
            return "resolved"
        if resolution and not any(token in resolution for token in ("FAILED", "AMBIGUOUS", "UNRESOLVED")):
            return "resolved"
        if grounded is False or resolution:
            saw_grounding_metadata = True
    return "unresolved" if saw_grounding_metadata else "missing"


def _key_point_label(mode: str, index: int) -> str:
    if mode == "experiment_proposal":
        return f"Prior evidence {index}"
    if mode == "project_progress_update":
        return f"Current evidence state {index}"
    if mode == "literature_update":
        return f"Update point {index}"
    return f"Key point {index}"


def _claim_slide_title(mode: str, index: int) -> str:
    if mode == "journal_club":
        return f"Main evidence {index}"
    if mode == "literature_update":
        return f"Key update {index}"
    if mode == "project_progress_update":
        return f"Progress evidence {index}"
    return f"Supporting evidence {index}"


def _claim_slide_purpose(mode: str) -> str:
    if mode == "experiment_proposal":
        return "Extract the prior evidence that justifies the proposed next experiment"
    if mode == "project_progress_update":
        return "Show the most decision-relevant evidence for the project"
    if mode == "literature_update":
        return "Show one evidence-backed update point"
    return "Show one evidence-backed discussion point"


def _support_summary(ref_ids: list[str]) -> str:
    if not ref_ids:
        return "Support status: uncertain, no structured evidence refs linked."
    return f"Support status: evidence-linked via {', '.join(ref_ids)}."


def _claim_uncertainty_note(claim: Any, ref_ids: list[str]) -> str | None:
    if not ref_ids:
        return "Structured evidence refs are missing for this claim."
    notes: list[str] = []
    confidence = getattr(claim, "confidence", None)
    if confidence is not None and float(confidence) < 0.6:
        notes.append("Claim confidence is mixed; present as tentative.")
    grounding_note = _claim_grounding_uncertainty_note(claim, ref_ids)
    if grounding_note:
        notes.append(grounding_note)
    if not notes:
        return None
    return " ".join(notes)


def _claim_grounding_uncertainty_note(claim: Any, ref_ids: list[str]) -> str | None:
    if not ref_ids:
        return None
    grounding_state = _claim_grounding_state(claim)
    if grounding_state == "resolved":
        return None
    if grounding_state == "unresolved":
        return "Direct evidence refs exist, but citation-grounding metadata is unresolved; re-check citation linkage before presentation."
    return "Direct evidence refs exist, but citation-grounding metadata is missing; re-check citation linkage before presentation."


def _merge_uncertainty_notes(*notes: str | None) -> str | None:
    merged = [note.strip() for note in notes if note and note.strip()]
    if not merged:
        return None
    return " ".join(merged)


def _consensus_summaries(consensus_points: list[MeetingPackConsensus]) -> list[str]:
    return [f"[Consensus] {point.summary}" for point in consensus_points]


def _conflict_summaries(conflicts: list[MeetingPackConflict]) -> list[str]:
    return [f"[Conflict] {conflict.summary}" for conflict in conflicts]


def _dedupe_conflicts(conflicts: list[MeetingPackConflict]) -> list[MeetingPackConflict]:
    deduped: list[MeetingPackConflict] = []
    seen: set[tuple[str, str]] = set()
    for conflict in conflicts:
        key = (conflict.conflict_type, conflict.summary)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(conflict)
    return deduped


def _dedupe_consensus_points(
    consensus_points: list[MeetingPackConsensus],
) -> list[MeetingPackConsensus]:
    deduped: list[MeetingPackConsensus] = []
    seen: set[tuple[str, str]] = set()
    for consensus in consensus_points:
        key = (consensus.consensus_type, consensus.summary)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(consensus)
    return deduped


def _speaker_note_text(mode: str, slide_title: str) -> str:
    if mode == "experiment_proposal":
        return f"Use '{slide_title}' to justify the next experiment without over-claiming mechanism."
    if mode == "project_progress_update":
        return f"Use '{slide_title}' to separate current evidence from next operational decision."
    if mode == "literature_update":
        return f"Use '{slide_title}' to explain what has changed in the evidence landscape."
    return f"Use '{slide_title}' to frame the discussion around evidence, not polished narrative."


def _build_discussion_questions(
    mode: str,
    key_points: list[MeetingPackKeyPoint],
    secondary_note_items: list[MeetingPackSourceItem],
    screening_contexts: list[ResolvedMeetingPackScreeningContext],
) -> list[MeetingPackQuestion]:
    primary_refs = list(key_points[0].evidence_refs) if key_points else []
    if mode == "experiment_proposal":
        questions = [
            MeetingPackQuestion(
                question="Which uncertainty most threatens the proposed experiment design?",
                rationale="The proposal should be driven by the weakest defended evidence link.",
                evidence_refs=primary_refs,
            ),
            MeetingPackQuestion(
                question="What would we need to observe to decide not to run this experiment?",
                rationale="The pack should expose stop conditions before effort is spent.",
                evidence_refs=primary_refs,
            ),
        ]
    elif mode == "project_progress_update":
        questions = [
            MeetingPackQuestion(
                question="Which blocker matters most for the next project decision?",
                rationale="Progress updates should separate evidence state from execution state.",
                evidence_refs=primary_refs,
            ),
            MeetingPackQuestion(
                question="Which current claim would change our next action if it were wrong?",
                rationale="This identifies the most decision-sensitive evidence link.",
                evidence_refs=primary_refs,
            ),
        ]
    elif mode == "literature_update":
        questions = [
            MeetingPackQuestion(
                question="Where do the selected sources actually agree, and where do they diverge?",
                rationale="Literature updates should make convergence and disagreement explicit.",
                evidence_refs=primary_refs,
            ),
            MeetingPackQuestion(
                question="What is still missing before we can claim a trend with confidence?",
                rationale="Trend summaries should stay bounded by the current evidence base.",
                evidence_refs=primary_refs,
            ),
        ]
    else:
        questions = [
            MeetingPackQuestion(
                question="Which claim is most decision-relevant, and how strong is its evidence support?",
                rationale="The pack should drive discussion from evidence-backed claims instead of presentation polish.",
                evidence_refs=primary_refs,
            ),
            MeetingPackQuestion(
                question="What is the strongest limitation we should surface before anyone asks?",
                rationale="Journal club drafts should lead with defensible limits, not only findings.",
                evidence_refs=primary_refs,
            ),
        ]

    if secondary_note_items:
        questions.append(
            MeetingPackQuestion(
                question=_note_context_question(mode),
                rationale=(
                    f"Context note(s) {_note_context_titles(secondary_note_items)} can frame the meeting, "
                    "but they should stay separate from evidence-backed claims."
                ),
                evidence_refs=primary_refs,
            )
        )
    if screening_contexts:
        questions.append(
            MeetingPackQuestion(
                question=_screening_context_question(mode),
                rationale=(
                    f"Screening scope {_screening_context_label(screening_contexts)} affects selection context "
                    "without changing what the evidence itself supports."
                ),
                evidence_refs=primary_refs,
            )
        )
    return questions


def _build_expected_questions(
    mode: str,
    key_points: list[MeetingPackKeyPoint],
    secondary_note_items: list[MeetingPackSourceItem],
    screening_contexts: list[ResolvedMeetingPackScreeningContext],
) -> list[MeetingPackExpectedQuestion]:
    primary_refs = list(key_points[0].evidence_refs) if key_points else []
    if mode == "experiment_proposal":
        questions = [
            MeetingPackExpectedQuestion(
                question="What is the strongest reason not to run this experiment yet?",
                suggested_response="The limiting factor is the weakest evidence-backed assumption, not the attractiveness of the idea.",
                evidence_refs=primary_refs,
            ),
            MeetingPackExpectedQuestion(
                question="Which assumption is still carrying too much uncertainty?",
                suggested_response="Point to the assumption with the thinnest direct support and make that the first follow-up check.",
                evidence_refs=primary_refs,
            ),
        ]
    elif mode == "project_progress_update":
        questions = [
            MeetingPackExpectedQuestion(
                question="What changed since the last update in a way that matters?",
                suggested_response="Answer with the most decision-relevant evidence delta, not with presentation polish.",
                evidence_refs=primary_refs,
            ),
            MeetingPackExpectedQuestion(
                question="Why are we not acting faster on this yet?",
                suggested_response="Lead with the blocker that is directly tied to uncertain or missing evidence.",
                evidence_refs=primary_refs,
            ),
        ]
    elif mode == "literature_update":
        questions = [
            MeetingPackExpectedQuestion(
                question="Is this a real trend or just a selective snapshot?",
                suggested_response="Describe the visible pattern, then explicitly state the current evidence limits and omissions.",
                evidence_refs=primary_refs,
            ),
            MeetingPackExpectedQuestion(
                question="Which paper would you trust least in this set?",
                suggested_response="Start from study design or evidence limitations that are directly traceable in source material.",
                evidence_refs=primary_refs,
            ),
        ]
    else:
        questions = [
            MeetingPackExpectedQuestion(
                question="What is the most defensible limitation to say first?",
                suggested_response="Lead with the limitation that is directly supported by source evidence instead of speculating beyond it.",
                evidence_refs=primary_refs,
            ),
            MeetingPackExpectedQuestion(
                question="Which result should we avoid overstating?",
                suggested_response="Avoid overstating any point whose support is indirect, mixed-confidence, or not numerically re-verified.",
                evidence_refs=primary_refs,
            ),
        ]

    if secondary_note_items:
        questions.append(
            MeetingPackExpectedQuestion(
                question=_note_context_expected_question(mode),
                suggested_response=(
                    f"Point back to note context {_note_context_titles(secondary_note_items)}, "
                    "then explicitly separate that framing from the evidence-linked claim set."
                ),
                evidence_refs=primary_refs,
            )
        )
    if screening_contexts:
        questions.append(
            MeetingPackExpectedQuestion(
                question=_screening_context_expected_question(mode),
                suggested_response=(
                    f"Answer with screening context {_screening_context_label(screening_contexts)} and make clear "
                    "that selection rationale is contextual only, not claim evidence."
                ),
                evidence_refs=primary_refs,
            )
        )
    return questions


def _build_next_steps(
    mode: str,
    key_points: list[MeetingPackKeyPoint],
    secondary_note_items: list[MeetingPackSourceItem],
    screening_contexts: list[ResolvedMeetingPackScreeningContext],
) -> list[MeetingPackNextStep]:
    primary_refs = list(key_points[0].evidence_refs) if key_points else []
    if mode == "experiment_proposal":
        steps = [
            MeetingPackNextStep(
                action="Re-check the strongest prior-evidence claim before finalizing the proposal.",
                why="Proposal credibility depends on the cleanest supported evidence link.",
                priority="high",
                evidence_refs=primary_refs,
            ),
            MeetingPackNextStep(
                action="Define the first failure criterion before discussing resourcing.",
                why="The proposal should be bounded by what would invalidate it early.",
                priority="medium",
                evidence_refs=primary_refs,
            ),
        ]
    elif mode == "project_progress_update":
        steps = [
            MeetingPackNextStep(
                action="Re-read the most decision-sensitive source section before the meeting.",
                why="Project updates should lead with the cleanest evidence-backed delta.",
                priority="high",
                evidence_refs=primary_refs,
            ),
            MeetingPackNextStep(
                action="Turn the main blocker into an explicit owner/question after discussion.",
                why="The meeting should end with a tractable next action rather than a vague blocker.",
                priority="medium",
                evidence_refs=primary_refs,
            ),
        ]
    elif mode == "literature_update":
        steps = [
            MeetingPackNextStep(
                action="Verify whether the apparent trend still holds after re-checking the outlier paper.",
                why="Trend summaries are weakest at the disagreement boundary.",
                priority="high",
                evidence_refs=primary_refs,
            ),
            MeetingPackNextStep(
                action="Capture the open question that most changes how we read the set.",
                why="A useful literature update should leave the team with one sharper question.",
                priority="medium",
                evidence_refs=primary_refs,
            ),
        ]
    else:
        steps = [
            MeetingPackNextStep(
                action="Re-read the source methods/results before presenting the main claim verbally.",
                why="Presentation confidence should stay bounded by the strongest linked evidence.",
                priority="high",
                evidence_refs=primary_refs,
            ),
            MeetingPackNextStep(
                action="Pick one strength and one limitation to say before open discussion.",
                why="Journal club discussion is clearer when the framing is balanced from the start.",
                priority="medium",
                evidence_refs=primary_refs,
            ),
        ]

    if secondary_note_items:
        steps.append(
            MeetingPackNextStep(
                action=_note_context_next_step(mode),
                why="Context-only note framing should be kept visible but separate from evidence-backed interpretation.",
                priority="medium",
                evidence_refs=primary_refs,
            )
        )
    if screening_contexts:
        steps.append(
            MeetingPackNextStep(
                action=_screening_context_next_step(mode),
                why="Selection rationale should be re-checked before the meeting turns it into a representative trend claim.",
                priority="medium",
                evidence_refs=primary_refs,
            )
        )
    return steps


def _note_context_titles(secondary_note_items: list[MeetingPackSourceItem]) -> str:
    titles = ", ".join(item.title for item in secondary_note_items[:2])
    if len(secondary_note_items) > 2:
        titles += f", +{len(secondary_note_items) - 2} more"
    return titles or "selected notes"


def _screening_context_label(
    screening_contexts: list[ResolvedMeetingPackScreeningContext],
) -> str:
    run_ids = ", ".join(context.run_id for context in screening_contexts[:2])
    if len(screening_contexts) > 2:
        run_ids += f", +{len(screening_contexts) - 2} more"
    return run_ids or "selected screening runs"


def _note_context_question(mode: str) -> str:
    if mode == "experiment_proposal":
        return "Which part of the proposal rationale still depends on note-derived framing rather than direct evidence?"
    if mode == "project_progress_update":
        return "Which part of the project framing is still note-derived rather than evidence-backed progress?"
    if mode == "literature_update":
        return "Which note-derived framing should stay separate from the evidence trend?"
    return "Which part of our framing comes from notes rather than the paper itself?"


def _screening_context_question(mode: str) -> str:
    if mode == "experiment_proposal":
        return "How much does the current screening scope shape which prior evidence we are using to justify the proposal?"
    if mode == "project_progress_update":
        return "How much does the current screening scope affect what counts as progress-relevant evidence?"
    if mode == "literature_update":
        return "How much does the screening scope shape the apparent trend?"
    return "How much does the screening scope shape which evidence reached this discussion?"


def _note_context_expected_question(mode: str) -> str:
    if mode == "experiment_proposal":
        return "Are we leaning too hard on project notes instead of defended prior evidence?"
    if mode == "project_progress_update":
        return "Is this update coming from the project note or from the underlying evidence state?"
    if mode == "literature_update":
        return "Are we reading the topic through the note framing more than through the sources?"
    return "How much of this framing is ours versus the paper's?"


def _screening_context_expected_question(mode: str) -> str:
    if mode == "experiment_proposal":
        return "Why did these particular prior studies make it into the proposal set?"
    if mode == "project_progress_update":
        return "Why is this the evidence set we are using for the current update?"
    if mode == "literature_update":
        return "Why were these papers in scope for this update?"
    return "Why did these papers make it into today's discussion set?"


def _note_context_next_step(mode: str) -> str:
    if mode == "experiment_proposal":
        return "Mark which proposal assumptions are note-derived before finalizing the draft."
    if mode == "project_progress_update":
        return "Separate project-note framing from evidence-backed progress bullets before the meeting."
    if mode == "literature_update":
        return "Mark which update bullets come from note framing rather than the evidence trend."
    return "Mark which framing bullets come from notes rather than the paper before presenting."


def _screening_context_next_step(mode: str) -> str:
    if mode == "experiment_proposal":
        return "Re-check screening scope before presenting the proposal rationale as representative prior evidence."
    if mode == "project_progress_update":
        return "Re-check screening scope before turning the current evidence set into a project-wide update."
    if mode == "literature_update":
        return "Re-check screening reason codes before presenting the current set as a topic trend."
    return "Re-check screening reason codes before presenting this set as a balanced discussion sample."


def _default_title(mode: str, ref: str) -> str:
    return f"{ref} {mode.replace('_', ' ')} draft"


def _overview_context_suffix(
    mode: str,
    secondary_note_items: list[MeetingPackSourceItem],
    screening_contexts: list[ResolvedMeetingPackScreeningContext],
) -> str:
    parts: list[str] = []
    if secondary_note_items:
        titles = _note_context_titles(secondary_note_items)
        if mode == "experiment_proposal":
            parts.append(f"Proposal framing uses note context: {titles} (context-only).")
        elif mode == "project_progress_update":
            parts.append(f"Project note frame: {titles} (context-only).")
        elif mode == "literature_update":
            parts.append(f"Topic framing uses note context: {titles} (context-only).")
        else:
            parts.append(f"Relevance framing uses note context: {titles} (context-only).")
    if screening_contexts:
        runs = _screening_context_label(screening_contexts)
        if mode == "experiment_proposal":
            parts.append(f"Prior-evidence scope is bounded by screening run(s): {runs} (context-only).")
        elif mode == "project_progress_update":
            parts.append(f"Current project evidence scope is bounded by screening run(s): {runs} (context-only).")
        elif mode == "literature_update":
            parts.append(f"Current evidence scope is bounded by screening run(s): {runs} (context-only).")
        else:
            parts.append(f"Selection context includes screening run(s): {runs} (context-only).")
    if not parts:
        return ""
    return " " + " ".join(parts)


def _key_point_context_note(
    mode: str,
    index: int,
    secondary_note_items: list[MeetingPackSourceItem],
    screening_contexts: list[ResolvedMeetingPackScreeningContext],
) -> str | None:
    if index != 1:
        return None

    notes: list[str] = []
    if secondary_note_items:
        titles = _note_context_titles(secondary_note_items)
        if mode == "experiment_proposal":
            notes.append(
                f"Proposal note frame {titles} can motivate this prior-evidence point, but it does not strengthen the claim itself."
            )
        elif mode == "project_progress_update":
            notes.append(
                f"Project note frame {titles} explains why this claim matters operationally, but it does not override the evidence."
            )
        elif mode == "literature_update":
            notes.append(
                f"Topic note frame {titles} explains why this update is in scope, but it does not override the evidence."
            )
        else:
            notes.append(
                f"Note frame {titles} can explain relevance, but paper interpretation should stay source-first."
            )
    if screening_contexts:
        runs = _screening_context_label(screening_contexts)
        if mode == "experiment_proposal":
            notes.append(
                f"Screening scope {runs} affects which prior evidence is in the proposal set; it is contextual only."
            )
        elif mode == "project_progress_update":
            notes.append(
                f"Screening scope {runs} affects which evidence is currently surfaced for the project; it is contextual only."
            )
        elif mode == "literature_update":
            notes.append(
                f"Screening scope {runs} defines which papers are in the update set; it is contextual only."
            )
        else:
            notes.append(
                f"Screening scope {runs} explains selection context only, not claim strength."
            )
    return " ".join(notes) if notes else None


def _opening_note_bullet(mode: str, secondary_note_items: list[MeetingPackSourceItem]) -> str:
    titles = _note_context_titles(secondary_note_items)
    if mode == "experiment_proposal":
        return f"Proposal motivation includes context from: {titles}."
    if mode == "project_progress_update":
        return f"Project note frame: {titles} highlights current blockers/actions."
    if mode == "literature_update":
        return f"Topic framing note: {titles}."
    return f"Relevance frame: {titles}."


def _opening_screening_bullet(
    mode: str,
    screening_contexts: list[ResolvedMeetingPackScreeningContext],
) -> str:
    runs = _screening_context_label(screening_contexts)
    if mode == "experiment_proposal":
        return f"Proposal evidence scope is bounded by screening run(s): {runs}."
    if mode == "project_progress_update":
        return f"Current project evidence scope is bounded by screening run(s): {runs}."
    if mode == "literature_update":
        return f"Current literature scope is bounded by screening run(s): {runs}."
    return f"Discussion set includes screening context from: {runs}."


def _context_bullets(
    mode: str,
    selected_ref_titles: list[str],
    source_count: int,
    secondary_note_items: list[MeetingPackSourceItem],
    screening_contexts: list[ResolvedMeetingPackScreeningContext],
) -> list[str]:
    note_bullet = _context_note_bullet(mode, secondary_note_items) if secondary_note_items else None
    screening_bullet = (
        _context_screening_bullet(mode, screening_contexts)
        if screening_contexts
        else None
    )
    if mode == "experiment_proposal":
        bullets = [
            f"Proposal context comes from: {', '.join(selected_ref_titles[:3])}",
            f"Evidence base pulled from {source_count} structured paper source(s).",
        ]
        if note_bullet:
            bullets.append(note_bullet)
        if screening_bullet:
            bullets.append(screening_bullet)
        return bullets
    if mode == "project_progress_update":
        bullets = [
            f"Project context comes from: {', '.join(selected_ref_titles[:3])}",
            "Separate what is evidence-backed from what is still blocked operationally.",
        ]
        if note_bullet:
            bullets.append(note_bullet)
        if screening_bullet:
            bullets.append(screening_bullet)
        return bullets
    if mode == "literature_update":
        bullets = [
            f"Update context comes from: {', '.join(selected_ref_titles[:3])}",
            f"Selected evidence set includes {source_count} structured paper source(s).",
        ]
        if note_bullet:
            bullets.append(note_bullet)
        if screening_bullet:
            bullets.append(screening_bullet)
        return bullets
    bullets = [
        f"Discussion context comes from: {', '.join(selected_ref_titles[:3])}",
        f"Selected evidence set includes {source_count} structured paper source(s).",
    ]
    if note_bullet:
        bullets.append(note_bullet)
    if screening_bullet:
        bullets.append(screening_bullet)
    return bullets


def _context_note_bullet(mode: str, secondary_note_items: list[MeetingPackSourceItem]) -> str:
    titles = _note_context_titles(secondary_note_items)
    if mode == "experiment_proposal":
        return f"Proposal note context: {titles} helps explain rationale, but remains context-only."
    if mode == "project_progress_update":
        return f"Project note context: {titles} helps separate blockers/actions from evidence-backed progress."
    if mode == "literature_update":
        return f"Topic note context: {titles} frames why this set matters, but does not define the trend."
    return f"Note context: {titles} can frame discussion relevance, but does not define the paper's claim."


def _context_screening_bullet(
    mode: str,
    screening_contexts: list[ResolvedMeetingPackScreeningContext],
) -> str:
    summary = _screening_context_summary(screening_contexts[0])
    if mode == "experiment_proposal":
        return f"Proposal screening scope: {summary}; use it to explain why this prior-evidence set was selected."
    if mode == "project_progress_update":
        return f"Project screening scope: {summary}; use it to explain what is surfaced, not what is true."
    if mode == "literature_update":
        return f"Literature-update screening scope: {summary}; use it to bound the trend, not to prove it."
    return f"Discussion screening scope: {summary}; use it to explain selection context only."


def _secondary_note_items(selected_items: list[MeetingPackSourceItem]) -> list[MeetingPackSourceItem]:
    return [
        item
        for item in selected_items
        if item.type in {"paper_note", "project_note", "research_note"}
    ]


def _screening_context_summary(context: ResolvedMeetingPackScreeningContext) -> str:
    summary = (
        f"{context.run_id} (include={context.include_count}, "
        f"exclude={context.exclude_count}, unclear={context.unclear_count})"
    )
    if context.top_reason_codes:
        summary += f"; top reasons={', '.join(context.top_reason_codes)}"
    return summary


def _build_cross_source_findings(
    *,
    sources: list[ResolvedMeetingPackSource],
    screening_contexts: list[ResolvedMeetingPackScreeningContext],
    evidence_ref_map: dict[tuple[str, str, str], str],
) -> tuple[list[MeetingPackConsensus], list[MeetingPackConflict]]:
    consensus_points, conflicts = _claim_direction_findings(
        sources=sources,
        evidence_ref_map=evidence_ref_map,
    )
    if len(screening_contexts) > 1:
        conflicts.append(
            MeetingPackConflict(
                label="Selection scope differs",
                summary="Multiple screening runs were selected; their counts and reason codes may reflect different selection criteria.",
                conflict_type="selection_scope",
                source_item_ids=[context.source_item.id for context in screening_contexts],
                evidence_refs=[],
            )
        )
    unmatched_screening_runs = [context.run_id for context in screening_contexts if not context.matched_paper_slugs]
    if unmatched_screening_runs:
        conflicts.append(
            MeetingPackConflict(
                label="Selection context only",
                summary=(
                    "Screening context without mapped structured papers: "
                    f"{', '.join(unmatched_screening_runs)}. Treat it as selection context only."
                ),
                conflict_type="selection_scope",
                source_item_ids=[
                    context.source_item.id
                    for context in screening_contexts
                    if context.run_id in unmatched_screening_runs
                ],
                evidence_refs=[],
            )
        )
    return _dedupe_consensus_points(consensus_points), _dedupe_conflicts(conflicts)


def _claim_direction_findings(
    *,
    sources: list[ResolvedMeetingPackSource],
    evidence_ref_map: dict[tuple[str, str, str], str],
) -> tuple[list[MeetingPackConsensus], list[MeetingPackConflict]]:
    families = _focus_families(
        _claim_focus_rows(
            sources=sources,
            evidence_ref_map=evidence_ref_map,
        )
    )

    ranked_consensus: list[tuple[int, int, int, str, MeetingPackConsensus]] = []
    ranked_conflicts: list[tuple[int, int, str, MeetingPackConflict]] = []
    aligned_families: list[dict[str, Any]] = []
    partial_families: list[dict[str, Any]] = []
    for family in families:
        source_item_ids = _sorted_source_item_ids(
            list(dict.fromkeys(str(row["source_item_id"]) for row in family["rows"]))
        )
        if len(source_item_ids) < 2:
            continue
        orientation = _focus_family_orientation(family["rows"])
        directions = _family_directions(family["rows"], orientation)
        evidence_refs = _family_evidence_refs(family["rows"])
        if _directions_conflict(directions):
            partial_support = _majority_direction_support(
                family["rows"],
                orientation=orientation,
            )
            if partial_support is not None:
                partial_consensus = _build_majority_direction_consensus(
                    label=str(family["label"]),
                    direction=str(partial_support["direction"]),
                    orientation=orientation,
                    supporting_source_ids=list(partial_support["supporting_source_ids"]),
                    outlier_source_item_ids=list(partial_support["outlier_source_item_ids"]),
                    total_sources=int(partial_support["total_sources"]),
                    outlier_counts=Counter(partial_support["outlier_counts"]),
                    evidence_refs=list(partial_support["evidence_refs"]),
                )
                ranked_consensus.append(
                    (
                        2,
                        len(partial_consensus.source_item_ids),
                        len(partial_consensus.evidence_refs),
                        str(family["label"]),
                        partial_consensus,
                    )
                )
                partial_families.append(
                    {
                        "label": str(family["label"]),
                        "direction": str(partial_support["direction"]),
                        "orientation": orientation,
                        "pattern_direction": _cross_focus_pattern_direction(
                            family["rows"],
                            str(partial_support["direction"]),
                            orientation,
                        ),
                        "pattern_orientation": _cross_focus_pattern_orientation(
                            family["rows"],
                            orientation,
                        ),
                        "supporting_source_item_ids": list(partial_support["supporting_source_ids"]),
                        "observed_source_item_ids": list(partial_support["observed_source_item_ids"]),
                        "total_sources": int(partial_support["total_sources"]),
                        "outlier_source_item_ids": list(partial_support["outlier_source_item_ids"]),
                        "evidence_refs": list(partial_support["evidence_refs"]),
                    }
                )
            conflict = MeetingPackConflict(
                label=f"Possible divergence: {family['label']}",
                summary=(
                    f"Selected sources describe {family['label']} with "
                    f"{_direction_conflict_summary(family['rows'], orientation)}. Compare source-specific claims before "
                    "presenting a consensus conclusion."
                ),
                conflict_type="possible_divergence",
                source_item_ids=source_item_ids,
                evidence_refs=evidence_refs,
            )
            ranked_conflicts.append(
                (len(source_item_ids), len(evidence_refs), str(family["label"]), conflict)
            )
            continue
        if not _family_directions_align(family["rows"], orientation):
            continue
        direction = _aligned_family_direction(family["rows"], orientation)
        consensus = MeetingPackConsensus(
            label=f"Directional convergence: {family['label']}",
            summary=(
                f"Selected sources describe {family['label']} with "
                f"{_direction_consensus_summary(direction, orientation)} across {len(source_item_ids)} source(s). "
                "Treat this as draft convergence only; re-check methods and effect size before presenting it as settled."
            ),
            consensus_type="directional_alignment",
            source_item_ids=source_item_ids,
            evidence_refs=evidence_refs,
        )
        ranked_consensus.append(
            (3, len(source_item_ids), len(evidence_refs), str(family["label"]), consensus)
        )
        aligned_families.append(
            {
                "label": str(family["label"]),
                "direction": direction,
                "orientation": orientation,
                "pattern_direction": _cross_focus_pattern_direction(family["rows"], direction, orientation),
                "pattern_orientation": _cross_focus_pattern_orientation(family["rows"], orientation),
                "source_item_ids": source_item_ids,
                "evidence_refs": evidence_refs,
            }
        )

    for pattern_consensus in _cross_focus_pattern_consensus(aligned_families):
        ranked_consensus.append(
            (
                5,
                len(pattern_consensus.source_item_ids),
                len(pattern_consensus.evidence_refs),
                pattern_consensus.label,
                pattern_consensus,
            )
        )
    for pattern_consensus in _cross_focus_majority_pattern_consensus(partial_families):
        ranked_consensus.append(
            (
                4,
                len(pattern_consensus.source_item_ids),
                len(pattern_consensus.evidence_refs),
                pattern_consensus.label,
                pattern_consensus,
            )
        )

    ranked_consensus.sort(key=lambda item: (-item[0], -item[1], -item[2], item[3]))
    ranked_conflicts.sort(key=lambda item: (-item[0], -item[1], item[2]))
    return (
        [consensus for _priority, _count, _refs, _label, consensus in ranked_consensus[:3]],
        [conflict for _count, _refs, _label, conflict in ranked_conflicts[:3]],
    )


def _claim_focus_rows(
    *,
    sources: list[ResolvedMeetingPackSource],
    evidence_ref_map: dict[tuple[str, str, str], str],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for source in sources:
        for claim in source.structured_state.claimset:
            direction = _claim_direction(claim.claim)
            if direction == "unknown":
                continue
            evidence_refs = _claim_ref_ids(source.source_item.ref, claim, evidence_ref_map)
            for term in _claim_focus_terms(source.structured_state, claim):
                roots = _focus_term_roots(term)
                if not roots:
                    continue
                rows.append(
                    {
                        "term": term,
                        "roots": roots,
                        "source_item_id": source.source_item.id,
                        "direction": direction,
                        "evidence_refs": evidence_refs,
                    }
                )
    return rows


def _focus_families(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not rows:
        return []

    term_roots: dict[str, set[str]] = {}
    for row in rows:
        term_roots.setdefault(str(row["term"]), set()).update(set(row["roots"]))

    parents = {term: term for term in term_roots}

    def _find(term: str) -> str:
        parent = parents[term]
        if parent != term:
            parents[term] = _find(parent)
        return parents[term]

    def _union(left: str, right: str) -> None:
        left_root = _find(left)
        right_root = _find(right)
        if left_root != right_root:
            parents[right_root] = left_root

    terms = sorted(term_roots)
    for index, left in enumerate(terms):
        for right in terms[index + 1 :]:
            if _focus_terms_match(term_roots[left], term_roots[right]):
                _union(left, right)

    grouped_rows: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        family_key = _find(str(row["term"]))
        grouped_rows.setdefault(family_key, []).append(row)

    families: list[dict[str, Any]] = []
    for family_key, family_rows in grouped_rows.items():
        families.append(
            {
                "label": _preferred_focus_label(family_rows, fallback=family_key),
                "rows": family_rows,
            }
        )
    return families


def _family_evidence_refs(rows: list[dict[str, Any]]) -> list[str]:
    evidence_refs: list[str] = []
    for row in rows:
        for ref_id in row["evidence_refs"]:
            if ref_id not in evidence_refs:
                evidence_refs.append(ref_id)
    return _sorted_ref_ids(evidence_refs)


def _preferred_focus_label(rows: list[dict[str, Any]], *, fallback: str) -> str:
    counts = {}
    for row in rows:
        term = str(row["term"])
        counts[term] = counts.get(term, 0) + 1
    ranked = sorted(counts.items(), key=lambda item: (-item[1], -len(item[0]), item[0]))
    return ranked[0][0] if ranked else fallback


def _focus_terms_match(left: set[str], right: set[str]) -> bool:
    shared = left & right
    if not shared:
        return False
    if any(root.endswith("_family") for root in shared):
        return True
    if left == right or len(shared) >= 2:
        return True
    return len(shared) == 1 and (len(left) == 1 or len(right) == 1)


def _claim_focus_terms(state: Any, claim: Any) -> list[str]:
    raw_terms = [
        *getattr(claim, "tags", []),
        *getattr(claim, "outcomes", []),
        *getattr(state, "outcomes", []),
        *getattr(state, "entities", []),
        *getattr(state, "mesh", []),
    ]
    terms: list[str] = []
    for raw in raw_terms:
        normalized = _normalize_focus_term(raw)
        if normalized and normalized not in terms:
            terms.append(normalized)
    return terms[:3]


def _normalize_focus_term(value: Any) -> str:
    tokens = FOCUS_TERM_TOKEN_PATTERN.findall(str(value or "").lower())
    if not tokens:
        return ""
    return " ".join(tokens[:4])


def _claim_direction(text: str) -> str:
    normalized = _normalize_claim_text(text)
    if not normalized:
        return "unknown"
    if any(phrase in normalized for phrase in NULL_DIRECTION_PHRASES):
        return "null_like"
    tokens = set(normalized.split())
    has_decrease = bool(tokens & DECREASE_DIRECTION_TOKENS)
    has_increase = bool(tokens & INCREASE_DIRECTION_TOKENS)
    has_benefit = bool(tokens & BENEFIT_DIRECTION_TOKENS)
    has_harm = bool(tokens & HARM_DIRECTION_TOKENS)
    matched_direction_count = sum([has_decrease, has_increase, has_benefit, has_harm])
    if matched_direction_count != 1:
        return "unknown"
    if has_decrease:
        return "decrease_like"
    if has_increase:
        return "increase_like"
    if has_benefit:
        return "benefit_like"
    if has_harm:
        return "harm_like"
    return "unknown"


def _normalize_claim_text(text: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9]+", " ", str(text or "").lower()).split())


def _focus_term_roots(term: str) -> set[str]:
    tokens = FOCUS_TERM_TOKEN_PATTERN.findall(term.lower())
    roots: list[str] = []
    for token in tokens:
        root = _canonical_focus_root(_focus_token_root(token))
        if not root or len(root) < 4:
            continue
        if token in FOCUS_GENERIC_TOKENS:
            continue
        if root not in roots:
            roots.append(root)
    for alias in sorted(_focus_family_aliases(set(roots))):
        if alias not in roots:
            roots.append(alias)
    if roots:
        return set(roots)

    fallback_roots = [
        _canonical_focus_root(_focus_token_root(token))
        for token in tokens
        if len(_canonical_focus_root(_focus_token_root(token))) >= 4
    ]
    return {root for root in fallback_roots[:1] if root}


def _focus_token_root(token: str) -> str:
    root = token.lower()
    for suffix in (
        "ations",
        "ation",
        "atory",
        "ators",
        "ments",
        "ment",
        "ances",
        "ance",
        "ences",
        "ence",
        "ities",
        "ity",
        "ions",
        "ion",
        "ings",
        "ing",
        "edly",
        "ed",
        "ies",
        "es",
        "s",
        "ary",
        "ory",
        "ive",
        "al",
        "ic",
        "ly",
    ):
        if root.endswith(suffix) and len(root) - len(suffix) >= 4:
            root = root[: -len(suffix)]
            break
    return root


def _canonical_focus_root(root: str) -> str:
    return FOCUS_ROOT_ALIASES.get(root, root)


def _focus_family_aliases(roots: set[str]) -> set[str]:
    aliases: set[str] = set()
    for alias, rule_groups in FOCUS_DERIVED_FAMILIES.items():
        if any(rule_group <= roots for rule_group in rule_groups):
            aliases.add(alias)
    return aliases


def _focus_family_orientation(rows: list[dict[str, Any]]) -> str | None:
    roots: set[str] = set()
    for row in rows:
        roots.update(set(row["roots"]))
    higher_is_better = bool(roots & HIGHER_IS_BETTER_ROOTS)
    higher_is_worse = bool(roots & HIGHER_IS_WORSE_ROOTS)
    if higher_is_better and not higher_is_worse:
        return "higher_is_better"
    if higher_is_worse and not higher_is_better:
        return "higher_is_worse"
    row_orientations = {
        row_orientation
        for row in rows
        if (row_orientation := _row_orientation(set(row["roots"]))) is not None
    }
    if row_orientations and len(row_orientations) == 2 and all(
        _row_orientation(set(row["roots"])) is not None for row in rows
    ):
        return "focus_relative"
    return None


def _family_directions(rows: list[dict[str, Any]], orientation: str | None) -> set[str]:
    return {
        mapped
        for row in rows
        if (mapped := _effective_row_direction(row, orientation)) != "unknown"
    }


def _family_single_directions(
    rows: list[dict[str, Any]],
    orientation: str | None,
) -> dict[str, str]:
    per_source: dict[str, set[str]] = {}
    for row in rows:
        direction = _effective_row_direction(row, orientation)
        if direction == "unknown":
            continue
        per_source.setdefault(str(row["source_item_id"]), set()).add(direction)
    return {
        source_item_id: next(iter(directions))
        for source_item_id, directions in per_source.items()
        if len(directions) == 1
    }


def _family_directions_align(rows: list[dict[str, Any]], orientation: str | None) -> bool:
    single_directions = _family_single_directions(rows, orientation)
    if len(single_directions) < 2:
        return False
    aligned = set(single_directions.values())
    return len(aligned) == 1 and "unknown" not in aligned


def _aligned_family_direction(rows: list[dict[str, Any]], orientation: str | None) -> str:
    aligned = set(_family_single_directions(rows, orientation).values())
    return next(iter(aligned)) if aligned else "unknown"


def _majority_direction_consensus(
    rows: list[dict[str, Any]],
    *,
    label: str,
    orientation: str | None,
) -> MeetingPackConsensus | None:
    support = _majority_direction_support(rows, orientation=orientation)
    if support is None:
        return None
    return _build_majority_direction_consensus(
        label=label,
        direction=str(support["direction"]),
        orientation=orientation,
        supporting_source_ids=list(support["supporting_source_ids"]),
        outlier_source_item_ids=list(support["outlier_source_item_ids"]),
        total_sources=int(support["total_sources"]),
        outlier_counts=Counter(support["outlier_counts"]),
        evidence_refs=list(support["evidence_refs"]),
    )


def _majority_direction_support(
    rows: list[dict[str, Any]],
    *,
    orientation: str | None,
) -> dict[str, Any] | None:
    single_directions = _family_single_directions(rows, orientation)
    total_sources = len(single_directions)
    if total_sources < 3:
        return None

    counts = Counter(single_directions.values())
    if len(counts) < 2:
        return None
    ranked = counts.most_common()
    top_direction, top_count = ranked[0]
    second_count = ranked[1][1]
    if top_count < 2 or top_count <= second_count:
        return None

    supporting_source_ids = [
        source_item_id
        for source_item_id, direction in single_directions.items()
        if direction == top_direction
    ]
    supporting_source_ids = _sorted_source_item_ids(supporting_source_ids)
    outlier_counts = Counter(
        direction
        for direction in single_directions.values()
        if direction != top_direction
    )
    outlier_source_ids = [
        source_item_id
        for source_item_id, direction in single_directions.items()
        if direction != top_direction
    ]
    outlier_source_ids = _sorted_source_item_ids(outlier_source_ids)
    if not supporting_source_ids or not outlier_counts or not outlier_source_ids:
        return None

    evidence_refs = _family_supporting_evidence_refs(
        rows,
        supporting_source_ids=supporting_source_ids,
        direction=top_direction,
        orientation=orientation,
    )
    return {
        "direction": top_direction,
        "supporting_source_ids": supporting_source_ids,
        "observed_source_item_ids": _sorted_source_item_ids(list(single_directions)),
        "total_sources": total_sources,
        "outlier_counts": outlier_counts,
        "outlier_source_item_ids": outlier_source_ids,
        "evidence_refs": evidence_refs,
    }


def _build_majority_direction_consensus(
    *,
    label: str,
    direction: str,
    orientation: str | None,
    supporting_source_ids: list[str],
    outlier_source_item_ids: list[str],
    total_sources: int,
    outlier_counts: Counter[str],
    evidence_refs: list[str],
) -> MeetingPackConsensus:
    support_count = len(supporting_source_ids)
    return MeetingPackConsensus(
        label=f"Partial directional convergence: {label}",
        summary=(
            f"{support_count} of {total_sources} sources describe {label} with "
            f"{_direction_consensus_summary(direction, orientation)}; "
            f"{_direction_remainder_summary(outlier_counts, orientation)}. "
            "Treat this as partial convergence only and re-check the outlier sources before presenting a consensus conclusion."
        ),
        consensus_type="majority_directional_alignment",
        source_item_ids=supporting_source_ids,
        outlier_source_item_ids=outlier_source_item_ids,
        evidence_refs=evidence_refs,
    )


def _family_supporting_evidence_refs(
    rows: list[dict[str, Any]],
    *,
    supporting_source_ids: list[str],
    direction: str,
    orientation: str | None,
) -> list[str]:
    supporting_ids = set(supporting_source_ids)
    evidence_refs: list[str] = []
    for row in rows:
        if str(row["source_item_id"]) not in supporting_ids:
            continue
        row_direction = _effective_row_direction(row, orientation)
        if row_direction != direction:
            continue
        for ref_id in row["evidence_refs"]:
            if ref_id not in evidence_refs:
                evidence_refs.append(ref_id)
    return _sorted_ref_ids(evidence_refs)


def _cross_focus_majority_pattern_consensus(
    partial_families: list[dict[str, Any]],
) -> list[MeetingPackConsensus]:
    grouped: dict[tuple[tuple[str, ...], tuple[str, ...], str, str | None], list[dict[str, Any]]] = {}
    for family in partial_families:
        observed_source_item_ids = tuple(
            str(source_item_id) for source_item_id in family["observed_source_item_ids"]
        )
        supporting_source_item_ids = tuple(
            str(source_item_id) for source_item_id in family["supporting_source_item_ids"]
        )
        direction = str(family.get("pattern_direction") or family["direction"])
        orientation = family.get("pattern_orientation", family["orientation"])
        grouped.setdefault(
            (observed_source_item_ids, supporting_source_item_ids, direction, orientation),
            [],
        ).append(family)

    consensus_points: list[MeetingPackConsensus] = []
    for (observed_source_item_ids, supporting_source_item_ids, direction, orientation), families in grouped.items():
        labels = list(dict.fromkeys(str(family["label"]) for family in families))
        if len(labels) < 2:
            continue
        evidence_sets = {
            tuple(str(ref_id) for ref_id in family["evidence_refs"])
            for family in families
            if family["evidence_refs"]
        }
        if len(evidence_sets) < 2:
            continue
        label_summary = _focus_label_summary(labels)
        support_count = len(supporting_source_item_ids)
        total_sources = len(observed_source_item_ids)
        remaining_count = total_sources - support_count
        remaining_unit = "source" if remaining_count == 1 else "sources"
        remaining_verb = "diverges" if remaining_count == 1 else "diverge"
        outlier_source_item_ids = [
            source_item_id
            for source_item_id in observed_source_item_ids
            if source_item_id not in supporting_source_item_ids
        ]
        consensus_points.append(
            MeetingPackConsensus(
                label=f"Partial cross-focus convergence: {label_summary}",
                summary=(
                    f"The same {support_count} of {total_sources} sources describe {label_summary} with "
                    f"{_direction_consensus_summary(direction, orientation)} across these families; the remaining "
                    f"{remaining_count} {remaining_unit} {remaining_verb} across at least one family. Treat this as partial "
                    "cross-focus convergence only and re-check the outlier sources before presenting a shared pattern."
                ),
                consensus_type="cross_focus_majority_pattern",
                source_item_ids=list(supporting_source_item_ids),
                outlier_source_item_ids=outlier_source_item_ids,
                evidence_refs=_merge_family_evidence_refs(families),
            )
        )
    consensus_points.sort(key=lambda item: (-len(item.source_item_ids), -len(item.evidence_refs), item.label))
    return consensus_points


def _cross_focus_pattern_consensus(
    aligned_families: list[dict[str, Any]],
) -> list[MeetingPackConsensus]:
    grouped: dict[tuple[tuple[str, ...], str, str | None], list[dict[str, Any]]] = {}
    for family in aligned_families:
        source_item_ids = tuple(str(source_item_id) for source_item_id in family["source_item_ids"])
        direction = str(family.get("pattern_direction") or family["direction"])
        orientation = family.get("pattern_orientation", family["orientation"])
        grouped.setdefault((source_item_ids, direction, orientation), []).append(family)

    consensus_points: list[MeetingPackConsensus] = []
    for (source_item_ids, direction, orientation), families in grouped.items():
        labels = list(dict.fromkeys(str(family["label"]) for family in families))
        if len(labels) < 2:
            continue
        evidence_sets = {
            tuple(str(ref_id) for ref_id in family["evidence_refs"])
            for family in families
            if family["evidence_refs"]
        }
        if len(evidence_sets) < 2:
            continue
        label_summary = _focus_label_summary(labels)
        source_count = len(source_item_ids)
        source_unit = "source" if source_count == 1 else "sources"
        consensus_points.append(
            MeetingPackConsensus(
                label=f"Cross-focus pattern: {label_summary}",
                summary=(
                    f"The same {source_count} {source_unit} describe {label_summary} with "
                    f"{_direction_consensus_summary(direction, orientation)}. Treat this as a repeated cross-focus "
                    "pattern across distinct evidence-linked families, not as proof that these outcomes are interchangeable."
                ),
                consensus_type="cross_focus_pattern",
                source_item_ids=list(source_item_ids),
                evidence_refs=_merge_family_evidence_refs(families),
            )
        )
    consensus_points.sort(key=lambda item: (-len(item.source_item_ids), -len(item.evidence_refs), item.label))
    return consensus_points


def _cross_focus_pattern_direction(
    rows: list[dict[str, Any]],
    direction: str,
    orientation: str | None,
) -> str:
    if orientation is not None:
        return direction
    shared_row_orientation = _shared_row_orientation(rows)
    if shared_row_orientation is None:
        return direction
    mapped = _mapped_family_direction(direction, shared_row_orientation)
    return mapped if mapped != "unknown" else direction


def _cross_focus_pattern_orientation(
    rows: list[dict[str, Any]],
    orientation: str | None,
) -> str | None:
    if orientation is not None:
        return orientation
    return _shared_row_orientation(rows)


def _shared_row_orientation(rows: list[dict[str, Any]]) -> str | None:
    row_orientations = {
        row_orientation
        for row in rows
        if (row_orientation := _row_orientation(set(row["roots"]))) is not None
    }
    if len(row_orientations) != 1:
        return None
    return next(iter(row_orientations))


def _merge_family_evidence_refs(families: list[dict[str, Any]]) -> list[str]:
    evidence_refs: list[str] = []
    for family in families:
        for ref_id in family["evidence_refs"]:
            if ref_id not in evidence_refs:
                evidence_refs.append(ref_id)
    return _sorted_ref_ids(evidence_refs)


def _focus_label_summary(labels: list[str]) -> str:
    unique_labels = sorted(dict.fromkeys(labels), key=str.casefold)
    if not unique_labels:
        return "multiple focus families"
    if len(unique_labels) <= 3:
        return _human_join(unique_labels)
    remainder = len(unique_labels) - 3
    remainder_label = "family" if remainder == 1 else "families"
    return f"{_human_join(unique_labels[:3])}, and {remainder} more focus {remainder_label}"


def _human_join(parts: list[str]) -> str:
    if not parts:
        return ""
    if len(parts) == 1:
        return parts[0]
    if len(parts) == 2:
        return f"{parts[0]} and {parts[1]}"
    return f"{', '.join(parts[:-1])}, and {parts[-1]}"


def _sorted_ref_ids(ref_ids: list[str]) -> list[str]:
    return sorted(dict.fromkeys(ref_ids), key=_ref_sort_key)


def _ref_sort_key(ref_id: str) -> tuple[int, str]:
    match = re.search(r"(\\d+)$", ref_id)
    if match:
        return (int(match.group(1)), ref_id)
    return (10**9, ref_id)


def _sorted_source_item_ids(source_item_ids: list[str]) -> list[str]:
    return sorted(dict.fromkeys(source_item_ids), key=_source_item_sort_key)


def _source_item_sort_key(source_item_id: str) -> tuple[int, str]:
    match = re.search(r"(\\d+)$", source_item_id)
    if match:
        return (int(match.group(1)), source_item_id)
    return (10**9, source_item_id)


def _mapped_family_direction(direction: str, orientation: str) -> str:
    if direction == "null_like":
        return "null_like"
    if orientation == "higher_is_better":
        if direction in {"increase_like", "benefit_like"}:
            return "positive_outcome"
        if direction in {"decrease_like", "harm_like"}:
            return "negative_outcome"
    if orientation == "higher_is_worse":
        if direction in {"decrease_like", "benefit_like"}:
            return "positive_outcome"
        if direction in {"increase_like", "harm_like"}:
            return "negative_outcome"
    return "unknown"


def _effective_row_direction(row: dict[str, Any], orientation: str | None) -> str:
    direction = str(row["direction"])
    if orientation is None:
        return direction
    if orientation == "focus_relative":
        row_orientation = _row_orientation(set(row["roots"]))
        if row_orientation is None:
            return "unknown"
        return _mapped_family_direction(direction, row_orientation)
    return _mapped_family_direction(direction, orientation)


def _row_orientation(roots: set[str]) -> str | None:
    higher_is_better = bool(roots & ROW_HIGHER_IS_BETTER_ROOTS)
    higher_is_worse = bool(roots & ROW_HIGHER_IS_WORSE_ROOTS)
    if higher_is_better and not higher_is_worse:
        return "higher_is_better"
    if higher_is_worse and not higher_is_better:
        return "higher_is_worse"
    return None


def _direction_consensus_summary(direction: str, orientation: str | None = None) -> str:
    label = _direction_label(direction, orientation)
    if orientation is None:
        return f"aligned {label}"
    return f"aligned {label} under a {_orientation_label(orientation)}"


def _direction_label(direction: str, orientation: str | None = None) -> str:
    if orientation is not None:
        if direction == "positive_outcome":
            return "positive-outcome wording"
        if direction == "negative_outcome":
            return "negative-outcome wording"
    if direction == "increase_like":
        return "increase-like wording"
    if direction == "decrease_like":
        return "decrease-like wording"
    if direction == "benefit_like":
        return "benefit-like wording"
    if direction == "harm_like":
        return "harm-like wording"
    return "null/no-change wording"


def _direction_set_summary(directions: set[str], orientation: str | None = None) -> str:
    labels = [_direction_label(direction, orientation) for direction in sorted(directions)]
    if not labels:
        return "mixed wording"
    if len(labels) == 1:
        summary = labels[0]
    elif len(labels) == 2:
        summary = f"{labels[0]} and {labels[1]}"
    else:
        summary = ", ".join(labels[:-1]) + f", and {labels[-1]}"
    if orientation is None:
        return summary
    return f"{summary} under a {_orientation_label(orientation)}"


def _direction_conflict_summary(rows: list[dict[str, Any]], orientation: str | None = None) -> str:
    single_direction_counts = Counter(_family_single_directions(rows, orientation).values())
    if len(single_direction_counts) < 2:
        return _direction_set_summary(_family_directions(rows, orientation), orientation)

    ranked = sorted(
        single_direction_counts.items(),
        key=lambda item: (-item[1], _direction_label(item[0], orientation)),
    )
    top_count = ranked[0][1]
    if sum(1 for _direction, count in ranked if count == top_count) > 1:
        return _direction_set_summary(set(single_direction_counts), orientation)

    primary_direction, primary_count = ranked[0]
    primary_unit = "source" if primary_count == 1 else "sources"
    remainder = [
        _counted_direction_phrase(direction, count, orientation)
        for direction, count in ranked[1:]
    ]
    if len(remainder) == 1:
        summary = (
            f"{primary_count} {primary_unit} use {_direction_label(primary_direction, orientation)} "
            f"while {remainder[0]}"
        )
        return _apply_orientation_summary(summary, orientation)
    summary = (
        f"{primary_count} {primary_unit} use {_direction_label(primary_direction, orientation)} "
        f"while {', '.join(remainder[:-1])}, and {remainder[-1]}"
    )
    return _apply_orientation_summary(summary, orientation)


def _counted_direction_phrase(direction: str, count: int, orientation: str | None = None) -> str:
    unit = "source" if count == 1 else "sources"
    verb = "uses" if count == 1 else "use"
    return f"{count} {unit} {verb} {_direction_label(direction, orientation)}"


def _direction_remainder_summary(counts: Counter[str], orientation: str | None = None) -> str:
    ranked = sorted(
        counts.items(),
        key=lambda item: (-item[1], _direction_label(item[0], orientation)),
    )
    if not ranked:
        return "no remaining sources diverge"
    parts = [
        _counted_direction_phrase(direction, count, orientation)
        for direction, count in ranked
    ]
    if len(parts) == 1:
        return parts[0]
    if len(parts) == 2:
        return f"{parts[0]} and {parts[1]}"
    return f"{', '.join(parts[:-1])}, and {parts[-1]}"


def _apply_orientation_summary(summary: str, orientation: str | None) -> str:
    if orientation is None:
        return summary
    return f"{summary} under a {_orientation_label(orientation)}"


def _orientation_label(orientation: str) -> str:
    if orientation == "higher_is_better":
        return "higher-is-better framing"
    if orientation == "focus_relative":
        return "focus-relative framing"
    return "higher-is-worse framing"


def _directions_align(rows: list[dict[str, Any]]) -> bool:
    per_source: dict[str, set[str]] = {}
    for row in rows:
        per_source.setdefault(str(row["source_item_id"]), set()).add(str(row["direction"]))
    if len(per_source) < 2 or any(len(directions) != 1 for directions in per_source.values()):
        return False
    aligned = {next(iter(directions)) for directions in per_source.values()}
    return len(aligned) == 1 and "unknown" not in aligned


def _directions_conflict(directions: set[str]) -> bool:
    if "positive_outcome" in directions and "negative_outcome" in directions:
        return True
    if "null_like" in directions and ("positive_outcome" in directions or "negative_outcome" in directions):
        return True
    if "increase_like" in directions and "decrease_like" in directions:
        return True
    if "null_like" in directions and ("increase_like" in directions or "decrease_like" in directions):
        return True
    if "null_like" in directions and ("benefit_like" in directions or "harm_like" in directions):
        return True
    if "benefit_like" in directions and "harm_like" in directions:
        return True
    return False


def _closing_bullets(mode: str) -> list[str]:
    if mode == "experiment_proposal":
        return [
            "Carry forward only the proposal assumptions that are evidence-linked.",
            "Name the riskiest failure mode before discussing execution.",
        ]
    if mode == "project_progress_update":
        return [
            "End with the next project decision, not with a generic status recap.",
            "Translate uncertainty into an explicit blocker or owner.",
        ]
    if mode == "literature_update":
        return [
            "Make the strongest convergence point and the sharpest disagreement explicit.",
            "Turn the remaining gap into one open question for the lab.",
        ]
    return [
        "Carry forward only evidence-linked claims.",
        "Mark unsupported interpretation as uncertainty, not conclusion.",
    ]
