from __future__ import annotations

import json
from pathlib import Path

from scripts.eval.run_processor_gate_frontier_claude_crosscheck import (
    run_processor_gate_frontier_claude_crosscheck,
)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


class _FakeUsage:
    input_tokens = 321
    output_tokens = 123


class _FakeBlock:
    type = "text"
    text = (
        "- Row 1 verdict: policy_only_review\n"
        "- Row 2 verdict: policy_only_review\n"
        "- High-threshold change justified now? no\n"
        "- One-line overall conclusion: both frontier rows still look policy-only."
    )


class _FakeMessage:
    content = [_FakeBlock()]
    stop_reason = "end_turn"
    usage = _FakeUsage()


class _FakeMessagesAPI:
    def create(self, **kwargs):
        return _FakeMessage()


class _FakeAnthropicClient:
    def __init__(self) -> None:
        self.messages = _FakeMessagesAPI()


def test_run_processor_gate_frontier_claude_crosscheck_writes_sidecars(
    monkeypatch,
    tmp_path: Path,
) -> None:
    run_root = tmp_path / "processor_gate_threshold_review_run"
    _write_json(
        run_root / "summary.json",
        {
            "schema_version": "processor_gate_threshold_review.v1",
            "generated_at": "2026-04-22T00:00:00Z",
            "run_id": "processor_gate_threshold_review_run",
        },
    )
    (run_root / "manual_review_frontier_crosscheck_packet.md").write_text(
        "# packet\n\nplease review these rows independently.\n",
        encoding="utf-8",
    )
    (run_root / "audit.md").write_text("# old audit\n", encoding="utf-8")

    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr(
        "scripts.eval.run_processor_gate_frontier_claude_crosscheck._anthropic_client",
        lambda api_key: _FakeAnthropicClient(),
    )

    payload = run_processor_gate_frontier_claude_crosscheck(
        review_run=run_root,
        model="claude-3-7-sonnet-latest",
        max_tokens=800,
        temperature=0.0,
    )

    response_markdown_path = run_root / "manual_review_frontier_claude_crosscheck.md"
    response_json_path = run_root / "manual_review_frontier_claude_crosscheck.json"
    audit_markdown = (run_root / "audit.md").read_text(encoding="utf-8")
    response_markdown = response_markdown_path.read_text(encoding="utf-8")
    response_json = json.loads(response_json_path.read_text(encoding="utf-8"))

    assert payload["response_markdown_path"] == str(response_markdown_path)
    assert payload["response_json_path"] == str(response_json_path)
    assert response_markdown_path.exists()
    assert response_json_path.exists()
    assert "Row 1 verdict: policy_only_review" in response_markdown
    assert response_json["provider"] == "anthropic"
    assert response_json["model"] == "claude-3-7-sonnet-latest"
    assert response_json["usage"] == {"input_tokens": 321, "output_tokens": 123}
    assert response_json["stop_reason"] == "end_turn"
    assert "manual_review_frontier_claude_crosscheck.md" in audit_markdown
    assert "manual_review_frontier_claude_crosscheck.json" in audit_markdown
