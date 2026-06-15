from __future__ import annotations

from fastapi import APIRouter, File, HTTPException, Request, Response, UploadFile
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse, PlainTextResponse

from src.chart_packs.cloud_adapter import build_cloud_derived_table_chart_snapshot
from src.image_evidence.cloud_adapter import build_cloud_derived_figure_image_evidence_request
from src.meeting_packs.cloud_adapter import build_meeting_pack_cloud_derived_context
from src.method_comparisons.cloud_adapter import build_method_comparison_cloud_derived_context
from src.schemas.chart_pack import ChartDataSnapshot, ChartTemplateId
from src.schemas.cloud_paper import (
    CloudPaperAuthPreflightResponse,
    CloudPaperBundlePublic,
    CloudPaperDerivedArtifactsResponse,
    CloudPaperDownstreamArtifactRegistryResponse,
    CloudPaperDownstreamArtifactRegistrationRequest,
    CloudPaperDownstreamArtifactRegistrationResponse,
    CloudPaperDownstreamArtifactReviewRequest,
    CloudPaperDownstreamAdapterResponse,
    CloudPaperDownstreamPromotionPlanResponse,
    CloudPaperDownstreamPromotionReadinessResponse,
    CloudPaperFigureAnalysisResponse,
    CloudPaperFiguresResponse,
    CloudPaperHydrationState,
    CloudPaperListResponse,
    CloudPaperOcrResponse,
    CloudPaperObsidianExportRequest,
    CloudPaperObsidianExportResponse,
    CloudPaperOperationErrorResponse,
    CloudPaperPageArtifactPublic,
    CloudPaperSearchResponse,
    CloudPaperSourceUploadResponse,
    CloudPaperSummaryResponse,
    CloudPaperTablesResponse,
    CloudPaperUploadCompletionRequest,
    CloudPaperUploadIntentRequest,
    CloudPaperUploadIntentResponse,
)
from src.schemas.image_evidence import ImageEvidenceRequest
from src.schemas.meeting_pack import MeetingPackCloudDerivedContext
from src.schemas.method_comparison import MethodComparisonCloudDerivedContext
from src.services.cloud_paper_fake import (
    CloudPaperNotFoundError,
    CloudPaperNotReadyError,
    blocked_operation_response,
    complete_mock_upload,
    create_mock_upload_intent,
    forbidden_operation_response,
    get_mock_cloud_bundle,
    get_mock_cloud_derived_artifacts,
    get_mock_cloud_page,
    hydrate_mock_cloud_paper,
    list_mock_cloud_bundles,
    not_ready_operation_response,
    search_mock_cloud_pages,
    upload_mock_source_pdf,
)
from src.services.cloud_paper_access import derive_cloud_paper_access_context_from_headers
from src.services.cloud_paper_auth_preflight import build_cloud_paper_auth_preflight
from src.services.cloud_paper_downstream import (
    CloudPaperDownstreamRegistryArtifactNotFoundError,
    build_cloud_paper_downstream_adapter_response,
    build_cloud_paper_downstream_promotion_plan,
    build_cloud_paper_downstream_promotion_readiness,
    get_cloud_paper_downstream_registry,
    register_cloud_paper_downstream_artifacts,
    review_cloud_paper_downstream_artifact,
    store_cloud_paper_downstream_registration,
)
from src.services.cloud_paper_storage import CloudPaperStorageConfigError, CloudPaperStorageUnavailableError
from src.services.cloud_paper_hydration import CloudPaperHydrationWriteError
from src.services.cloud_paper_obsidian_export import (
    prepare_cloud_derived_obsidian_export,
    render_cloud_derived_obsidian_section,
)
from src.services.cloud_paper_summary import build_cloud_paper_summary
from src.services.event_log import log_user_action


router = APIRouter(prefix="/cloud/papers", tags=["cloud-papers"])

_MOCK_FIGURE_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\xf8\x0f"
    b"\x00\x01\x01\x01\x00\x18\xdd\x8d\xb0\x00\x00\x00\x00IEND\xaeB`\x82"
)


def _forbidden_response(bundle: CloudPaperBundlePublic | None = None) -> JSONResponse:
    error = forbidden_operation_response(bundle)
    return JSONResponse(status_code=403, content=jsonable_encoder(error.model_dump(mode="json")))


