import asyncio
import json
import sqlite3
from pathlib import Path
from types import SimpleNamespace

import src.db_utils as db_utils
import backend.services.job_runner as job_runner_mod
from backend.routers.paper_notes import _build_references
from src.schemas import PaperStatus
from src.schemas.provenance import (
    PROVENANCE_SOURCE_DOCUMENT_ARTIFACT,
    PROVENANCE_SOURCE_FIGURE_CAPTIONS,
    PROVENANCE_SOURCE_NOTE_FRONTMATTER,
    PROVENANCE_SOURCE_NOTE_REFERENCES_SECTION,
    PaperRunProvenanceSummary,
    ProvenanceAspect,
)


def _init_minimal_papers_db(path: Path) -> None:
    conn = sqlite3.connect(path)
    conn.execute(
        """
        CREATE TABLE papers (
            paper_id TEXT PRIMARY KEY,
            title TEXT,
            source TEXT,
            processed_date TEXT,
            status TEXT,
            processed_at TEXT,
            updated_at TEXT
        )
        """
    )
    conn.commit()
    conn.close()


def test_mark_paper_deepread_indexed_only_promotes_open_source_ready_states(tmp_path):
    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        _init_minimal_papers_db(db_utils.DB_PATH)
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


def test_mark_paper_deepread_indexed_promotes_doi_alias_rows(tmp_path):
    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        conn = sqlite3.connect(db_utils.DB_PATH)
        conn.execute(
            """
            CREATE TABLE papers (
                paper_id TEXT PRIMARY KEY,
                doi TEXT,
                status TEXT,
                updated_at TEXT
            )
            """
        )
        conn.execute(
            "INSERT INTO papers (paper_id, doi, status) VALUES (?, ?, ?)",
            ("internal-1", "10.1000/example", "APPROVED"),
        )
        conn.commit()
        conn.close()

        assert job_runner_mod._mark_paper_deepread_indexed("doi:10.1000/example") is True

        conn = sqlite3.connect(db_utils.DB_PATH)
        row = conn.execute("SELECT status FROM papers WHERE paper_id = ?", ("internal-1",)).fetchone()
        conn.close()

        assert row[0] == PaperStatus.INDEXED
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
            source_artifacts=[
                PROVENANCE_SOURCE_NOTE_FRONTMATTER,
                PROVENANCE_SOURCE_NOTE_REFERENCES_SECTION,
            ],
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


def test_run_provenance_only_lists_written_document_artifact_sources():
    before_ingest = job_runner_mod._build_run_provenance_summary(paper_id="paper-1", run_id="run-1")
    after_document = job_runner_mod._build_run_provenance_summary(
        paper_id="paper-1",
        run_id="run-1",
        document_artifact_written=True,
        figure_caption_artifact=PROVENANCE_SOURCE_FIGURE_CAPTIONS,
        figure_caption_count=1,
        figure_status="captured",
    )

    assert before_ingest["metadata"]["source_artifacts"] == ["run_meta.json"]
    assert before_ingest["figures"]["source_artifacts"] == []
    assert after_document["metadata"]["source_artifacts"] == [
        "run_meta.json",
        PROVENANCE_SOURCE_DOCUMENT_ARTIFACT,
    ]
    assert after_document["figures"]["source_artifacts"] == [
        PROVENANCE_SOURCE_DOCUMENT_ARTIFACT,
        PROVENANCE_SOURCE_FIGURE_CAPTIONS,
    ]


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
    assert run_meta["provenance"]["metadata"]["source_artifacts"] == ["run_meta.json"]
    assert run_meta["provenance"]["metadata"]["source_fields"] == [
        "paper_id",
        "pdf_sha256",
        "pdf_mtime",
        "parser_backend",
    ]
    assert run_meta["provenance"]["figures"]["status"] == "not_run"
    assert run_meta["provenance"]["figures"]["source_artifacts"] == []
    assert run_meta["provenance"]["references"]["status"] == "not_run"


def test_paper_note_references_include_minimal_reference_provenance(monkeypatch):
    monkeypatch.setenv("PAPERPIPE_MASK_LOCAL_PATHS", "0")

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
    assert by_source["pdf"].provenance.source_artifacts == [PROVENANCE_SOURCE_NOTE_FRONTMATTER]
    assert by_source["pdf"].provenance.source_fields == ["frontmatter.pdf_url"]
    assert by_source["external"].provenance.source_artifacts == [PROVENANCE_SOURCE_NOTE_REFERENCES_SECTION]
    assert by_source["doi"].provenance.source_fields == ["frontmatter.doi"]
    assert by_source["zotero"].provenance.source_fields == ["frontmatter.zotero_link"]
    assert by_source["external"].provenance.source_fields == ["references.markdown_links"]


def test_duplicate_paper_note_references_merge_reference_provenance():
    references = _build_references(
        {"doi": "10.1000/example"},
        "[DOI](https://doi.org/10.1000/example)",
    )

    assert len(references) == 1
    assert references[0].source == "doi"
    assert references[0].provenance.source_artifacts == [
        PROVENANCE_SOURCE_NOTE_FRONTMATTER,
        PROVENANCE_SOURCE_NOTE_REFERENCES_SECTION,
    ]
    assert references[0].provenance.source_fields == [
        "frontmatter.doi",
        "references.markdown_links",
    ]
