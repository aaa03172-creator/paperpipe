from __future__ import annotations

from types import SimpleNamespace

from src.llm_provider import LLMProvider


class _DummyProvider(LLMProvider):
    def _initialize(self) -> None:
        self.client = True

    def _make_request(self, *args, **kwargs):
        raise NotImplementedError

    def get_embedding(self, text: str):
        return None


def _provider() -> _DummyProvider:
    return _DummyProvider(SimpleNamespace(features=None, default_model=None))


def test_escalation_fast_reject_flags_clear_off_scope_case() -> None:
    provider = _provider()

    reason = provider._escalation_fast_reject_reason(
        {
            "title": "Poly(Lactic Acid): Recent Stereochemical Advances and New Materials Engineering",
            "summary": "A materials engineering paper about biodegradable polymers.",
            "tags": ["#MaterialsScience/Polymers"],
        }
    )

    assert reason is not None
    assert "pending review" in reason.lower()


def test_escalation_fast_reject_allows_neuroscience_focus_case() -> None:
    provider = _provider()

    reason = provider._escalation_fast_reject_reason(
        {
            "title": "Microglial neuroinflammation drives amyloid-linked cognitive decline in Alzheimer's disease",
            "summary": "Mechanistic Alzheimer study on microglia, amyloid pathology, and cognition.",
            "tags": ["#Alzheimers_Disease", "#Microglia"],
        }
    )

    assert reason is None


def test_escalation_fast_reject_allows_methods_lane_case() -> None:
    provider = _provider()

    reason = provider._escalation_fast_reject_reason(
        {
            "title": "Optimizing tamoxifen induction and recombination efficiency in inducible Cre-loxP mouse models",
            "summary": "Actionable protocol guidance for neuroscience experiments.",
            "tags": ["#methods", "#Cre-loxP", "#tamoxifen"],
        }
    )

    assert reason is None


def test_escalation_fast_approve_flags_methods_lane_case() -> None:
    provider = _provider()

    reason = provider._escalation_fast_approve_reason(
        {
            "title": "Optimizing tamoxifen induction and recombination efficiency in inducible Cre-loxP mouse models",
            "summary": "Actionable protocol guidance for neuroscience experiments.",
            "tags": ["#methods", "#Cre-loxP", "#tamoxifen"],
        }
    )

    assert reason is not None
    assert "auto-approve" in reason.lower()


def test_escalation_fast_approve_flags_neurology_guidance_case() -> None:
    provider = _provider()

    reason = provider._escalation_fast_approve_reason(
        {
            "title": "Clinical practice guideline for blood biomarkers in Alzheimer's disease",
            "summary": "Consensus guidance for biomarkers, diagnosis, and neurology practice.",
            "tags": ["#ClinicalGuideline", "#Alzheimers_Disease"],
        }
    )

    assert reason is not None
    assert "guidance" in reason.lower() or "authoritative" in reason.lower()


def test_escalation_fast_approve_keeps_review_style_microbiome_case_pending() -> None:
    provider = _provider()

    reason = provider._escalation_fast_approve_reason(
        {
            "title": "The Microbiota–Gut–Brain Axis and Alzheimer’s Disease: Neuroinflammation Is to Blame?",
            "summary": "This review highlights disturbances in the microbiota-gut-brain axis in Alzheimer's disease.",
            "tags": ["#Alzheimers_Disease", "#Gut_Microbiome", "#Review"],
        }
    )

    assert reason is None


def test_escalation_fast_approve_skips_negative_scope_language() -> None:
    provider = _provider()

    reason = provider._escalation_fast_approve_reason(
        {
            "title": "Ketogenic diet improves endurance performance in collegiate cyclists",
            "summary": "The study did not involve neurological disease, cognition, or neuroscience methods.",
            "tags": ["#sports_nutrition", "#healthy_adults"],
        }
    )

    assert reason is None


def test_escalation_prompt_states_conservative_policy() -> None:
    provider = _provider()

    prompt = provider._build_escalation_prompt(
        {
            "title": "Clinical practice guideline for blood biomarkers in Alzheimer's disease",
            "summary": "Guidance for diagnosis.",
            "tags": ["#ClinicalDiagnosis"],
        }
    )

    lowered = prompt.lower()
    assert "default answer is no" in lowered
    assert "if there is any uncertainty" in lowered
    assert "broad review" in lowered
    assert "authoritative recommendation" in lowered
    assert "biomedical workspace scope" in lowered
    assert "biomedical practice" in lowered
    assert "current paperpipe lane" not in lowered
    assert "alzheimer or neurology practice" not in lowered
