import asyncio
import json
from types import SimpleNamespace
from pathlib import Path

import backend.services.job_runner as job_runner
from src.contracts.document_artifact_v2 import (
    ArtifactMetaV2,
    BlockV2,
    DocumentArtifactV2,
    LineV2,
    PageV2,
    SpanV2,
)
from src.schemas.agent_artifacts import ClaimSet, IndexArtifact, ScientificClaim


def test_resolve_persona_hint_returns_none_for_default(monkeypatch):
    monkeypatch.setattr(job_runner, "load_profiles", lambda: SimpleNamespace(profiles=[]))
    assert job_runner._resolve_persona_hint("default") is None


def test_resolve_persona_hint_reads_enabled_profile(monkeypatch):
    profile = SimpleNamespace(
        id="coglab",
        title="Cognitive Lab",
        enabled=True,
        notes="prioritize confounds",
        query=SimpleNamespace(to_boolean_string=lambda: "(memory AND confound)"),
    )
    monkeypatch.setattr(job_runner, "load_profiles", lambda: SimpleNamespace(profiles=[profile]))

    hint = job_runner._resolve_persona_hint("coglab")

    assert hint is not None
    assert "profile_id=coglab" in hint
    assert "title=Cognitive Lab" in hint
    assert "notes=prioritize confounds" in hint
    assert "query_focus=(memory AND confound)" in hint


def test_resolve_persona_hint_skips_disabled_profile(monkeypatch):
    profile = SimpleNamespace(
        id="coglab",
        title="Cognitive Lab",
        enabled=False,
        notes="x",
        query=SimpleNamespace(to_boolean_string=lambda: "x"),
    )
    monkeypatch.setattr(job_runner, "load_profiles", lambda: SimpleNamespace(profiles=[profile]))
    assert job_runner._resolve_persona_hint("coglab") is None


