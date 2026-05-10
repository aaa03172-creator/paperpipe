from __future__ import annotations

from src.meeting_packs.source_resolver import ResolvedMeetingPackBundle
from src.output_modes import resolve_meeting_pack_output_mode_family
from src.schemas.artifact_brief import (
    ArtifactBrief,
    ArtifactCommunicativeIntent,
    ArtifactPlan,
    ArtifactPlanItem,
    ArtifactPlanReview,
    ArtifactSourceContextItem,
    ArtifactTraceSummary,
    SourceContextManifest,
)
from src.schemas.chart_pack import ChartPack, ChartPackRequest
from src.schemas.meeting_pack import MeetingPack, MeetingPackGenerateRequest


_MEETING_PACK_SOURCE_CONTRACTS: dict[str, tuple[str, str, str]] = {
    "paper_slug": (
        "canonical",
        "canonical_structured_state",
        "Structured paper state is the primary scientific truth source for this artifact.",
    ),
    "paper_state": (
        "canonical",
        "canonical_structured_state",
        "Structured paper state is the primary scientific truth source for this artifact.",
    ),
    "paper_note": (
        "context_only",
        "raw_memory",
        "Paper-note context can frame communication but must not override structured claims.",
    ),
    "project_note": (
        "context_only",
        "raw_memory",
        "Project-note context can frame communication but must not override structured claims.",
    ),
    "research_note": (
        "context_only",
        "raw_memory",
        "Research-note context can frame communication but must not override structured claims.",
    ),
    "screening_decision": (
        "context_only",
        "review_gate_artifact",
        "Screening rationale is selection context only and must not be treated as evidence.",
    ),
    "project_profile": (
        "context_only",
        "compiled_knowledge",
        "Profile-derived selection context can scope the pack but does not own scientific truth.",
    ),
    "research_profile": (
        "context_only",
        "compiled_knowledge",
        "Profile-derived selection context can scope the pack but does not own scientific truth.",
    ),
    "topic": (
        "context_only",
        "compiled_knowledge",
        "Topic selectors scope retrieval only and do not become evidence-backed truth on their own.",
    ),
}

_MEETING_PACK_GOALS: dict[str, str] = {
    "journal_club": "Prepare a discussion-oriented lab meeting draft grounded in selected evidence.",
    "literature_update": "Summarize the current evidence movement for a scoped topic or source set.",
    "project_progress_update": "Translate the current evidence state into a project-facing update draft.",
    "experiment_proposal": "Package prior evidence into an experiment-proposal framing without overstating support.",
}

_MEETING_PACK_AUDIENCES: dict[str, str] = {
    "journal_club": "lab discussion participants",
    "literature_update": "research team tracking topic movement",
    "project_progress_update": "project stakeholders and operators",
    "experiment_proposal": "experiment reviewers and builders",
}

_CHART_PACK_SOURCE_CONTRACTS: dict[str, tuple[str, str, str]] = {
    "stats_report": (
        "canonical",
        "review_gate_artifact",
        "Saved verification output is the truth owner for charted verification status, not for broader paper claims.",
    ),
    "document_table": (
        "canonical",
        "canonical_structured_state",
        "Saved document-table structure is the truth owner for table-derived chart values.",
    ),
}


def build_meeting_pack_artifact_brief(
    *,
    request: MeetingPackGenerateRequest,
    bundle: ResolvedMeetingPackBundle,
    pack: MeetingPack,
) -> tuple[ArtifactBrief, ArtifactPlanReview]:
    source_context = _build_meeting_pack_source_context(bundle=bundle, pack=pack)
    communicative_intent = ArtifactCommunicativeIntent(
        artifact_family="meeting_pack",
        goal=_MEETING_PACK_GOALS[request.mode],
        audience=_MEETING_PACK_AUDIENCES[request.mode],
        output_mode_family=resolve_meeting_pack_output_mode_family(request.mode),
        mode=request.mode,
        constraints=[
            "Use canonical structured paper state as the primary scientific truth owner.",
            "Treat note, screening, topic, and profile inputs as framing or selection context only.",
            "Keep the saved output reviewable and non-canonical.",
        ],
        must_include=[
            "Selected source lineage",
            "Evidence-linked key points when support exists",
            "Visible uncertainty when support is missing or contextual",
        ],
        must_not_infer=[
            "Do not upgrade context-only inputs into evidence-backed claims.",
            "Do not present unsupported items as stronger than the saved evidence allows.",
            "Do not hide citation-grounding or support gaps behind polished wording.",
        ],
    )
    plan = _build_meeting_pack_plan(pack=pack, source_context=source_context)
    review = _review_artifact_plan(source_context=source_context, plan=plan)
    brief = ArtifactBrief(
        artifact_family="meeting_pack",
        source_context=source_context,
        communicative_intent=communicative_intent,
        plan=plan,
    )
    return brief, review


