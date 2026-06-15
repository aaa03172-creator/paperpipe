from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
from itertools import count
import re
from typing import Callable

from src.schemas.cloud_paper import (
    CloudPaperAccessContext,
    CloudPaperBundleInternal,
    CloudPaperBundlePublic,
    CloudPaperDerivedArtifactFigure,
    CloudPaperDerivedArtifactFigureAnalysis,
    CloudPaperDerivedArtifactInternal,
    CloudPaperDerivedArtifactOcrBlock,
    CloudPaperDerivedArtifactSourceLocator,
    CloudPaperDerivedArtifactTable,
    CloudPaperDerivedArtifactsResponse,
    CloudPaperOperationErrorResponse,
    CloudPaperHydrationState,
    CloudPaperMetadataRecord,
    CloudPaperPageArtifactInternal,
    CloudPaperPageArtifactPublic,
    CloudPaperPageBlockInternal,
    CloudPaperPermissions,
    CloudPaperProvenance,
    CloudPaperProcessingStatus,
    CloudPaperSearchBlockHit,
    CloudPaperSearchHit,
    CloudPaperSearchResponse,
    CloudPaperSourceUploadResponse,
    CloudPaperUploadCompletionRequest,
    CloudPaperUploadIntentRequest,
    CloudPaperUploadIntentResponse,
    CloudPaperWarning,
    derive_cloud_paper_public_bundle,
    derive_cloud_paper_public_derived_artifacts,
    derive_cloud_page_artifact_public,
)
from src.services.cloud_paper_metadata import (
    CloudPaperMetadataStore,
    InMemoryCloudPaperMetadataStore,
    get_cloud_paper_metadata_store,
    resolve_cloud_paper_metadata_config,
)
from src.services.cloud_paper_storage import (
    CloudPaperDerivedArtifactNotFoundError,
    CloudPaperPageArtifactNotFoundError,
    MockCloudPaperStorageAdapter,
    CloudPaperStorageUnavailableError,
    get_cloud_paper_storage_adapter,
    resolve_cloud_paper_storage_config,
)
from src.services.cloud_paper_hydration import (
    CloudPaperHydrationConflictError,
    read_cloud_paper_local_hydration_state,
    write_cloud_paper_local_bundle,
)
from src.services.cloud_paper_access import derive_cloud_paper_permissions_for_access_context
from src.services.cloud_paper_processing import process_cloud_paper_page_artifact
from src.services.cloud_paper_processing import process_cloud_paper_derived_artifacts
from src.services.cloud_paper_downstream import reset_cloud_paper_downstream_registry
from src.services.cloud_paper_submission_bundle import (
    get_submission_demo_bundle,
    get_submission_demo_derived_artifacts,
    get_submission_demo_page,
    list_submission_demo_bundles,
    submission_demo_enabled,
)


_MOCK_CREATED_AT = datetime(2026, 5, 30, 1, 2, 3, tzinfo=timezone.utc)
_MOCK_READY_SHA256 = "a" * 64
_MOCK_ID_COUNTER = count(1)
_IN_MEMORY_METADATA_STORE = InMemoryCloudPaperMetadataStore()
_METADATA_STORE_CACHE: CloudPaperMetadataStore | None = None
_METADATA_STORE_CACHE_KEY: tuple[str, str | None, str] | None = None
_FIXTURE_PAPER_IDS = (
    "paper_mock_ready",
    "paper_mock_pending",
    "paper_mock_running",
    "paper_mock_failed",
    "paper_mock_blocked",
)
_REAL_CLOUD_ID_SHA_PREFIX_LENGTH = 12


