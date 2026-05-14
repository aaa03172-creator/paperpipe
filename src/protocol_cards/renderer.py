from __future__ import annotations

from src.schemas.protocol_card import ProtocolCard, ProtocolVersion


def render_protocol_card_markdown(protocol_card: ProtocolCard, versions: list[ProtocolVersion]) -> str:
    lines: list[str] = [
        f"# {protocol_card.title}",
        "",
        f"- Protocol ID: `{protocol_card.protocol_id}`",
        f"- Source kind: `{protocol_card.source_kind}`",
        f"- Validation status: `{protocol_card.validation_status}`",
        f"- Current version: `{protocol_card.current_version_id or 'none'}`",
        "",
    ]

    if protocol_card.purpose:
        lines.extend(["## Purpose", "", protocol_card.purpose, ""])
    if protocol_card.context:
        lines.extend(["## Context", "", protocol_card.context, ""])
    if protocol_card.linked_paper_ids:
        lines.extend(["## Linked Papers", ""])
        lines.extend([f"- `{paper_id}`" for paper_id in protocol_card.linked_paper_ids])
        lines.append("")
    if protocol_card.linked_note_slugs:
        lines.extend(["## Linked Notes", ""])
        lines.extend([f"- `{note_slug}`" for note_slug in protocol_card.linked_note_slugs])
        lines.append("")

    lines.extend(["## Versions", ""])
    for version in sorted(versions, key=lambda item: (item.version_number, item.created_at, item.version_id)):
        lines.extend(
            [
                f"### v{version.version_number} `{version.version_id}`",
                "",
                f"- Status: `{version.status}`",
                f"- Created by: `{version.created_by}`",
                f"- Source refs: `{len(version.source_refs)}`",
            ]
        )
        if version.change_reason:
            lines.append(f"- Change reason: {version.change_reason}")
        lines.append("")
        if version.key_steps_summary:
            lines.append("Key steps:")
            lines.extend([f"- {item}" for item in version.key_steps_summary])
            lines.append("")
        if version.critical_conditions:
            lines.append("Critical conditions:")
            lines.extend([f"- {item}" for item in version.critical_conditions])
            lines.append("")
        if version.readouts:
            lines.append("Readouts:")
            lines.extend([f"- {item}" for item in version.readouts])
            lines.append("")
        lines.extend(["Content snapshot:", "", version.content_snapshot, ""])

    return "\n".join(lines).rstrip() + "\n"
