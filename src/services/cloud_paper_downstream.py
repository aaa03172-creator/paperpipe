from __future__ import annotations

import hashlib

from src.schemas.cloud_paper import (
    CloudPaperDerivedArtifactsResponse,
    CloudPaperDownstreamAdapterResponse,
    CloudPaperDownstreamArtifactCandidate,
    CloudPaperDownstreamArtifactRegistryResponse,
    CloudPaperDownstreamLane,
    CloudPaperDownstreamPromotionBlocker,
    CloudPaperDownstreamPromotionPlanItem,
    CloudPaperDownstreamPromotionPlanResponse,
    CloudPaperDownstreamPromotionReadinessResponse,
    CloudPaperDownstreamReviewStatus,
    CloudPaperRole,
    CloudPaperDownstreamArtifactRegistrationResponse,
    CloudPaperDownstreamArtifactRegistrationRequest,
    CloudPaperRegisteredDownstreamArtifact,
)
from src.services.cloud_paper_downstream_registry import (
    CloudPaperDownstreamRegistryArtifactNotFoundError,
    CloudPaperDownstreamRegistryStore,
    InMemoryCloudPaperDownstreamRegistryStore,
    get_cloud_paper_downstream_registry_store,
    resolve_cloud_paper_downstream_registry_config,
)

_REGISTRY_STORE_CACHE: CloudPaperDownstreamRegistryStore | None = None
_REGISTRY_STORE_CACHE_KEY: tuple[str, str | None, str] | None = None


def _registry_store() -> CloudPaperDownstreamRegistryStore:
    global _REGISTRY_STORE_CACHE, _REGISTRY_STORE_CACHE_KEY
    config = resolve_cloud_paper_downstream_registry_config()
    cache_key = (config.store, config.gcp_project_id, config.firestore_collection)
    if _REGISTRY_STORE_CACHE is not None and _REGISTRY_STORE_CACHE_KEY == cache_key:
        return _REGISTRY_STORE_CACHE
    _REGISTRY_STORE_CACHE = get_cloud_paper_downstream_registry_store(config)
    _REGISTRY_STORE_CACHE_KEY = cache_key
    return _REGISTRY_STORE_CACHE


def build_cloud_paper_downstream_adapter_response(
    derived_artifacts: CloudPaperDerivedArtifactsResponse,
) -> CloudPaperDownstreamAdapterResponse:
    candidates: list[CloudPaperDownstreamArtifactCandidate] = []

    for block in derived_artifacts.ocr_blocks:
        candidates.append(
            CloudPaperDownstreamArtifactCandidate(
                candidate_id=block.ocr_block_id,
                kind="ocr_text",
                paper_id=derived_artifacts.paper_id,
                run_id=derived_artifacts.run_id,
                payload_class=block.payload_class,
                allowed_lanes=["meeting_pack", "method_comparison", "obsidian_export"],
                source=block.source,
                title=f"OCR block {block.ocr_block_id}",
                text=block.text,
                confidence=block.confidence,
                provenance_summary=derived_artifacts.provenance_summary,
            )
        )

    for table in derived_artifacts.tables:
        candidates.append(
            CloudPaperDownstreamArtifactCandidate(
                candidate_id=table.table_id,
                kind="table",
                paper_id=derived_artifacts.paper_id,
                run_id=derived_artifacts.run_id,
                payload_class=table.payload_class,
                allowed_lanes=["chart_pack", "meeting_pack", "method_comparison", "obsidian_export"],
                source=table.source,
                title=table.caption or f"Table {table.table_id}",
                text=table.caption,
                table_columns=table.columns,
                table_rows=table.rows,
                confidence=table.confidence,
                provenance_summary=derived_artifacts.provenance_summary,
            )
        )

    for figure in derived_artifacts.figures:
        candidates.append(
            CloudPaperDownstreamArtifactCandidate(
                candidate_id=figure.figure_id,
                kind="figure",
                paper_id=derived_artifacts.paper_id,
                run_id=derived_artifacts.run_id,
                payload_class=figure.payload_class,
                allowed_lanes=["image_evidence", "meeting_pack", "obsidian_export"],
                source=figure.source,
                title=figure.caption or f"Figure {figure.figure_id}",
                text=figure.caption,
                image_route=figure.image_route if figure.image_available else None,
                confidence=figure.confidence,
                provenance_summary=derived_artifacts.provenance_summary,
            )
        )

    analyses_by_figure_id = {
        figure.figure_id: figure
        for figure in derived_artifacts.figures
    }
    for analysis in derived_artifacts.figure_analyses:
        figure = analyses_by_figure_id.get(analysis.figure_id)
        lanes: list[CloudPaperDownstreamLane] = ["meeting_pack", "obsidian_export"]
        if figure is not None and figure.image_available:
            lanes.insert(0, "image_evidence")
        candidates.append(
            CloudPaperDownstreamArtifactCandidate(
                candidate_id=analysis.analysis_id,
                kind="figure_analysis",
                paper_id=derived_artifacts.paper_id,
                run_id=derived_artifacts.run_id,
                payload_class=analysis.payload_class,
                allowed_lanes=lanes,
                source=analysis.source,
                title=f"Analysis for {analysis.figure_id}",
                text=analysis.summary,
                image_route=figure.image_route if figure is not None and figure.image_available else None,
                confidence=analysis.confidence,
                provenance_summary=derived_artifacts.provenance_summary,
            )
        )

    return CloudPaperDownstreamAdapterResponse(
        paper_id=derived_artifacts.paper_id,
        run_id=derived_artifacts.run_id,
        source_pdf_sha256=derived_artifacts.source_pdf_sha256,
        payload_class=derived_artifacts.payload_class,
        candidates=candidates,
        warnings=derived_artifacts.warnings,
        provenance_summary=derived_artifacts.provenance_summary,
    )