def _metadata_store() -> CloudPaperMetadataStore:
    global _METADATA_STORE_CACHE, _METADATA_STORE_CACHE_KEY
    config = resolve_cloud_paper_metadata_config()
    if config.store == "memory":
        return _IN_MEMORY_METADATA_STORE

    cache_key = (config.store, config.gcp_project_id, config.firestore_collection)
    if _METADATA_STORE_CACHE is not None and _METADATA_STORE_CACHE_KEY == cache_key:
        return _METADATA_STORE_CACHE
    _METADATA_STORE_CACHE = get_cloud_paper_metadata_store(config)
    _METADATA_STORE_CACHE_KEY = cache_key
    return _METADATA_STORE_CACHE


def _cloud_storage_mode() -> str:
    return resolve_cloud_paper_storage_config().adapter


def reset_mock_cloud_paper_state() -> None:
    global _METADATA_STORE_CACHE, _METADATA_STORE_CACHE_KEY, _MOCK_ID_COUNTER
    _IN_MEMORY_METADATA_STORE.clear()
    _METADATA_STORE_CACHE = None
    _METADATA_STORE_CACHE_KEY = None
    MockCloudPaperStorageAdapter._derived_artifacts.clear()
    MockCloudPaperStorageAdapter._page_artifacts.clear()
    MockCloudPaperStorageAdapter._source_pdfs.clear()
    reset_cloud_paper_downstream_registry()
    _MOCK_ID_COUNTER = count(1)


class CloudPaperNotFoundError(LookupError):
    pass


class CloudPaperNotReadyError(RuntimeError):
    def __init__(self, bundle: CloudPaperBundlePublic):
        super().__init__("Cloud paper page is not ready")
        self.bundle = bundle


class CloudPaperHydrationBlockedError(RuntimeError):
    def __init__(self, bundle: CloudPaperBundlePublic):
        super().__init__("Cloud paper hydration is blocked.")
        self.bundle = bundle


def _reader_permissions() -> CloudPaperPermissions:
    return CloudPaperPermissions(role="reader", can_read_page=True)


def _provenance(*, source_pdf_sha256: str) -> CloudPaperProvenance:
    return CloudPaperProvenance(
        uploaded_by="mock_user",
        processor_name="paperpipe-mock-cloud-page-worker",
        processor_version="0.1.0",
        model_name="mock-page-processor",
        model_version="2026-05-30",
        created_at=_MOCK_CREATED_AT,
        source_pdf_sha256=source_pdf_sha256,
    )


def _real_cloud_provenance(*, source_pdf_sha256: str) -> CloudPaperProvenance:
    return CloudPaperProvenance(
        uploaded_by="backend_upload",
        processor_name="paperpipe-real-cloud-page-worker",
        processor_version="0.1.0",
        model_name="fitz-text-extractor",
        model_version="pymupdf",
        created_at=_MOCK_CREATED_AT,
        source_pdf_sha256=source_pdf_sha256,
    )


def _safe_cloud_id_part(value: str, *, fallback: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "_", str(value or "").strip().lower()).strip("_")
    return (cleaned or fallback)[:24]


def _upload_identifiers_for_request(
    request: CloudPaperUploadIntentRequest,
    *,
    storage_adapter_mode: str,
) -> tuple[str, str]:
    if storage_adapter_mode == "gcs":
        lab_part = _safe_cloud_id_part(request.lab_id, fallback="lab")
        sha_part = request.source_pdf_sha256[:_REAL_CLOUD_ID_SHA_PREFIX_LENGTH]
        paper_id = f"cloudpdf_{lab_part}_{sha_part}"
        return paper_id, f"upl_gcs_{lab_part}_{sha_part}"

    next_id = next(_MOCK_ID_COUNTER)
    return f"paper_mock_{next_id:06d}", f"upl_mock_{next_id:06d}"


