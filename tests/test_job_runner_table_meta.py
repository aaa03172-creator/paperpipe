import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

import backend.services.job_runner as job_runner
from src.contracts.document_artifact_v2 import ArtifactMetaV2, BlockV2, DocumentArtifactV2, LineV2, PageV2, SpanV2
from src.profiles.profile_schema import Profile, ProfileConfig
from src.schemas.agent_artifacts import ClaimSet, ScientificClaim, StatCheckEntry, StatsReport, VerificationStatus


def _make_basic_doc(paper_id: str, pdf_path: str) -> DocumentArtifactV2:
    return DocumentArtifactV2(
        document_id=paper_id,
        meta=ArtifactMetaV2(title="Meta Test", authors=["A"], source_ref=pdf_path),
        pages=[
            PageV2(
                page_index=0,
                width=595.0,
                height=842.0,
                blocks=[
                    BlockV2(
                        block_id="b1",
                        lines=[LineV2(line_id="l1", text="smoke", spans=[SpanV2(span_id="s1", text="smoke")])],
                    )
                ],
            )
        ],
        tables=[],
    )


def test_persona_application_events_require_actual_profile_hint():
    selection = SimpleNamespace(
        persona_id="disabled-profile",
        reasoning_persona=None,
        profile_id="disabled-profile",
    )

    assert job_runner._persona_application_event_messages(
        selection,
        reasoning_hint=None,
        profile_hint=None,
    ) == []

    assert job_runner._persona_application_event_messages(
        selection,
        reasoning_hint=None,
        profile_hint="profile_id=disabled-profile",
    ) == [(52, "Profile context applied: disabled-profile")]


def test_resolve_persona_hint_masks_local_paths_in_profile_notes(monkeypatch):
    monkeypatch.setattr(
        job_runner,
        "load_profiles",
        lambda: ProfileConfig(
            profiles=[
                Profile(
                    id="path_profile",
                    title="Path Profile",
                    notes="source_of_truth: /Users/example/paperpipe/private/profile.yaml",
                )
            ]
        ),
    )

    hint = job_runner._resolve_persona_hint("path_profile")

    assert hint is not None
    assert "/Users/example" not in hint
    assert "source_of_truth: .../profile.yaml" in hint


def test_run_deepread_job_records_table_extraction_meta(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    paper_id = "paper_table_meta_001"
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
            ingest=SimpleNamespace(
                parser_backend="fitz_pdfplumber",
                enable_docling=False,
                enable_ocr_fallback=True,
                ocr_lang="eng",
                ocr_min_text_chars=123,
                enable_table_pass2_ocr=True,
                enable_cloud_table_fallback=True,
                cloud_table_page_budget=4,
            ),
            agents=SimpleNamespace(main_model="unit-test-model"),
        ),
    )
    monkeypatch.setattr(job_runner, "_resolve_pdf_path_from_db", lambda _: None)
    monkeypatch.setattr(job_runner, "_resolve_persona_hint", lambda _persona_id: None)
    monkeypatch.setattr(job_runner, "_load_similar_feedback_top3", lambda **_kwargs: [])

    captured_init = {}

    class FakeIngestAgent:
        def __init__(self, **kwargs):
            captured_init.update(kwargs)
            self.last_table_extraction_meta = {
                "parser_backend": "fitz_pdfplumber",
                "table_extraction_pass": "pass2",
                "table_failure_taxonomy": ["NO_TABLE_FOUND", "OCR_LOW_CONF"],
                "fallback_used": True,
                "fallback_pages": [1, 2],
            }

        def process_v2(self, pdf_path: str):
            return _make_basic_doc(paper_id, pdf_path)

    class FakeIndexerAgent:
        def process(self, doc):
            from src.schemas.agent_artifacts import IndexArtifact

            return IndexArtifact(doc_id=doc.document_id, vector_store_id="smoke", chunk_count=1, chunks=[])

    class FakeReaderAgent:
        def __init__(self, model_name: str = "llama3:latest", persona_hint: str | None = None):
            self.model_name = model_name

        def analyze(self, doc):
            return ClaimSet(
                doc_id=doc.document_id,
                claims=[ScientificClaim(claim_id="c1", type="efficacy", statement="claim", confidence=0.9)],
            )

    monkeypatch.setattr(job_runner, "IngestAgent", FakeIngestAgent)
    monkeypatch.setattr(job_runner, "IndexerAgent", FakeIndexerAgent)
    monkeypatch.setattr(job_runner, "ReaderAgent", FakeReaderAgent)

    result = asyncio.run(
        job_runner.run_deepread_job(
            job_id="job_table_meta",
            paper_id=paper_id,
            persona_id="default",
            run_verify=False,
            run_id="run_table_meta",
            progress_callback=lambda _event: asyncio.sleep(0),
        )
    )

    assert result["status"] == "succeeded"
    assert captured_init["enable_table_pass2_ocr"] is True
    assert captured_init["enable_cloud_table_fallback"] is True
    assert captured_init["cloud_table_page_budget"] == 4

    artifact_dir = Path(result["artifact_dir"])
    bootstrap = json.loads((artifact_dir / "bootstrap_meta.json").read_text(encoding="utf-8"))
    run_meta = json.loads((artifact_dir / "run_meta.json").read_text(encoding="utf-8"))
    assert bootstrap["table_extraction_pass"] == "pass2"
    assert bootstrap["fallback_used"] is True
    assert bootstrap["fallback_pages"] == [1, 2]
    assert bootstrap["table_pass2_enabled"] is True
    assert bootstrap["table_pass3_enabled"] is True
    assert bootstrap["table_page_budget"] == 4
    assert run_meta["table_extraction"]["pass"] == "pass2"
    assert run_meta["table_extraction"]["fallback_used"] is True


