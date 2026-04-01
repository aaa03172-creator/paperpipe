from __future__ import annotations

from src.meeting_packs.store import save_meeting_pack_artifact_json
from src.schemas.meeting_pack import MeetingPack
from src.schemas.meeting_pack_handoff import (
    MeetingPackAcceptanceCheck,
    MeetingPackAcceptanceContract,
    MeetingPackQualityGate,
    MeetingPackQualityGateCheck,
)


def _requested_scope_source_items(pack: MeetingPack) -> list[dict[str, object]]:
    if pack.generation_request is not None:
        return [
            {"type": item.type, "ref": item.ref}
            for item in pack.generation_request.source_items
        ]

    explicit_selectors = [item for item in pack.source_items if item.type != "paper_state"]
    selector_items = explicit_selectors or [item for item in pack.source_items if item.type == "paper_state"]
    return [{"type": item.type, "ref": item.ref} for item in selector_items]


def _requested_scope_max_slides(pack: MeetingPack) -> int:
    if pack.generation_request is not None:
        return pack.generation_request.max_slides
    return min(8, max(5, len(pack.slides) or 5))


def build_meeting_pack_acceptance_contract(
    *,
    pack: MeetingPack,
    regenerate_strategy: str,
) -> MeetingPackAcceptanceContract:
    checks = [
        MeetingPackAcceptanceCheck(
            name="meeting_pack_bundle_written",
            source="storage/meeting_packs/<pack_id>/meeting_pack.{json,md}",
            description="Primary bundle-local manifest and markdown draft were persisted.",
        ),
        MeetingPackAcceptanceCheck(
            name="generation_request_or_deterministic_fallback_available",
            source="meeting_pack.json.generation_request or deterministic source_items fallback",
            description="Saved intent exists for bounded regenerate or rerender recovery.",
        ),
        MeetingPackAcceptanceCheck(
            name="retrieval_trace_persisted",
            required=False,
            source="meeting_pack.json.retrieval_trace[]",
            description="Selector/load observability metadata was saved for bounded operator review.",
        ),
        MeetingPackAcceptanceCheck(
            name="readiness_labeled",
            source="meeting_pack.json.readiness",
            description="Pack truth is labeled as evidence_backed or background_only.",
        ),
        MeetingPackAcceptanceCheck(
            name="markdown_synced_at_write",
            source="deterministic render at bundle write time",
            description="Saved markdown matched the deterministic render when artifacts were written.",
        ),
    ]
    return MeetingPackAcceptanceContract(
        pack_id=pack.id,
        requested_scope={
            "mode": pack.mode,
            "output_mode_family": pack.output_mode_family,
            "title": pack.title,
            "source_items": _requested_scope_source_items(pack),
            "max_slides": _requested_scope_max_slides(pack),
        },
        expected_outputs=[
            "meeting_pack.json",
            "meeting_pack.md",
        ],
        acceptance_checks=checks,
        operator_contract={
            "discussion_ready_rule": "bundle ready plus readiness=evidence_backed",
            "validate_endpoint_authoritative_for_current_regenerate_availability": True,
            "regenerate_strategy_snapshot": regenerate_strategy,
            "owner": "current Meeting Pack runtime; additive pilot metadata only",
        },
    )


def build_meeting_pack_quality_gate(
    *,
    pack: MeetingPack,
    regenerate_strategy: str,
    markdown_sync_status: str,
) -> MeetingPackQualityGate:
    trace_available = bool(pack.retrieval_trace)
    regenerate_available = regenerate_strategy != "unavailable"
    markdown_synced = markdown_sync_status == "in_sync"
    bundle_ready = regenerate_available and markdown_synced
    discussion_ready = bundle_ready and pack.readiness == "evidence_backed"

    checks = [
        MeetingPackQualityGateCheck(
            name="generation_request_or_deterministic_fallback_available",
            status="pass" if regenerate_available else "fail",
            detail=regenerate_strategy,
        ),
        MeetingPackQualityGateCheck(
            name="retrieval_trace_persisted",
            status="pass" if trace_available else "warn",
            detail=str(trace_available).lower(),
        ),
        MeetingPackQualityGateCheck(
            name="markdown_synced_at_write",
            status="pass" if markdown_synced else "fail",
            detail=markdown_sync_status,
        ),
        MeetingPackQualityGateCheck(
            name="readiness_evidence_backed",
            status="pass" if pack.readiness == "evidence_backed" else "warn",
            detail=pack.readiness,
        ),
    ]

    reason_codes: list[str] = []
    if not regenerate_available:
        reason_codes.append("REGENERATE_UNAVAILABLE")
    if not trace_available:
        reason_codes.append("TRACE_MISSING")
    if not markdown_synced:
        reason_codes.append("MARKDOWN_DRIFT_AT_WRITE")
    if pack.readiness != "evidence_backed":
        reason_codes.append("BACKGROUND_ONLY")

    if discussion_ready:
        overall_status: str = "pass"
    elif bundle_ready:
        overall_status = "warn"
    else:
        overall_status = "fail"

    return MeetingPackQualityGate(
        pack_id=pack.id,
        overall_status=overall_status,  # type: ignore[arg-type]
        bundle_ready=bundle_ready,
        discussion_ready=discussion_ready,
        reason_codes=reason_codes,
        checks=checks,
    )


def write_meeting_pack_handoff_artifacts(
    *,
    pack: MeetingPack,
    root=None,
    regenerate_strategy: str,
    markdown_sync_status: str,
) -> dict[str, str]:
    contract = build_meeting_pack_acceptance_contract(
        pack=pack,
        regenerate_strategy=regenerate_strategy,
    )
    quality_gate = build_meeting_pack_quality_gate(
        pack=pack,
        regenerate_strategy=regenerate_strategy,
        markdown_sync_status=markdown_sync_status,
    )
    contract_path = save_meeting_pack_artifact_json(
        pack.id,
        "acceptance_contract.json",
        contract.model_dump(mode="json", exclude_none=True),
        root=root,
    )
    quality_gate_path = save_meeting_pack_artifact_json(
        pack.id,
        "quality_gate.json",
        quality_gate.model_dump(mode="json", exclude_none=True),
        root=root,
    )
    return {
        "acceptance_contract_path": str(contract_path),
        "quality_gate_path": str(quality_gate_path),
    }