def _internal_bundle(
    *,
    paper_id: str,
    source_pdf_sha256: str,
    lab_id: str = "lab_001",
    processing_status: CloudPaperProcessingStatus = "ready",
    local_hydration: CloudPaperHydrationState | None = None,
    warnings: list[CloudPaperWarning] | None = None,
) -> CloudPaperBundleInternal:
    return CloudPaperBundleInternal(
        paper_id=paper_id,
        lab_id=lab_id,
        cloud_source_id=f"src_{paper_id}",
        gcs_pdf_object_ref=f"gs://paperpipe-mock-raw/{lab_id}/{paper_id}/source.pdf",
        source_pdf_sha256=source_pdf_sha256,
        source_pdf_size_bytes=123456,
        source_pdf_content_type="application/pdf",
        gcs_page_artifact_object_ref=f"gs://paperpipe-mock-pages/{lab_id}/{paper_id}/page.json",
        page_artifact_sha256="b" * 64,
        page_schema_version="cloud_page_artifact.v1",
        run_id=f"run_{paper_id}",
        processing_status=processing_status,
        payload_class="local_only",
        created_at=_MOCK_CREATED_AT,
        updated_at=_MOCK_CREATED_AT,
        provenance=(
            _real_cloud_provenance(source_pdf_sha256=source_pdf_sha256)
            if paper_id.startswith("cloudpdf_")
            else _provenance(source_pdf_sha256=source_pdf_sha256)
        ),
        local_hydration=local_hydration or CloudPaperHydrationState(status="not_hydrated"),
        warnings=warnings or [],
    )


def create_mock_upload_intent(request: CloudPaperUploadIntentRequest) -> CloudPaperUploadIntentResponse:
    storage_adapter = get_cloud_paper_storage_adapter()
    paper_id, upload_intent_id = _upload_identifiers_for_request(
        request,
        storage_adapter_mode=storage_adapter.adapter,
    )
    store = _metadata_store()
    response = storage_adapter.create_upload_intent(
        request,
        paper_id=paper_id,
        upload_intent_id=upload_intent_id,
        expires_at=_MOCK_CREATED_AT + timedelta(minutes=15),
    )
    store.create_upload_intent_record(
        paper_id=paper_id,
        upload_intent_id=upload_intent_id,
        request=request,
    )
    return response


def _fixture_state(paper_id: str) -> CloudPaperMetadataRecord | None:
    fixture_statuses: dict[str, CloudPaperProcessingStatus] = {
        "paper_mock_ready": "ready",
        "paper_mock_pending": "pending",
        "paper_mock_running": "running",
        "paper_mock_failed": "failed",
        "paper_mock_blocked": "blocked",
    }
    status = fixture_statuses.get(paper_id)
    if status is None:
        return None
    warnings = []
    if status in {"failed", "blocked"}:
        warnings = [
            CloudPaperWarning(
                code=f"MOCK_{status.upper()}",
                message=f"Mock cloud paper is {status}.",
                severity="high",
            )
        ]
    upload_status_by_processing_status = {
        "pending": "intent_created",
        "running": "processing",
        "ready": "ready",
        "failed": "failed",
        "blocked": "blocked",
    }
    return CloudPaperMetadataRecord(
        paper_id=paper_id,
        upload_intent_id=f"upl_{paper_id}",
        request=CloudPaperUploadIntentRequest(
            filename=f"{paper_id}.pdf",
            content_type="application/pdf",
            source_pdf_sha256=_MOCK_READY_SHA256,
            lab_id="lab_001",
        ),
        upload_status=upload_status_by_processing_status[status],
        processing_status=status,
        warnings=warnings,
    )


def _state_for_paper(paper_id: str) -> CloudPaperMetadataRecord:
    if submission_demo_enabled():
        bundle = get_submission_demo_bundle(paper_id)
        if bundle is None:
            raise CloudPaperNotFoundError(paper_id)
        return CloudPaperMetadataRecord(
            paper_id=bundle.paper_id,
            upload_intent_id=f"upl_submission_{bundle.paper_id}",
            request=CloudPaperUploadIntentRequest(
                filename=f"{bundle.paper_id}.pdf",
                content_type="application/pdf",
                source_pdf_sha256=bundle.provenance_summary.source_pdf_sha256,
                lab_id=bundle.lab_id,
            ),
            upload_status="ready",
            processing_status=bundle.processing_status,
            warnings=bundle.warnings,
        )
    if _cloud_storage_mode() == "gcs" and paper_id.startswith("paper_mock_"):
        raise CloudPaperNotFoundError(paper_id)
    state = _metadata_store().get(paper_id) or _fixture_state(paper_id)
    if state is None:
        raise CloudPaperNotFoundError(paper_id)
    return state