def _access_controlled_bundle(paper_id: str, request: Request) -> CloudPaperBundlePublic:
    base_bundle = get_mock_cloud_bundle(paper_id)
    access_context = derive_cloud_paper_access_context_from_headers(
        request.headers,
        paper_lab_id=base_bundle.lab_id,
    )
    return get_mock_cloud_bundle(paper_id, access_context=access_context)


def _best_effort_log_cloud_action(
    *,
    action_type: str,
    paper_id: str,
    request: Request,
    bundle: CloudPaperBundlePublic,
) -> None:
    try:
        access_context = derive_cloud_paper_access_context_from_headers(
            request.headers,
            paper_lab_id=bundle.lab_id,
        )
        log_user_action(
            paper_id=paper_id,
            action_type=action_type,
            source="cloud_papers",
            payload={
                "actor_id": access_context.actor_id,
                "lab_id": access_context.lab_id,
                "paper_lab_id": access_context.paper_lab_id,
                "role": access_context.role,
                "device_registered": access_context.device_registered,
                "session_approved": access_context.session_approved,
                "download_allowed_by_policy": access_context.download_allowed_by_policy,
                "processing_status": bundle.processing_status,
                "run_id": bundle.run_id,
            },
        )
    except Exception:
        pass


def _read_cloud_derived_artifacts(
    *,
    paper_id: str,
    request: Request,
    action_type: str,
    require_export: bool = False,
) -> tuple[CloudPaperBundlePublic, CloudPaperDerivedArtifactsResponse] | JSONResponse:
    try:
        bundle = _access_controlled_bundle(paper_id, request)
        if require_export and not bundle.permissions.can_export:
            return _forbidden_response(bundle)
        if not require_export and not bundle.permissions.can_read_page:
            return _forbidden_response()
        artifacts = get_mock_cloud_derived_artifacts(paper_id)
    except CloudPaperNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Cloud paper not found") from exc
    except CloudPaperNotReadyError as exc:
        error = not_ready_operation_response(exc.bundle)
        return JSONResponse(status_code=409, content=jsonable_encoder(error.model_dump(mode="json")))
    except (CloudPaperStorageConfigError, CloudPaperStorageUnavailableError) as exc:
        error = CloudPaperOperationErrorResponse(
            error_code="CLOUD_PAPER_STORAGE_UNAVAILABLE",
            message=str(exc),
        )
        return JSONResponse(status_code=503, content=jsonable_encoder(error.model_dump(mode="json")))
    _best_effort_log_cloud_action(
        action_type=action_type,
        paper_id=paper_id,
        request=request,
        bundle=bundle,
    )
    return bundle, artifacts


@router.post(
    "/upload-intents",
    response_model=CloudPaperUploadIntentResponse,
    responses={503: {"model": CloudPaperOperationErrorResponse}},
)
def create_cloud_paper_upload_intent(
    payload: CloudPaperUploadIntentRequest,
) -> CloudPaperUploadIntentResponse | JSONResponse:
    try:
        return create_mock_upload_intent(payload)
    except (CloudPaperStorageConfigError, CloudPaperStorageUnavailableError) as exc:
        error = CloudPaperOperationErrorResponse(
            error_code="CLOUD_PAPER_STORAGE_UNAVAILABLE",
            message=str(exc),
        )
        return JSONResponse(status_code=503, content=jsonable_encoder(error.model_dump(mode="json")))


@router.get("", response_model=CloudPaperListResponse)
def list_cloud_papers(request: Request) -> CloudPaperListResponse:
    bundles = list_mock_cloud_bundles(
        access_context_for_lab=lambda paper_lab_id: derive_cloud_paper_access_context_from_headers(
            request.headers,
            paper_lab_id=paper_lab_id,
        )
    )
    return CloudPaperListResponse(items=bundles)


@router.get("/auth-preflight", response_model=CloudPaperAuthPreflightResponse)
def get_cloud_paper_auth_preflight() -> CloudPaperAuthPreflightResponse:
    return build_cloud_paper_auth_preflight()


