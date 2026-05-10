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


def test_extract_json_unwraps_nested_tagging_payload() -> None:
    provider = _DummyProvider(SimpleNamespace(features=None, default_model=None))

    payload = provider._extract_json(
        """
        {
          "response": {
            "content": {
              "hard_tags": ["#MCI", "#Trial"],
              "soft_tags": ["clinical"],
              "evidence_span": "Participants had MCI."
            }
          }
        }
        """
    )

    assert payload == {
        "hard_tags": ["#MCI", "#Trial"],
        "soft_tags": ["clinical"],
        "evidence_span": "Participants had MCI.",
    }


def test_augment_tagging_hard_tags_preserves_existing_llm_values() -> None:
    provider = _DummyProvider(SimpleNamespace(features=None, default_model=None))

    payload = {
        "hard_tags": {
            "species": "rat",
            "sample_size": 12,
            "model": "custom_model",
            "design": "observational",
            "study_type": "Clinical Trial",
        },
        "soft_tags": ["#Test"],
        "evidence_span": "Existing evidence",
        "confidence": 0.8,
    }

    augmented = provider._augment_tagging_hard_tags(
        payload,
        {
            "title": "5xFAD mouse study",
            "summary": "We analyzed 48 mice in this experiment.",
        },
    )

    assert augmented["hard_tags"] == {
        "species": "rat",
        "sample_size": 12,
        "model": "custom_model",
        "design": "observational",
        "study_type": "Clinical Trial",
    }