def _stored_state_for_paper(paper_id: str, state: CloudPaperMetadataRecord) -> CloudPaperMetadataRecord:
    store = _metadata_store()
    stored_state = store.get(paper_id)
    if stored_state is not None:
        return stored_state
    store.create_upload_intent_record(
        paper_id=paper_id,
        upload_intent_id=state.upload_intent_id,
        request=state.request,
    )
    return store.get(paper_id) or state


def _block_upload(
    paper_id: str,
    state: CloudPaperMetadataRecord,
    *,
    code: str,
    message: str,
) -> tuple[CloudPaperBundlePublic, bool]:
    warning = CloudPaperWarning(code=code, message=message, severity="high")
    store = _metadata_store()
    _stored_state_for_paper(paper_id, state)
    blocked_state = store.mark_upload_blocked(paper_id, warning=warning)
    return _public_bundle_for_state(paper_id, blocked_state), False


def _public_bundle_for_state(paper_id: str, state: CloudPaperMetadataRecord) -> CloudPaperBundlePublic:
    return _public_bundle_for_state_with_permissions(paper_id, state, _reader_permissions())


def _public_bundle_for_state_with_permissions(
    paper_id: str,
    state: CloudPaperMetadataRecord,
    permissions: CloudPaperPermissions,
) -> CloudPaperBundlePublic:
    return derive_cloud_paper_public_bundle(
        _internal_bundle(
            paper_id=paper_id,
            lab_id=state.request.lab_id,
            source_pdf_sha256=state.request.source_pdf_sha256,
            processing_status=state.processing_status,
            local_hydration=read_cloud_paper_local_hydration_state(
                paper_id=paper_id,
                run_id=f"run_{paper_id}",
                expected_source_pdf_sha256=state.request.source_pdf_sha256,
            ),
            warnings=state.warnings,
        ),
        current_actor_permissions=permissions,
    )


def get_mock_cloud_bundle(
    paper_id: str,
    *,
    access_context: CloudPaperAccessContext | None = None,
) -> CloudPaperBundlePublic:
    if submission_demo_enabled():
        bundle = get_submission_demo_bundle(paper_id)
        if bundle is not None:
            return bundle
    state = _state_for_paper(paper_id)
    if access_context is None:
        return _public_bundle_for_state(paper_id, state)
    return _public_bundle_for_state_with_permissions(
        paper_id,
        state,
        derive_cloud_paper_permissions_for_access_context(access_context),
    )


def list_mock_cloud_bundles(
    *,
    access_context_for_lab: Callable[[str], CloudPaperAccessContext] | None = None,
) -> list[CloudPaperBundlePublic]:
    if submission_demo_enabled():
        return [bundle for bundle in list_submission_demo_bundles() if bundle.permissions.can_read_page]

    storage_mode = _cloud_storage_mode()
    records_by_id: dict[str, CloudPaperMetadataRecord] = {}
    if storage_mode == "mock":
        for paper_id in _FIXTURE_PAPER_IDS:
            fixture = _fixture_state(paper_id)
            if fixture is not None:
                records_by_id[paper_id] = fixture
    for record in _metadata_store().list_records():
        if storage_mode == "gcs" and record.paper_id.startswith("paper_mock_"):
            continue
        records_by_id[record.paper_id] = record

    bundles: list[CloudPaperBundlePublic] = []
    for paper_id, state in records_by_id.items():
        permissions = _reader_permissions()
        if access_context_for_lab is not None:
            permissions = derive_cloud_paper_permissions_for_access_context(access_context_for_lab(state.request.lab_id))
        bundle = _public_bundle_for_state_with_permissions(paper_id, state, permissions)
        if bundle.permissions.can_read_page:
            bundles.append(bundle)
    return bundles


