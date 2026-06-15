from __future__ import annotations

from types import SimpleNamespace

from src.config import LLMConfig
from src.llm_provider import AnthropicProvider, OllamaProvider, OpenAIProvider, get_llm_provider


class _FakeOpenAICompletions:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content='{"approved": true, "reason": "ok"}'))]
        )


class _FakeOpenAIResponses:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(output_text='{"approved": true, "reason": "ok"}')


class _FakeOpenAIClient:
    def __init__(self) -> None:
        self.chat = SimpleNamespace(completions=_FakeOpenAICompletions())
        self.responses = _FakeOpenAIResponses()


class _FakeOllamaClient:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def chat(self, **kwargs):
        self.calls.append(kwargs)
        return {"message": {"content": '{"approved": true, "reason": "ok"}'}}


class _FakeAnthropicMessages:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(
            content=[SimpleNamespace(type="text", text='{"approved": true, "reason": "ok"}')],
        )


class _FakeAnthropicClient:
    def __init__(self) -> None:
        self.messages = _FakeAnthropicMessages()


class _TestOpenAIProvider(OpenAIProvider):
    def _initialize(self) -> None:
        self.client = _FakeOpenAIClient()


class _TestOllamaProvider(OllamaProvider):
    def _initialize(self) -> None:
        self.host = self.config.local.base_url
        self.models = self.config.local.models
        self.ollama_client = _FakeOllamaClient()
        self.client = True


class _TestAnthropicProvider(AnthropicProvider):
    def _initialize(self) -> None:
        self.client = _FakeAnthropicClient()


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


def _anthropic_config():
    return SimpleNamespace(
        cloud=SimpleNamespace(api_key="anthropic-test", model="claude-sonnet-4-20250514", provider="anthropic"),
        timeout_seconds=15,
        max_retries=0,
        features=None,
        default_model=None,
    )


def test_openai_provider_uses_zero_temperature_for_escalation() -> None:
    provider = _TestOpenAIProvider(_openai_config())

    provider._make_request("escalation", "prompt", is_json=True)

    assert provider.client.chat.completions.calls[-1]["temperature"] == 0.0


def test_openai_provider_uses_zero_temperature_for_slot_adjudication() -> None:
    provider = _TestOpenAIProvider(_openai_config())

    provider._make_request("slot_adjudication", "prompt", is_json=True)

    assert provider.client.chat.completions.calls[-1]["temperature"] == 0.0


def test_openai_provider_uses_zero_temperature_for_tagging_adjudication() -> None:
    provider = _TestOpenAIProvider(_openai_config())

    provider._make_request("tagging_adjudication", "prompt", is_json=True)

    assert provider.client.chat.completions.calls[-1]["temperature"] == 0.0


def test_openai_provider_keeps_default_temperature_for_non_gate_tasks() -> None:
    provider = _TestOpenAIProvider(_openai_config())

    provider._make_request("one_liner", "prompt")

    assert provider.client.chat.completions.calls[-1]["temperature"] == 0.3


def test_openai_provider_defaults_to_chat_completions_api() -> None:
    provider = _TestOpenAIProvider(_openai_config())

    provider._make_request("one_liner", "prompt")

    assert len(provider.client.chat.completions.calls) == 1
    assert provider.client.responses.calls == []
    assert provider.client.chat.completions.calls[-1]["messages"] == [{"role": "user", "content": "prompt"}]


def test_openai_provider_can_opt_into_responses_api_without_stored_state() -> None:
    config = _openai_config()
    config.cloud.openai_api = "responses"
    provider = _TestOpenAIProvider(config)

    result = provider._make_request("slot_adjudication", "prompt", is_json=True, system_prompt="system")

    assert result == '{"approved": true, "reason": "ok"}'
    assert provider.client.chat.completions.calls == []
    assert len(provider.client.responses.calls) == 1
    call = provider.client.responses.calls[-1]
    assert call["model"] == "gpt-4o"
    assert call["input"] == [{"role": "system", "content": "system"}, {"role": "user", "content": "prompt"}]
    assert call["temperature"] == 0.0
    assert call["timeout"] == 15
    assert call["store"] is False
    assert call["text"] == {"format": {"type": "json_object"}}