def test_run_deepread_job_writes_anchor_verify_log(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    paper_id = "paper_anchor_meta_001"
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
            ingest=SimpleNamespace(parser_backend="fitz_pdfplumber", enable_docling=False),
            agents=SimpleNamespace(main_model="unit-test-model"),
        ),
    )
    monkeypatch.setattr(job_runner, "_resolve_pdf_path_from_db", lambda _: None)
    monkeypatch.setattr(job_runner, "_resolve_persona_hint", lambda _persona_id: None)
    monkeypatch.setattr(job_runner, "_load_similar_feedback_top3", lambda **_kwargs: [])

    class FakeIngestAgent:
        def __init__(self, **_kwargs):
            self.last_table_extraction_meta = {
                "parser_backend": "fitz_pdfplumber",
                "table_extraction_pass": "pass1",
                "table_failure_taxonomy": [],
                "fallback_used": False,
                "fallback_pages": [],
            }

        def process_v2(self, pdf_path: str):
            return _make_basic_doc(paper_id, pdf_path)

    class FakeIndexerAgent:
        def process(self, doc):
            from src.schemas.agent_artifacts import IndexArtifact

            return IndexArtifact(doc_id=doc.document_id, vector_store_id="smoke", chunk_count=1, chunks=[])

    class FakeReaderAgent:
        def __init__(self, model_name: str = "llama3:latest", persona_hint: str | None = None):
            self.model_name = model_name

        def analyze(self, doc):
            return ClaimSet(
                doc_id=doc.document_id,
                claims=[ScientificClaim(claim_id="c1", type="efficacy", statement="claim", confidence=0.9)],
            )

    class FakeStatsAgent:
        def run(self, job_id: str, doc, claims: ClaimSet):
            return StatsReport(
                doc_id=doc.document_id,
                run_id=job_id,
                checks=[
                    StatCheckEntry(
                        check_id="a-pass",
                        test_type="t-test",
                        code="print('ok')",
                        outputs="ok",
                        verdict=VerificationStatus.VERIFIED,
                    ),
                    StatCheckEntry(
                        check_id="a-noapi",
                        test_type="chi-square",
                        code="print('na')",
                        outputs="na",
                        verdict=VerificationStatus.UNVERIFIABLE,
                    ),
                ],
            )

    monkeypatch.setattr(job_runner, "IngestAgent", FakeIngestAgent)
    monkeypatch.setattr(job_runner, "IndexerAgent", FakeIndexerAgent)
    monkeypatch.setattr(job_runner, "ReaderAgent", FakeReaderAgent)
    monkeypatch.setattr(job_runner, "StatsVerificationAgent", FakeStatsAgent)

    result = asyncio.run(
        job_runner.run_deepread_job(
            job_id="job_anchor_meta",
            paper_id=paper_id,
            persona_id="default",
            run_verify=True,
            run_id="run_anchor_meta",
            progress_callback=lambda _event: asyncio.sleep(0),
        )
    )

    assert result["status"] == "succeeded"
    artifact_dir = Path(result["artifact_dir"])
    run_meta = json.loads((artifact_dir / "run_meta.json").read_text(encoding="utf-8"))
    summary = run_meta["anchor_verify_summary"]
    assert summary["pass"] == 1
    assert summary["no_api"] == 1
    assert run_meta["anchor_verify_api"]["provider"] == "none"
    entries = run_meta["anchor_verify_log"]
    assert isinstance(entries, list) and len(entries) == 2
    assert entries[0]["anchor_id"] == "a-pass"
    assert entries[0]["result"] == "PASS"
    assert entries[1]["anchor_id"] == "a-noapi"
    assert entries[1]["result"] == "NO_API"