def _cloud_page_search_terms(query: str) -> list[str]:
    cleaned = str(query or "").strip().lower()
    if not cleaned:
        return []
    return [term for term in cleaned.split() if term]


def _cloud_page_matches_terms(text: str | None, terms: list[str]) -> bool:
    lowered = str(text or "").lower()
    return bool(lowered) and all(term in lowered for term in terms)


def _cloud_page_text_snippet(text: str, terms: list[str], *, max_length: int = 180) -> str:
    lowered = text.lower()
    positions = [lowered.find(term) for term in terms if lowered.find(term) >= 0]
    first_match = min(positions) if positions else 0
    start = max(first_match - 48, 0)
    end = min(start + max_length, len(text))
    snippet = text[start:end].strip()
    if start > 0:
        snippet = f"...{snippet}"
    if end < len(text):
        snippet = f"{snippet}..."
    return snippet


def search_mock_cloud_pages(
    query: str,
    *,
    access_context_for_lab: Callable[[str], CloudPaperAccessContext] | None = None,
    limit: int = 20,
) -> CloudPaperSearchResponse:
    cleaned_query = str(query or "").strip()
    terms = _cloud_page_search_terms(cleaned_query)
    if not terms:
        return CloudPaperSearchResponse(query=cleaned_query, items=[])

    hits: list[CloudPaperSearchHit] = []
    for bundle in list_mock_cloud_bundles(access_context_for_lab=access_context_for_lab):
        if bundle.processing_status != "ready" or "read_page" not in bundle.allowed_actions:
            continue
        try:
            page = get_mock_cloud_page(bundle.paper_id)
        except CloudPaperNotReadyError:
            continue

        matched_blocks: list[CloudPaperSearchBlockHit] = []
        for block in page.blocks:
            if not _cloud_page_matches_terms(block.text, terms):
                continue
            matched_blocks.append(
                CloudPaperSearchBlockHit(
                    block_id=block.block_id,
                    page=block.page,
                    kind=block.kind,
                    text_snippet=_cloud_page_text_snippet(block.text or "", terms),
                    payload_class=block.payload_class,
                    metadata=block.metadata,
                )
            )

        if matched_blocks:
            hits.append(CloudPaperSearchHit(bundle=bundle, matched_blocks=matched_blocks[:3]))
        if len(hits) >= limit:
            break

    return CloudPaperSearchResponse(query=cleaned_query, items=hits)


def complete_mock_upload(paper_id: str, request: CloudPaperUploadCompletionRequest) -> tuple[CloudPaperBundlePublic, bool]:
    store = _metadata_store()
    state = _state_for_paper(paper_id)
    expected_sha256 = state.request.source_pdf_sha256
    if request.source_pdf_sha256 != expected_sha256:
        return _block_upload(
            paper_id,
            state,
            code="CHECKSUM_MISMATCH",
            message="Uploaded PDF checksum did not match the expected source checksum.",
        )

    if store.get(paper_id) is not None:
        verification = get_cloud_paper_storage_adapter().verify_source_pdf(
            paper_id=paper_id,
            lab_id=state.request.lab_id,
            expected_source_pdf_sha256=request.source_pdf_sha256,
        )
        if not verification.exists:
            return _block_upload(
                paper_id,
                state,
                code="SOURCE_PDF_MISSING",
                message="Uploaded PDF object was not found in cloud storage.",
            )
        if not verification.checksum_matches:
            return _block_upload(
                paper_id,
                state,
                code="CHECKSUM_MISMATCH",
                message="Uploaded PDF checksum did not match the expected source checksum.",
            )

    if store.get(paper_id) is not None:
        storage_adapter = get_cloud_paper_storage_adapter()
        state = process_cloud_paper_page_artifact(
            paper_id=paper_id,
            state=state,
            metadata_store=store,
            storage_adapter=storage_adapter,
        )
        if state.processing_status == "ready":
            try:
                derived_artifact = process_cloud_paper_derived_artifacts(
                    paper_id=paper_id,
                    state=state,
                    storage_adapter=storage_adapter,
                )
                storage_adapter.write_derived_artifact(derived_artifact, lab_id=state.request.lab_id)
            except CloudPaperStorageUnavailableError:
                pass
    else:
        state = state.model_copy(update={"upload_status": "ready", "processing_status": "ready", "warnings": []})
    return _public_bundle_for_state(paper_id, state), True


