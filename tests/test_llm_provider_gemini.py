from src import llm_provider as llm_provider_mod
from src.config import CloudLLMConfig, FeatureConfig, LLMConfig, LLMFeatures, LocalLLMConfig


def _features() -> LLMFeatures:
    return LLMFeatures(
        slot_classification=FeatureConfig(enabled=False),
        one_liner=FeatureConfig(enabled=False),
    )


def test_gemini_cloud_provider_uses_openai_compatible_endpoint(monkeypatch):
    captured: dict[str, object] = {}

    class FakeOpenAI:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr(llm_provider_mod, "OpenAI", FakeOpenAI)
    config = LLMConfig(
        mode="cloud",
        local=LocalLLMConfig(),
        cloud=CloudLLMConfig(
            provider="gemini",
            api_key="gemini-test-secret",
            model="gemini-2.5-flash",
        ),
        features=_features(),
    )

    provider = llm_provider_mod.get_llm_provider(config)

    assert isinstance(provider, llm_provider_mod.GeminiProvider)
    assert captured == {
        "api_key": "gemini-test-secret",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
    }
    assert provider._get_model("tagging") == "gemini-2.5-flash"


def test_gemini_cloud_provider_uses_gemini_env_key(monkeypatch):
    captured: dict[str, object] = {}

    class FakeOpenAI:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr(llm_provider_mod, "OpenAI", FakeOpenAI)
    monkeypatch.setenv("GEMINI_API_KEY", "gemini-env-secret")
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    config = LLMConfig(
        mode="cloud",
        local=LocalLLMConfig(),
        cloud=CloudLLMConfig(
            provider="gemini",
            api_key=None,
            model="gemini-2.5-flash",
        ),
        features=_features(),
    )

    provider = llm_provider_mod.get_llm_provider(config)

    assert isinstance(provider, llm_provider_mod.GeminiProvider)
    assert captured["api_key"] == "gemini-env-secret"