def test_run_deepread_job_verify_failure_sets_no_api_context(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    paper_id = "paper_anchor_fail_001"
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
            ingest=SimpleNamespace(parser_backend="fitz_pdfplumber", enable_docling=False),
            agents=SimpleNamespace(main_model="unit-test-model"),
        ),
    )
    monkeypatch.setattr(job_runner, "_resolve_pdf_path_from_db", lambda _: None)
    monkeypatch.setattr(job_runner, "_resolve_persona_hint", lambda _persona_id: None)
    monkeypatch.setattr(job_runner, "_load_similar_feedback_top3", lambda **_kwargs: [])

    class FakeIngestAgent:
        def __init__(self, **_kwargs):
            self.last_table_extraction_meta = {
                "parser_backend": "fitz_pdfplumber",
                "table_extraction_pass": "pass1",
                "table_failure_taxonomy": [],
                "fallback_used": False,
                "fallback_pages": [],
            }

        def process_v2(self, pdf_path: str):
            return _make_basic_doc(paper_id, pdf_path)

    class FakeIndexerAgent:
        def process(self, doc):
            from src.schemas.agent_artifacts import IndexArtifact

            return IndexArtifact(doc_id=doc.document_id, vector_store_id="smoke", chunk_count=1, chunks=[])

    class FakeReaderAgent:
        def __init__(self, model_name: str = "llama3:latest", persona_hint: str | None = None):
            self.model_name = model_name

        def analyze(self, doc):
            return ClaimSet(
                doc_id=doc.document_id,
                claims=[ScientificClaim(claim_id="c1", type="efficacy", statement="claim", confidence=0.9)],
            )

    class FakeStatsAgent:
        def run(self, job_id: str, doc, claims: ClaimSet):
            raise RuntimeError("Connection refused while fetching docker API version")

    monkeypatch.setattr(job_runner, "IngestAgent", FakeIngestAgent)
    monkeypatch.setattr(job_runner, "IndexerAgent", FakeIndexerAgent)
    monkeypatch.setattr(job_runner, "ReaderAgent", FakeReaderAgent)
    monkeypatch.setattr(job_runner, "StatsVerificationAgent", FakeStatsAgent)

    result = asyncio.run(
        job_runner.run_deepread_job(
            job_id="job_anchor_fail",
            paper_id=paper_id,
            persona_id="default",
            run_verify=True,
            run_id="run_anchor_fail",
            progress_callback=lambda _event: asyncio.sleep(0),
        )
    )

    assert result["status"] == "succeeded"
    artifact_dir = Path(result["artifact_dir"])
    run_meta = json.loads((artifact_dir / "run_meta.json").read_text(encoding="utf-8"))
    bootstrap = json.loads((artifact_dir / "bootstrap_meta.json").read_text(encoding="utf-8"))
    assert run_meta["verification_status"] == "failed"
    assert run_meta["anchor_verify_summary"] == {"pass": 0, "warn": 0, "fail": 0, "no_api": 0}
    assert run_meta["anchor_verify_api"]["status"] == "docker_unavailable"
    assert "DOCKER_UNAVAILABLE" in run_meta["anchor_verify_api"]["reason_codes"]
    assert run_meta["anchor_verify_log"] == []
    assert bootstrap["anchor_verify_api"]["status"] == "docker_unavailable"
