from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import md5, sha1, sha256, sha512
import json
from pathlib import Path

from src.image_evidence.store import (
    list_image_evidence_ids,
    load_image_evidence,
    load_image_handoff_targets,
    load_image_view_state,
    save_image_evidence_bundle,
)
from src.schemas.image_evidence import (
    ImageEvidence,
    ImageEvidenceListResponse,
    ImageEvidenceRequest,
    ImageEvidenceResponse,
    ImageEvidenceSummary,
    ImageHandoffTarget,
    ImageMetadata,
    ImageViewState,
    ImageWarning,
    summarize_image_evidence,
)


@dataclass(frozen=True)
class ImageEvidenceResult:
    image_evidence: ImageEvidence
    view_state: ImageViewState | None
    handoff_targets: list[ImageHandoffTarget]


def register_image_evidence(
    *,
    request: ImageEvidenceRequest,
    root: Path | None = None,
    now: datetime | None = None,
) -> ImageEvidenceResult:
    created_at = now.astimezone(timezone.utc) if now is not None else datetime.now(timezone.utc)
    image_evidence_id = request.image_evidence_id or _new_image_evidence_id(request)
    metadata = request.metadata.model_copy(deep=True)
    warnings = [warning.model_copy(deep=True) for warning in request.warnings]
    source_ref = request.source_ref.model_copy(deep=True)
    checksum = request.checksum.model_copy(deep=True) if request.checksum is not None else None

    if source_ref.source_kind == "local_file" and source_ref.local_path is not None:
        local_path = Path(source_ref.local_path).expanduser()
        if not local_path.exists():
            warnings.append(
                ImageWarning(
                    code="LOCAL_SOURCE_MISSING",
                    severity="warning",
                    message=f"Local source file does not exist: {local_path}",
                )
            )
        elif not local_path.is_file():
            warnings.append(
                ImageWarning(
                    code="LOCAL_SOURCE_NOT_FILE",
                    severity="error",
                    message=f"Local source ref is not a file: {local_path}",
                )
            )
        else:
            if metadata.filename is None:
                metadata.filename = local_path.name
            if metadata.source_size_bytes is None:
                metadata.source_size_bytes = local_path.stat().st_size
            if checksum is not None:
                actual_checksum = _compute_checksum(local_path, checksum.algorithm)
                if actual_checksum.lower() != checksum.value.lower():
                    warnings.append(
                        ImageWarning(
                            code="CHECKSUM_MISMATCH",
                            severity="warning",
                            message=(
                                f"Provided {checksum.algorithm} checksum does not match local file "
                                f"for {local_path.name}: expected {checksum.value}, observed {actual_checksum}"
                            ),
                        )
                    )

    image_evidence = ImageEvidence(
        image_evidence_id=image_evidence_id,
        title=request.title or _default_title(request, metadata, source_ref, image_evidence_id),
        created_at=created_at,
        paper_id=request.paper_id,
        paper_slug=request.paper_slug,
        source_ref=source_ref,
        content_format=request.content_format,
        checksum=checksum,
        metadata=metadata,
        view_state_ref=(
            {"kind": "view_state_json", "path": "view_state.json"} if request.view_state is not None else None
        ),
        handoff_ref=(
            {"kind": "handoff_json", "path": "handoff.json"} if request.handoff_targets else None
        ),
        derived_outputs=[output.model_copy(deep=True) for output in request.derived_outputs],
        linked_claim_refs=[link.model_copy(deep=True) for link in request.linked_claim_refs],
        linked_artifact_refs=[link.model_copy(deep=True) for link in request.linked_artifact_refs],
        warnings=_dedupe_warnings(warnings),
    )
    save_image_evidence_bundle(
        image_evidence,
        view_state=request.view_state.model_copy(deep=True) if request.view_state is not None else None,
        handoff_targets=[target.model_copy(deep=True) for target in request.handoff_targets] or None,
        root=root,
    )
    return ImageEvidenceResult(
        image_evidence=image_evidence,
        view_state=request.view_state.model_copy(deep=True) if request.view_state is not None else None,
        handoff_targets=[target.model_copy(deep=True) for target in request.handoff_targets],
    )


def get_image_evidence_bundle(image_evidence_id: str, *, root: Path | None = None) -> ImageEvidenceResult:
    image_evidence = load_image_evidence(image_evidence_id, root)
    view_state = (
        load_image_view_state(image_evidence_id, root)
        if image_evidence.view_state_ref is not None
        else None
    )
    handoff_targets = (
        load_image_handoff_targets(image_evidence_id, root)
        if image_evidence.handoff_ref is not None
        else []
    )
    return ImageEvidenceResult(
        image_evidence=image_evidence,
        view_state=view_state,
        handoff_targets=handoff_targets,
    )


def list_image_evidence_summaries(*, root: Path | None = None) -> list[ImageEvidence]:
    items = [load_image_evidence(image_evidence_id, root) for image_evidence_id in list_image_evidence_ids(root)]
    return sorted(items, key=lambda item: (item.created_at, item.image_evidence_id), reverse=True)


def image_evidence_response_payload(result: ImageEvidenceResult) -> ImageEvidenceResponse:
    return ImageEvidenceResponse(
        image_evidence=result.image_evidence,
        view_state=result.view_state,
        handoff_targets=result.handoff_targets,
    )


def image_evidence_list_response(*, root: Path | None = None) -> ImageEvidenceListResponse:
    items: list[ImageEvidenceSummary] = [
        summarize_image_evidence(image_evidence)
        for image_evidence in list_image_evidence_summaries(root=root)
    ]
    return ImageEvidenceListResponse(items=items, total=len(items))


def _new_image_evidence_id(request: ImageEvidenceRequest) -> str:
    payload = request.model_dump(mode="json", exclude_none=True)
    digest = sha1(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()[:10]
    return f"imageev_{digest}"


def _default_title(
    request: ImageEvidenceRequest,
    metadata: ImageMetadata,
    source_ref,
    image_evidence_id: str,
) -> str:
    if metadata.filename:
        return metadata.filename
    if source_ref.source_label:
        return source_ref.source_label
    if source_ref.source_kind == "local_file" and source_ref.local_path:
        return Path(source_ref.local_path).name
    if source_ref.source_kind == "external_image_ref" and source_ref.external_ref:
        return source_ref.external_ref.rsplit("/", 1)[-1] or image_evidence_id
    return image_evidence_id


def _dedupe_warnings(warnings: list[ImageWarning]) -> list[ImageWarning]:
    deduped: list[ImageWarning] = []
    seen: set[tuple[str, str, str]] = set()
    for warning in warnings:
        key = (warning.code, warning.severity, warning.message)
        if key not in seen:
            deduped.append(warning)
            seen.add(key)
    return deduped


def _compute_checksum(path: Path, algorithm: str) -> str:
    hasher_map = {
        "md5": md5,
        "sha1": sha1,
        "sha256": sha256,
        "sha512": sha512,
    }
    hasher = hasher_map[algorithm]()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()