def test_openai_provider_reports_configured_api_mode() -> None:
    chat_provider = _TestOpenAIProvider(_openai_config())
    responses_config = _openai_config()
    responses_config.cloud.openai_api = "responses"
    responses_provider = _TestOpenAIProvider(responses_config)

    assert chat_provider.provider_api_mode() == "chat_completions"
    assert responses_provider.provider_api_mode() == "responses"


def test_openai_responses_schema_mode_uses_text_format_json_schema() -> None:
    config = _openai_config()
    config.cloud.openai_api = "responses"
    config.cloud.openai_json_mode = "json_schema"
    provider = _TestOpenAIProvider(config)
    schema = {
        "name": "slot_adjudication",
        "schema": {
            "type": "object",
            "properties": {"approved": {"type": "boolean"}, "reason": {"type": "string"}},
            "required": ["approved", "reason"],
            "additionalProperties": False,
        },
    }

    provider._make_request("slot_adjudication", "prompt", schema=schema)

    assert provider.client.responses.calls[-1]["text"] == {
        "format": {
            "type": "json_schema",
            "name": "slot_adjudication",
            "strict": True,
            "schema": schema["schema"],
        }
    }


def test_ollama_provider_uses_zero_temperature_for_escalation() -> None:
    provider = _TestOllamaProvider(_ollama_config())

    provider._make_request("escalation", "prompt", is_json=True)

    assert provider.ollama_client.calls[-1]["options"]["temperature"] == 0.0


def test_ollama_provider_uses_zero_temperature_for_slot_adjudication() -> None:
    provider = _TestOllamaProvider(_ollama_config())

    provider._make_request("slot_adjudication", "prompt", is_json=True)

    assert provider.ollama_client.calls[-1]["options"]["temperature"] == 0.0


def test_ollama_provider_uses_zero_temperature_for_tagging_adjudication() -> None:
    provider = _TestOllamaProvider(_ollama_config())

    provider._make_request("tagging_adjudication", "prompt", is_json=True)

    assert provider.ollama_client.calls[-1]["options"]["temperature"] == 0.0


def test_ollama_provider_keeps_default_temperature_for_non_gate_tasks() -> None:
    provider = _TestOllamaProvider(_ollama_config())

    provider._make_request("deep_read", "prompt")

    assert provider.ollama_client.calls[-1]["options"]["temperature"] == 0.3


def test_anthropic_provider_uses_zero_temperature_for_escalation() -> None:
    provider = _TestAnthropicProvider(_anthropic_config())

    provider._make_request("escalation", "prompt", is_json=True)

    assert provider.client.messages.calls[-1]["temperature"] == 0.0


def test_anthropic_provider_adds_json_instruction_for_json_tasks() -> None:
    provider = _TestAnthropicProvider(_anthropic_config())

    provider._make_request("slot_adjudication", "prompt", is_json=True)

    system_prompt = str(provider.client.messages.calls[-1]["system"])
    assert "valid JSON object" in system_prompt


def test_anthropic_provider_returns_no_embedding() -> None:
    provider = _TestAnthropicProvider(_anthropic_config())

    assert provider.get_embedding("test text") is None


def test_openai_provider_uses_extractor_feature_model_for_clinical_extraction_task() -> None:
    config = SimpleNamespace(
        cloud=SimpleNamespace(api_key="sk-test", model=None),
        timeout_seconds=15,
        max_retries=0,
        features=SimpleNamespace(
            clinical_extraction=SimpleNamespace(model="gpt-4.1-mini"),
            specialty_trial_extraction=SimpleNamespace(model="gpt-4.1"),
            trial_extraction=SimpleNamespace(model="gpt-4o-mini"),
            one_liner=None,
            slot_classification=None,
        ),
        default_model="fallback-model",
    )
    provider = _TestOpenAIProvider(config)

    assert provider._get_model("clinical_extraction") == "gpt-4.1-mini"


