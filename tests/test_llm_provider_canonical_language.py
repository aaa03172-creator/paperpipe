from __future__ import annotations

from types import SimpleNamespace

from src.llm_provider import LLMProvider


class _CapturingProvider(LLMProvider):
    def _initialize(self) -> None:
        self.client = True
        self.last_request: dict[str, object] | None = None

    def _make_request(self, task: str, prompt: str, is_json: bool = False, schema=None, system_prompt=None):
        self.last_request = {
            "task": task,
            "prompt": prompt,
            "is_json": is_json,
            "schema": schema,
            "system_prompt": system_prompt,
        }
        return "ok"

    def get_embedding(self, text: str):
        return None


def _provider() -> _CapturingProvider:
    return _CapturingProvider(SimpleNamespace(features=None, default_model=None))


def test_generate_one_liner_defaults_to_english_canonical_prompt() -> None:
    provider = _provider()

    provider.generate_one_liner({"title": "Test Paper", "summary": "Test summary."})

    assert provider.last_request is not None
    assert provider.last_request["task"] == "one_liner"
    prompt = str(provider.last_request["prompt"])
    assert "ONE SINGLE English sentence" in prompt
    assert "Korean sentence" not in prompt


def test_review_claimset_bundle_uses_teacher_review_task() -> None:
    provider = _provider()

    provider.review_claimset_bundle(prompt="{}", system_prompt="system")

    assert provider.last_request is not None
    assert provider.last_request["task"] == "teacher_review"
    assert provider.last_request["is_json"] is True
    assert provider.last_request["system_prompt"] == "system"


def test_generate_deep_read_defaults_to_english_canonical_prompt() -> None:
    provider = _provider()

    provider.generate_deep_read({"title": "Test Paper", "summary": "Test summary.", "slot": "mechanism"})

    assert provider.last_request is not None
    assert provider.last_request["task"] == "deep_read"
    prompt = str(provider.last_request["prompt"])
    assert "structured report in English" in prompt
    assert "structured report in Korean" not in prompt