def upload_mock_source_pdf(
    paper_id: str,
    *,
    pdf_bytes: bytes,
    content_type: str,
) -> tuple[CloudPaperSourceUploadResponse | CloudPaperBundlePublic, bool]:
    store = _metadata_store()
    state = _state_for_paper(paper_id)
    if hashlib.sha256(pdf_bytes).hexdigest() != state.request.source_pdf_sha256:
        warning = CloudPaperWarning(
            code="CHECKSUM_MISMATCH",
            message="Uploaded PDF checksum did not match the expected source checksum.",
            severity="high",
        )
        if store.get(paper_id) is None:
            store.create_upload_intent_record(
                paper_id=paper_id,
                upload_intent_id=state.upload_intent_id,
                request=state.request,
            )
        blocked_state = store.mark_upload_blocked(paper_id, warning=warning)
        return _public_bundle_for_state(paper_id, blocked_state), False

    response = get_cloud_paper_storage_adapter().upload_source_pdf(
        pdf_bytes,
        paper_id=paper_id,
        lab_id=state.request.lab_id,
        content_type=content_type,
    )
    if store.get(paper_id) is not None:
        store.mark_upload_received(paper_id)
    return response, True


def blocked_operation_response(bundle: CloudPaperBundlePublic) -> CloudPaperOperationErrorResponse:
    return CloudPaperOperationErrorResponse(
        error_code="CLOUD_PAPER_BLOCKED",
        message="Cloud paper upload is blocked.",
        bundle=bundle,
    )


def forbidden_operation_response(bundle: CloudPaperBundlePublic | None = None) -> CloudPaperOperationErrorResponse:
    return CloudPaperOperationErrorResponse(
        error_code="CLOUD_PAPER_FORBIDDEN",
        message="Cloud paper access is not allowed for this actor, lab, device, or policy.",
        bundle=bundle,
    )


def not_ready_operation_response(bundle: CloudPaperBundlePublic) -> CloudPaperOperationErrorResponse:
    return CloudPaperOperationErrorResponse(
        error_code="CLOUD_PAPER_NOT_READY",
        message="Cloud paper page is not ready.",
        bundle=bundle,
    )


def _mock_page_artifact_for_bundle(bundle: CloudPaperBundlePublic) -> CloudPaperPageArtifactInternal:
    paper_id = bundle.paper_id
    internal_artifact = CloudPaperPageArtifactInternal(
        paper_id=bundle.paper_id,
        run_id=bundle.run_id or f"run_{paper_id}",
        page_schema_version=bundle.page_schema_version or "cloud_page_artifact.v1",
        source_pdf_sha256=bundle.provenance_summary.source_pdf_sha256,
        gcs_page_artifact_object_ref=f"gs://paperpipe-mock-pages/{bundle.lab_id}/{paper_id}/page.json",
        blocks=[
            CloudPaperPageBlockInternal(
                block_id="block_001",
                page=1,
                kind="text",
                text="Mock processed page text for cloud paper API contract verification.",
                bbox_pct={"left": 0.1, "top": 0.1, "width": 0.8, "height": 0.2},
                payload_class=bundle.payload_class,
                metadata={"section": "abstract"},
                worker_metadata={
                    "gcs_page_artifact_object_ref": f"gs://paperpipe-mock-pages/{bundle.lab_id}/{paper_id}/page.json",
                    "service_account": "mock-worker@example.iam.gserviceaccount.com",
                    "local_path": f"/Users/mock/{paper_id}/page.json",
                },
            )
        ],
        warnings=bundle.warnings,
        provenance=_provenance(source_pdf_sha256=bundle.provenance_summary.source_pdf_sha256),
        worker_metadata={
            "gcs_page_artifact_object_ref": f"gs://paperpipe-mock-pages/{bundle.lab_id}/{paper_id}/page.json",
            "service_account": "mock-worker@example.iam.gserviceaccount.com",
            "local_path": f"/Users/mock/{paper_id}/page.json",
        },
    )
    return internal_artifact