def test_openai_provider_feature_model_overrides_cloud_default_model() -> None:
    config = SimpleNamespace(
        cloud=SimpleNamespace(api_key="sk-test", model="gpt-5.4-mini"),
        timeout_seconds=15,
        max_retries=0,
        features=SimpleNamespace(
            clinical_extraction=SimpleNamespace(model="gpt-5.5"),
            specialty_trial_extraction=None,
            trial_extraction=None,
            one_liner=SimpleNamespace(model="gpt-5.4-nano"),
            slot_classification=None,
        ),
        default_model="fallback-model",
    )
    provider = _TestOpenAIProvider(config)

    assert provider._get_model("clinical_extraction") == "gpt-5.5"
    assert provider._get_model("one_liner") == "gpt-5.4-nano"
    assert provider._get_model("teacher_review") == "gpt-5.4-mini"


def test_llm_config_default_openai_model_tracks_current_low_cost_frontier_default() -> None:
    config = LLMConfig(
        features={
            "specialty_trial_extraction": {"enabled": False},
            "slot_classification": {"enabled": False},
            "one_liner": {"enabled": False},
        }
    )

    assert config.cloud.model == "gpt-5.4-mini"
    assert config.cloud.openai_api == "chat_completions"
    assert config.cloud.openai_json_mode == "json_object"


def test_openai_provider_falls_back_to_trial_extraction_model_for_clinical_extraction_task() -> None:
    config = SimpleNamespace(
        cloud=SimpleNamespace(api_key="sk-test", model=None),
        timeout_seconds=15,
        max_retries=0,
        features=SimpleNamespace(
            clinical_extraction=None,
            specialty_trial_extraction=None,
            trial_extraction=SimpleNamespace(model="gpt-4o-mini"),
            one_liner=None,
            slot_classification=None,
        ),
        default_model="fallback-model",
    )
    provider = _TestOpenAIProvider(config)

    assert provider._get_model("clinical_extraction") == "gpt-4o-mini"


def test_openai_provider_supports_missing_legacy_trial_extraction_when_clinical_feature_exists() -> None:
    config = SimpleNamespace(
        cloud=SimpleNamespace(api_key="sk-test", model=None),
        timeout_seconds=15,
        max_retries=0,
        features=SimpleNamespace(
            clinical_extraction=SimpleNamespace(model="gpt-4.1-mini"),
            specialty_trial_extraction=None,
            trial_extraction=None,
            one_liner=None,
            slot_classification=None,
        ),
        default_model="fallback-model",
    )
    provider = _TestOpenAIProvider(config)

    assert provider._get_model("clinical_extraction") == "gpt-4.1-mini"
    assert provider._get_model("specialty_trial_extraction") == "fallback-model"
    assert provider._get_model("trial_extraction") == "fallback-model"


def test_openai_provider_uses_explicit_specialty_feature_model_for_trial_extraction_task() -> None:
    config = SimpleNamespace(
        cloud=SimpleNamespace(api_key="sk-test", model=None),
        timeout_seconds=15,
        max_retries=0,
        features=SimpleNamespace(
            clinical_extraction=None,
            specialty_trial_extraction=SimpleNamespace(model="gpt-4.1"),
            trial_extraction=SimpleNamespace(model="gpt-4o-mini"),
            one_liner=None,
            slot_classification=None,
        ),
        default_model="fallback-model",
    )
    provider = _TestOpenAIProvider(config)

    assert provider._get_model("specialty_trial_extraction") == "gpt-4.1"
    assert provider._get_model("trial_extraction") == "gpt-4.1"


