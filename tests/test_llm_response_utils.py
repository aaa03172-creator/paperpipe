from src.llm_response_utils import (
    escalation_result_from_payload,
    extract_llm_json,
    relevance_result_from_payload,
    slot_prediction_from_payload,
)


def test_extract_llm_json_unwraps_nested_tagging_payload():
    payload = '{"response":{"hard_tags":{"study_type":"RCT"},"soft_tags":["#A"],"evidence_span":"ok"}}'
    result = extract_llm_json(payload)
    assert result["hard_tags"]["study_type"] == "RCT"
    assert result["soft_tags"] == ["#A"]
    assert result["evidence_span"] == "ok"


def test_slot_prediction_allows_only_supported_values():
    assert slot_prediction_from_payload({"predicted_slot": "Clinical"}) == "Clinical"
    assert slot_prediction_from_payload({"predicted_slot": "Unknown"}) is None


def test_escalation_result_defaults_missing_fields():
    result = escalation_result_from_payload({})
    assert result["approved"] is False
    assert result["new_confidence"] == 0.0
    assert result["reason"] == "No reason provided"


def test_relevance_result_defaults_missing_fields():
    result = relevance_result_from_payload({})
    assert result == {"gap": "N/A", "insight": "N/A", "limitation": "N/A"}
