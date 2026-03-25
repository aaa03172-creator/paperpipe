import asyncio
from contextlib import nullcontext
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
import types

import scripts.bootstrap as bootstrap
from rich.console import Console

from src.timeout_policy import StepTimeoutError


def test_bootstrap_teacher_review_uses_configured_provider_and_repairs_wrapped_json(monkeypatch):
    class FakeProvider:
        def __init__(self):
            self.calls = []

        def is_available(self):
            return True

        def review_claimset_bundle(self, *, prompt: str, system_prompt: str | None = None):
            self.calls.append({"prompt": prompt, "system_prompt": system_prompt})
            return json.dumps(
                {
                    "claimset": {
                        "doc_id": "doc:test",
                        "claims": [
                            {
                                "claim_id": "CLM-1",
                                "type": "efficacy",
                                "statement": "The treatment improved the outcome.",
                                "evidence_spans": [
                                    {
                                        "raw_text": "The treatment improved the outcome.",
                                        "quote": "The treatment improved the outcome.",
                                        "rationale": "Direct support from the provided excerpt.",
                                    }
                                ],
                                "limitations": [],
                                "confidence": 0.5,
                            }
                        ],
                    }
                }
            )

    provider = FakeProvider()
    monkeypatch.setattr(bootstrap, "load_config", lambda: SimpleNamespace(llm=SimpleNamespace()))
    monkeypatch.setattr(bootstrap, "get_llm_provider", lambda _cfg: provider)

    result = asyncio.run(
        bootstrap.run_teacher_review(
            {"doc_id": "doc:test", "claims": []},
            "The treatment improved the outcome.",
            "Biomedical Paper Analysis",
        )
    )

    assert result is not None
    assert result.doc_id == "doc:test"
    assert len(result.claims) == 1
    assert result.claims[0].evidence_spans[0].raw_text == "The treatment improved the outcome."
    assert provider.calls and "Biomedical Paper Analysis" in provider.calls[0]["prompt"]


def test_run_batch_script_executes_without_scripts_import_failure(tmp_path):
    storage_dir = tmp_path / "storage"
    storage_dir.mkdir()

    repo_root = Path(__file__).resolve().parents[1]
    script_path = repo_root / "scripts" / "run_batch.py"

    result = subprocess.run(
        [sys.executable, str(script_path)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )

    combined = f"{result.stdout}\n{result.stderr}"
    assert result.returncode == 0
    assert "ModuleNotFoundError" not in combined
    assert "Zotero export not found" in combined


def test_cli_workflow_falls_back_from_docling_and_reports_reader_timeout(monkeypatch, tmp_path):
    import src.services.cli_workflows as workflows

    pdf_path = tmp_path / "paper_docling.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n")

    config = SimpleNamespace(
        agents=SimpleNamespace(enabled=True, main_model="mock-reader"),
        llm=SimpleNamespace(timeout_seconds=15),
        ingest=SimpleNamespace(
            parser_backend="docling",
            enable_docling=False,
            enable_ocr_fallback=False,
            ocr_lang="eng",
            ocr_min_text_chars=200,
            enable_table_pass2_ocr=False,
            enable_cloud_table_fallback=False,
            cloud_table_page_budget=2,
            cloud_table_model="gpt-4o-mini",
            cloud_table_base_url=None,
            cloud_table_api_key=None,
            cloud_table_timeout_seconds=30,
        ),
        paths=SimpleNamespace(
            library_dir=tmp_path,
            obsidian_vault=tmp_path,
            index_all="missing.csv",
        ),
    )

    ingest_calls: dict[str, object] = {}

    class FakeIngestAgent:
        def __init__(self, **kwargs):
            ingest_calls.update(kwargs)

        def process_v2(self, _path: str):
            return SimpleNamespace(
                pages=[object(), object(), object()],
                tables=[object()],
                meta=SimpleNamespace(title="Mock Paper"),
            )

    class FakeIndexerAgent:
        def __init__(self, **_kwargs):
            pass

        def process(self, _doc):
            return SimpleNamespace(chunk_count=3)

    class FakeReaderAgent:
        def __init__(self, **_kwargs):
            self.model_name = "mock-reader"

        def analyze(self, _doc):
            raise StepTimeoutError("step_timeout:99s")

    class FakeFeedbackRetriever:
        def query_relevant_feedback(self, *_args, **_kwargs):
            return []

    monkeypatch.setattr(workflows, "load_config", lambda: config)
    monkeypatch.setattr(
        workflows,
        "get_paper_by_id",
        lambda _identifier: {"local_path": str(pdf_path), "pdf_path": str(pdf_path)},
    )
    monkeypatch.setattr(workflows, "default_reader_timeout_base_seconds", lambda _llm_timeout: 90)
    monkeypatch.setattr(workflows, "estimate_reader_timeout_seconds", lambda *_args, **_kwargs: 123)
    monkeypatch.setattr(workflows, "time_limit", lambda _seconds: nullcontext())

    fake_ingest_module = types.ModuleType("src.agents.ingest_agent")
    fake_ingest_module.IngestAgent = FakeIngestAgent
    fake_indexer_module = types.ModuleType("src.agents.indexer_agent")
    fake_indexer_module.IndexerAgent = FakeIndexerAgent
    fake_reader_module = types.ModuleType("src.agents.reader_agent")
    fake_reader_module.ReaderAgent = FakeReaderAgent
    fake_feedback_module = types.ModuleType("src.agents.feedback_retriever")
    fake_feedback_module.FeedbackRetriever = FakeFeedbackRetriever

    monkeypatch.setitem(sys.modules, "src.agents.ingest_agent", fake_ingest_module)
    monkeypatch.setitem(sys.modules, "src.agents.indexer_agent", fake_indexer_module)
    monkeypatch.setitem(sys.modules, "src.agents.reader_agent", fake_reader_module)
    monkeypatch.setitem(sys.modules, "src.agents.feedback_retriever", fake_feedback_module)

    console = Console(record=True, width=120)
    workflows.run_deepread_workflow("paper_docling", verify=False, console=console)

    output = console.export_text()
    assert ingest_calls["parser_backend"] == "fitz_pdfplumber"
    assert "Reader timeout after 123s" in output
