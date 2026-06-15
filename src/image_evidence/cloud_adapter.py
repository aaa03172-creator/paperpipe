from __future__ import annotations

from src.schemas.cloud_paper import CloudPaperDownstreamAdapterResponse
from src.schemas.image_evidence import (
    ImageDerivedOutput,
    ImageEvidenceRequest,
    ImageMetadata,
    ImageSourceRef,
    ImageWarning,
)


def build_cloud_derived_figure_image_evidence_request(
    adapter_response: CloudPaperDownstreamAdapterResponse,
    *,
    figure_id: str,
) -> ImageEvidenceRequest:
    figure = next(
        (
            candidate
            for candidate in adapter_response.candidates
            if candidate.kind == "figure"
            and candidate.candidate_id == figure_id
            and "image_evidence" in candidate.allowed_lanes
        ),
        None,
    )
    if figure is None:
        raise FileNotFoundError(f"cloud-derived figure candidate not found: {figure_id}")
    if not figure.image_route or not figure.image_route.startswith("/api/cloud/papers/"):
        raise ValueError("cloud-derived figure candidate requires a same-origin image proxy route")

    image_evidence_id = f"imageev_cloud_{_safe_id(adapter_response.paper_id)}_{_safe_id(figure.candidate_id)}"
    note = (
        "Cloud-derived figure candidate; "
        f"source_pdf_sha256={adapter_response.source_pdf_sha256}; "
        f"run_id={adapter_response.run_id}; "
        f"candidate_id={figure.candidate_id}; "
        "canonical_status=derived_noncanonical."
    )

    return ImageEvidenceRequest(
        image_evidence_id=image_evidence_id,
        title=figure.title,
        paper_id=adapter_response.paper_id,
        paper_slug=adapter_response.paper_id,
        source_ref=ImageSourceRef(
            source_kind="external_image_ref",
            external_ref=figure.image_route,
            source_label=figure.title,
        ),
        content_format="image/png",
        metadata=ImageMetadata(
            filename=f"{figure.candidate_id}.png",
            modality="cloud-derived-pdf-figure",
            acquisition_note=note,
        ),
        derived_outputs=[
            ImageDerivedOutput(
                derived_output_id=f"derived_{_safe_id(figure.candidate_id)}",
                kind="representative_crop",
                source_image_evidence_id=image_evidence_id,
                created_by="paperpipe-cloud-paper-adapter",
                created_at=adapter_response.provenance_summary.created_at,
                tool_name=adapter_response.provenance_summary.processor_name,
                tool_version=adapter_response.provenance_summary.processor_version,
                external_ref=figure.image_route,
                note=note,
            )
        ],
        linked_claim_refs=[],
        linked_artifact_refs=[],
        warnings=[
            ImageWarning(
                code="cloud_derived_noncanonical",
                severity="warning",
                message="This Image Evidence request uses a cloud-derived figure crop, not canonical structured evidence.",
            )
        ],
    )


def _safe_id(value: str) -> str:
    cleaned = "".join(character if character.isalnum() or character in "._-" else "_" for character in value.strip())
    return cleaned.strip("._-") or "unknown"
