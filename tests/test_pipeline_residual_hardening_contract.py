import asyncio
import json
import sqlite3
from pathlib import Path
from types import SimpleNamespace

import src.db_utils as db_utils
import backend.services.job_runner as job_runner_mod
from backend.routers.paper_notes import _build_references
from src.schemas import PaperStatus
from src.schemas.provenance import PaperRunProvenanceSummary, ProvenanceAspect


def test_paper_status_lifecycle_contract_is_documented():
    spec = Path("docs/Lattice_v3_Master_Spec.md").read_text(encoding="utf-8")

    assert "Paper status lifecycle contract" in spec
    assert "Deep Read completion may transition" in spec
    for status in ("NEW", "FETCHED", "PDF_DOWNLOADED", "APPROVED", "INDEXED", "FAILED", "QUARANTINED"):
        assert status in spec


def test_pipeline_residual_risk_runbook_has_verifiable_sections():
    runbook = Path("docs/PIPELINE_RESIDUAL_RISK_RUNBOOK.md").read_text(encoding="utf-8")

    for heading in (
        "Production Chroma Verification",
        "Worker Restart Verification",
        "Hard-Scanned PDF Verification",
    ):
        assert heading in runbook
    for command_hint in (
        "python -m src.indexer",
        "GET /ops/stale-jobs",
        "ocrmypdf --version",
    ):
        assert command_hint in runbook


def test_mark_paper_deepread_indexed_only_promotes_open_source_ready_states(tmp_path):
    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()
        source_ready = ["NEW", "FETCHED", "PDF_DOWNLOADED", "APPROVED"]
        protected = ["INDEXED", "FAILED", "QUARANTINED", "DONE", "PENDING_REVIEW"]

        for status in source_ready + protected:
            db_utils.save_paper_state(f"paper_{status.lower()}", status, "test", "2026-05-14", status=status)

        for status in source_ready:
            assert job_runner_mod._mark_paper_deepread_indexed(f"paper_{status.lower()}") is True
        for status in protected:
            assert job_runner_mod._mark_paper_deepread_indexed(f"paper_{status.lower()}") is False

        conn = sqlite3.connect(db_utils.DB_PATH)
        rows = dict(conn.execute("SELECT paper_id, status FROM papers").fetchall())
        conn.close()

        for status in source_ready:
            assert rows[f"paper_{status.lower()}"] == PaperStatus.INDEXED
        for status in protected:
            assert rows[f"paper_{status.lower()}"] == status
    finally:
        db_utils.DB_PATH = original_db_path


def test_provenance_schema_covers_metadata_figure_and_reference_aspects():
    summary = PaperRunProvenanceSummary(
        paper_id="paper-1",
        run_id="run-1",
        metadata=ProvenanceAspect(
            kind="metadata",
            status="captured",
            source_artifacts=["run_meta.json", "document_artifact.json"],
            source_fields=["paper_id", "pdf_sha256", "parser_backend"],
        ),
        figures=ProvenanceAspect(
            kind="figure",
            status="captured",
            source_artifacts=["document_artifact.json", "figure_captions.json"],
            artifact_path="figure_captions.json",
            count=2,
        ),
        references=ProvenanceAspect(
            kind="reference",
            status="partial",
            source_artifacts=["note_frontmatter", "note_references_section"],
            source_fields=["frontmatter.doi", "references.markdown_links"],
            count=3,
        ),
    )

    payload = summary.model_dump(mode="json")

    assert payload["schema_version"] == "paper_run_provenance.v1"
    assert payload["layer"] == "review_gate_artifact"
    assert payload["canonical_status"] == "non_canonical"
    assert payload["metadata"]["kind"] == "metadata"
    assert payload["figures"]["count"] == 2
    assert payload["references"]["source_fields"] == ["frontmatter.doi", "references.markdown_links"]


def test_failed_run_meta_records_minimal_provenance_without_secrets(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    library_dir = tmp_path / "Library"
    library_dir.mkdir(parents=True, exist_ok=True)
    vault_dir = tmp_path / "Vault"
    vault_dir.mkdir(parents=True, exist_ok=True)
    paper_id = "paper_provenance_failed_001"
    run_id = "run_provenance_failed"
    secret = "sk-live-provenance-secret"
    (library_dir / f"{paper_id}.pdf").write_bytes(b"%PDF-1.4\n%fake\n")

    monkeypatch.setattr(
        job_runner_mod,
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
                ocr_min_text_chars=200,
                enable_table_pass2_ocr=False,
                enable_cloud_table_fallback=True,
                cloud_table_page_budget=1,
                cloud_table_model="gpt-4o-mini",
                cloud_table_base_url=None,
                cloud_table_api_key=secret,
                cloud_table_timeout_seconds=30,
            ),
        ),
    )

    class FakeIngestAgent:
        def __init__(self, *args, **kwargs):
            self.last_table_extraction_meta = {
                "parser_failure_code": "PDF_CORRUPTED",
                "parser_failure_reason": "xref table is unreadable",
            }

        def process_v2(self, pdf_path: str):
            return None

    monkeypatch.setattr(job_runner_mod, "IngestAgent", FakeIngestAgent)

    result = asyncio.run(
        job_runner_mod.run_deepread_job(
            job_id="job-provenance-failed",
            paper_id=paper_id,
            run_id=run_id,
        )
    )

    assert result["status"] == "failed"
    run_meta_path = job_runner_mod.artifact_run_dir(paper_id, run_id) / "run_meta.json"
    raw_run_meta = run_meta_path.read_text(encoding="utf-8")
    run_meta = json.loads(raw_run_meta)

    assert secret not in raw_run_meta
    assert run_meta["provenance"]["schema_version"] == "paper_run_provenance.v1"
    assert run_meta["provenance"]["metadata"]["status"] == "captured"
    assert run_meta["provenance"]["metadata"]["source_fields"] == [
        "paper_id",
        "pdf_sha256",
        "pdf_mtime",
        "parser_backend",
    ]
    assert run_meta["provenance"]["figures"]["status"] == "not_run"
    assert run_meta["provenance"]["references"]["status"] == "not_run"


def test_paper_note_references_include_minimal_reference_provenance():
    references = _build_references(
        {
            "pdf_url": "/papers/paper-1/pdf",
            "doi": "10.1000/example",
            "zotero_link": "zotero://select/items/ABC123",
        },
        "[Supplement](https://example.org/supplement)",
    )

    by_source = {reference.source: reference for reference in references}

    assert by_source["pdf"].provenance is not None
    assert by_source["pdf"].provenance.kind == "reference"
    assert by_source["pdf"].provenance.source_fields == ["frontmatter.pdf_url"]
    assert by_source["doi"].provenance.source_fields == ["frontmatter.doi"]
    assert by_source["zotero"].provenance.source_fields == ["frontmatter.zotero_link"]
    assert by_source["external"].provenance.source_fields == ["references.markdown_links"]
