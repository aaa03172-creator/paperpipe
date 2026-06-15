from __future__ import annotations

import hashlib

from src.schemas.cloud_paper import (
    CloudPaperDownstreamAdapterResponse,
    CloudPaperDownstreamArtifactCandidate,
    CloudPaperObsidianExportResponse,
    CloudPaperObsidianSectionMarkers,
)

_SECTION_START_PREFIX = "<!-- paperpipe:cloud-derived:start "
_SECTION_END_MARKER = "<!-- paperpipe:cloud-derived:end -->"


def render_cloud_derived_obsidian_section(
    adapter_response: CloudPaperDownstreamAdapterResponse,
    *,
    max_text_chars: int = 280,
) -> str:
    lines = [
        (
            "<!-- paperpipe:cloud-derived:start "
            f"paper_id={adapter_response.paper_id} run_id={adapter_response.run_id} -->"
        ),
        "## Cloud-Derived Context",
        "",
        "> [!warning] Derived, non-canonical",
        "> This section is generated from cloud-derived OCR/table/figure artifacts. Do not treat it as canonical evidence unless reviewed structured state supports it.",
        "",
        f"- Paper ID: `{adapter_response.paper_id}`",
        f"- Run ID: `{adapter_response.run_id}`",
        f"- Source PDF SHA256: `{adapter_response.source_pdf_sha256}`",
        "- Canonical status: derived_noncanonical",
        "- Payload class: `{}`".format(adapter_response.payload_class),
        "",
    ]

    grouped: list[tuple[str, str, list[CloudPaperDownstreamArtifactCandidate]]] = [
        ("OCR", "ocr_text", []),
        ("Tables", "table", []),
        ("Figures", "figure", []),
        ("Figure analysis", "figure_analysis", []),
    ]
    buckets = {kind: bucket for _label, kind, bucket in grouped}
    for candidate in adapter_response.candidates:
        bucket = buckets.get(candidate.kind)
        if bucket is not None:
            bucket.append(candidate)

    for label, _kind, candidates in grouped:
        if not candidates:
            continue
        lines.extend([f"### {label}", ""])
        for candidate in candidates:
            lines.append(_candidate_markdown_line(candidate, max_text_chars=max_text_chars))
        lines.append("")

    lines.append("<!-- paperpipe:cloud-derived:end -->")
    return "\n".join(lines).rstrip() + "\n"


def prepare_cloud_derived_obsidian_export(
    adapter_response: CloudPaperDownstreamAdapterResponse,
    *,
    existing_markdown: str | None = None,
) -> CloudPaperObsidianExportResponse:
    section_markdown = render_cloud_derived_obsidian_section(adapter_response)
    note_markdown = replace_cloud_derived_obsidian_section(existing_markdown or "", section_markdown)
    start_marker = section_markdown.splitlines()[0]
    artifact_id = _obsidian_export_artifact_id(adapter_response, section_markdown)
    return CloudPaperObsidianExportResponse(
        paper_id=adapter_response.paper_id,
        run_id=adapter_response.run_id,
        artifact_id=artifact_id,
        source_pdf_sha256=adapter_response.source_pdf_sha256,
        payload_class=adapter_response.payload_class,
        section_markers=CloudPaperObsidianSectionMarkers(
            start=start_marker,
            end=_SECTION_END_MARKER,
        ),
        section_markdown=section_markdown,
        note_markdown=note_markdown,
        warnings=adapter_response.warnings,
        provenance_summary=adapter_response.provenance_summary,
    )


def replace_cloud_derived_obsidian_section(existing_markdown: str, section_markdown: str) -> str:
    section = section_markdown.strip()
    existing = str(existing_markdown or "")
    if not existing.strip():
        return section + "\n"

    start_index = existing.find(_SECTION_START_PREFIX)
    if start_index < 0:
        return _join_markdown_blocks(existing, section)

    end_index = existing.find(_SECTION_END_MARKER, start_index)
    if end_index < 0:
        return _join_markdown_blocks(existing[:start_index], section)

    end_index += len(_SECTION_END_MARKER)
    while end_index < len(existing) and existing[end_index] in "\r\n":
        end_index += 1

    prefix = existing[:start_index]
    suffix = existing[end_index:]
    return _join_markdown_blocks(prefix, section, suffix)


def _candidate_markdown_line(
    candidate: CloudPaperDownstreamArtifactCandidate,
    *,
    max_text_chars: int,
) -> str:
    text = _truncate(_single_line(candidate.text or candidate.title), max_text_chars=max_text_chars)
    page = candidate.source.page
    if candidate.kind == "ocr_text":
        return f"- OCR `{candidate.candidate_id}` page {page}: {text}"
    if candidate.kind == "table":
        return f"- Table `{candidate.candidate_id}` page {page}: {text}"
    if candidate.kind == "figure":
        route_note = " image_proxy=available" if candidate.image_route else ""
        return f"- Figure `{candidate.candidate_id}` page {page}: {text}{route_note}"
    if candidate.kind == "figure_analysis":
        return f"- Figure analysis `{candidate.candidate_id}` page {page}: {text}"
    return f"- `{candidate.candidate_id}` page {page}: {text}"


def _single_line(value: str) -> str:
    return " ".join(str(value or "").split())


def _truncate(value: str, *, max_text_chars: int) -> str:
    if len(value) <= max_text_chars:
        return value
    return value[: max(0, max_text_chars - 3)].rstrip() + "..."


def _join_markdown_blocks(*blocks: str) -> str:
    joined = "\n\n".join(block.strip() for block in blocks if block and block.strip())
    return joined.rstrip() + "\n"


def _obsidian_export_artifact_id(
    adapter_response: CloudPaperDownstreamAdapterResponse,
    section_markdown: str,
) -> str:
    digest = hashlib.sha256(
        "\n".join(
            [
                adapter_response.paper_id,
                adapter_response.run_id,
                adapter_response.source_pdf_sha256,
                section_markdown,
            ]
        ).encode("utf-8")
    ).hexdigest()[:16]
    return f"cloud_obsidian_export_{digest}"