def build_chart_pack_artifact_brief(
    *,
    request: ChartPackRequest,
    pack: ChartPack,
) -> tuple[ArtifactBrief, ArtifactPlanReview]:
    source_context = _build_chart_pack_source_context(pack=pack)
    communicative_intent = ArtifactCommunicativeIntent(
        artifact_family="chart_pack",
        goal="Render deterministic charts from saved structured artifacts without introducing new scientific claims.",
        audience="artifact reviewers and downstream handoff consumers",
        mode="template_first",
        constraints=[
            "Use the named saved source artifact as the truth owner for each rendered chart.",
            "Keep transforms, warning states, and source lineage visible in saved artifacts.",
            "Treat the chart pack as a derived artifact rather than a new canonical truth store.",
        ],
        must_include=[
            "Source lineage per chart",
            "Saved data snapshot and spec references",
            "Visible warning and caution state when present",
        ],
        must_not_infer=[
            "Do not extrapolate beyond the saved source artifact.",
            "Do not hide sparse, empty, or warning-heavy chart states behind cleaner presentation.",
            "Do not treat review-gate artifacts as broader scientific truth than they actually support.",
        ],
    )
    plan = _build_chart_pack_plan(pack=pack, source_context=source_context)
    review = _review_artifact_plan(
        source_context=source_context,
        plan=plan,
        require_allowed_evidence_refs=False,
    )
    review = _augment_chart_pack_review(review=review, pack=pack, plan=plan)
    brief = ArtifactBrief(
        artifact_family="chart_pack",
        source_context=source_context,
        communicative_intent=communicative_intent,
        plan=plan,
    )
    return brief, review


def _build_meeting_pack_source_context(
    *,
    bundle: ResolvedMeetingPackBundle,
    pack: MeetingPack,
) -> SourceContextManifest:
    items: list[ArtifactSourceContextItem] = []
    for item in pack.source_items:
        role, layer, note = _MEETING_PACK_SOURCE_CONTRACTS.get(
            item.type,
            (
                "context_only",
                "compiled_knowledge",
                "Unrecognized selector types default to context-only until a stronger ownership contract exists.",
            ),
        )
        items.append(
            ArtifactSourceContextItem(
                source_item_id=item.id,
                source_type=item.type,
                ref=item.ref,
                title=item.title,
                role=role,
                layer=layer,
                note=note,
            )
        )

    return SourceContextManifest(
        source_items=items,
        allowed_evidence_refs=[ref.id for ref in pack.evidence_refs],
        trace_summary=ArtifactTraceSummary(
            selector_count=len(bundle.selected_items),
            retrieval_trace_entry_count=len(bundle.retrieval_trace),
            source_path_count=len({entry.source_path for entry in bundle.retrieval_trace if entry.source_path}),
            matched_paper_count=len({source.source_item.ref for source in bundle.sources}),
        ),
        warnings=[
            "Context-only inputs remain framing or selection aids only."
            if any(item.role == "context_only" for item in items)
            else ""
        ],
    )


def _build_chart_pack_source_context(
    *,
    pack: ChartPack,
) -> SourceContextManifest:
    items: list[ArtifactSourceContextItem] = []
    for index, source in enumerate(pack.source_items, start=1):
        role, layer, note = _CHART_PACK_SOURCE_CONTRACTS.get(
            source.source_kind,
            (
                "canonical",
                "compiled_knowledge",
                "Unrecognized chart-pack source kinds default to canonical-for-this-artifact but stay non-authoritative until classified.",
            ),
        )
        ref = f"{source.paper_id}/{source.run_id}" + (f"/{source.table_id}" if source.table_id else "")
        items.append(
            ArtifactSourceContextItem(
                source_item_id=f"chart_source_{index:02d}",
                source_type=source.source_kind,
                ref=ref,
                title=source.source_label or source.source_kind.replace("_", " "),
                role=role,
                layer=layer,
                note=note,
            )
        )

    warnings: list[str] = []
    if any(item.layer == "review_gate_artifact" for item in items):
        warnings.append(
            "Some chart sources are review-gate artifacts and should be read as verification views rather than broader paper truth."
        )

    return SourceContextManifest(
        source_items=items,
        allowed_evidence_refs=[],
        trace_summary=ArtifactTraceSummary(
            selector_count=len(pack.charts),
            retrieval_trace_entry_count=0,
            source_path_count=len({item.ref for item in items}),
            matched_paper_count=len({source.paper_id for source in pack.source_items}),
        ),
        warnings=warnings,
    )


