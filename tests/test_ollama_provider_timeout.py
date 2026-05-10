from __future__ import annotations

from types import SimpleNamespace

from src.llm_provider import OllamaProvider


def test_ollama_provider_passes_timeout_to_client(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class DummyClient:
        def __init__(self, host=None, **kwargs):
            captured["host"] = host
            captured["kwargs"] = kwargs

        def list(self):
            return {"models": []}

    monkeypatch.setattr("src.llm_provider.ollama.Client", DummyClient)

    config = SimpleNamespace(
        local=SimpleNamespace(base_url="http://localhost:11434", models={}),
        timeout_seconds=120,
    )

    provider = OllamaProvider(config)

    assert provider.is_available() is True
    assert captured["host"] == "http://localhost:11434"
    assert captured["kwargs"] == {"timeout": 120}
