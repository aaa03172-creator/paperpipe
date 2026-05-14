import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

import backend.services.job_runner as job_runner
from src.contracts.document_artifact_v2 import ArtifactMetaV2, BlockV2, DocumentArtifactV2, LineV2, PageV2, SpanV2
from src.schemas.core import BiomedicalClinicalExtraction
from src.schemas.agent_artifacts import ClaimSet, IndexArtifact, ScientificClaim


def _make_doc(
    paper_id: str,
    pdf_path: str,
    *,
    text: str = "Clinical abstract text describing a human oncology trial.",
) -> DocumentArtifactV2:
    return DocumentArtifactV2(
        document_id=paper_id,
        meta=ArtifactMetaV2(title="Clinical Artifact Title", authors=["A"], source_ref=pdf_path),
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
                                text=text,
                                spans=[SpanV2(span_id="s1", text=text)],
                            )
                        ],
                    )
                ],
            )
        ],
        tables=[],
    )


@pytest.mark.parametrize(
    ("paper_id", "title", "condition", "intervention_name", "intervention_category", "followup_tag"),
    [
        (
            "paper_oncology_job_001",
            "Circulating tumor DNA monitoring in metastatic colorectal cancer",
            "Metastatic colorectal cancer",
            "ctDNA-guided monitoring",
            "diagnostic",
            "biomarker",
        ),
        (
            "paper_immunology_job_001",
            "Prospective cytokine profiling in ulcerative colitis",
            "Ulcerative colitis",
            "Multiplex cytokine monitoring",
            "diagnostic",
            "observational",
        ),
        (
            "paper_biomaterial_job_001",
            "Injectable hydrogel scaffold pilot for cartilage repair",
            "Knee osteoarthritis",
            "Injectable hydrogel scaffold",
            "biomaterial",
            "device",
        ),
        (
            "paper_neuro_job_001",
            "Blood biomarker study in mild cognitive impairment",
            "Mild cognitive impairment",
            "Plasma biomarker panel",
            "diagnostic",
            "biomarker",
        ),
    ],
)
def test_run_deepread_job_uses_generic_clinical_extraction_across_biomedical_domains(
    tmp_path,
    monkeypatch,
    paper_id,
    title,
    condition,
    intervention_name,
    intervention_category,
    followup_tag,
):
    monkeypatch.chdir(tmp_path)

    library_dir = tmp_path / "Library"
    library_dir.mkdir(parents=True, exist_ok=True)
    (library_dir / f"{paper_id}.pdf").write_bytes(b"%PDF-1.4\n%fake\n")
    vault_dir = tmp_path / "Vault"
    (vault_dir / "00_Index").mkdir(parents=True, exist_ok=True)
    (vault_dir / "Inbox").mkdir(parents=True, exist_ok=True)
    note_path = vault_dir / "Inbox" / f"{paper_id}.md"
    note_path.write_text(
        "---\n"
        "type: clinical_paper\n"
        "slot: clinical\n"
        f"aliases:\n  - {title}\n"
        "---\n\n"
        "# Paper\n",
        encoding="utf-8",
    )
    (vault_dir / "00_Index" / "paper_collection.csv").write_text(
        f"Paper_ID,DOI,Title,Note_Path\n{paper_id},10.1000/test,{title},Inbox/{paper_id}.md\n",
        encoding="utf-8",
    )

    fake_config = SimpleNamespace(
        paths=SimpleNamespace(
            library_dir=library_dir,
            obsidian_vault=vault_dir,
            index_all=Path("00_Index/paper_collection.csv"),
        ),
        llm=SimpleNamespace(
            features=SimpleNamespace(
                clinical_extraction=SimpleNamespace(enabled=True),
                specialty_trial_extraction=SimpleNamespace(enabled=True),
            ),
            timeout_seconds=15,
            max_retries=0,
            mode="local",
            local=SimpleNamespace(provider="ollama", models={}),
            cloud=SimpleNamespace(provider="openai"),
        ),
        entity_aliases={},
        agents=SimpleNamespace(main_model="unit-test-model"),
    )
    monkeypatch.setattr(job_runner, "load_config", lambda: fake_config)
    monkeypatch.setattr(job_runner, "_resolve_pdf_path_from_db", lambda _: None)
    monkeypatch.setattr(job_runner, "_resolve_persona_hint", lambda _persona_id: None)
    monkeypatch.setattr(job_runner, "_load_similar_feedback_top3", lambda **_kwargs: [])

    class FakeIngestAgent:
        def __init__(self, **_kwargs):
            self.last_table_extraction_meta = {}

        def process_v2(self, pdf_path: str):
            return _make_doc(paper_id, pdf_path)

    class FakeIndexerAgent:
        def process(self, doc):
            return IndexArtifact(doc_id=doc.document_id, vector_store_id="smoke", chunk_count=1, chunks=[])

    class FakeReaderAgent:
        def __init__(self, model_name: str = "llama3:latest", persona_hint: str | None = None):
            self.model_name = model_name

        def analyze(self, doc):
            return ClaimSet(
                doc_id=doc.document_id,
                claims=[ScientificClaim(claim_id="c1", type="efficacy", statement="claim", confidence=0.9)],
            )

    call_counts = {"generic": 0, "specialty": 0}

    class FakeClinicalProvider:
        def is_available(self):
            return True

        def extract_biomedical_clinical_data(self, _paper_payload, _methods_snippet=""):
            call_counts["generic"] += 1
            return BiomedicalClinicalExtraction(
                paper_id=paper_id,
                citation={
                    "title": title,
                    "authors_first": "Kim",
                    "year": 2026,
                    "journal_or_server": "Test Journal",
                    "doi": None,
                    "url": None,
                },
                population={"condition": condition, "n_total": 50},
                intervention={"category": intervention_category, "name": intervention_name},
                eligibility_flags={"followup_tag": followup_tag},
            )

        def extract_specialty_trial_data(self, _paper_payload, _methods_snippet=""):
            call_counts["specialty"] += 1
            raise AssertionError("Specialty extraction should not be used for generic clinical notes")

    monkeypatch.setattr(job_runner, "IngestAgent", FakeIngestAgent)
    monkeypatch.setattr(job_runner, "IndexerAgent", FakeIndexerAgent)
    monkeypatch.setattr(job_runner, "ReaderAgent", FakeReaderAgent)
    monkeypatch.setattr(job_runner, "get_llm_provider", lambda *_args, **_kwargs: FakeClinicalProvider())

    result = asyncio.run(
        job_runner.run_deepread_job(
            job_id=f"job_{paper_id}",
            paper_id=paper_id,
            persona_id="default",
            run_verify=False,
            run_id=f"run_{paper_id}",
            progress_callback=lambda _event: asyncio.sleep(0),
        )
    )

    assert result["status"] == "succeeded"
    artifact_dir = Path(result["artifact_dir"])
    clinical_payload = json.loads((artifact_dir / "clinical_extraction.json").read_text(encoding="utf-8"))
    updated_note = note_path.read_text(encoding="utf-8")

    assert call_counts["generic"] == 1
    assert call_counts["specialty"] == 0
    assert clinical_payload["population"]["condition"] == condition
    assert clinical_payload["intervention"]["name"] == intervention_name
    assert "### 🏥 Clinical Extraction" in updated_note
    assert condition in updated_note
    assert intervention_name in updated_note