def test_load_similar_feedback_top3_ignores_same_paper_and_limits(tmp_path, monkeypatch):
    feedback_file = tmp_path / "feedback.jsonl"
    feedback_file.write_text(
        "\n".join(
            [
                '{"paper_id":"same","accepted":true,"user_correction":"should be ignored"}',
                '{"paper_id":"p1","accepted":false,"user_correction":"corr1 rejected"}',
                '{"paper_id":"p2","accepted":true,"user_correction":"corr2"}',
                '{"paper_id":"p2","accepted":true,"user_correction":"corr2 duplicate latest"}',
                '{"paper_id":"p3","accepted":true,"user_correction":"corr3"}',
                '{"paper_id":"p4","accepted":true,"user_correction":"corr4"}',
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(job_runner, "FEEDBACK_FILE", feedback_file)

    top3 = job_runner._load_similar_feedback_top3("same", limit=3)

    assert len(top3) == 3
    # reverse scan (latest first)
    assert top3[0]["paper_id"] == "p4"
    assert top3[1]["paper_id"] == "p3"
    assert top3[2]["paper_id"] == "p2"


def test_load_similar_feedback_top3_sanitizes_legacy_fallback_preview(tmp_path, monkeypatch):
    feedback_file = tmp_path / "feedback.jsonl"
    feedback_file.write_text(
        json.dumps(
            {
                "paper_id": "paper_secret_fallback",
                "accepted": True,
                "user_correction": "Never inject Authorization: Bearer fallback-feedback-token-123 into prompts.",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    class FailingRetriever:
        def query_relevant_feedback(self, query_text, limit=3):
            raise RuntimeError("force fallback")

    monkeypatch.setattr(job_runner, "FEEDBACK_FILE", feedback_file)
    monkeypatch.setattr(job_runner, "FeedbackRetriever", lambda: FailingRetriever())

    top = job_runner._load_similar_feedback_top3("other_paper", limit=1)

    assert top == [
        {
            "paper_id": "paper_secret_fallback",
            "preview": "Never inject Authorization: <redacted> into prompts.",
        }
    ]


def test_run_deepread_job_injects_top3_feedback_into_persona_context(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    paper_id = "paper_persona_top3_001"
    library_dir = tmp_path / "Library"
    library_dir.mkdir(parents=True, exist_ok=True)
    (library_dir / f"{paper_id}.pdf").write_bytes(b"%PDF-1.4\n%fake\n")

    vault_dir = tmp_path / "Vault"
    vault_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(
        job_runner,
        "load_config",
        lambda: SimpleNamespace(
            paths=SimpleNamespace(
                library_dir=library_dir,
                obsidian_vault=vault_dir,
                index_all=Path("00_Index/paper_collection.csv"),
            ),
            agents=SimpleNamespace(main_model="unit-test-model"),
        ),
    )
    monkeypatch.setattr(job_runner, "_resolve_pdf_path_from_db", lambda _: None)
    monkeypatch.setattr(
        job_runner,
        "_resolve_persona_hint",
        lambda persona_id: "profile_id=coglab\ntitle=Cognitive Lab" if persona_id == "coglab" else None,
    )
    monkeypatch.setattr(
        job_runner,
        "_load_similar_feedback_top3",
        lambda query_text, limit=3: [
            {"paper_id": "case_a", "preview": "use stricter endpoint wording"},
            {"paper_id": "case_b", "preview": "link confidence to evidence span"},
        ],
    )

    captured: dict[str, str] = {}

    class FakeIngestAgent:
        def process_v2(self, pdf_path: str):
            return DocumentArtifactV2(
                document_id=paper_id,
                meta=ArtifactMetaV2(title="Persona Top3", authors=["A"], source_ref=pdf_path),
                pages=[
                    PageV2(
                        page_index=0,
                        width=595.0,
                        height=842.0,
                        blocks=[
                            BlockV2(
                                block_id="b1",
                                lines=[
                                    LineV2(
                                        line_id="l1",
                                        text="smoke text",
                                        spans=[SpanV2(span_id="s1", text="smoke text")],
                                    )
                                ],
                            )
                        ],
                    )
                ],
                tables=[],
            )

    class FakeIndexerAgent:
        def process(self, doc):
            return IndexArtifact(
                doc_id=doc.document_id,
                vector_store_id="smoke",
                chunk_count=1,
                chunks=[],
            )

    class FakeReaderAgent:
        def __init__(self, model_name: str = "llama3:latest", persona_hint: str | None = None):
            captured["persona_hint"] = persona_hint or ""
            self.model_name = model_name

        def analyze(self, doc):
            return ClaimSet(
                doc_id=doc.document_id,
                claims=[
                    ScientificClaim(
                        claim_id="c1",
                        type="efficacy",
                        statement="claim",
                        confidence=0.9,
                    )
                ],
            )

    monkeypatch.setattr(job_runner, "IngestAgent", FakeIngestAgent)
    monkeypatch.setattr(job_runner, "IndexerAgent", FakeIndexerAgent)
    monkeypatch.setattr(job_runner, "ReaderAgent", FakeReaderAgent)

    events = []

    async def progress_callback(event):
        events.append(event)

    result = asyncio.run(
        job_runner.run_deepread_job(
            job_id="job_top3_persona",
            paper_id=paper_id,
            persona_id="coglab",
            run_verify=False,
            run_id="run_top3_persona",
            progress_callback=progress_callback,
        )
    )

    assert result["status"] == "succeeded"
    assert "Similar feedback examples (Top-3):" in captured["persona_hint"]
    assert "paper_id=case_a" in captured["persona_hint"]
    assert "paper_id=case_b" in captured["persona_hint"]
    assert any(evt["message"] == "Similar feedback injected: 2" for evt in events)
    assert any(evt["message"] == "Profile context applied: coglab" for evt in events)

    meta_path = Path(result["artifact_dir"]) / "bootstrap_meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    assert meta["persona_applied"] is True
    assert meta["profile_id"] == "coglab"
    assert meta["similar_feedback_count"] == 2
    assert meta["similar_feedback_paper_ids"] == ["case_a", "case_b"]


def test_run_deepread_job_applies_reasoning_persona_without_profile(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    paper_id = "paper_reasoning_lane_001"
    library_dir = tmp_path / "Library"
    library_dir.mkdir(parents=True, exist_ok=True)
    (library_dir / f"{paper_id}.pdf").write_bytes(b"%PDF-1.4\n%fake\n")

    vault_dir = tmp_path / "Vault"
    vault_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(
        job_runner,
        "load_config",
        lambda: SimpleNamespace(
            paths=SimpleNamespace(
                library_dir=library_dir,
                obsidian_vault=vault_dir,
                index_all=Path("00_Index/paper_collection.csv"),
            ),
            agents=SimpleNamespace(main_model="unit-test-model"),
        ),
    )
    monkeypatch.setattr(job_runner, "_resolve_pdf_path_from_db", lambda _: None)
    monkeypatch.setattr(job_runner, "_load_similar_feedback_top3", lambda query_text, limit=3: [])

    captured: dict[str, str] = {}

    class FakeIngestAgent:
        def process_v2(self, pdf_path: str):
            return DocumentArtifactV2(
                document_id=paper_id,
                meta=ArtifactMetaV2(title="Reasoning Lane", authors=["A"], source_ref=pdf_path),
                pages=[
                    PageV2(
                        page_index=0,
                        width=595.0,
                        height=842.0,
                        blocks=[
                            BlockV2(
                                block_id="b1",
                                lines=[
                                    LineV2(
                                        line_id="l1",
                                        text="smoke text",
                                        spans=[SpanV2(span_id="s1", text="smoke text")],
                                    )
                                ],
                            )
                        ],
                    )
                ],
                tables=[],
            )

    class FakeIndexerAgent:
        def process(self, doc):
            return IndexArtifact(
                doc_id=doc.document_id,
                vector_store_id="smoke",
                chunk_count=1,
                chunks=[],
            )

    class FakeReaderAgent:
        def __init__(self, model_name: str = "llama3:latest", persona_hint: str | None = None):
            captured["persona_hint"] = persona_hint or ""
            self.model_name = model_name

        def analyze(self, doc):
            return ClaimSet(
                doc_id=doc.document_id,
                claims=[
                    ScientificClaim(
                        claim_id="c1",
                        type="efficacy",
                        statement="claim",
                        confidence=0.9,
                    )
                ],
            )

    monkeypatch.setattr(job_runner, "IngestAgent", FakeIngestAgent)
    monkeypatch.setattr(job_runner, "IndexerAgent", FakeIndexerAgent)
    monkeypatch.setattr(job_runner, "ReaderAgent", FakeReaderAgent)

    events = []

    async def progress_callback(event):
        events.append(event)

    result = asyncio.run(
        job_runner.run_deepread_job(
            job_id="job_reasoning_lane",
            paper_id=paper_id,
            reasoning_persona="librarian",
            run_verify=False,
            run_id="run_reasoning_lane",
            progress_callback=progress_callback,
        )
    )

    assert result["status"] == "succeeded"
    assert "reasoning_persona=librarian" in captured["persona_hint"]
    assert any(evt["message"] == "Reasoning persona applied: librarian" for evt in events)

    meta_path = Path(result["artifact_dir"]) / "bootstrap_meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    assert meta["persona_id"] == "librarian"
    assert meta["reasoning_persona"] == "librarian"
    assert meta["profile_id"] is None
