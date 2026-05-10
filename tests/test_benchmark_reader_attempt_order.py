from __future__ import annotations

from types import SimpleNamespace

from scripts import benchmark_reader_attempt_order as benchmark_mod
from src.contracts.document_artifact_v2 import ArtifactMetaV2, DocumentArtifactV2
from src.schemas.agent_artifacts import ClaimSet, ScientificClaim


class _FakeAdapter:
    def __init__(self) -> None:
        self.last_request_meta: dict[str, object] = {}

    def generate(self, prompt: str, format: str | None = None):
        if prompt == "WARM":
            self.last_request_meta = {
                "status": "ok",
                "request_wall_seconds": 0.321,
                "eval_count": 2,
            }
            return SimpleNamespace(text="OK")
        self.last_request_meta = {
            "status": "ok",
            "request_wall_seconds": 12.3456,
            "done_reason": "stop",
            "prompt_eval_count": 321,
            "eval_count": 111,
            "total_duration_seconds": 12.300001,
        }
        return SimpleNamespace(text='{"ok": true}')


class _FakeReader:
    def __init__(self) -> None:
        self.min_claims = 1
        self.adapter = _FakeAdapter()

    def _collect_sections(self, doc):
        return []

    def _collect_chunks(self, sections):
        return []

    def _build_table_context(self, doc):
        return ""

    def _build_attempt_contexts(self, sections):
        return ["[CHUNK p01_c01 | section=abstract | page=0]\nPrimary context text\n"]

    def _build_extraction_prompt(
        self,
        *,
        doc_id: str,
        title: str,
        authors: list[str],
        paper_context: str,
        table_context: str,
        example_json: str,
        min_claims: int,
        attempt_idx: int,
    ) -> str:
        return f"prompt-{attempt_idx}-{doc_id}"

    def _collect_context_composition_metrics(self, context: str):
        return {
            "included_chunk_count": 1,
            "unique_section_count": 1,
            "sentence_focus_count": 0,
        }

    def _estimate_token_count(self, text: str):
        return max(1, len(text) // 4)

    def _parse_claimset_payload(self, raw_text: str, *, expected_doc_id: str, chunks):
        return ClaimSet(
            doc_id=expected_doc_id,
            claims=[
                ScientificClaim(
                    claim_id="CLM-1",
                    type="efficacy",
                    statement="Supported statement.",
                    confidence=0.6,
                    evidence_spans=[],
                )
            ],
        )


def _doc() -> DocumentArtifactV2:
    return DocumentArtifactV2(
        document_id="doc:test",
        meta=ArtifactMetaV2(title="Test", authors=["Kim"], source_ref="file.pdf"),
        pages=[],
        tables=[],
    )


def test_run_policy_records_provider_metrics():
    reader = _FakeReader()

    result = benchmark_mod._run_policy(reader=reader, doc=_doc(), policy_name="current")

    assert result.selected_attempt_label == "primary"
    assert result.selected_claim_count == 1
    assert len(result.attempts) == 1
    attempt = result.attempts[0]
    assert attempt.provider_status == "ok"
    assert attempt.provider_request_wall_seconds == 12.346
    assert attempt.provider_done_reason == "stop"
    assert attempt.provider_prompt_eval_count == 321
    assert attempt.provider_eval_count == 111
    assert attempt.provider_total_duration_seconds == 12.300001
    assert attempt.provider_error_type is None


def test_run_policy_records_warmup_metrics():
    reader = _FakeReader()

    result = benchmark_mod._run_policy(reader=reader, doc=_doc(), policy_name="current", warmup_prompt="WARM")

    assert result.warmup_prompt == "WARM"
    assert result.warmup_status == "ok"
    assert result.warmup_request_wall_seconds == 0.321
    assert result.warmup_eval_count == 2
    assert result.warmup_error_type is None


def test_format_markdown_omits_provider_columns_by_default():
    result = benchmark_mod.PolicyResult(
        name="current",
        attempts=[
            benchmark_mod.AttemptResult(
                label="primary",
                elapsed_seconds=10.0,
                context_chars=100,
                estimated_prompt_tokens=20,
                estimated_response_tokens=5,
                included_chunk_count=1,
                unique_section_count=1,
                sentence_focus_count=0,
                parsed_claim_count=1,
                status="parsed",
                provider_status="ok",
                provider_request_wall_seconds=9.9,
                provider_done_reason="stop",
                provider_prompt_eval_count=100,
                provider_eval_count=50,
                provider_total_duration_seconds=9.8,
                provider_error_type=None,
            )
        ],
        selected_attempt_label="primary",
        selected_claim_count=1,
        total_elapsed_seconds=10.0,
        total_prompt_tokens=20,
        total_response_tokens=5,
    )

    output = benchmark_mod._format_markdown(
        run_id="run_1",
        run_root=benchmark_mod.ARTIFACTS_ROOT,
        model_name="fake-model",
        results=[result],
    )

    assert "Provider req sec" not in output
    assert "include_provider_metrics: `False`" in output


def test_format_markdown_includes_provider_columns_when_requested():
    result = benchmark_mod.PolicyResult(
        name="current",
        attempts=[
            benchmark_mod.AttemptResult(
                label="primary",
                elapsed_seconds=10.0,
                context_chars=100,
                estimated_prompt_tokens=20,
                estimated_response_tokens=5,
                included_chunk_count=1,
                unique_section_count=1,
                sentence_focus_count=0,
                parsed_claim_count=1,
                status="parsed",
                provider_status="ok",
                provider_request_wall_seconds=9.9,
                provider_done_reason="stop",
                provider_prompt_eval_count=100,
                provider_eval_count=50,
                provider_total_duration_seconds=9.8,
                provider_error_type=None,
            )
        ],
        selected_attempt_label="primary",
        selected_claim_count=1,
        total_elapsed_seconds=10.0,
        total_prompt_tokens=20,
        total_response_tokens=5,
        warmup_prompt="WARM",
        warmup_elapsed_seconds=0.4,
        warmup_status="ok",
        warmup_request_wall_seconds=0.321,
        warmup_eval_count=2,
        warmup_error_type=None,
    )

    output = benchmark_mod._format_markdown(
        run_id="run_1",
        run_root=benchmark_mod.ARTIFACTS_ROOT,
        model_name="fake-model",
        results=[result],
        include_provider_metrics=True,
        warmup_prompt="WARM",
    )

    assert "Provider req sec" in output
    assert "`ok` | `9.9` | `50` | `stop`" in output
    assert "include_provider_metrics: `True`" in output
    assert "warmup_prompt: `WARM`" in output
    assert "warmup: prompt=`WARM` status=`ok`" in output


def test_format_markdown_includes_repeat_summary_when_requested():
    repeat_one = benchmark_mod.PolicyResult(
        name="current",
        repeat_index=1,
        attempts=[
            benchmark_mod.AttemptResult(
                label="primary",
                elapsed_seconds=10.0,
                context_chars=100,
                estimated_prompt_tokens=20,
                estimated_response_tokens=5,
                included_chunk_count=1,
                unique_section_count=1,
                sentence_focus_count=0,
                parsed_claim_count=1,
                status="parsed",
                provider_status="ok",
                provider_request_wall_seconds=9.9,
                provider_done_reason="stop",
                provider_prompt_eval_count=100,
                provider_eval_count=50,
                provider_total_duration_seconds=9.8,
                provider_error_type=None,
            )
        ],
        selected_attempt_label="primary",
        selected_claim_count=1,
        total_elapsed_seconds=10.0,
        total_prompt_tokens=20,
        total_response_tokens=5,
    )
    repeat_two = benchmark_mod.PolicyResult(
        name="current",
        repeat_index=2,
        attempts=[
            benchmark_mod.AttemptResult(
                label="focused",
                elapsed_seconds=20.0,
                context_chars=120,
                estimated_prompt_tokens=25,
                estimated_response_tokens=8,
                included_chunk_count=2,
                unique_section_count=2,
                sentence_focus_count=0,
                parsed_claim_count=2,
                status="parsed",
                provider_status="ok",
                provider_request_wall_seconds=19.9,
                provider_done_reason="stop",
                provider_prompt_eval_count=110,
                provider_eval_count=60,
                provider_total_duration_seconds=19.8,
                provider_error_type=None,
            )
        ],
        selected_attempt_label="focused",
        selected_claim_count=2,
        total_elapsed_seconds=20.0,
        total_prompt_tokens=25,
        total_response_tokens=8,
    )

    output = benchmark_mod._format_markdown(
        run_id="run_1",
        run_root=benchmark_mod.ARTIFACTS_ROOT,
        model_name="fake-model",
        results=[repeat_one, repeat_two],
        repeats=2,
    )

    assert "repeats: `2`" in output
    assert "| Policy | Runs | Selected attempts | Avg elapsed sec | Min elapsed sec | Max elapsed sec | Avg claims |" in output
    assert "`current` | `2` | `primary, focused` | `15.0` | `10.0` | `20.0` | `1.5`" in output
    assert "## current (repeat 1)" in output
    assert "## current (repeat 2)" in output
