from __future__ import annotations

import json
from typing import Any

from src.schemas.paper_synthesis import PaperSynthesis
from src.schemas.skills import SkillClaimCard, StructuredPaperState


def render_paper_synthesis_markdown(
    synthesis: PaperSynthesis,
    *,
    state: StructuredPaperState,
    claim_cards: list[SkillClaimCard],
    run_meta: dict[str, Any],
    visual_evidence_ledger: dict[str, Any] | None = None,
) -> str:
    lines: list[str] = [
        "---",
        f"artifact_family: {synthesis.artifact_family}",
        f"template_kind: {synthesis.template_kind}",
        f"layer: {synthesis.layer}",
        f"canonical_status: {synthesis.canonical_status}",
        f"paper_slug: {_yaml_scalar(synthesis.paper_slug)}",
        f"synthesis_id: {_yaml_scalar(synthesis.synthesis_id)}",
        f"run_id: {_yaml_scalar(_display_text(str(run_meta.get('run_id') or 'unknown')))}",
        f"readiness: {synthesis.readiness}",
        f"freshness: {synthesis.freshness}",
        "required_answer_route: canonical_state_then_upstream_evidence",
        f"source_ref_count: {len(synthesis.source_refs)}",
        f"evidence_ref_count: {len(synthesis.evidence_refs)}",
        f"warning_count: {len(synthesis.warnings)}",
        f"uncertainty_note_count: {len(synthesis.uncertainty_notes)}",
        "source_refs:",
        *[
            line
            for source_ref in synthesis.source_refs
            for line in _render_source_ref_frontmatter_lines(
                source_ref.kind,
                source_ref.paper_slug,
                source_ref.run_id,
                source_ref.path,
            )
        ],
        "---",
        "",
        f"# {synthesis.title}",
        "",
        "## Layer contract",
        "",
        f"- Artifact family: `{synthesis.artifact_family}`",
        f"- Template kind: `{synthesis.template_kind}`",
        f"- Canonical status: `{synthesis.canonical_status}`",
        "- Allowed upstream inputs: canonical structured state, selected run artifacts, and optional additive gate artifacts.",
        "- Excluded truth owners: raw memory, project memory, and free-form chat/work traces.",
        "",
        f"- Synthesis ID: `{synthesis.synthesis_id}`",
        f"- Paper slug: `{synthesis.paper_slug}`",
        f"- Layer: `{synthesis.layer}`",
        f"- Canonical status: `{synthesis.canonical_status}`",
        f"- Status: `{synthesis.status}`",
        f"- Readiness: `{synthesis.readiness}`",
        f"- Freshness: `{synthesis.freshness}`",
        f"- Generated from run: `{_display_text(str(run_meta.get('run_id') or 'unknown'))}`",
        "",
    ]

    if synthesis.summary:
        lines.extend(["## Summary", "", synthesis.summary, ""])

    lines.extend(
        [
            "## Allowed source inputs",
            "",
            *[
                _render_source_ref_line(source_ref.kind, source_ref.paper_slug, source_ref.run_id, source_ref.path)
                for source_ref in synthesis.source_refs
            ],
            "",
            "## Canonical state snapshot",
            "",
            f"- Updated at: `{state.updated_at}`",
            f"- Canonical run count: `{len(state.runs)}`",
            f"- Canonical claim count: `{len(state.claimset)}`",
            f"- Canonical evidence count: `{sum(len(claim.evidence) for claim in state.claimset)}`",
            "",
            "## Selected run snapshot",
            "",
            f"- Run ID: `{_display_text(str(run_meta.get('run_id') or 'unknown'))}`",
            f"- Status: `{_display_text(str(run_meta.get('status') or 'unknown'))}`",
            f"- Finished at: `{_display_text(str(run_meta.get('finished_at') or run_meta.get('completed_at') or 'unknown'))}`",
            f"- Parser backend: `{_display_text(str(run_meta.get('parser_backend') or 'unknown'))}`",
            "",
            "## Reviewable claim snapshot",
            "",
        ]
    )

    if claim_cards:
        for index, claim in enumerate(claim_cards[:10], start=1):
            grounded_count = sum(1 for evidence in claim.evidence if evidence.grounded is True)
            lines.extend(
                [
                    f"### Claim {index}",
                    f"- Claim ID: `{claim.id}`",
                    f"- Text: {claim.claim}",
                    f"- Evidence count: `{len(claim.evidence)}`",
                    f"- Grounded evidence: `{grounded_count}/{len(claim.evidence)}`",
                ]
            )
            if claim.run_id:
                lines.append(f"- Run ID: `{claim.run_id}`")
            if claim.tags:
                lines.append(f"- Tags: {', '.join(f'`{tag}`' for tag in claim.tags)}")
            lines.append("")
        remaining = len(claim_cards) - 10
        if remaining > 0:
            lines.extend([f"- Additional claims not expanded here: `{remaining}`", ""])
    else:
        lines.extend(["- No claims were available from the selected `claimset.resolved.json`.", ""])

    if synthesis.warnings:
        lines.extend(["## Warnings", ""])
        lines.extend(f"- {warning}" for warning in synthesis.warnings)
        lines.append("")

    if synthesis.uncertainty_notes:
        lines.extend(["## Uncertainty notes", ""])
        lines.extend(f"- {note}" for note in synthesis.uncertainty_notes)
        lines.append("")

    visual_replay = _render_visual_evidence_replay(visual_evidence_ledger)
    if visual_replay:
        lines.extend(visual_replay)

    lines.extend(
        [
            "## Promotion guardrail",
            "",
            "- This compiled note is derived and reviewable, not canonical scientific truth.",
            "- Promoted biomedical answers must jump back to upstream claim/evidence/source data before reuse.",
            "",
        ]
    )

    return "\n".join(lines).strip() + "\n"


