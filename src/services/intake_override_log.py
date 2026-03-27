from __future__ import annotations

import json
from typing import Any

from src.schemas.intake_override_log import IntakeOverrideLog


def build_intake_override_log(
    *,
    producer: str,
    analysis_available: bool,
    llm_tagging_used: bool,
    llm_slot_classification_used: bool,
    input_slot: str | None,
    stored_slot: str | None,
    input_tags: list[str] | None,
    stored_tags: list[str] | None,
    processing_status: str | None,
    issues_state: str | None,
    confidence: float | None,
) -> IntakeOverrideLog:
    normalized_input_tags = _normalize_tags(input_tags)
    normalized_stored_tags = _normalize_tags(stored_tags)
    normalized_input_slot = (input_slot or "").strip() or None
    normalized_stored_slot = (stored_slot or "").strip() or None
    return IntakeOverrideLog(
        producer=producer,
        analysis_available=analysis_available,
        llm_tagging_used=llm_tagging_used,
        llm_slot_classification_used=llm_slot_classification_used,
        input_slot=normalized_input_slot,
        stored_slot=normalized_stored_slot,
        slot_changed=normalized_input_slot != normalized_stored_slot,
        input_tags=normalized_input_tags,
        stored_tags=normalized_stored_tags,
        tags_changed=normalized_input_tags != normalized_stored_tags,
        processing_status=processing_status,
        issues_state=issues_state,
        confidence=confidence,
    )


def merge_feedback_json_with_intake_override(
    feedback_json: str | None,
    intake_override_log: IntakeOverrideLog,
) -> str:
    payload = _parse_feedback_json(feedback_json)
    payload["intake_override_log"] = intake_override_log.model_dump(mode="json")
    return json.dumps(payload, ensure_ascii=False)


def _parse_feedback_json(feedback_json: str | None) -> dict[str, Any]:
    if not feedback_json:
        return {}
    try:
        parsed = json.loads(feedback_json)
    except Exception:
        return {"raw_feedback_json": str(feedback_json)}
    if isinstance(parsed, dict):
        return parsed
    return {"raw_feedback_json": feedback_json}


def _normalize_tags(tags: list[str] | None) -> list[str]:
    normalized = [str(tag).strip() for tag in (tags or []) if str(tag).strip()]
    return sorted(dict.fromkeys(normalized))
