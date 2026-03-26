from __future__ import annotations

from types import SimpleNamespace

from src.llm_provider import OllamaProvider, OpenAIProvider


class _FakeOpenAICompletions:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content='{"approved": true, "reason": "ok"}'))]
        )


class _FakeOpenAIClient:
    def __init__(self) -> None:
        self.chat = SimpleNamespace(completions=_FakeOpenAICompletions())


class _FakeOllamaClient:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def chat(self, **kwargs):
        self.calls.append(kwargs)
        return {"message": {"content": '{"approved": true, "reason": "ok"}'}}


class _TestOpenAIProvider(OpenAIProvider):
    def _initialize(self) -> None:
        self.client = _FakeOpenAIClient()


class _TestOllamaProvider(OllamaProvider):
    def _initialize(self) -> None:
        self.host = self.config.local.base_url
        self.models = self.config.local.models
        self.ollama_client = _FakeOllamaClient()
        self.client = True


def _openai_config():
    return SimpleNamespace(
        cloud=SimpleNamespace(api_key="sk-test", model="gpt-4o"),
        timeout_seconds=15,
        max_retries=0,
        features=None,
        default_model=None,
    )


def _ollama_config():
    return SimpleNamespace(
        local=SimpleNamespace(base_url="http://localhost:11434", models={"judge": "llama3:latest", "chat": "phi3"}),
        timeout_seconds=15,
        max_retries=0,
        features=None,
        default_model=None,
    )


def test_openai_provider_uses_zero_temperature_for_escalation() -> None:
    provider = _TestOpenAIProvider(_openai_config())

    provider._make_request("escalation", "prompt", is_json=True)

    assert provider.client.chat.completions.calls[-1]["temperature"] == 0.0


def test_openai_provider_keeps_default_temperature_for_non_gate_tasks() -> None:
    provider = _TestOpenAIProvider(_openai_config())

    provider._make_request("one_liner", "prompt")

    assert provider.client.chat.completions.calls[-1]["temperature"] == 0.3


def test_ollama_provider_uses_zero_temperature_for_escalation() -> None:
    provider = _TestOllamaProvider(_ollama_config())

    provider._make_request("escalation", "prompt", is_json=True)

    assert provider.ollama_client.calls[-1]["options"]["temperature"] == 0.0


def test_ollama_provider_keeps_default_temperature_for_non_gate_tasks() -> None:
    provider = _TestOllamaProvider(_ollama_config())

    provider._make_request("deep_read", "prompt")

    assert provider.ollama_client.calls[-1]["options"]["temperature"] == 0.3
