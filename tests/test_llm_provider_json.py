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
