from __future__ import annotations

from typing import Any, Dict, Optional

from src.json_repair import repair_and_parse_json

EXPECTED_TAGGING_KEYS = ["hard_tags", "soft_tags"]
ALLOWED_SLOT_PREDICTIONS = {"Mechanism", "Clinical", "Methods"}


def find_dict_with_keys(obj: Any, keys: list[str]) -> Optional[Dict[str, Any]]:
    if isinstance(obj, dict):
        if all(key in obj for key in keys):
            return obj
        for value in obj.values():
            found = find_dict_with_keys(value, keys)
            if found:
                return found
    return None


def extract_llm_json(response_content: str) -> Dict[str, Any]:
    parsed = repair_and_parse_json(response_content)
    unwrapped = find_dict_with_keys(parsed, EXPECTED_TAGGING_KEYS)
    if unwrapped:
        return unwrapped
    return parsed


def slot_prediction_from_payload(payload: Dict[str, Any]) -> Optional[str]:
    predicted = payload.get("predicted_slot")
    if predicted in ALLOWED_SLOT_PREDICTIONS:
        return str(predicted)
    return None


def escalation_result_from_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "approved": payload.get("approved", False),
        "new_confidence": payload.get("new_confidence", 0.0),
        "reason": payload.get("reason", "No reason provided"),
    }


def relevance_result_from_payload(payload: Dict[str, Any]) -> Dict[str, str]:
    return {
        "gap": payload.get("gap", "N/A"),
        "insight": payload.get("insight", "N/A"),
        "limitation": payload.get("limitation", "N/A"),
    }
