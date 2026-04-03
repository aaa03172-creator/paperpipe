from __future__ import annotations

from types import SimpleNamespace

from src.llm_provider import (
    ESCALATION_ROUTE_APPROVE,
    ESCALATION_ROUTE_REVIEW,
    LLMProvider,
)


class _DummyProvider(LLMProvider):
    def __init__(self, config, response: str | None = None):
        self._response = response
        super().__init__(config)

    def _initialize(self) -> None:
        self.client = True

    def _make_request(self, *args, **kwargs):
        return self._response

    def get_embedding(self, text: str):
        return None


def _provider(response: str | None = None) -> _DummyProvider:
    return _DummyProvider(SimpleNamespace(features=None, default_model=None), response=response)


def test_evaluate_escalation_fast_reject_returns_structured_route_fields() -> None:
    provider = _provider()

    result = provider.evaluate_escalation(
        {
            "title": "Ceramide-inspired self-assembly improves membrane stability in synthetic polymer films",
            "summary": "This materials-science paper studies synthetic polymer films without biological or translational context.",
            "tags": ["#materials_science", "#polymer"],
        }
    )

    assert result["approved"] is False
    assert result["in_biomedical_scope"] is False
    assert result["final_route"] == ESCALATION_ROUTE_REVIEW
    assert result["reason_codes"] == ["OUT_OF_BIOMEDICAL_SCOPE"]


def test_evaluate_escalation_fast_approve_returns_structured_route_fields() -> None:
    provider = _provider()

    result = provider.evaluate_escalation(
        {
            "title": "Clinical practice guideline for liquid biopsy biomarkers in metastatic colorectal cancer",
            "summary": "Consensus guidance for diagnosis, treatment monitoring, and plasma biomarker interpretation in metastatic colorectal cancer.",
            "tags": ["#Oncology", "#ClinicalGuideline", "#LiquidBiopsy"],
        }
    )

    assert result["approved"] is True
    assert result["in_biomedical_scope"] is True
    assert result["final_route"] == ESCALATION_ROUTE_APPROVE
    assert result["reason_codes"] == ["FASTLANE_GUIDANCE"]


def test_evaluate_escalation_preserves_model_supplied_structured_fields() -> None:
    provider = _provider(
        response=(
            '{"approved": false, "new_confidence": 0.41, "reason": "Needs human review.", '
            '"reason_codes": ["review_style_low_clarity"], "final_route": "QUEUE_HUMAN_REVIEW"}'
        )
    )

    result = provider.evaluate_escalation(
        {
            "title": "Review of hydrogel scaffolds for regenerative medicine and wound healing",
            "summary": "This broad review surveys hydrogel scaffolds and translational biomaterials applications without new clinical data.",
            "tags": ["#Review", "#Biomaterials", "#RegenerativeMedicine"],
        }
    )

    assert result["approved"] is False
    assert result["in_biomedical_scope"] is True
    assert result["final_route"] == ESCALATION_ROUTE_REVIEW
    assert result["reason_codes"] == ["REVIEW_STYLE_LOW_CLARITY"]


def test_evaluate_escalation_normalizes_model_reason_code_aliases() -> None:
    provider = _provider(
        response=(
            '{"approved": false, "new_confidence": 0.33, "reason": "Needs human review.", '
            '"reason_codes": ["broad_review", "no_authority"], "final_route": "QUEUE_HUMAN_REVIEW"}'
        )
    )

    result = provider.evaluate_escalation(
        {
            "title": "Review of biomarker transferability across heterogeneous cancer cohorts",
            "summary": "This broad review discusses biomarker transferability across heterogeneous cancer cohorts without new data.",
            "tags": ["#Oncology", "#Review"],
        }
    )

    assert result["reason_codes"] == ["REVIEW_STYLE_LOW_CLARITY", "MODEL_REVIEW_REQUIRED"]


def test_evaluate_escalation_maps_unknown_model_reason_code_to_fallback_bucket() -> None:
    provider = _provider(
        response=(
            '{"approved": true, "new_confidence": 0.88, "reason": "Strong fit.", '
            '"reason_codes": ["very_strong_fit"], "final_route": "FAST_LANE_APPROVE"}'
        )
    )

    result = provider.evaluate_escalation(
        {
            "title": "Exploratory biomarker atlas for inflammatory bowel disease specimens",
            "summary": "This biomedical study organizes biomarker observations from inflammatory bowel disease specimens and discusses possible translational implications.",
            "tags": ["#Immunology", "#Biomarker"],
        }
    )

    assert result["reason_codes"] == ["MODEL_FAST_LANE_APPROVE"]


def test_evaluate_escalation_defaults_structured_fields_for_plain_model_response() -> None:
    provider = _provider(
        response='{"approved": false, "new_confidence": 0.2, "reason": "Interesting but uncertain from metadata alone."}'
    )

    result = provider.evaluate_escalation(
        {
            "title": "Exploratory macrophage state mapping in colorectal cancer samples",
            "summary": "This exploratory biomedical paper examines macrophage states in colorectal cancer samples and discusses potential translational implications.",
            "tags": ["#Oncology", "#Immunology"],
        }
    )

    assert result["approved"] is False
    assert result["in_biomedical_scope"] is True
    assert result["final_route"] == ESCALATION_ROUTE_REVIEW
    assert result["reason_codes"] == ["MODEL_REVIEW_REQUIRED"]
