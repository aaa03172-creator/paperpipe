from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

from src.meeting_packs.store import (
    list_meeting_pack_ids,
    meeting_pack_json_path,
    save_meeting_pack_artifact_json,
)
from src.schemas.meeting_pack import MeetingPack
from src.schemas.meeting_pack_handoff import (
    MeetingPackAcceptanceCheck,
    MeetingPackAcceptanceContract,
    MeetingPackQualityGate,
    MeetingPackQualityGateCheck,
)

_GENERIC_KEY_POINT_TEXTS = frozenset(
    {
        "The intervention shows an initial improvement window during early follow-up.",
        "No severe adverse events were reported in the observed cohort.",
    }
)
_TITLE_TOKEN_STOPWORDS = frozenset(
    {
        "about",
        "after",
        "analysis",
        "and",
        "article",
        "assessment",
        "biological",
        "clinical",
        "construct",
        "constructs",
        "disease",
        "effects",
        "evidence",
        "follow",
        "from",
        "group",
        "initial",
        "international",
        "intervention",
        "journal",
        "meeting",
        "observed",
        "paper",
        "period",
        "project",
        "recommendation",
        "report",
        "results",
        "review",
        "severe",
        "shows",
        "study",
        "summary",
        "update",
        "window",
    }
)
_KEY_POINT_REUSE_WARN_THRESHOLD = 3


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
            name="artifact_brief_persisted",
            required=False,
            source="meeting_pack.json.artifact_brief + artifact_brief_review",
            description="Saved source-context vs communicative-intent planning metadata exists for bounded downstream review.",
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
            "source_items": [
                {"type": item.type, "ref": item.ref}
                for item in (pack.generation_request.source_items if pack.generation_request else [])
            ],
            "max_slides": pack.generation_request.max_slides if pack.generation_request else len(pack.slides),
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
    root: Path | None = None,
) -> MeetingPackQualityGate:
    trace_available = bool(pack.retrieval_trace)
    regenerate_available = regenerate_strategy != "unavailable"
    markdown_synced = markdown_sync_status == "in_sync"
    bundle_ready = regenerate_available and markdown_synced
    discussion_ready = bundle_ready and pack.readiness == "evidence_backed"
    content_risk_codes, content_risk_detail = _content_quality_risk_summary(pack=pack, root=root)
    content_review_required = bool(content_risk_codes)
    brief_review = pack.artifact_brief_review
    brief_reason_codes = list(brief_review.reason_codes) if brief_review is not None else []
    brief_review_required = bool(brief_review is not None and brief_review.overall_status != "pass")

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
        MeetingPackQualityGateCheck(
            name="artifact_brief_review",
            status="warn" if brief_review_required else "pass",
            detail=(
                "missing"
                if brief_review is None
                else "; ".join(brief_reason_codes) or brief_review.overall_status
            ),
        ),
        MeetingPackQualityGateCheck(
            name="content_quality_risk_scan",
            status="warn" if content_review_required else "pass",
            detail=content_risk_detail,
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
    if brief_review_required:
        reason_codes.extend(brief_reason_codes or ["ARTIFACT_BRIEF_WARN"])
    reason_codes.extend(content_risk_codes)
    reason_codes = list(dict.fromkeys(reason_codes))

    if discussion_ready and not content_review_required:
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
        root=root,
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


def meeting_pack_content_risk_warnings(*, pack: MeetingPack, root: Path | None = None) -> list[str]:
    reason_codes, _detail = _content_quality_risk_summary(pack=pack, root=root)
    warnings: list[str] = []
    for code in reason_codes:
        if code == "GENERIC_KEY_POINT_TEXT":
            warnings.append(
                "Generic key-point wording was detected; re-check that the summary reflects paper-specific claims."
            )
        elif code == "KEY_POINT_TEXT_REUSED":
            warnings.append(
                "Exact key-point text is reused across multiple saved packs; review for fixture-like or low-diversity output."
            )
        elif code == "TITLE_KEYPOINT_TOKEN_MISMATCH":
            warnings.append(
                "Pack title and highlighted key points do not appear semantically aligned; review before presentation."
            )
    return warnings


def _content_quality_risk_summary(*, pack: MeetingPack, root: Path | None) -> tuple[list[str], str]:
    key_point_texts = [point.text.strip() for point in pack.one_page_summary.key_points if point.text.strip()]
    if not key_point_texts:
        return [], "no_key_points"

    reason_codes: list[str] = []
    detail_parts: list[str] = []

    generic_hits = sorted({text for text in key_point_texts if text in _GENERIC_KEY_POINT_TEXTS})
    if generic_hits:
        reason_codes.append("GENERIC_KEY_POINT_TEXT")
        detail_parts.append(f"generic_hits={len(generic_hits)}")

    reuse_counts = _reused_key_point_counts(pack=pack, root=root, key_point_texts=key_point_texts)
    reused_hits = sorted(text for text, count in reuse_counts.items() if count >= _KEY_POINT_REUSE_WARN_THRESHOLD)
    if reused_hits:
        reason_codes.append("KEY_POINT_TEXT_REUSED")
        detail_parts.append(f"reused_hits={len(reused_hits)}")

    title_tokens = _content_tokens(pack.title)
    key_point_tokens: set[str] = set()
    for text in key_point_texts:
        key_point_tokens.update(_content_tokens(text))
    if title_tokens and key_point_tokens and not (title_tokens & key_point_tokens) and (generic_hits or reused_hits):
        reason_codes.append("TITLE_KEYPOINT_TOKEN_MISMATCH")
        detail_parts.append("title_overlap=0")

    return list(dict.fromkeys(reason_codes)), "; ".join(detail_parts) if detail_parts else "no_content_risk_signals"


def _reused_key_point_counts(
    *,
    pack: MeetingPack,
    root: Path | None,
    key_point_texts: list[str],
) -> Counter[str]:
    normalized_targets = {
        _normalize_key_point_text(text): text
        for text in key_point_texts
        if _normalize_key_point_text(text)
    }
    if not normalized_targets:
        return Counter()

    counts: Counter[str] = Counter()
    for pack_id in list_meeting_pack_ids(root):
        if pack_id == pack.id:
            continue
        path = meeting_pack_json_path(pack_id, root)
        if not path.exists():
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        for raw_point in payload.get("one_page_summary", {}).get("key_points", []):
            normalized = _normalize_key_point_text(str(raw_point.get("text") or ""))
            if normalized in normalized_targets:
                counts[normalized_targets[normalized]] += 1
    return counts


def _content_tokens(text: str) -> set[str]:
    tokens: set[str] = set()
    for token in re.findall(r"[A-Za-z0-9]+", text.lower()):
        if len(token) < 4 or token.isdigit() or token in _TITLE_TOKEN_STOPWORDS:
            continue
        tokens.add(token)
    return tokens


def _normalize_key_point_text(text: str) -> str:
    return " ".join(text.split()).strip().lower()