def test_openai_provider_keeps_generic_and_specialty_extraction_models_separate() -> None:
    config = SimpleNamespace(
        cloud=SimpleNamespace(api_key="sk-test", model=None),
        timeout_seconds=15,
        max_retries=0,
        features=SimpleNamespace(
            clinical_extraction=SimpleNamespace(model="gpt-4.1-mini"),
            specialty_trial_extraction=SimpleNamespace(model="gpt-4.1"),
            trial_extraction=SimpleNamespace(model="gpt-4o-mini"),
            one_liner=None,
            slot_classification=None,
        ),
        default_model="fallback-model",
    )
    provider = _TestOpenAIProvider(config)

    assert provider._get_model("clinical_extraction") == "gpt-4.1-mini"
    assert provider._get_model("specialty_trial_extraction") == "gpt-4.1"
    assert provider._get_model("trial_extraction") == "gpt-4.1"


def test_ollama_provider_routes_clinical_extraction_to_extractor_model() -> None:
    config = SimpleNamespace(
        local=SimpleNamespace(
            base_url="http://localhost:11434",
            models={"judge": "llama3:latest", "chat": "phi3", "extractor": "biomistral:latest"},
        ),
        timeout_seconds=15,
        max_retries=0,
        features=None,
        default_model=None,
    )
    provider = _TestOllamaProvider(config)

    assert provider._get_model("clinical_extraction") == "biomistral:latest"


def test_get_llm_provider_supports_anthropic_cloud_mode(monkeypatch) -> None:
    monkeypatch.setattr(AnthropicProvider, "_initialize", lambda self: setattr(self, "client", object()))

    config = LLMConfig(
        mode="cloud",
        cloud={
            "provider": "anthropic",
            "api_key": "anthropic-test",
            "model": "claude-sonnet-4-20250514",
        },
        features={
            "specialty_trial_extraction": {"enabled": False, "model": "claude-sonnet-4-20250514"},
            "slot_classification": {"enabled": False, "model": "claude-sonnet-4-20250514"},
            "one_liner": {"enabled": False, "model": "claude-sonnet-4-20250514"},
        },
    )

    provider = get_llm_provider(config)

    assert isinstance(provider, AnthropicProvider)


def test_anthropic_provider_feature_model_overrides_cloud_default_model() -> None:
    config = SimpleNamespace(
        cloud=SimpleNamespace(api_key="anthropic-test", model="claude-sonnet-4-20250514", provider="anthropic"),
        timeout_seconds=15,
        max_retries=0,
        features=SimpleNamespace(
            clinical_extraction=SimpleNamespace(model="claude-opus-4-1-20250805"),
            specialty_trial_extraction=None,
            trial_extraction=None,
            one_liner=None,
            slot_classification=None,
        ),
        default_model="fallback-model",
    )
    provider = _TestAnthropicProvider(config)

    assert provider._get_model("clinical_extraction") == "claude-opus-4-1-20250805"
    assert provider._get_model("teacher_review") == "claude-sonnet-4-20250514"


def test_hybrid_provider_uses_anthropic_for_cloud_path(monkeypatch) -> None:
    def _fake_ollama_init(self) -> None:
        self.host = "http://localhost:11434"
        self.models = {}
        self.ollama_client = None
        self.client = None

    def _fake_anthropic_init(self) -> None:
        self.client = object()

    monkeypatch.setattr(OllamaProvider, "_initialize", _fake_ollama_init)
    monkeypatch.setattr(AnthropicProvider, "_initialize", _fake_anthropic_init)

    config = LLMConfig(
        mode="hybrid",
        local={
            "provider": "ollama",
            "base_url": "http://localhost:11434",
            "models": {
                "classifier": "llama3:8b",
                "tagger": "biomistral:7b",
                "embedder": "nomic-embed-text",
                "judge": "llama3:latest",
                "chat": "phi3",
            },
        },
        cloud={
            "provider": "anthropic",
            "api_key": "anthropic-test",
            "model": "claude-sonnet-4-20250514",
        },
        features={
            "specialty_trial_extraction": {"enabled": False, "model": "claude-sonnet-4-20250514"},
            "slot_classification": {"enabled": False, "model": "claude-sonnet-4-20250514"},
            "one_liner": {"enabled": False, "model": "claude-sonnet-4-20250514"},
        },
    )

    provider = get_llm_provider(config)

    assert provider is not None
    assert isinstance(provider.cloud, AnthropicProvider)