def _write_mock_page_artifact_for_state(paper_id: str, state: CloudPaperMetadataRecord) -> None:
    bundle = _public_bundle_for_state(
        paper_id,
        state.model_copy(update={"upload_status": "ready", "processing_status": "ready", "warnings": []}),
    )
    get_cloud_paper_storage_adapter().write_page_artifact(
        _mock_page_artifact_for_bundle(bundle),
        lab_id=state.request.lab_id,
    )


def get_mock_cloud_page(paper_id: str) -> CloudPaperPageArtifactPublic:
    if submission_demo_enabled():
        page = get_submission_demo_page(paper_id)
        if page is not None:
            return page

    store = _metadata_store()
    state = _state_for_paper(paper_id)
    bundle = _public_bundle_for_state(paper_id, state)
    if bundle.processing_status != "ready":
        raise CloudPaperNotReadyError(bundle)
    stored_state = store.get(paper_id)
    if stored_state is not None:
        try:
            artifact = get_cloud_paper_storage_adapter().read_page_artifact(
                paper_id=paper_id,
                lab_id=stored_state.request.lab_id,
                run_id=bundle.run_id or f"run_{paper_id}",
            )
            return derive_cloud_page_artifact_public(artifact)
        except CloudPaperPageArtifactNotFoundError as exc:
            raise CloudPaperNotReadyError(bundle) from exc
    return derive_cloud_page_artifact_public(_mock_page_artifact_for_bundle(bundle))