def register_cloud_paper_downstream_artifacts(
    adapter_response: CloudPaperDownstreamAdapterResponse,
    request: CloudPaperDownstreamArtifactRegistrationRequest,
) -> CloudPaperDownstreamArtifactRegistrationResponse:
    registered_artifacts: list[CloudPaperRegisteredDownstreamArtifact] = []
    for lane in request.lanes:
        candidates = [
            candidate
            for candidate in adapter_response.candidates
            if lane in candidate.allowed_lanes
        ]
        if not candidates:
            continue
        candidate_ids = [candidate.candidate_id for candidate in candidates]
        registered_artifacts.append(
            CloudPaperRegisteredDownstreamArtifact(
                artifact_id=_registered_artifact_id(
                    adapter_response,
                    lane=lane,
                    candidate_ids=candidate_ids,
                ),
                lane=lane,
                candidate_ids=candidate_ids,
                candidate_count=len(candidate_ids),
                source_pdf_sha256=adapter_response.source_pdf_sha256,
                payload_class=adapter_response.payload_class,
            )
        )

    return CloudPaperDownstreamArtifactRegistrationResponse(
        paper_id=adapter_response.paper_id,
        run_id=adapter_response.run_id,
        source_pdf_sha256=adapter_response.source_pdf_sha256,
        payload_class=adapter_response.payload_class,
        registered_artifacts=registered_artifacts,
        warnings=adapter_response.warnings,
        provenance_summary=adapter_response.provenance_summary,
    )


def store_cloud_paper_downstream_registration(
    registration: CloudPaperDownstreamArtifactRegistrationResponse,
) -> CloudPaperDownstreamArtifactRegistrationResponse:
    return _registry_store().store_registration(registration)


def get_cloud_paper_downstream_registry(
    adapter_response: CloudPaperDownstreamAdapterResponse,
):
    return _registry_store().get_registry(adapter_response)


def review_cloud_paper_downstream_artifact(
    adapter_response: CloudPaperDownstreamAdapterResponse,
    *,
    artifact_id: str,
    review_status: CloudPaperDownstreamReviewStatus,
    reviewer_role: CloudPaperRole,
    reviewer_note_recorded: bool = False,
):
    return _registry_store().review_artifact(
        adapter_response,
        artifact_id=artifact_id,
        review_status=review_status,
        reviewer_role=reviewer_role,
        reviewer_note_recorded=reviewer_note_recorded,
    )


