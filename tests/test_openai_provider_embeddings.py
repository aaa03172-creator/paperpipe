from __future__ import annotations

from types import SimpleNamespace

from src.config import LLMConfig
from src.llm_provider import OpenAIProvider


class _FakeEmbeddingsAPI:
    def __init__(self) -> None:
        self.last_model: str | None = None

    def create(self, *, input: str, model: str):
        self.last_model = model
        return SimpleNamespace(data=[SimpleNamespace(embedding=[0.1, 0.2, 0.3])])


class _FakeClient:
    def __init__(self) -> None:
        self.embeddings = _FakeEmbeddingsAPI()


class _TestOpenAIProvider(OpenAIProvider):
    def _initialize(self) -> None:
        self.client = _FakeClient()


def _build_config() -> LLMConfig:
    return LLMConfig(
        mode="cloud",
        cloud={
            "provider": "openai",
            "api_key": "sk-test",
            "model": "gpt-4o",
        },
        features={
            "trial_extraction": {"enabled": False, "model": "gpt-4o-mini"},
            "slot_classification": {"enabled": False, "model": "gpt-4o-mini"},
            "one_liner": {"enabled": False, "model": "gpt-4o-mini"},
        },
    )


def test_openai_provider_embedding_falls_back_to_default_model() -> None:
    provider = _TestOpenAIProvider(_build_config())

    embedding = provider.get_embedding("test text")

    assert embedding == [0.1, 0.2, 0.3]
    assert provider.client.embeddings.last_model == "text-embedding-3-small"