@router.get("/search", response_model=CloudPaperSearchResponse)
def search_cloud_papers(request: Request, q: str = "") -> CloudPaperSearchResponse:
    return search_mock_cloud_pages(
        q,
        access_context_for_lab=lambda paper_lab_id: derive_cloud_paper_access_context_from_headers(
            request.headers,
            paper_lab_id=paper_lab_id,
        ),
    )


@router.post(
    "/{paper_id}/complete-upload",
    response_model=CloudPaperBundlePublic,
    responses={
        409: {"model": CloudPaperOperationErrorResponse},
        503: {"model": CloudPaperOperationErrorResponse},
    },
)
def complete_cloud_paper_upload(
    paper_id: str,
    payload: CloudPaperUploadCompletionRequest,
) -> CloudPaperBundlePublic | JSONResponse:
    try:
        bundle, completed = complete_mock_upload(paper_id, payload)
    except CloudPaperNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Cloud paper not found") from exc
    except (CloudPaperStorageConfigError, CloudPaperStorageUnavailableError) as exc:
        error = CloudPaperOperationErrorResponse(
            error_code="CLOUD_PAPER_STORAGE_UNAVAILABLE",
            message=str(exc),
        )
        return JSONResponse(status_code=503, content=jsonable_encoder(error.model_dump(mode="json")))
    if not completed:
        error = blocked_operation_response(bundle)
        return JSONResponse(status_code=409, content=jsonable_encoder(error.model_dump(mode="json")))
    return bundle


@router.post(
    "/{paper_id}/source-pdf",
    response_model=CloudPaperSourceUploadResponse,
    responses={
        409: {"model": CloudPaperOperationErrorResponse},
        503: {"model": CloudPaperOperationErrorResponse},
    },
)
async def upload_cloud_paper_source_pdf(
    paper_id: str,
    source_pdf: UploadFile = File(...),
) -> CloudPaperSourceUploadResponse | JSONResponse:
    try:
        result, uploaded = upload_mock_source_pdf(
            paper_id,
            pdf_bytes=await source_pdf.read(),
            content_type=source_pdf.content_type or "",
        )
    except CloudPaperNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Cloud paper not found") from exc
    except (CloudPaperStorageConfigError, CloudPaperStorageUnavailableError) as exc:
        error = CloudPaperOperationErrorResponse(
            error_code="CLOUD_PAPER_STORAGE_UNAVAILABLE",
            message=str(exc),
        )
        return JSONResponse(status_code=503, content=jsonable_encoder(error.model_dump(mode="json")))
    if not uploaded:
        error = blocked_operation_response(result)  # type: ignore[arg-type]
        return JSONResponse(status_code=409, content=jsonable_encoder(error.model_dump(mode="json")))
    return result


@router.get("/{paper_id}", response_model=CloudPaperBundlePublic)
def get_cloud_paper(paper_id: str, request: Request) -> CloudPaperBundlePublic | JSONResponse:
    try:
        bundle = _access_controlled_bundle(paper_id, request)
    except CloudPaperNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Cloud paper not found") from exc
    if not bundle.permissions.can_read_page:
        return _forbidden_response()
    _best_effort_log_cloud_action(
        action_type="cloud_paper_status_read",
        paper_id=paper_id,
        request=request,
        bundle=bundle,
    )
    return bundle


@router.post(
    "/{paper_id}/hydrate-local",
    response_model=CloudPaperHydrationState,
    responses={
        409: {"model": CloudPaperOperationErrorResponse},
        503: {"model": CloudPaperOperationErrorResponse},
    },
)
def hydrate_cloud_paper_local_bundle(paper_id: str, request: Request) -> CloudPaperHydrationState | JSONResponse:
    try:
        bundle = _access_controlled_bundle(paper_id, request)
        if not bundle.permissions.can_hydrate:
            return _forbidden_response()
        hydration = hydrate_mock_cloud_paper(paper_id)
    except CloudPaperNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Cloud paper not found") from exc
    except CloudPaperNotReadyError as exc:
        error = not_ready_operation_response(exc.bundle)
        return JSONResponse(status_code=409, content=jsonable_encoder(error.model_dump(mode="json")))
    except (CloudPaperStorageConfigError, CloudPaperStorageUnavailableError, CloudPaperHydrationWriteError) as exc:
        error = CloudPaperOperationErrorResponse(
            error_code="CLOUD_PAPER_STORAGE_UNAVAILABLE",
            message=str(exc),
        )
        return JSONResponse(status_code=503, content=jsonable_encoder(error.model_dump(mode="json")))
    _best_effort_log_cloud_action(
        action_type="cloud_paper_hydrate_download",
        paper_id=paper_id,
        request=request,
        bundle=bundle,
    )
    return hydration


