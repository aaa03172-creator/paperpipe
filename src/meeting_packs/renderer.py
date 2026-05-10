from __future__ import annotations

from src.schemas.meeting_pack import MeetingPack


def render_meeting_pack_markdown(pack: MeetingPack) -> str:
    lines: list[str] = []
    lines.append(f"# {pack.title}")
    lines.append("")
    lines.append(f"- Mode: {pack.mode}")
    lines.append(f"- Layer: {pack.layer}")
    lines.append(f"- Canonical status: {pack.canonical_status}")
    lines.append(f"- Status: {pack.status}")
    lines.append(f"- Readiness: {pack.readiness}")
    lines.append(f"- Created at: {pack.created_at.isoformat()}")
    if pack.regenerated_from_pack_id:
        lines.append(f"- Regenerated from: {pack.regenerated_from_pack_id}")
    source_refs = ", ".join(item.ref for item in pack.source_items) or "none"
    lines.append(f"- Sources: {source_refs}")
    lines.append("")

    lines.append("## One-page Summary")
    if pack.one_page_summary.overview:
        lines.append(pack.one_page_summary.overview)
        lines.append("")
    for point in pack.one_page_summary.key_points:
        suffix = _format_refs(point.evidence_refs)
        uncertainty = f" [Uncertain: {point.uncertainty_note}]" if point.uncertainty_note else ""
        lines.append(f"- {point.label}: {point.text}{suffix}{uncertainty}")
    for consensus in pack.one_page_summary.consensus_points:
        lines.append(
            f"- [Consensus] {consensus.label}: {consensus.summary}{_format_refs(consensus.evidence_refs)}"
        )
    for conflict in pack.one_page_summary.conflicts:
        lines.append(
            f"- [Conflict] {conflict.label}: {conflict.summary}{_format_refs(conflict.evidence_refs)}"
        )
    for item in pack.one_page_summary.uncertainties:
        lines.append(f"- Uncertainty: {item}")
    lines.append("")

    lines.append("## Slide Outline")
    for index, slide in enumerate(pack.slides, start=1):
        lines.append(f"{index}. {slide.slide_title}")
        lines.append(f"   - Purpose: {slide.purpose}")
        for bullet in slide.bullets:
            lines.append(f"   - {bullet}")
        if slide.evidence_refs:
            lines.append(f"   - Evidence: {', '.join(slide.evidence_refs)}")
        for note in slide.caution_notes:
            lines.append(f"   - Caution: {note}")
    lines.append("")

    lines.append("## Speaker Notes")
    for item in pack.speaker_notes:
        lines.append(f"- Slide {item.slide_index}: {item.text}{_format_refs(item.evidence_refs)}")
    lines.append("")

    lines.append("## Discussion Questions")
    for item in pack.discussion_questions:
        lines.append(f"- {item.question}{_format_refs(item.evidence_refs)}")
        lines.append(f"  - Rationale: {item.rationale}")
    lines.append("")

    lines.append("## Expected Questions")
    for item in pack.expected_questions:
        lines.append(f"- {item.question}{_format_refs(item.evidence_refs)}")
        lines.append(f"  - Suggested response: {item.suggested_response}")
    lines.append("")

    lines.append("## Next Steps")
    for item in pack.next_steps:
        lines.append(f"- [{item.priority}] {item.action}{_format_refs(item.evidence_refs)}")
        lines.append(f"  - Why: {item.why}")
    lines.append("")

    lines.append("## Evidence Ledger")
    for ref in pack.evidence_refs:
        location = []
        if ref.locator and ref.locator.page is not None:
            location.append(f"page {ref.locator.page}")
        if ref.locator and ref.locator.section:
            location.append(ref.locator.section)
        location_text = f" ({', '.join(location)})" if location else ""
        claim_id = f", claim_id={ref.claim_id}" if ref.claim_id else ""
        evidence_id = f", evidence_id={ref.evidence_id}" if ref.evidence_id else ""
        lines.append(f"- {ref.id}: {ref.paper_slug}{claim_id}{evidence_id}{location_text}")
        if ref.note:
            lines.append(f"  - Note: {ref.note}")

    if pack.review_artifacts:
        lines.extend(["", "## Review Artifacts"])
        for artifact in pack.review_artifacts:
            lines.append(
                f"- {artifact.kind}: {artifact.paper_slug}"
                f"{f' run={artifact.run_id}' if artifact.run_id else ''}"
                f" entries={artifact.entry_count}, partial={artifact.partially_observed_count}, unknown={artifact.unknown_count}"
            )
            if artifact.path:
                lines.append(f"  - Path: {artifact.path}")
            if artifact.replay_required:
                lines.append("  - Replay required before promoting figure/table-backed claims.")
            if artifact.note:
                lines.append(f"  - Note: {artifact.note}")

    if pack.artifact_brief is not None:
        lines.extend(
            [
                "",
                "## Artifact Brief",
                "",
                f"- Artifact family: {pack.artifact_brief.artifact_family}",
                f"- Goal: {pack.artifact_brief.communicative_intent.goal}",
                f"- Allowed evidence refs: {len(pack.artifact_brief.source_context.allowed_evidence_refs)}",
                f"- Context-only inputs: {sum(1 for item in pack.artifact_brief.source_context.source_items if item.role == 'context_only')}",
            ]
        )

    if pack.artifact_brief_review is not None:
        lines.extend(
            [
                "",
                "## Artifact Brief Review",
                "",
                f"- Status: {pack.artifact_brief_review.overall_status}",
            ]
        )
        for reason_code in pack.artifact_brief_review.reason_codes:
            lines.append(f"- Reason code: {reason_code}")
        for warning in pack.artifact_brief_review.warnings:
            lines.append(f"- Warning: {warning}")

    lines.extend(
        [
            "",
            "## Promotion guardrail",
            "",
            "- This meeting pack is a derived user-facing artifact, not canonical scientific truth.",
            "- Promoted biomedical answers must jump back to upstream claim/evidence/source data before reuse.",
        ]
    )

    return "\n".join(lines).strip() + "\n"


def _format_refs(ref_ids: list[str]) -> str:
    if not ref_ids:
        return ""
    return f" [{' ,'.join(ref_ids)}]".replace(" ,", ", ")
