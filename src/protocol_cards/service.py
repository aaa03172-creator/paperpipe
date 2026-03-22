from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha1
import json
import re
from pathlib import Path

from src.protocol_cards.renderer import render_protocol_card_markdown
from src.protocol_cards.store import (
    list_protocol_card_ids,
    load_protocol_card,
    load_protocol_card_markdown,
    load_protocol_version,
    load_protocol_versions,
    save_protocol_card_bundle,
)
from src.schemas.protocol_card import (
    ProtocolCard,
    ProtocolCardListResponse,
    ProtocolCardRequest,
    ProtocolCardResponse,
    ProtocolCardSummary,
    ProtocolValidationStatus,
    ProtocolVersion,
    ProtocolVersionListResponse,
    build_protocol_version_summary,
    summarize_protocol_card,
)


@dataclass(frozen=True)
class ProtocolCardResult:
    protocol_card: ProtocolCard
    versions: list[ProtocolVersion]
    markdown: str


def upsert_protocol_card(
    *,
    request: ProtocolCardRequest,
    root: Path | None = None,
    now: datetime | None = None,
) -> ProtocolCardResult:
    now = now.astimezone(timezone.utc) if now is not None else datetime.now(timezone.utc)
    protocol_id = request.protocol_id or _new_protocol_id(request, now)
    versions = [
        ProtocolVersion(
            version_id=version.version_id or _new_version_id(protocol_id, version.version_number),
            protocol_id=protocol_id,
            version_number=version.version_number,
            key_steps_summary=list(version.key_steps_summary),
            materials=list(version.materials),
            equipment=list(version.equipment),
            critical_conditions=list(version.critical_conditions),
            readouts=list(version.readouts),
            cautions=list(version.cautions),
            content_snapshot=version.content_snapshot,
            change_reason=version.change_reason,
            status=version.status,
            created_by=version.created_by,
            created_at=version.created_at or now,
            source_refs=[ref.model_copy(deep=True) for ref in version.source_refs],
            note=version.note,
        )
        for version in request.versions
    ]
    current_version_id = _resolve_current_version_id(request.current_version_id, versions)
    protocol_card = ProtocolCard(
        protocol_id=protocol_id,
        title=request.title,
        purpose=request.purpose,
        context=request.context,
        source_kind=request.source_kind,
        linked_paper_ids=list(request.linked_paper_ids),
        linked_note_slugs=list(request.linked_note_slugs),
        current_version_id=current_version_id,
        validation_status=_resolve_validation_status(request.validation_status, versions),
        created_at=request.created_at or _resolve_created_at(versions, now),
        updated_at=request.updated_at or now,
        version_summaries=[build_protocol_version_summary(version) for version in versions],
    )
    markdown = render_protocol_card_markdown(protocol_card, versions)
    save_protocol_card_bundle(protocol_card, markdown, versions=versions, root=root)
    return ProtocolCardResult(protocol_card=protocol_card, versions=versions, markdown=markdown)


def get_protocol_card_bundle(protocol_id: str, *, root: Path | None = None) -> ProtocolCardResult:
    protocol_card = load_protocol_card(protocol_id, root)
    markdown = load_protocol_card_markdown(protocol_id, root)
    versions = load_protocol_versions(protocol_id, root)
    return ProtocolCardResult(protocol_card=protocol_card, versions=versions, markdown=markdown)


def list_protocol_card_summaries(*, root: Path | None = None) -> list[ProtocolCard]:
    items = [load_protocol_card(protocol_id, root) for protocol_id in list_protocol_card_ids(root)]
    return sorted(items, key=lambda item: (item.updated_at, item.protocol_id), reverse=True)


def protocol_card_response_payload(result: ProtocolCardResult) -> ProtocolCardResponse:
    return ProtocolCardResponse(
        protocol_card=result.protocol_card,
        versions=result.versions,
        markdown=result.markdown,
    )


def protocol_card_list_response(*, root: Path | None = None) -> ProtocolCardListResponse:
    items: list[ProtocolCardSummary] = [
        summarize_protocol_card(protocol_card)
        for protocol_card in list_protocol_card_summaries(root=root)
    ]
    return ProtocolCardListResponse(items=items, total=len(items))


def protocol_version_list_response(protocol_id: str, *, root: Path | None = None) -> ProtocolVersionListResponse:
    load_protocol_card(protocol_id, root)
    items = load_protocol_versions(protocol_id, root)
    return ProtocolVersionListResponse(items=items, total=len(items))


def get_protocol_version_item(protocol_id: str, version_id: str, *, root: Path | None = None) -> ProtocolVersion:
    return load_protocol_version(protocol_id, version_id, root)


def _resolve_current_version_id(
    requested_current_version_id: str | None,
    versions: list[ProtocolVersion],
) -> str:
    if requested_current_version_id is not None:
        return requested_current_version_id
    active_versions = [version for version in versions if version.status == "active"]
    candidate_pool = active_versions or versions
    selected = max(candidate_pool, key=lambda item: (item.version_number, item.created_at, item.version_id))
    return selected.version_id


def _resolve_created_at(versions: list[ProtocolVersion], now: datetime) -> datetime:
    if not versions:
        return now
    return min(version.created_at for version in versions)


def _resolve_validation_status(
    requested_status: ProtocolValidationStatus,
    versions: list[ProtocolVersion],
) -> ProtocolValidationStatus:
    if requested_status != "unreviewed":
        return requested_status
    if any(version.status == "active" for version in versions):
        return "draft"
    return requested_status


def _new_protocol_id(request: ProtocolCardRequest, now: datetime) -> str:
    payload = request.model_dump(mode="json", exclude_none=True)
    digest = sha1(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()[:8]
    return f"protocol_{now.strftime('%Y%m%dT%H%M%SZ')}_{digest}"


def _new_version_id(protocol_id: str, version_number: int) -> str:
    protocol_suffix = protocol_id.removeprefix("protocol_")
    safe_suffix = re.sub(r"[^A-Za-z0-9._-]+", "_", protocol_suffix).strip("._") or "protocol"
    return f"protver_{safe_suffix}_v{version_number}"
