from __future__ import annotations

from src.schemas.cloud_paper import CloudPaperDownstreamAdapterResponse
from src.schemas.meeting_pack import (
    MeetingPackCloudDerivedContext,
    MeetingPackCloudDerivedContextItem,
)


def build_meeting_pack_cloud_derived_context(
    adapter_response: CloudPaperDownstreamAdapterResponse,
) -> MeetingPackCloudDerivedContext:
    items: list[MeetingPackCloudDerivedContextItem] = []
    for candidate in adapter_response.candidates:
        if "meeting_pack" not in candidate.allowed_lanes:
            continue
        items.append(
            MeetingPackCloudDerivedContextItem(
                context_id=f"cloudctx_{len(items) + 1:02d}",
                candidate_id=candidate.candidate_id,
                kind=candidate.kind,
                paper_id=candidate.paper_id,
                run_id=candidate.run_id,
                title=candidate.title,
                text=candidate.text,
                source_page=candidate.source.page,
                source_block_id=candidate.source.block_id,
                source_pdf_sha256=candidate.source.source_pdf_sha256,
                payload_class=candidate.payload_class,
                support_type="background",
                canonical_status=candidate.canonical_status,
                confidence=candidate.confidence,
                image_route=candidate.image_route,
                evidence_refs=[],
            )
        )

    return MeetingPackCloudDerivedContext(
        paper_id=adapter_response.paper_id,
        run_id=adapter_response.run_id,
        source_pdf_sha256=adapter_response.source_pdf_sha256,
        readiness="background_only",
        payload_class=adapter_response.payload_class,
        items=items,
        warnings=[warning.message for warning in adapter_response.warnings],
    )