@router.get(
    "/{paper_id}/summary",
    response_model=CloudPaperSummaryResponse,
    responses={
        409: {"model": CloudPaperOperationErrorResponse},
        503: {"model": CloudPaperOperationErrorResponse},
    },
)
def get_cloud_paper_summary(paper_id: str, request: Request) -> CloudPaperSummaryResponse | JSONResponse:
    try:
        bundle = _access_controlled_bundle(paper_id, request)
        if not bundle.permissions.can_read_page:
            return _forbidden_response()
        page = get_mock_cloud_page(paper_id)
        summary = build_cloud_paper_summary(page)
    except CloudPaperNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Cloud paper not found") from exc
    except CloudPaperNotReadyError as exc:
        error = not_ready_operation_response(exc.bundle)
        return JSONResponse(status_code=409, content=jsonable_encoder(error.model_dump(mode="json")))
    except (CloudPaperStorageConfigError, CloudPaperStorageUnavailableError) as exc:
        error = CloudPaperOperationErrorResponse(
            error_code="CLOUD_PAPER_STORAGE_UNAVAILABLE",
            message=str(exc),
        )
        return JSONResponse(status_code=503, content=jsonable_encoder(error.model_dump(mode="json")))
    _best_effort_log_cloud_action(
        action_type="cloud_paper_summary_read",
        paper_id=paper_id,
        request=request,
        bundle=bundle,
    )
    return summary


@router.get(
    "/{paper_id}/derived-artifacts",
    response_model=CloudPaperDerivedArtifactsResponse,
    responses={
        409: {"model": CloudPaperOperationErrorResponse},
        503: {"model": CloudPaperOperationErrorResponse},
    },
)
def get_cloud_paper_derived_artifacts(
    paper_id: str,
    request: Request,
) -> CloudPaperDerivedArtifactsResponse | JSONResponse:
    try:
        bundle = _access_controlled_bundle(paper_id, request)
        if not bundle.permissions.can_read_page:
            return _forbidden_response()
        artifacts = get_mock_cloud_derived_artifacts(paper_id)
    except CloudPaperNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Cloud paper not found") from exc
    except CloudPaperNotReadyError as exc:
        error = not_ready_operation_response(exc.bundle)
        return JSONResponse(status_code=409, content=jsonable_encoder(error.model_dump(mode="json")))
    except (CloudPaperStorageConfigError, CloudPaperStorageUnavailableError) as exc:
        error = CloudPaperOperationErrorResponse(
            error_code="CLOUD_PAPER_STORAGE_UNAVAILABLE",
            message=str(exc),
        )
        return JSONResponse(status_code=503, content=jsonable_encoder(error.model_dump(mode="json")))
    _best_effort_log_cloud_action(
        action_type="cloud_paper_derived_artifacts_read",
        paper_id=paper_id,
        request=request,
        bundle=bundle,
    )
    return artifacts


@router.get(
    "/{paper_id}/downstream-adapter",
    response_model=CloudPaperDownstreamAdapterResponse,
    responses={
        409: {"model": CloudPaperOperationErrorResponse},
        503: {"model": CloudPaperOperationErrorResponse},
    },
)
def get_cloud_paper_downstream_adapter(
    paper_id: str,
    request: Request,
) -> CloudPaperDownstreamAdapterResponse | JSONResponse:
    loaded = _read_cloud_derived_artifacts(
        paper_id=paper_id,
        request=request,
        action_type="cloud_paper_downstream_adapter_read",
    )
    if isinstance(loaded, JSONResponse):
        return loaded
    _bundle, artifacts = loaded
    return build_cloud_paper_downstream_adapter_response(artifacts)