def _build_meeting_pack_plan(
    *,
    pack: MeetingPack,
    source_context: SourceContextManifest,
) -> ArtifactPlan:
    context_source_ids = [item.source_item_id for item in source_context.source_items if item.role == "context_only"]
    plan_items: list[ArtifactPlanItem] = [
        ArtifactPlanItem(
            item_id="overview",
            kind="overview",
            label="One-page summary overview",
            support_status=_support_status([], context_source_ids=context_source_ids),
            requires_evidence=False,
            source_item_ids=context_source_ids,
            note="Overview framing may summarize context, but it must not outrank evidence-linked key points.",
        )
    ]
    plan_items.extend(
        _plan_items_from_key_points(pack=pack, context_source_ids=context_source_ids)
    )
    plan_items.extend(
        _plan_items_from_slides(pack=pack, context_source_ids=context_source_ids)
    )
    plan_items.extend(
        _plan_items_from_simple_sections(pack=pack, context_source_ids=context_source_ids)
    )
    return ArtifactPlan(
        artifact_family="meeting_pack",
        items=plan_items,
    )


def _build_chart_pack_plan(
    *,
    pack: ChartPack,
    source_context: SourceContextManifest,
) -> ArtifactPlan:
    source_item_ids_by_ref = {
        source_item.ref: source_item.source_item_id for source_item in source_context.source_items
    }
    plan_items: list[ArtifactPlanItem] = []
    for chart in pack.charts:
        source_ref = f"{chart.source_ref.paper_id}/{chart.source_ref.run_id}" + (
            f"/{chart.source_ref.table_id}" if chart.source_ref.table_id else ""
        )
        note_parts: list[str] = []
        if chart.transforms:
            note_parts.append(
                "Transforms: " + "; ".join(transform.description for transform in chart.transforms)
            )
        if chart.warnings:
            note_parts.append(
                "Warnings: "
                + " | ".join(f"[{warning.code}] {warning.message}" for warning in chart.warnings)
            )
        if chart.data_snapshot_ref is not None:
            note_parts.append(f"Data snapshot: {chart.data_snapshot_ref.path}")
        if chart.spec_ref is not None:
            note_parts.append(f"Spec: {chart.spec_ref.path}")
        source_item_id = source_item_ids_by_ref.get(source_ref)
        plan_items.append(
            ArtifactPlanItem(
                item_id=chart.chart_id,
                kind="chart",
                label=chart.title,
                support_status="direct" if source_item_id else "background_only",
                requires_evidence=False,
                source_item_ids=[source_item_id] if source_item_id else [],
                note=" ".join(note_parts) or None,
            )
        )

    return ArtifactPlan(
        artifact_family="chart_pack",
        items=plan_items,
    )


def _plan_items_from_key_points(
    *,
    pack: MeetingPack,
    context_source_ids: list[str],
) -> list[ArtifactPlanItem]:
    items: list[ArtifactPlanItem] = []
    for index, point in enumerate(pack.one_page_summary.key_points, start=1):
        items.append(
            ArtifactPlanItem(
                item_id=f"key_point_{index:02d}",
                kind="key_point",
                label=point.label,
                support_status=_support_status(point.evidence_refs, context_source_ids=context_source_ids),
                requires_evidence=True,
                evidence_refs=list(point.evidence_refs),
                source_item_ids=_source_item_ids_for_refs(pack=pack, evidence_refs=point.evidence_refs, fallback=context_source_ids),
                note=point.uncertainty_note,
            )
        )
    return items


def _plan_items_from_slides(
    *,
    pack: MeetingPack,
    context_source_ids: list[str],
) -> list[ArtifactPlanItem]:
    items: list[ArtifactPlanItem] = []
    for index, slide in enumerate(pack.slides, start=1):
        items.append(
            ArtifactPlanItem(
                item_id=f"slide_{index:02d}",
                kind="slide",
                label=slide.slide_title,
                support_status=_support_status(slide.evidence_refs, context_source_ids=context_source_ids),
                requires_evidence=bool(slide.evidence_refs),
                evidence_refs=list(slide.evidence_refs),
                source_item_ids=_source_item_ids_for_refs(pack=pack, evidence_refs=slide.evidence_refs, fallback=context_source_ids),
                note=" | ".join(slide.caution_notes) or None,
            )
        )
    return items