def test_run_deepread_job_writes_clinical_extraction_artifact_for_clinical_note(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("LATTICE_PRIVACY_PREFLIGHT_MODE", "report_only")

    paper_id = "paper_clinical_job_001"
    library_dir = tmp_path / "Library"
    library_dir.mkdir(parents=True, exist_ok=True)
    (library_dir / f"{paper_id}.pdf").write_bytes(b"%PDF-1.4\n%fake\n")
    vault_dir = tmp_path / "Vault"
    (vault_dir / "00_Index").mkdir(parents=True, exist_ok=True)
    (vault_dir / "Inbox").mkdir(parents=True, exist_ok=True)
    note_path = vault_dir / "Inbox" / "paper_clinical_job_001.md"
    note_path.write_text(
        "---\n"
        "type: clinical_paper\n"
        "slot: clinical\n"
        "aliases:\n"
        "  - Clinical Artifact Title\n"
        "---\n\n"
        "# Paper\n",
        encoding="utf-8",
    )
    (vault_dir / "00_Index" / "paper_collection.csv").write_text(
        "Paper_ID,DOI,Title,Note_Path\n"
        "paper_clinical_job_001,10.1000/test,Clinical Artifact Title,Inbox/paper_clinical_job_001.md\n",
        encoding="utf-8",
    )

    fake_config = SimpleNamespace(
        paths=SimpleNamespace(
            library_dir=library_dir,
            obsidian_vault=vault_dir,
            index_all=Path("00_Index/paper_collection.csv"),
        ),
        llm=SimpleNamespace(
            features=SimpleNamespace(specialty_trial_extraction=SimpleNamespace(enabled=True)),
            timeout_seconds=15,
            max_retries=0,
            mode="local",
            local=SimpleNamespace(provider="ollama", models={}),
            cloud=SimpleNamespace(provider="openai"),
        ),
        entity_aliases={},
        agents=SimpleNamespace(main_model="unit-test-model"),
    )
    monkeypatch.setattr(job_runner, "load_config", lambda: fake_config)
    monkeypatch.setattr(job_runner, "_resolve_pdf_path_from_db", lambda _: None)
    monkeypatch.setattr(job_runner, "_resolve_persona_hint", lambda _persona_id: None)
    monkeypatch.setattr(job_runner, "_load_similar_feedback_top3", lambda **_kwargs: [])

    class FakeIngestAgent:
        def __init__(self, **_kwargs):
            self.last_table_extraction_meta = {}

        def process_v2(self, pdf_path: str):
            return _make_doc(paper_id, pdf_path)

    class FakeIndexerAgent:
        def process(self, doc):
            return IndexArtifact(doc_id=doc.document_id, vector_store_id="smoke", chunk_count=1, chunks=[])

    class FakeReaderAgent:
        def __init__(self, model_name: str = "llama3:latest", persona_hint: str | None = None):
            self.model_name = model_name

        def analyze(self, doc):
            return ClaimSet(
                doc_id=doc.document_id,
                claims=[ScientificClaim(claim_id="c1", type="efficacy", statement="claim", confidence=0.9)],
            )

    seen_payloads: list[dict] = []

    class FakeClinicalProvider:
        def is_available(self):
            return True

        def extract_biomedical_clinical_data(self, paper_payload, _methods_snippet=""):
            seen_payloads.append(dict(paper_payload))
            return BiomedicalClinicalExtraction(
                paper_id=paper_id,
                citation={
                    "title": "Clinical Artifact Title",
                    "authors_first": "Kim",
                    "year": 2026,
                    "journal_or_server": "Test Journal",
                    "doi": None,
                    "url": None,
                },
                population={"condition": "Metastatic non-small cell lung cancer", "n_total": 50},
                intervention={"category": "small_molecule", "name": "Targeted therapy"},
            )

    monkeypatch.setattr(job_runner, "IngestAgent", FakeIngestAgent)
    monkeypatch.setattr(job_runner, "IndexerAgent", FakeIndexerAgent)
    monkeypatch.setattr(job_runner, "ReaderAgent", FakeReaderAgent)
    monkeypatch.setattr(job_runner, "get_llm_provider", lambda *_args, **_kwargs: FakeClinicalProvider())

    result = asyncio.run(
        job_runner.run_deepread_job(
            job_id="job_clinical_sidecar",
            paper_id=paper_id,
            persona_id="default",
            run_verify=False,
            run_id="run_clinical_sidecar",
            progress_callback=lambda _event: asyncio.sleep(0),
        )
    )

    assert result["status"] == "succeeded"
    artifact_dir = Path(result["artifact_dir"])
    clinical_payload = json.loads((artifact_dir / "clinical_extraction.json").read_text(encoding="utf-8"))
    bootstrap = json.loads((artifact_dir / "bootstrap_meta.json").read_text(encoding="utf-8"))
    run_meta = json.loads((artifact_dir / "run_meta.json").read_text(encoding="utf-8"))
    updated_note = note_path.read_text(encoding="utf-8")

    assert clinical_payload["population"]["condition"] == "Metastatic non-small cell lung cancer"
    assert bootstrap["artifact_clinical_extraction_written"] is True
    assert bootstrap["clinical_extraction_status"] == "completed"
    assert bootstrap["clinical_extraction_note_type"] == "clinical"
    assert run_meta["clinical_extraction_status"] == "completed"
    assert str(run_meta["clinical_extraction_artifact"]).endswith("clinical_extraction.json")
    assert run_meta["selected_backend"] == "local"
    assert run_meta["payload_class"] == "mixed"
    assert run_meta["redaction_applied"] is True
    assert run_meta["inference_lanes"]["clinical_extraction"]["selected_backend"] == "local"
    assert run_meta["inference_lanes"]["clinical_extraction"]["payload_class"] == "external_allowed"
    assert run_meta["inference_lanes"]["clinical_extraction"]["redaction_applied"] is True
    assert seen_payloads[0]["link"] is None
    privacy_preflight = run_meta["inference_lanes"]["clinical_extraction"]["privacy_preflight"]
    assert privacy_preflight["mode"] == "report_only"
    assert privacy_preflight["status"] == "pass"
    assert privacy_preflight["mutation_applied"] is False
    assert run_meta["inference_lanes"]["reader"]["selected_backend"] == "local"
    assert run_meta["inference_lanes"]["reader"]["payload_class"] == "local_only"
    assert "## 🤖 Agent Deep Read" in updated_note
    assert "### 🏥 Clinical Extraction" in updated_note
    assert "Metastatic non-small cell lung cancer, n=50" in updated_note
    assert "Targeted therapy, Small Molecule" in updated_note


def test_run_deepread_job_blocks_clinical_extraction_when_privacy_preflight_blocks(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("LATTICE_PRIVACY_PREFLIGHT_MODE", "block_on_review")

    paper_id = "paper_clinical_privacy_block_001"
    library_dir = tmp_path / "Library"
    library_dir.mkdir(parents=True, exist_ok=True)
    (library_dir / f"{paper_id}.pdf").write_bytes(b"%PDF-1.4\n%fake\n")
    vault_dir = tmp_path / "Vault"
    (vault_dir / "00_Index").mkdir(parents=True, exist_ok=True)
    (vault_dir / "Inbox").mkdir(parents=True, exist_ok=True)
    note_path = vault_dir / "Inbox" / f"{paper_id}.md"
    note_path.write_text(
        "---\n"
        "type: clinical_paper\n"
        "slot: clinical\n"
        "---\n\n"
        "# Paper\n",
        encoding="utf-8",
    )
    (vault_dir / "00_Index" / "paper_collection.csv").write_text(
        f"Paper_ID,DOI,Title,Note_Path\n{paper_id},10.1000/test,Clinical Artifact Title,Inbox/{paper_id}.md\n",
        encoding="utf-8",
    )

    fake_config = SimpleNamespace(
        paths=SimpleNamespace(
            library_dir=library_dir,
            obsidian_vault=vault_dir,
            index_all=Path("00_Index/paper_collection.csv"),
        ),
        llm=SimpleNamespace(
            features=SimpleNamespace(clinical_extraction=SimpleNamespace(enabled=True)),
            timeout_seconds=15,
            max_retries=0,
            mode="local",
            local=SimpleNamespace(provider="ollama", models={}),
            cloud=SimpleNamespace(provider="openai"),
        ),
        entity_aliases={},
        agents=SimpleNamespace(main_model="unit-test-model"),
    )
    monkeypatch.setattr(job_runner, "load_config", lambda: fake_config)
    monkeypatch.setattr(job_runner, "_resolve_pdf_path_from_db", lambda _: None)
    monkeypatch.setattr(job_runner, "_resolve_persona_hint", lambda _persona_id: None)
    monkeypatch.setattr(job_runner, "_load_similar_feedback_top3", lambda **_kwargs: [])

    class FakeIngestAgent:
        def __init__(self, **_kwargs):
            self.last_table_extraction_meta = {}

        def process_v2(self, pdf_path: str):
            return _make_doc(
                paper_id,
                pdf_path,
                text="Reminder: Maya's lumbar puncture appointment is scheduled tomorrow.",
            )

    class FakeIndexerAgent:
        def process(self, doc):
            return IndexArtifact(doc_id=doc.document_id, vector_store_id="smoke", chunk_count=1, chunks=[])

    class FakeReaderAgent:
        def __init__(self, model_name: str = "llama3:latest", persona_hint: str | None = None):
            self.model_name = model_name

        def analyze(self, doc):
            return ClaimSet(
                doc_id=doc.document_id,
                claims=[ScientificClaim(claim_id="c1", type="efficacy", statement="claim", confidence=0.9)],
            )

    calls = {"clinical": 0}

    class FakeClinicalProvider:
        def is_available(self):
            return True

        def extract_biomedical_clinical_data(self, _paper_payload, _methods_snippet=""):
            calls["clinical"] += 1
            raise AssertionError("privacy preflight should block before calling provider")

    monkeypatch.setattr(job_runner, "IngestAgent", FakeIngestAgent)
    monkeypatch.setattr(job_runner, "IndexerAgent", FakeIndexerAgent)
    monkeypatch.setattr(job_runner, "ReaderAgent", FakeReaderAgent)
    monkeypatch.setattr(job_runner, "get_llm_provider", lambda *_args, **_kwargs: FakeClinicalProvider())

    result = asyncio.run(
        job_runner.run_deepread_job(
            job_id="job_privacy_block",
            paper_id=paper_id,
            persona_id="default",
            run_verify=False,
            run_id="run_privacy_block",
            progress_callback=lambda _event: asyncio.sleep(0),
        )
    )

    assert result["status"] == "succeeded"
    artifact_dir = Path(result["artifact_dir"])
    run_meta = json.loads((artifact_dir / "run_meta.json").read_text(encoding="utf-8"))
    bootstrap = json.loads((artifact_dir / "bootstrap_meta.json").read_text(encoding="utf-8"))

    assert calls["clinical"] == 0
    assert not (artifact_dir / "clinical_extraction.json").exists()
    assert bootstrap["clinical_extraction_status"] == "privacy_preflight_blocked"
    assert run_meta["clinical_extraction_status"] == "privacy_preflight_blocked"
    privacy_preflight = run_meta["inference_lanes"]["clinical_extraction"]["privacy_preflight"]
    assert privacy_preflight["mode"] == "block_on_review"
    assert privacy_preflight["status"] == "blocked"
    assert privacy_preflight["summary"]["manual_review_records"] == 1
    assert privacy_preflight["findings"][0]["text_preview"] == "<short_private_name>"


def test_run_deepread_job_reports_invalid_privacy_preflight_mode(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("LATTICE_PRIVACY_PREFLIGHT_MODE", "surprise")

    paper_id = "paper_clinical_privacy_bad_mode_001"
    library_dir = tmp_path / "Library"
    library_dir.mkdir(parents=True, exist_ok=True)
    (library_dir / f"{paper_id}.pdf").write_bytes(b"%PDF-1.4\n%fake\n")
    vault_dir = tmp_path / "Vault"
    (vault_dir / "00_Index").mkdir(parents=True, exist_ok=True)
    (vault_dir / "Inbox").mkdir(parents=True, exist_ok=True)
    note_path = vault_dir / "Inbox" / f"{paper_id}.md"
    note_path.write_text(
        "---\n"
        "type: clinical_paper\n"
        "slot: clinical\n"
        "---\n\n"
        "# Paper\n",
        encoding="utf-8",
    )
    (vault_dir / "00_Index" / "paper_collection.csv").write_text(
        f"Paper_ID,DOI,Title,Note_Path\n{paper_id},10.1000/test,Clinical Artifact Title,Inbox/{paper_id}.md\n",
        encoding="utf-8",
    )

    fake_config = SimpleNamespace(
        paths=SimpleNamespace(
            library_dir=library_dir,
            obsidian_vault=vault_dir,
            index_all=Path("00_Index/paper_collection.csv"),
        ),
        llm=SimpleNamespace(
            features=SimpleNamespace(clinical_extraction=SimpleNamespace(enabled=True)),
            timeout_seconds=15,
            max_retries=0,
            mode="local",
            local=SimpleNamespace(provider="ollama", models={}),
            cloud=SimpleNamespace(provider="openai"),
        ),
        entity_aliases={},
        agents=SimpleNamespace(main_model="unit-test-model"),
    )
    monkeypatch.setattr(job_runner, "load_config", lambda: fake_config)
    monkeypatch.setattr(job_runner, "_resolve_pdf_path_from_db", lambda _: None)
    monkeypatch.setattr(job_runner, "_resolve_persona_hint", lambda _persona_id: None)
    monkeypatch.setattr(job_runner, "_load_similar_feedback_top3", lambda **_kwargs: [])

    class FakeIngestAgent:
        def __init__(self, **_kwargs):
            self.last_table_extraction_meta = {}

        def process_v2(self, pdf_path: str):
            return _make_doc(paper_id, pdf_path)

    class FakeIndexerAgent:
        def process(self, doc):
            return IndexArtifact(doc_id=doc.document_id, vector_store_id="smoke", chunk_count=1, chunks=[])

    class FakeReaderAgent:
        def __init__(self, model_name: str = "llama3:latest", persona_hint: str | None = None):
            self.model_name = model_name

        def analyze(self, doc):
            return ClaimSet(
                doc_id=doc.document_id,
                claims=[ScientificClaim(claim_id="c1", type="efficacy", statement="claim", confidence=0.9)],
            )

    calls = {"clinical": 0}

    class FakeClinicalProvider:
        def is_available(self):
            return True

        def extract_biomedical_clinical_data(self, _paper_payload, _methods_snippet=""):
            calls["clinical"] += 1
            raise AssertionError("invalid privacy preflight mode should skip provider call")

    monkeypatch.setattr(job_runner, "IngestAgent", FakeIngestAgent)
    monkeypatch.setattr(job_runner, "IndexerAgent", FakeIndexerAgent)
    monkeypatch.setattr(job_runner, "ReaderAgent", FakeReaderAgent)
    monkeypatch.setattr(job_runner, "get_llm_provider", lambda *_args, **_kwargs: FakeClinicalProvider())

    result = asyncio.run(
        job_runner.run_deepread_job(
            job_id="job_privacy_bad_mode",
            paper_id=paper_id,
            persona_id="default",
            run_verify=False,
            run_id="run_privacy_bad_mode",
            progress_callback=lambda _event: asyncio.sleep(0),
        )
    )

    assert result["status"] == "succeeded"
    artifact_dir = Path(result["artifact_dir"])
    run_meta = json.loads((artifact_dir / "run_meta.json").read_text(encoding="utf-8"))
    bootstrap = json.loads((artifact_dir / "bootstrap_meta.json").read_text(encoding="utf-8"))

    assert calls["clinical"] == 0
    assert bootstrap["clinical_extraction_status"] == "failed:invalid_privacy_preflight_mode"
    assert run_meta["clinical_extraction_status"] == "failed:invalid_privacy_preflight_mode"
    assert "LATTICE_PRIVACY_PREFLIGHT_MODE" in run_meta["privacy_preflight_error"]


def test_run_deepread_job_skips_clinical_extraction_for_non_clinical_note(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    paper_id = "paper_nonclinical_job_001"
    library_dir = tmp_path / "Library"
    library_dir.mkdir(parents=True, exist_ok=True)
    (library_dir / f"{paper_id}.pdf").write_bytes(b"%PDF-1.4\n%fake\n")
    vault_dir = tmp_path / "Vault"
    (vault_dir / "00_Index").mkdir(parents=True, exist_ok=True)
    (vault_dir / "Inbox").mkdir(parents=True, exist_ok=True)
    note_path = vault_dir / "Inbox" / "paper_nonclinical_job_001.md"
    note_path.write_text(
        "---\n"
        "type: paper\n"
        "slot: mechanism\n"
        "---\n\n"
        "# Paper\n",
        encoding="utf-8",
    )
    (vault_dir / "00_Index" / "paper_collection.csv").write_text(
        "Paper_ID,DOI,Title,Note_Path\n"
        "paper_nonclinical_job_001,10.1000/test,Mechanism Title,Inbox/paper_nonclinical_job_001.md\n",
        encoding="utf-8",
    )

    fake_config = SimpleNamespace(
        paths=SimpleNamespace(
            library_dir=library_dir,
            obsidian_vault=vault_dir,
            index_all=Path("00_Index/paper_collection.csv"),
        ),
        llm=SimpleNamespace(
            features=SimpleNamespace(specialty_trial_extraction=SimpleNamespace(enabled=True)),
            timeout_seconds=15,
            max_retries=0,
            mode="local",
            local=SimpleNamespace(provider="ollama", models={}),
            cloud=SimpleNamespace(provider="openai"),
        ),
        entity_aliases={},
        agents=SimpleNamespace(main_model="unit-test-model"),
    )
    monkeypatch.setattr(job_runner, "load_config", lambda: fake_config)
    monkeypatch.setattr(job_runner, "_resolve_pdf_path_from_db", lambda _: None)
    monkeypatch.setattr(job_runner, "_resolve_persona_hint", lambda _persona_id: None)
    monkeypatch.setattr(job_runner, "_load_similar_feedback_top3", lambda **_kwargs: [])

    class FakeIngestAgent:
        def __init__(self, **_kwargs):
            self.last_table_extraction_meta = {}

        def process_v2(self, pdf_path: str):
            return _make_doc(paper_id, pdf_path)

    class FakeIndexerAgent:
        def process(self, doc):
            return IndexArtifact(doc_id=doc.document_id, vector_store_id="smoke", chunk_count=1, chunks=[])

    class FakeReaderAgent:
        def __init__(self, model_name: str = "llama3:latest", persona_hint: str | None = None):
            self.model_name = model_name

        def analyze(self, doc):
            return ClaimSet(
                doc_id=doc.document_id,
                claims=[ScientificClaim(claim_id="c1", type="efficacy", statement="claim", confidence=0.9)],
            )

    called = {"count": 0}

    def _fake_get_llm_provider(*_args, **_kwargs):
        called["count"] += 1
        raise AssertionError("get_llm_provider should not be called for non-clinical notes")

    monkeypatch.setattr(job_runner, "IngestAgent", FakeIngestAgent)
    monkeypatch.setattr(job_runner, "IndexerAgent", FakeIndexerAgent)
    monkeypatch.setattr(job_runner, "ReaderAgent", FakeReaderAgent)
    monkeypatch.setattr(job_runner, "get_llm_provider", _fake_get_llm_provider)

    result = asyncio.run(
        job_runner.run_deepread_job(
            job_id="job_nonclinical_sidecar",
            paper_id=paper_id,
            persona_id="default",
            run_verify=False,
            run_id="run_nonclinical_sidecar",
            progress_callback=lambda _event: asyncio.sleep(0),
        )
    )

    assert result["status"] == "succeeded"
    artifact_dir = Path(result["artifact_dir"])
    bootstrap = json.loads((artifact_dir / "bootstrap_meta.json").read_text(encoding="utf-8"))
    run_meta = json.loads((artifact_dir / "run_meta.json").read_text(encoding="utf-8"))
    updated_note = note_path.read_text(encoding="utf-8")

    assert called["count"] == 0
    assert not (artifact_dir / "clinical_extraction.json").exists()
    assert bootstrap["artifact_clinical_extraction_written"] is False
    assert bootstrap["clinical_extraction_status"] == "not_clinical_note"
    assert bootstrap["clinical_extraction_note_type"] == "non_clinical"
    assert run_meta["clinical_extraction_status"] == "not_clinical_note"
    assert run_meta["selected_backend"] == "local"
    assert run_meta["payload_class"] == "local_only"
    assert run_meta["redaction_applied"] is False
    assert "clinical_extraction" not in run_meta["inference_lanes"]
    assert run_meta["inference_lanes"]["reader"]["selected_backend"] == "local"
    assert run_meta["inference_lanes"]["reader"]["payload_class"] == "local_only"
    assert "### 🏥 Clinical Extraction" not in updated_note
