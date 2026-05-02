from types import SimpleNamespace

from src.agents import reader_agent as reader_mod
from src.contracts.document_artifact_v2 import ArtifactMetaV2, DocumentArtifactV2
from src.schemas.agent_artifacts import ClaimSet, ScientificClaim


def test_reader_agent_records_attempt_metrics(monkeypatch):
    class FakeAdapter:
        def __init__(self, model_name: str = "fake-model"):
            self._responses = [
                SimpleNamespace(text="{bad json"),
                SimpleNamespace(text='{"ok": true}'),
            ]
            self.last_request_meta = {}

        def generate(self, prompt: str, format: str | None = None):
            response = self._responses.pop(0)
            self.last_request_meta = {
                "status": "ok",
                "provider": "ollama",
                "model": "fake-model",
                "timeout_seconds": 15,
                "request_wall_seconds": 1.25,
                "done_reason": "stop",
                "prompt_eval_count": 123,
                "eval_count": 45,
                "total_duration_seconds": 1.11,
            }
            return response

        def count_tokens(self, text: str):
            return SimpleNamespace(total_tokens=max(1, len(text) // 4))

    monkeypatch.setattr(reader_mod, "OllamaModelAdapter", FakeAdapter)
    monkeypatch.setattr(
        reader_mod.ReaderAgent,
        "_collect_sections",
        lambda self, doc: [],
    )
    monkeypatch.setattr(
        reader_mod.ReaderAgent,
        "_collect_chunks",
        lambda self, sections: [],
    )
    monkeypatch.setattr(
        reader_mod.ReaderAgent,
        "_build_table_context",
        lambda self, doc: "",
    )
    monkeypatch.setattr(
        reader_mod.ReaderAgent,
        "_build_attempt_contexts",
        lambda self, sections: [
            "[CHUNK p01_c01 | section=abstract | page=0]\nPrimary context text\n",
            "[CHUNK p02_c01 | section=results | page=1]\nFocused context text\n...[truncated]",
        ],
    )

    def fake_parse(self, raw_text: str, *, expected_doc_id: str, chunks):
        if "ok" not in raw_text:
            return None
        return ClaimSet(
            doc_id=expected_doc_id,
            claims=[
                ScientificClaim(
                    claim_id="CLM-1",
                    type="efficacy",
                    statement="Supported statement.",
                    confidence=0.5,
                    evidence_spans=[],
                )
            ],
        )

    monkeypatch.setattr(reader_mod.ReaderAgent, "_parse_claimset_payload", fake_parse)

    reader = reader_mod.ReaderAgent(model_name="fake-model")
    doc = DocumentArtifactV2(
        document_id="doc:test",
        meta=ArtifactMetaV2(title="Test", authors=["Kim"], source_ref="file.pdf"),
        pages=[],
        tables=[],
    )

    result = reader.analyze(doc)

    assert result is not None
    assert len(result.claims) == 1
    metrics = reader.last_analysis_metrics
    assert metrics["return_mode"] == "success"
    assert metrics["configured_attempt_order"] == "current"
    assert metrics["effective_attempt_order"] == ["primary", "focused"]
    assert metrics["attempt_count"] == 2
    assert metrics["selected_attempt"] == 2
    assert metrics["selected_attempt_label"] == "focused"
    assert metrics["final_claim_count"] == 1
    assert metrics["analysis_wall_seconds"] >= 0
    assert metrics["attempts"][0]["status"] == "parse_failed"
    assert metrics["attempts"][1]["status"] == "parsed"
    assert metrics["attempts"][1]["estimated_prompt_tokens"] > 0
    assert metrics["attempts"][1]["estimated_response_tokens"] > 0
    assert metrics["attempts"][0]["generate_wall_seconds"] >= 0
    assert metrics["attempts"][0]["parse_wall_seconds"] >= 0
    assert metrics["attempts"][0]["attempt_wall_seconds"] >= 0
    assert metrics["attempts"][1]["generate_wall_seconds"] >= 0
    assert metrics["attempts"][1]["parse_wall_seconds"] >= 0
    assert metrics["attempts"][1]["attempt_wall_seconds"] >= 0
    assert metrics["attempts"][1]["context_mode"] == "chunk_context"
    assert metrics["attempts"][1]["included_chunk_count"] == 1
    assert metrics["attempts"][1]["unique_section_count"] == 1
    assert metrics["attempts"][1]["truncated_chunk_count"] == 1
    assert metrics["attempts"][1]["provider_status"] == "ok"
    assert metrics["attempts"][1]["provider_request_wall_seconds"] == 1.25
    assert metrics["attempts"][1]["provider_done_reason"] == "stop"
    assert metrics["attempts"][1]["provider_prompt_eval_count"] == 123
    assert metrics["attempts"][1]["provider_eval_count"] == 45
    assert metrics["attempts"][1]["provider_total_duration_seconds"] == 1.11


def test_reader_agent_supports_focused_first_attempt_order(monkeypatch):
    class FakeAdapter:
        def __init__(self, model_name: str = "fake-model"):
            self._responses = [SimpleNamespace(text='{"ok": true}')]
            self.last_request_meta = {}

        def generate(self, prompt: str, format: str | None = None):
            self.last_request_meta = {
                "status": "ok",
                "provider": "ollama",
                "model": "fake-model",
                "request_wall_seconds": 0.75,
                "done_reason": "stop",
            }
            return self._responses.pop(0)

        def count_tokens(self, text: str):
            return SimpleNamespace(total_tokens=max(1, len(text) // 4))

    monkeypatch.setattr(reader_mod, "OllamaModelAdapter", FakeAdapter)
    monkeypatch.setattr(
        reader_mod.ReaderAgent,
        "_collect_sections",
        lambda self, doc: [],
    )
    monkeypatch.setattr(
        reader_mod.ReaderAgent,
        "_collect_chunks",
        lambda self, sections: [],
    )
    monkeypatch.setattr(
        reader_mod.ReaderAgent,
        "_build_table_context",
        lambda self, doc: "",
    )
    monkeypatch.setattr(
        reader_mod.ReaderAgent,
        "_build_attempt_contexts",
        lambda self, sections: [
            "[CHUNK p01_c01 | section=abstract | page=0]\nPrimary context text\n",
            "[CHUNK p02_c01 | section=results | page=1]\nFocused context text\n",
        ],
    )

    def fake_parse(self, raw_text: str, *, expected_doc_id: str, chunks):
        return ClaimSet(
            doc_id=expected_doc_id,
            claims=[
                ScientificClaim(
                    claim_id="CLM-1",
                    type="efficacy",
                    statement="Focused-first statement.",
                    confidence=0.7,
                    evidence_spans=[],
                )
            ],
        )

    monkeypatch.setattr(reader_mod.ReaderAgent, "_parse_claimset_payload", fake_parse)

    reader = reader_mod.ReaderAgent(model_name="fake-model", attempt_order="focused_first")
    doc = DocumentArtifactV2(
        document_id="doc:test",
        meta=ArtifactMetaV2(title="Test", authors=["Kim"], source_ref="file.pdf"),
        pages=[],
        tables=[],
    )

    result = reader.analyze(doc)

    assert result is not None
    assert len(result.claims) == 1
    metrics = reader.last_analysis_metrics
    assert metrics["configured_attempt_order"] == "focused_first"
    assert metrics["effective_attempt_order"] == ["focused", "primary"]
    assert metrics["attempt_count"] == 1
    assert metrics["selected_attempt"] == 1
    assert metrics["selected_attempt_label"] == "focused"
    assert metrics["attempts"][0]["label"] == "focused"
    assert metrics["attempts"][0]["generate_wall_seconds"] >= 0
    assert metrics["attempts"][0]["parse_wall_seconds"] >= 0
    assert metrics["attempts"][0]["attempt_wall_seconds"] >= 0
    assert metrics["attempts"][0]["provider_request_wall_seconds"] == 0.75
    assert metrics["attempts"][0]["provider_done_reason"] == "stop"


def test_reader_agent_focused_context_includes_methods_sections(monkeypatch):
    class FakeAdapter:
        def __init__(self, model_name: str = "fake-model"):
            self._responses = [SimpleNamespace(text='{"ok": true}')]
            self.last_request_meta = {}

        def generate(self, prompt: str, format: str | None = None):
            self.last_request_meta = {
                "status": "ok",
                "provider": "ollama",
                "model": "fake-model",
                "request_wall_seconds": 0.55,
                "done_reason": "stop",
            }
            return self._responses.pop(0)

        def count_tokens(self, text: str):
            return SimpleNamespace(total_tokens=max(1, len(text) // 4))

    monkeypatch.setattr(reader_mod, "OllamaModelAdapter", FakeAdapter)
    monkeypatch.setattr(
        reader_mod.ReaderAgent,
        "_collect_sections",
        lambda self, doc: [
            reader_mod._SectionRecord(
                name="Methods",
                text="Participants were randomized 1:1 to intervention or placebo.",
                page=0,
            ),
            reader_mod._SectionRecord(
                name="Results",
                text="Compared with placebo, intervention improved the primary endpoint by 18%.",
                page=1,
            ),
        ],
    )
    monkeypatch.setattr(
        reader_mod.ReaderAgent,
        "_build_table_context",
        lambda self, doc: "",
    )

    def fake_parse(self, raw_text: str, *, expected_doc_id: str, chunks):
        return ClaimSet(
            doc_id=expected_doc_id,
            claims=[
                ScientificClaim(
                    claim_id="CLM-1",
                    type="efficacy",
                    statement="Intervention improved the primary endpoint.",
                    confidence=0.7,
                    evidence_spans=[],
                )
            ],
        )

    monkeypatch.setattr(reader_mod.ReaderAgent, "_parse_claimset_payload", fake_parse)

    reader = reader_mod.ReaderAgent(model_name="fake-model", attempt_order="focused_first")
    doc = DocumentArtifactV2(
        document_id="doc:test",
        meta=ArtifactMetaV2(title="Test", authors=["Kim"], source_ref="file.pdf"),
        pages=[],
        tables=[],
    )

    result = reader.analyze(doc)

    assert result is not None
    assert len(result.claims) == 1
    metrics = reader.last_analysis_metrics
    assert metrics["priority_section_count"] == 2
    assert metrics["selected_attempt_label"] == "focused"
    assert metrics["attempts"][0]["included_chunk_count"] == 2
    assert metrics["attempts"][0]["unique_section_count"] == 2


def test_reader_agent_records_timeout_attempt_wall_time(monkeypatch):
    class ReadTimeout(Exception):
        pass

    class FakeAdapter:
        def __init__(self, model_name: str = "fake-model"):
            self.last_request_meta = {}

        def generate(self, prompt: str, format: str | None = None):
            self.last_request_meta = {
                "status": "timeout",
                "provider": "ollama",
                "model": "fake-model",
                "timeout_seconds": 120,
                "request_wall_seconds": 120.0,
                "error_type": "ReadTimeout",
            }
            raise ReadTimeout("timed out")

        def count_tokens(self, text: str):
            return SimpleNamespace(total_tokens=max(1, len(text) // 4))

    monkeypatch.setattr(reader_mod, "OllamaModelAdapter", FakeAdapter)
    monkeypatch.setattr(
        reader_mod.ReaderAgent,
        "_collect_sections",
        lambda self, doc: [],
    )
    monkeypatch.setattr(
        reader_mod.ReaderAgent,
        "_collect_chunks",
        lambda self, sections: [],
    )
    monkeypatch.setattr(
        reader_mod.ReaderAgent,
        "_build_table_context",
        lambda self, doc: "",
    )
    monkeypatch.setattr(
        reader_mod.ReaderAgent,
        "_build_attempt_contexts",
        lambda self, sections: [
            "[CHUNK p01_c01 | section=abstract | page=0]\nPrimary context text\n",
        ],
    )

    reader = reader_mod.ReaderAgent(model_name="fake-model")
    doc = DocumentArtifactV2(
        document_id="doc:test",
        meta=ArtifactMetaV2(title="Test", authors=["Kim"], source_ref="file.pdf"),
        pages=[],
        tables=[],
    )

    try:
        reader.analyze(doc)
        raise AssertionError("expected timeout")
    except ReadTimeout:
        pass

    metrics = reader.last_analysis_metrics
    assert metrics["attempt_count"] == 1
    assert metrics["analysis_wall_seconds"] >= 0
    assert metrics["attempts"][0]["status"] == "timeout"
    assert metrics["attempts"][0]["error_type"] == "ReadTimeout"
    assert metrics["attempts"][0]["generate_wall_seconds"] >= 0
    assert metrics["attempts"][0]["attempt_wall_seconds"] >= 0
    assert metrics["attempts"][0]["parse_wall_seconds"] is None
    assert metrics["attempts"][0]["provider_status"] == "timeout"
    assert metrics["attempts"][0]["provider_request_wall_seconds"] == 120.0
    assert metrics["attempts"][0]["provider_timeout_seconds"] == 120
    assert metrics["attempts"][0]["provider_error_type"] == "ReadTimeout"