def _plan_items_from_simple_sections(
    *,
    pack: MeetingPack,
    context_source_ids: list[str],
) -> list[ArtifactPlanItem]:
    items: list[ArtifactPlanItem] = []
    section_specs = [
        ("discussion_question", pack.discussion_questions),
        ("expected_question", pack.expected_questions),
        ("next_step", pack.next_steps),
    ]
    for kind, rows in section_specs:
        for index, row in enumerate(rows, start=1):
            evidence_refs = list(getattr(row, "evidence_refs", []) or [])
            label = (
                getattr(row, "question", None)
                or getattr(row, "action", None)
                or f"{kind}_{index:02d}"
            )
            items.append(
                ArtifactPlanItem(
                    item_id=f"{kind}_{index:02d}",
                    kind=kind,
                    label=str(label),
                    support_status=_support_status(evidence_refs, context_source_ids=context_source_ids),
                    requires_evidence=False,
                    evidence_refs=evidence_refs,
                    source_item_ids=_source_item_ids_for_refs(pack=pack, evidence_refs=evidence_refs, fallback=context_source_ids),
                )
            )
    return items


def _review_artifact_plan(
    *,
    source_context: SourceContextManifest,
    plan: ArtifactPlan,
    require_allowed_evidence_refs: bool = True,
) -> ArtifactPlanReview:
    missing_direct_support_item_ids = [
        item.item_id
        for item in plan.items
        if item.requires_evidence and item.support_status != "direct"
    ]
    context_only_source_item_ids = [
        item.source_item_id for item in source_context.source_items if item.role == "context_only"
    ]
    context_only_item_ids = [item.item_id for item in plan.items if item.support_status == "context_only"]
    background_only_item_ids = [item.item_id for item in plan.items if item.support_status == "background_only"]
    warnings: list[str] = []
    reason_codes: list[str] = []

    if require_allowed_evidence_refs and not source_context.allowed_evidence_refs:
        warnings.append("No allowed evidence refs were available for this artifact brief.")
        reason_codes.append("NO_ALLOWED_EVIDENCE_REFS")
    if missing_direct_support_item_ids:
        warnings.append("Some evidence-required plan items do not have direct evidence refs.")
        reason_codes.append("MISSING_DIRECT_SUPPORT")
    if context_only_source_item_ids:
        warnings.append("Context-only inputs are present and must not be promoted into scientific truth.")
        reason_codes.append("CONTEXT_ONLY_SOURCE_PRESENT")

    return ArtifactPlanReview(
        overall_status="warn" if reason_codes else "pass",
        warnings=warnings,
        reason_codes=reason_codes,
        direct_supported_item_count=sum(1 for item in plan.items if item.support_status == "direct"),
        evidence_required_item_count=sum(1 for item in plan.items if item.requires_evidence),
        missing_direct_support_item_ids=missing_direct_support_item_ids,
        context_only_source_item_ids=context_only_source_item_ids,
        context_only_item_ids=context_only_item_ids,
        background_only_item_ids=background_only_item_ids,
    )


def _augment_chart_pack_review(
    *,
    review: ArtifactPlanReview,
    pack: ChartPack,
    plan: ArtifactPlan,
) -> ArtifactPlanReview:
    warnings = list(review.warnings)
    reason_codes = list(review.reason_codes)

    if pack.warnings or any(chart.warnings for chart in pack.charts):
        warnings.append("Saved chart warnings are present and must remain visible in viewers and exports.")
        reason_codes.append("CHART_WARNING_PRESENT")

    if any(not item.source_item_ids for item in plan.items):
        warnings.append("Some chart plan items did not bind back to a saved source artifact.")
        reason_codes.append("MISSING_SOURCE_BINDING")

    return review.model_copy(
        update={
            "overall_status": "warn" if reason_codes else "pass",
            "warnings": warnings,
            "reason_codes": reason_codes,
        }
    )


def _source_item_ids_for_refs(
    *,
    pack: MeetingPack,
    evidence_refs: list[str],
    fallback: list[str],
) -> list[str]:
    if not evidence_refs:
        return list(fallback)
    source_refs = {ref.id: ref.paper_slug for ref in pack.evidence_refs}
    ids: list[str] = []
    for evidence_ref in evidence_refs:
        paper_slug = source_refs.get(evidence_ref)
        if not paper_slug:
            continue
        for source_item in pack.source_items:
            if source_item.ref != paper_slug:
                continue
            if source_item.id not in ids:
                ids.append(source_item.id)
    return ids or list(fallback)


def _support_status(evidence_refs: list[str], *, context_source_ids: list[str]) -> str:
    if evidence_refs:
        return "direct"
    if context_source_ids:
        return "context_only"
    return "background_only"