@router.get(
    "/{paper_id}/meeting-pack-context",
    response_model=MeetingPackCloudDerivedContext,
    responses={
        409: {"model": CloudPaperOperationErrorResponse},
        503: {"model": CloudPaperOperationErrorResponse},
    },
)
def get_cloud_paper_meeting_pack_context(
    paper_id: str,
    request: Request,
) -> MeetingPackCloudDerivedContext | JSONResponse:
    loaded = _read_cloud_derived_artifacts(
        paper_id=paper_id,
        request=request,
        action_type="cloud_paper_meeting_pack_context_read",
    )
    if isinstance(loaded, JSONResponse):
        return loaded
    _bundle, artifacts = loaded
    return build_meeting_pack_cloud_derived_context(build_cloud_paper_downstream_adapter_response(artifacts))


@router.get(
    "/{paper_id}/chart-pack/tables/{table_id}/snapshot",
    response_model=ChartDataSnapshot,
    responses={
        409: {"model": CloudPaperOperationErrorResponse},
        503: {"model": CloudPaperOperationErrorResponse},
    },
)
def get_cloud_paper_chart_table_snapshot(
    paper_id: str,
    table_id: str,
    request: Request,
    template_id: ChartTemplateId = "table_numeric_bar",
) -> ChartDataSnapshot | JSONResponse:
    loaded = _read_cloud_derived_artifacts(
        paper_id=paper_id,
        request=request,
        action_type="cloud_paper_chart_table_snapshot_read",
    )
    if isinstance(loaded, JSONResponse):
        return loaded
    _bundle, artifacts = loaded
    try:
        return build_cloud_derived_table_chart_snapshot(
            build_cloud_paper_downstream_adapter_response(artifacts),
            table_id=table_id,
            template_id=template_id,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Cloud-derived table candidate not found") from exc


@router.get(
    "/{paper_id}/image-evidence/figures/{figure_id}/request",
    response_model=ImageEvidenceRequest,
    responses={
        409: {"model": CloudPaperOperationErrorResponse},
        503: {"model": CloudPaperOperationErrorResponse},
    },
)
def get_cloud_paper_image_evidence_request(
    paper_id: str,
    figure_id: str,
    request: Request,
) -> ImageEvidenceRequest | JSONResponse:
    loaded = _read_cloud_derived_artifacts(
        paper_id=paper_id,
        request=request,
        action_type="cloud_paper_image_evidence_request_read",
    )
    if isinstance(loaded, JSONResponse):
        return loaded
    _bundle, artifacts = loaded
    try:
        return build_cloud_derived_figure_image_evidence_request(
            build_cloud_paper_downstream_adapter_response(artifacts),
            figure_id=figure_id,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Cloud-derived figure candidate not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get(
    "/{paper_id}/method-comparison-context",
    response_model=MethodComparisonCloudDerivedContext,
    responses={
        409: {"model": CloudPaperOperationErrorResponse},
        503: {"model": CloudPaperOperationErrorResponse},
    },
)
def get_cloud_paper_method_comparison_context(
    paper_id: str,
    request: Request,
) -> MethodComparisonCloudDerivedContext | JSONResponse:
    loaded = _read_cloud_derived_artifacts(
        paper_id=paper_id,
        request=request,
        action_type="cloud_paper_method_comparison_context_read",
    )
    if isinstance(loaded, JSONResponse):
        return loaded
    _bundle, artifacts = loaded
    return build_method_comparison_cloud_derived_context(build_cloud_paper_downstream_adapter_response(artifacts))


@router.get(
    "/{paper_id}/obsidian-section",
    response_model=None,
    response_class=PlainTextResponse,
    responses={
        409: {"model": CloudPaperOperationErrorResponse},
        503: {"model": CloudPaperOperationErrorResponse},
    },
)
def get_cloud_paper_obsidian_section(paper_id: str, request: Request) -> PlainTextResponse | JSONResponse:
    loaded = _read_cloud_derived_artifacts(
        paper_id=paper_id,
        request=request,
        action_type="cloud_paper_obsidian_section_read",
    )
    if isinstance(loaded, JSONResponse):
        return loaded
    _bundle, artifacts = loaded
    markdown = render_cloud_derived_obsidian_section(build_cloud_paper_downstream_adapter_response(artifacts))
    return PlainTextResponse(markdown)


@router.get(
    "/{paper_id}/downstream-artifacts/registry",
    response_model=CloudPaperDownstreamArtifactRegistryResponse,
    responses={
        409: {"model": CloudPaperOperationErrorResponse},
        503: {"model": CloudPaperOperationErrorResponse},
    },
)
def get_cloud_paper_downstream_artifact_registry(
    paper_id: str,
    request: Request,
) -> CloudPaperDownstreamArtifactRegistryResponse | JSONResponse:
    loaded = _read_cloud_derived_artifacts(
        paper_id=paper_id,
        request=request,
        action_type="cloud_paper_downstream_artifacts_registry_read",
    )
    if isinstance(loaded, JSONResponse):
        return loaded
    _bundle, artifacts = loaded
    return get_cloud_paper_downstream_registry(build_cloud_paper_downstream_adapter_response(artifacts))


@router.get(
    "/{paper_id}/downstream-artifacts/promotion-readiness",
    response_model=CloudPaperDownstreamPromotionReadinessResponse,
    responses={
        409: {"model": CloudPaperOperationErrorResponse},
        503: {"model": CloudPaperOperationErrorResponse},
    },
)
def get_cloud_paper_downstream_promotion_readiness(
    paper_id: str,
    request: Request,
) -> CloudPaperDownstreamPromotionReadinessResponse | JSONResponse:
    loaded = _read_cloud_derived_artifacts(
        paper_id=paper_id,
        request=request,
        action_type="cloud_paper_downstream_promotion_readiness_read",
    )
    if isinstance(loaded, JSONResponse):
        return loaded
    _bundle, artifacts = loaded
    registry = get_cloud_paper_downstream_registry(build_cloud_paper_downstream_adapter_response(artifacts))
    return build_cloud_paper_downstream_promotion_readiness(registry)


@router.get(
    "/{paper_id}/downstream-artifacts/promotion-plan",
    response_model=CloudPaperDownstreamPromotionPlanResponse,
    responses={
        409: {"model": CloudPaperOperationErrorResponse},
        503: {"model": CloudPaperOperationErrorResponse},
    },
)
def get_cloud_paper_downstream_promotion_plan(
    paper_id: str,
    request: Request,
) -> CloudPaperDownstreamPromotionPlanResponse | JSONResponse:
    loaded = _read_cloud_derived_artifacts(
        paper_id=paper_id,
        request=request,
        action_type="cloud_paper_downstream_promotion_plan_read",
    )
    if isinstance(loaded, JSONResponse):
        return loaded
    _bundle, artifacts = loaded
    registry = get_cloud_paper_downstream_registry(build_cloud_paper_downstream_adapter_response(artifacts))
    return build_cloud_paper_downstream_promotion_plan(registry)


@router.post(
    "/{paper_id}/obsidian-section/export",
    response_model=CloudPaperObsidianExportResponse,
    responses={
        403: {"model": CloudPaperOperationErrorResponse},
        409: {"model": CloudPaperOperationErrorResponse},
        503: {"model": CloudPaperOperationErrorResponse},
    },
)
def export_cloud_paper_obsidian_section(
    paper_id: str,
    payload: CloudPaperObsidianExportRequest,
    request: Request,
) -> CloudPaperObsidianExportResponse | JSONResponse:
    loaded = _read_cloud_derived_artifacts(
        paper_id=paper_id,
        request=request,
        action_type="cloud_paper_obsidian_section_export",
        require_export=True,
    )
    if isinstance(loaded, JSONResponse):
        return loaded
    _bundle, artifacts = loaded
    return prepare_cloud_derived_obsidian_export(
        build_cloud_paper_downstream_adapter_response(artifacts),
        existing_markdown=payload.existing_markdown,
    )


@router.post(
    "/{paper_id}/downstream-artifacts/register",
    response_model=CloudPaperDownstreamArtifactRegistrationResponse,
    responses={
        403: {"model": CloudPaperOperationErrorResponse},
        409: {"model": CloudPaperOperationErrorResponse},
        503: {"model": CloudPaperOperationErrorResponse},
    },
)
def register_cloud_paper_downstream_artifact_manifest(
    paper_id: str,
    payload: CloudPaperDownstreamArtifactRegistrationRequest,
    request: Request,
) -> CloudPaperDownstreamArtifactRegistrationResponse | JSONResponse:
    loaded = _read_cloud_derived_artifacts(
        paper_id=paper_id,
        request=request,
        action_type="cloud_paper_downstream_artifacts_register",
        require_export=True,
    )
    if isinstance(loaded, JSONResponse):
        return loaded
    _bundle, artifacts = loaded
    registration = register_cloud_paper_downstream_artifacts(
        build_cloud_paper_downstream_adapter_response(artifacts),
        payload,
    )
    return store_cloud_paper_downstream_registration(registration)


@router.post(
    "/{paper_id}/downstream-artifacts/{artifact_id}/review",
    response_model=CloudPaperDownstreamArtifactRegistryResponse,
    responses={
        403: {"model": CloudPaperOperationErrorResponse},
        409: {"model": CloudPaperOperationErrorResponse},
        503: {"model": CloudPaperOperationErrorResponse},
    },
)
def review_cloud_paper_downstream_artifact_manifest(
    paper_id: str,
    artifact_id: str,
    payload: CloudPaperDownstreamArtifactReviewRequest,
    request: Request,
) -> CloudPaperDownstreamArtifactRegistryResponse | JSONResponse:
    loaded = _read_cloud_derived_artifacts(
        paper_id=paper_id,
        request=request,
        action_type="cloud_paper_downstream_artifact_review",
        require_export=True,
    )
    if isinstance(loaded, JSONResponse):
        return loaded
    bundle, artifacts = loaded
    access_context = derive_cloud_paper_access_context_from_headers(
        request.headers,
        paper_lab_id=bundle.lab_id,
    )
    try:
        return review_cloud_paper_downstream_artifact(
            build_cloud_paper_downstream_adapter_response(artifacts),
            artifact_id=artifact_id,
            review_status=payload.review_status,
            reviewer_role=access_context.role,
            reviewer_note_recorded=payload.reviewer_note is not None,
        )
    except CloudPaperDownstreamRegistryArtifactNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Cloud paper downstream artifact not found") from exc


@router.get(
    "/{paper_id}/ocr",
    response_model=CloudPaperOcrResponse,
    responses={
        409: {"model": CloudPaperOperationErrorResponse},
        503: {"model": CloudPaperOperationErrorResponse},
    },
)
def get_cloud_paper_ocr(paper_id: str, request: Request) -> CloudPaperOcrResponse | JSONResponse:
    loaded = _read_cloud_derived_artifacts(
        paper_id=paper_id,
        request=request,
        action_type="cloud_paper_ocr_read",
    )
    if isinstance(loaded, JSONResponse):
        return loaded
    _bundle, artifacts = loaded
    return CloudPaperOcrResponse(
        paper_id=artifacts.paper_id,
        run_id=artifacts.run_id,
        source_pdf_sha256=artifacts.source_pdf_sha256,
        payload_class=artifacts.payload_class,
        ocr_blocks=artifacts.ocr_blocks,
        warnings=artifacts.warnings,
        provenance_summary=artifacts.provenance_summary,
    )


@router.get(
    "/{paper_id}/tables",
    response_model=CloudPaperTablesResponse,
    responses={
        409: {"model": CloudPaperOperationErrorResponse},
        503: {"model": CloudPaperOperationErrorResponse},
    },
)
def get_cloud_paper_tables(paper_id: str, request: Request) -> CloudPaperTablesResponse | JSONResponse:
    loaded = _read_cloud_derived_artifacts(
        paper_id=paper_id,
        request=request,
        action_type="cloud_paper_tables_read",
    )
    if isinstance(loaded, JSONResponse):
        return loaded
    _bundle, artifacts = loaded
    return CloudPaperTablesResponse(
        paper_id=artifacts.paper_id,
        run_id=artifacts.run_id,
        source_pdf_sha256=artifacts.source_pdf_sha256,
        payload_class=artifacts.payload_class,
        tables=artifacts.tables,
        warnings=artifacts.warnings,
        provenance_summary=artifacts.provenance_summary,
    )


@router.get(
    "/{paper_id}/figures",
    response_model=CloudPaperFiguresResponse,
    responses={
        409: {"model": CloudPaperOperationErrorResponse},
        503: {"model": CloudPaperOperationErrorResponse},
    },
)
def get_cloud_paper_figures(paper_id: str, request: Request) -> CloudPaperFiguresResponse | JSONResponse:
    loaded = _read_cloud_derived_artifacts(
        paper_id=paper_id,
        request=request,
        action_type="cloud_paper_figures_read",
    )
    if isinstance(loaded, JSONResponse):
        return loaded
    _bundle, artifacts = loaded
    return CloudPaperFiguresResponse(
        paper_id=artifacts.paper_id,
        run_id=artifacts.run_id,
        source_pdf_sha256=artifacts.source_pdf_sha256,
        payload_class=artifacts.payload_class,
        figures=artifacts.figures,
        warnings=artifacts.warnings,
        provenance_summary=artifacts.provenance_summary,
    )


@router.get(
    "/{paper_id}/figures/{figure_id}/analysis",
    response_model=CloudPaperFigureAnalysisResponse,
    responses={
        409: {"model": CloudPaperOperationErrorResponse},
        503: {"model": CloudPaperOperationErrorResponse},
    },
)
def get_cloud_paper_figure_analysis(
    paper_id: str,
    figure_id: str,
    request: Request,
) -> CloudPaperFigureAnalysisResponse | JSONResponse:
    loaded = _read_cloud_derived_artifacts(
        paper_id=paper_id,
        request=request,
        action_type="cloud_paper_figure_analysis_read",
    )
    if isinstance(loaded, JSONResponse):
        return loaded
    _bundle, artifacts = loaded
    analyses = [analysis for analysis in artifacts.figure_analyses if analysis.figure_id == figure_id]
    if not analyses:
        raise HTTPException(status_code=404, detail="Cloud paper figure analysis not found")
    return CloudPaperFigureAnalysisResponse(
        paper_id=artifacts.paper_id,
        run_id=artifacts.run_id,
        figure_id=figure_id,
        source_pdf_sha256=artifacts.source_pdf_sha256,
        payload_class=artifacts.payload_class,
        analyses=analyses,
        warnings=artifacts.warnings,
        provenance_summary=artifacts.provenance_summary,
    )


@router.get(
    "/{paper_id}/figures/{figure_id}/image",
    response_model=None,
    responses={
        409: {"model": CloudPaperOperationErrorResponse},
        503: {"model": CloudPaperOperationErrorResponse},
    },
)
def get_cloud_paper_figure_image(paper_id: str, figure_id: str, request: Request) -> Response:
    loaded = _read_cloud_derived_artifacts(
        paper_id=paper_id,
        request=request,
        action_type="cloud_paper_figure_image_read",
    )
    if isinstance(loaded, JSONResponse):
        return loaded
    _bundle, artifacts = loaded
    figure = next((item for item in artifacts.figures if item.figure_id == figure_id), None)
    if figure is None or not figure.image_available:
        raise HTTPException(status_code=404, detail="Cloud paper figure image not found")
    return Response(content=_MOCK_FIGURE_PNG, media_type="image/png")


@router.get(
    "/{paper_id}/page",
    response_model=CloudPaperPageArtifactPublic,
    responses={
        409: {"model": CloudPaperOperationErrorResponse},
        503: {"model": CloudPaperOperationErrorResponse},
    },
)
def get_cloud_paper_page(paper_id: str, request: Request) -> CloudPaperPageArtifactPublic | JSONResponse:
    try:
        bundle = _access_controlled_bundle(paper_id, request)
        if not bundle.permissions.can_read_page:
            return _forbidden_response()
        page = get_mock_cloud_page(paper_id)
    except CloudPaperNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Cloud paper not found") from exc
    except CloudPaperNotReadyError as exc:
        error = not_ready_operation_response(exc.bundle)
        return JSONResponse(status_code=409, content=jsonable_encoder(error.model_dump(mode="json")))
    except (CloudPaperStorageConfigError, CloudPaperStorageUnavailableError) as exc:
        error = CloudPaperOperationErrorResponse(
            error_code="CLOUD_PAPER_STORAGE_UNAVAILABLE",
            message=str(exc),
        )
        return JSONResponse(status_code=503, content=jsonable_encoder(error.model_dump(mode="json")))
    _best_effort_log_cloud_action(
        action_type="cloud_paper_page_read",
        paper_id=paper_id,
        request=request,
        bundle=bundle,
    )
    return page