def build_cloud_paper_downstream_promotion_readiness(
    registry: CloudPaperDownstreamArtifactRegistryResponse,
) -> CloudPaperDownstreamPromotionReadinessResponse:
    artifacts = [artifact for registration in registry.registrations for artifact in registration.registered_artifacts]
    blockers: list[CloudPaperDownstreamPromotionBlocker] = []
    if not artifacts:
        blockers.append(
            CloudPaperDownstreamPromotionBlocker(
                code="registry_empty",
                message="No registered downstream artifacts are available for promotion review.",
            )
        )
    for artifact in artifacts:
        if artifact.review_status == "review_pending":
            blockers.append(
                CloudPaperDownstreamPromotionBlocker(
                    code="review_pending",
                    message="Registered downstream artifact is still pending review.",
                    artifact_id=artifact.artifact_id,
                    lane=artifact.lane,
                )
            )
        elif artifact.review_status == "review_rejected":
            blockers.append(
                CloudPaperDownstreamPromotionBlocker(
                    code="review_rejected",
                    message="Registered downstream artifact was rejected during review.",
                    artifact_id=artifact.artifact_id,
                    lane=artifact.lane,
                )
            )
    approved_count = sum(1 for artifact in artifacts if artifact.review_status == "review_approved")
    pending_count = sum(1 for artifact in artifacts if artifact.review_status == "review_pending")
    rejected_count = sum(1 for artifact in artifacts if artifact.review_status == "review_rejected")
    eligible = bool(artifacts) and not blockers
    return CloudPaperDownstreamPromotionReadinessResponse(
        paper_id=registry.paper_id,
        run_id=registry.run_id,
        promotion_status="eligible" if eligible else "blocked",
        eligible=eligible,
        canonical_status="derived_noncanonical",
        review_status=registry.review_status,
        total_artifact_count=len(artifacts),
        approved_artifact_count=approved_count,
        pending_artifact_count=pending_count,
        rejected_artifact_count=rejected_count,
        blockers=blockers,
        source_pdf_sha256=registry.source_pdf_sha256,
        payload_class=registry.payload_class,
        warnings=registry.warnings,
        provenance_summary=registry.provenance_summary,
    )


def build_cloud_paper_downstream_promotion_plan(
    registry: CloudPaperDownstreamArtifactRegistryResponse,
) -> CloudPaperDownstreamPromotionPlanResponse:
    readiness = build_cloud_paper_downstream_promotion_readiness(registry)
    artifacts = [artifact for registration in registry.registrations for artifact in registration.registered_artifacts]
    promotion_items = [
        CloudPaperDownstreamPromotionPlanItem(
            artifact_id=artifact.artifact_id,
            lane=artifact.lane,
            candidate_ids=artifact.candidate_ids,
            candidate_count=artifact.candidate_count,
            source_pdf_sha256=artifact.source_pdf_sha256,
            payload_class=artifact.payload_class,
        )
        for artifact in artifacts
        if readiness.eligible and artifact.review_status == "review_approved"
    ]
    return CloudPaperDownstreamPromotionPlanResponse(
        paper_id=registry.paper_id,
        run_id=registry.run_id,
        plan_status="ready" if readiness.eligible else "blocked",
        dry_run=True,
        mutation_applied=False,
        promotion_target="canonical_structured_state",
        canonical_status="derived_noncanonical",
        review_status=registry.review_status,
        total_artifact_count=readiness.total_artifact_count,
        approved_artifact_count=readiness.approved_artifact_count,
        pending_artifact_count=readiness.pending_artifact_count,
        rejected_artifact_count=readiness.rejected_artifact_count,
        blockers=readiness.blockers,
        promotion_items=promotion_items,
        source_pdf_sha256=registry.source_pdf_sha256,
        payload_class=registry.payload_class,
        warnings=registry.warnings,
        provenance_summary=registry.provenance_summary,
    )


def reset_cloud_paper_downstream_registry() -> None:
    global _REGISTRY_STORE_CACHE, _REGISTRY_STORE_CACHE_KEY
    if isinstance(_REGISTRY_STORE_CACHE, InMemoryCloudPaperDownstreamRegistryStore):
        _REGISTRY_STORE_CACHE.clear()
    _REGISTRY_STORE_CACHE = None
    _REGISTRY_STORE_CACHE_KEY = None


def _registered_artifact_id(
    adapter_response: CloudPaperDownstreamAdapterResponse,
    *,
    lane: CloudPaperDownstreamLane,
    candidate_ids: list[str],
) -> str:
    digest = hashlib.sha256(
        "\n".join(
            [
                adapter_response.paper_id,
                adapter_response.run_id,
                adapter_response.source_pdf_sha256,
                lane,
                *candidate_ids,
            ]
        ).encode("utf-8")
    ).hexdigest()[:16]
    return f"cloud_downstream_{lane}_{digest}"