def _render_visual_evidence_replay(ledger: dict[str, Any] | None) -> list[str]:
    if not isinstance(ledger, dict):
        return []
    entries = ledger.get("entries")
    if not isinstance(entries, list) or not entries:
        return []
    metrics = ledger.get("metrics")
    metrics = metrics if isinstance(metrics, dict) else {}
    lines = [
        "## Visual evidence replay",
        "",
        "- Gate: required before promoting figure/table-backed claims from this synthesis.",
        (
            f"- Entries: `{int(metrics.get('entry_count') or len(entries))}` "
            f"(partial=`{int(metrics.get('partially_observed_count') or 0)}`, "
            f"unknown=`{int(metrics.get('unknown_count') or 0)}`)"
        ),
        "",
    ]
    for entry in entries[:8]:
        if not isinstance(entry, dict):
            continue
        locator = entry.get("figure_id") or entry.get("table_id") or entry.get("evidence_id") or "visual_evidence"
        page = entry.get("page")
        status = entry.get("status") or "unknown"
        lines.append(f"- `{locator}`: page `{page}`, status=`{status}`")
        caption = _compact(entry.get("caption"), limit=180)
        if caption:
            lines.append(f"  - Caption: {caption}")
        extracted_values = entry.get("extracted_values")
        if isinstance(extracted_values, list) and extracted_values:
            cells = []
            for value in extracted_values[:5]:
                if not isinstance(value, dict):
                    continue
                label = value.get("cell_id") or value.get("label") or "value"
                cells.append(f"{label}={_compact(value.get('value'), limit=60)}")
            if cells:
                lines.append(f"  - Parsed values: {'; '.join(cells)}")
        not_allowed = _compact_list(entry.get("not_allowed_claims"), limit=120)
        if not_allowed:
            lines.append(f"  - Not allowed: {'; '.join(not_allowed)}")
        failure_reason = entry.get("failure_reason")
        if failure_reason:
            lines.append(f"  - Failure reason: {failure_reason}")
    if len(entries) > 8:
        lines.append(f"- Additional visual evidence entries omitted from replay: `{len(entries) - 8}`")
    lines.append("")
    return lines


def _render_source_ref_line(kind: str, paper_slug: str, run_id: str | None, path: str | None) -> str:
    parts = [f"`{kind}`", f"paper=`{paper_slug}`"]
    if run_id:
        parts.append(f"run=`{run_id}`")
    if path:
        parts.append(f"path=`{path}`")
    return "- " + ", ".join(parts)


def _render_source_ref_frontmatter_lines(
    kind: str,
    paper_slug: str,
    run_id: str | None,
    path: str | None,
) -> list[str]:
    lines = [
        f"  - kind: {kind}",
        f"    paper_slug: {_yaml_scalar(paper_slug)}",
    ]
    if run_id:
        lines.append(f"    run_id: {_yaml_scalar(run_id)}")
    if path:
        lines.append(f"    path: {_yaml_scalar(path)}")
    return lines


def _display_text(value: str) -> str:
    text = str(value or "").strip()
    return text or "unknown"


def _compact(value: Any, *, limit: int) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 3)].rstrip() + "..."


def _compact_list(values: Any, *, limit: int) -> list[str]:
    if not isinstance(values, list):
        return []
    return [text for text in (_compact(value, limit=limit) for value in values[:3]) if text]


def _yaml_scalar(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)