def get_mock_cloud_derived_artifacts(paper_id: str) -> CloudPaperDerivedArtifactsResponse:
    if submission_demo_enabled():
        derived_artifacts = get_submission_demo_derived_artifacts(paper_id)
        if derived_artifacts is not None:
            return derived_artifacts

    state = _state_for_paper(paper_id)
    bundle = _public_bundle_for_state(paper_id, state)
    if bundle.processing_status != "ready":
        raise CloudPaperNotReadyError(bundle)
    stored_state = _metadata_store().get(paper_id)
    if stored_state is not None:
        try:
            artifact = get_cloud_paper_storage_adapter().read_derived_artifact(
                paper_id=paper_id,
                lab_id=stored_state.request.lab_id,
                run_id=bundle.run_id or f"run_{paper_id}",
            )
            return derive_cloud_paper_public_derived_artifacts(artifact)
        except CloudPaperDerivedArtifactNotFoundError:
            pass
    source_pdf_sha256 = bundle.provenance_summary.source_pdf_sha256
    source_page_1 = CloudPaperDerivedArtifactSourceLocator(
        page=1,
        source_pdf_sha256=source_pdf_sha256,
        block_id="block_001",
        bbox_pct={"left": 0.1, "top": 0.1, "width": 0.8, "height": 0.2},
    )
    source_page_2 = CloudPaperDerivedArtifactSourceLocator(page=2, source_pdf_sha256=source_pdf_sha256)
    source_page_3 = CloudPaperDerivedArtifactSourceLocator(page=3, source_pdf_sha256=source_pdf_sha256)
    artifact = CloudPaperDerivedArtifactInternal(
        paper_id=paper_id,
        run_id=bundle.run_id or f"run_{paper_id}",
        source_pdf_sha256=source_pdf_sha256,
        gcs_derived_artifact_object_ref=(
            f"gs://paperpipe-mock-derived/{bundle.lab_id}/{paper_id}/{bundle.run_id or f'run_{paper_id}'}/derived.json"
        ),
        payload_class=bundle.payload_class,
        ocr_blocks=[
            CloudPaperDerivedArtifactOcrBlock(
                ocr_block_id="ocr_001",
                text="Mock OCR text recovered from a rendered cloud PDF page.",
                confidence=0.91,
                source=source_page_1,
                payload_class=bundle.payload_class,
                metadata={
                    "engine": "mock-ocr",
                    "gcs_image_object_ref": f"gs://paperpipe-mock-derived/{bundle.lab_id}/{paper_id}/page-1.png",
                    "local_path": f"/Users/mock/{paper_id}/page-1.png",
                },
            )
        ],
        tables=[
            CloudPaperDerivedArtifactTable(
                table_id="table_001",
                page=2,
                caption="Mock reconstructed table from cloud PDF layout.",
                columns=["Group", "N"],
                rows=[["Control", "10"], ["Treatment", "12"]],
                confidence=0.82,
                source=source_page_2,
                payload_class=bundle.payload_class,
            )
        ],
        figures=[
            CloudPaperDerivedArtifactFigure(
                figure_id="figure_001",
                page=3,
                caption="Mock figure crop from rendered cloud PDF page.",
                bbox_pct={"left": 0.1, "top": 0.1, "width": 0.7, "height": 0.5},
                image_available=True,
                image_route=f"/api/cloud/papers/{paper_id}/figures/figure_001/image",
                confidence=0.77,
                source=source_page_3,
                payload_class=bundle.payload_class,
                metadata={"signed_url": "https://signed.example.test/private"},
            )
        ],
        figure_analyses=[
            CloudPaperDerivedArtifactFigureAnalysis(
                analysis_id="figure_analysis_001",
                figure_id="figure_001",
                page=3,
                summary="Mock figure analysis placeholder derived from a server-side figure crop.",
                confidence=0.7,
                source=source_page_3,
                payload_class=bundle.payload_class,
            )
        ],
        warnings=bundle.warnings,
        provenance=_provenance(source_pdf_sha256=source_pdf_sha256),
        worker_metadata={
            "service_account": "mock-worker@example.iam.gserviceaccount.com",
            "local_path": f"/Users/mock/{paper_id}/derived.json",
        },
    )
    return derive_cloud_paper_public_derived_artifacts(artifact)


def hydrate_mock_cloud_paper(paper_id: str, *, device_id: str = "mock_device") -> CloudPaperHydrationState:
    state = _state_for_paper(paper_id)
    bundle = _public_bundle_for_state(paper_id, state)
    if bundle.processing_status != "ready":
        raise CloudPaperNotReadyError(bundle)
    try:
        storage_adapter = get_cloud_paper_storage_adapter()
        source_pdf_bytes = storage_adapter.read_source_pdf(paper_id=paper_id, lab_id=state.request.lab_id)
        page_artifact = storage_adapter.read_page_artifact(
            paper_id=paper_id,
            lab_id=state.request.lab_id,
            run_id=bundle.run_id or f"run_{paper_id}",
        )
        manifest = write_cloud_paper_local_bundle(
            paper_id=paper_id,
            run_id=bundle.run_id or f"run_{paper_id}",
            device_id=device_id,
            source_pdf_bytes=source_pdf_bytes,
            page_artifact=page_artifact,
        )
    except CloudPaperHydrationConflictError as exc:
        return CloudPaperHydrationState(
            status="stale",
            hydrated_at=exc.manifest.hydrated_at,
            source_pdf_sha256=exc.manifest.source_pdf_sha256,
            page_artifact_sha256=exc.manifest.page_artifact_sha256,
        )
    return manifest.to_public_state()
