from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
import asyncio
import json
import sqlite3

import src.db_utils as db_utils
import src.jobs.worker as worker_mod
from src.jobs.queue import JobQueue
import backend.services.job_runner as job_runner_mod
from backend.services.job_runner import _ingest_runtime_options_for_run_meta

from src.contracts.document_artifact_v2 import (
    DocumentArtifactV2,
    ArtifactMetaV2,
    PageV2,
    BlockV2,
    LineV2,
    SpanV2,
)
from src.schemas.agent_artifacts import (
    DocumentChunk,
    EvidenceSpan,
    IndexArtifact,
    ClaimSet,
    ScientificClaim,
    StatsReport,
    StatCheckEntry,
    VerificationStatus,
)


def test_ingest_runtime_options_for_run_meta_redacts_cloud_table_api_key():
    persisted = _ingest_runtime_options_for_run_meta(
        {
            "parser_backend": "docling",
            "cloud_table_fallback_enabled": True,
            "cloud_table_api_key": "sk-secret-value",
        }
    )

    assert persisted["parser_backend"] == "docling"
    assert persisted["cloud_table_fallback_enabled"] is True
    assert persisted["cloud_table_api_key_configured"] is True
    assert "cloud_table_api_key" not in persisted
    assert "sk-secret-value" not in json.dumps(persisted)


def test_run_meta_redacts_cloud_table_api_key_on_failed_ingest(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    library_dir = tmp_path / "Library"
    library_dir.mkdir(parents=True, exist_ok=True)
    vault_dir = tmp_path / "Vault"
    vault_dir.mkdir(parents=True, exist_ok=True)
    paper_id = "paper_secret_redaction_001"
    run_id = "run_secret_redaction"
    secret = "sk-live-runmeta-secret-abcdef123456"
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
                enable_ocr_fallback=False,
                ocr_lang="eng",
                ocr_min_text_chars=200,
                enable_table_pass2_ocr=False,
                enable_cloud_table_fallback=True,
                cloud_table_page_budget=2,
                cloud_table_model="gpt-4o-mini",
                cloud_table_base_url=None,
                cloud_table_api_key=secret,
                cloud_table_timeout_seconds=30,
            ),
        ),
    )

    class FakeIngestAgent:
        def __init__(self, *args, **kwargs):
            self.kwargs = kwargs
            self.last_table_extraction_meta = {
                "parser_failure_code": "PDF_CORRUPTED",
                "parser_failure_reason": "xref table is unreadable",
            }

        def process_v2(self, pdf_path: str):
            return None

    monkeypatch.setattr(job_runner_mod, "IngestAgent", FakeIngestAgent)

    result = asyncio.run(
        job_runner_mod.run_deepread_job(
            job_id="job-secret-redaction",
            paper_id=paper_id,
            run_id=run_id,
        )
    )

    assert result["status"] == "failed"
    artifact_dir = job_runner_mod.artifact_run_dir(paper_id, run_id)
    run_meta_path = artifact_dir / "run_meta.json"
    raw_run_meta = run_meta_path.read_text(encoding="utf-8")
    run_meta = json.loads(raw_run_meta)

    assert secret not in raw_run_meta
    assert "cloud_table_api_key" not in run_meta["ingest_options"]
    assert run_meta["ingest_options"]["cloud_table_api_key_configured"] is True
    assert run_meta["status"] == "failed"
    assert run_meta["parser_failure_code"] == "PDF_CORRUPTED"
    assert run_meta["parser_failure_reason"] == "xref table is unreadable"


def test_failed_runner_preserves_original_error_when_handoff_write_fails(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    library_dir = tmp_path / "Library"
    library_dir.mkdir(parents=True, exist_ok=True)
    vault_dir = tmp_path / "Vault"
    vault_dir.mkdir(parents=True, exist_ok=True)
    paper_id = "paper_failed_handoff_001"
    run_id = "run_failed_handoff"
    (library_dir / f"{paper_id}.pdf").write_bytes(b"%PDF-1.4\n%fake\n")

    monkeypatch.setattr(
        job_runner_mod,
        "load_config",
        lambda: SimpleNamespace(
            paths=SimpleNamespace(
                library_dir=library_dir,
                obsidian_vault=vault_dir,
                index_all=Path("00_Index/paper_collection.csv"),
            )
        ),
    )

    class FakeIngestAgent:
        def __init__(self, *args, **kwargs):
            pass

        def process_v2(self, pdf_path: str):
            return None

    def fail_handoff(*args, **kwargs):
        raise RuntimeError("handoff exploded")

    monkeypatch.setattr(job_runner_mod, "IngestAgent", FakeIngestAgent)
    monkeypatch.setattr(job_runner_mod, "write_deepread_handoff_artifacts", fail_handoff)

    result = asyncio.run(
        job_runner_mod.run_deepread_job(
            job_id="job-failed-handoff",
            paper_id=paper_id,
            run_id=run_id,
        )
    )

    assert result["status"] == "failed"
    assert result["error"] == "Ingestion failed to produce artifact"

    artifact_dir = job_runner_mod.artifact_run_dir(paper_id, run_id)
    run_meta = json.loads((artifact_dir / "run_meta.json").read_text(encoding="utf-8"))
    bootstrap_meta = json.loads((artifact_dir / "bootstrap_meta.json").read_text(encoding="utf-8"))

    assert run_meta["status"] == "failed"
    assert run_meta["error"] == "Ingestion failed to produce artifact"
    assert run_meta["handoff_write_error"] == "handoff exploded"
    assert bootstrap_meta["handoff_write_error"] == "handoff exploded"
    assert bootstrap_meta["artifact_acceptance_contract_written"] is False
    assert bootstrap_meta["artifact_quality_gate_written"] is False


def test_mark_paper_deepread_indexed_preserves_terminal_or_blocked_status(tmp_path):
    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()
        db_utils.save_paper_state("paper_new", "New", "test", "2026-05-10", status="NEW")
        db_utils.save_paper_state("paper_done", "Done", "test", "2026-05-10", status="DONE")
        db_utils.save_paper_state("paper_quarantined", "Quarantined", "test", "2026-05-10", status="QUARANTINED")

        assert job_runner_mod._mark_paper_deepread_indexed("paper_new") is True
        assert job_runner_mod._mark_paper_deepread_indexed("paper_done") is False
        assert job_runner_mod._mark_paper_deepread_indexed("paper_quarantined") is False

        conn = sqlite3.connect(db_utils.DB_PATH)
        rows = dict(conn.execute("SELECT paper_id, status FROM papers").fetchall())
        conn.close()

        assert rows["paper_new"] == "INDEXED"
        assert rows["paper_done"] == "DONE"
        assert rows["paper_quarantined"] == "QUARANTINED"
    finally:
        db_utils.DB_PATH = original_db_path


def test_worker_passes_current_job_runner_signature_kwargs(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()
        captured: dict[str, object] = {}
        artifact_dir = tmp_path / "artifacts" / "paper_signature_001" / "run"

        async def fake_run_deepread_job(
            *,
            job_id: str,
            paper_id: str,
            persona_id: str,
            reasoning_persona: str | None,
            profile_id: str | None,
            parser_backend: str | None,
            run_verify: bool,
            clean_reindex: bool,
            run_id: str,
            progress_callback,
            cancel_check,
        ):
            captured.update(
                {
                    "job_id": job_id,
                    "paper_id": paper_id,
                    "persona_id": persona_id,
                    "reasoning_persona": reasoning_persona,
                    "profile_id": profile_id,
                    "parser_backend": parser_backend,
                    "run_verify": run_verify,
                    "clean_reindex": clean_reindex,
                    "run_id": run_id,
                    "progress_callback": progress_callback,
                    "cancel_check": cancel_check,
                    "cancel_check_during_runner": cancel_check(),
                }
            )
            return {"status": "succeeded", "artifact_dir": str(artifact_dir)}

        monkeypatch.setattr(worker_mod, "run_deepread_job", fake_run_deepread_job)

        queue = JobQueue()
        job_id = queue.enqueue(
            paper_id="paper_signature_001",
            clean_reindex=True,
            run_verify=True,
            persona_id="default",
            reasoning_persona="researcher",
            profile_id="profile-alpha",
            parser_backend="docling",
        )
        claimed = queue.claim_next_job()
        assert claimed is not None

        worker = worker_mod.Worker()
        worker.process_job(claimed)

        done = queue.get_job(job_id)
        assert done is not None
        assert done.status == "completed"
        assert done.progress == 100
        assert done.artifact_dir == str(artifact_dir)
        assert captured["job_id"] == job_id
        assert captured["paper_id"] == "paper_signature_001"
        assert captured["persona_id"] == "profile-alpha"
        assert captured["reasoning_persona"] == "researcher"
        assert captured["profile_id"] == "profile-alpha"
        assert captured["parser_backend"] == "docling"
        assert captured["run_verify"] is True
        assert captured["clean_reindex"] is True
        assert captured["run_id"] == claimed.run_id
        assert callable(captured["progress_callback"])
        assert callable(captured["cancel_check"])
        assert captured["cancel_check_during_runner"] is False
    finally:
        db_utils.DB_PATH = original_db_path


def test_worker_still_supports_legacy_job_runner_signature_without_new_persona_kwargs(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()
        captured: dict[str, object] = {}
        artifact_dir = tmp_path / "artifacts" / "paper_legacy_signature_001" / "run"

        async def fake_legacy_run_deepread_job(
            *,
            job_id: str,
            paper_id: str,
            persona_id: str,
            run_verify: bool,
            clean_reindex: bool,
            run_id: str,
            progress_callback,
            cancel_check,
        ):
            captured.update(
                {
                    "job_id": job_id,
                    "paper_id": paper_id,
                    "persona_id": persona_id,
                    "run_verify": run_verify,
                    "clean_reindex": clean_reindex,
                    "run_id": run_id,
                    "progress_callback": progress_callback,
                    "cancel_check": cancel_check,
                }
            )
            return {"status": "succeeded", "artifact_dir": str(artifact_dir)}

        monkeypatch.setattr(worker_mod, "run_deepread_job", fake_legacy_run_deepread_job)

        queue = JobQueue()
        job_id = queue.enqueue(
            paper_id="paper_legacy_signature_001",
            clean_reindex=True,
            run_verify=True,
            persona_id="legacy-profile",
            reasoning_persona="researcher",
            profile_id="legacy-profile",
            parser_backend="docling",
        )
        claimed = queue.claim_next_job()
        assert claimed is not None

        worker = worker_mod.Worker()
        worker.process_job(claimed)

        done = queue.get_job(job_id)
        assert done is not None
        assert done.status == "completed"
        assert done.artifact_dir == str(artifact_dir)
        assert captured["job_id"] == job_id
        assert captured["paper_id"] == "paper_legacy_signature_001"
        assert captured["persona_id"] == "legacy-profile"
        assert captured["run_verify"] is True
        assert captured["clean_reindex"] is True
        assert captured["run_id"] == claimed.run_id
    finally:
        db_utils.DB_PATH = original_db_path


def test_worker_still_supports_older_job_runner_signature_without_clean_reindex(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()
        captured: dict[str, object] = {}
        artifact_dir = tmp_path / "artifacts" / "paper_older_signature_001" / "run"

        async def fake_older_run_deepread_job(
            *,
            job_id: str,
            paper_id: str,
            persona_id: str,
            run_verify: bool,
            run_id: str,
            progress_callback,
            cancel_check,
        ):
            captured.update(
                {
                    "job_id": job_id,
                    "paper_id": paper_id,
                    "persona_id": persona_id,
                    "run_verify": run_verify,
                    "run_id": run_id,
                    "progress_callback": progress_callback,
                    "cancel_check": cancel_check,
                }
            )
            return {"status": "succeeded", "artifact_dir": str(artifact_dir)}

        monkeypatch.setattr(worker_mod, "run_deepread_job", fake_older_run_deepread_job)

        queue = JobQueue()
        job_id = queue.enqueue(
            paper_id="paper_older_signature_001",
            clean_reindex=True,
            run_verify=True,
            persona_id="older-profile",
            reasoning_persona="researcher",
            profile_id="older-profile",
            parser_backend="docling",
        )
        claimed = queue.claim_next_job()
        assert claimed is not None

        worker = worker_mod.Worker()
        worker.process_job(claimed)

        done = queue.get_job(job_id)
        assert done is not None
        assert done.status == "completed"
        assert done.artifact_dir == str(artifact_dir)
        assert captured["job_id"] == job_id
        assert captured["paper_id"] == "paper_older_signature_001"
        assert captured["persona_id"] == "older-profile"
        assert captured["run_verify"] is True
        assert captured["run_id"] == claimed.run_id
    finally:
        db_utils.DB_PATH = original_db_path


def test_worker_does_not_retry_internal_type_error_as_signature_compatibility(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()
        calls = {"count": 0}
        artifact_dir = tmp_path / "artifacts" / "paper_internal_typeerror" / "run"

        async def fake_run_deepread_job(**_kwargs):
            calls["count"] += 1
            if calls["count"] == 1:
                raise TypeError("internal parser bug")
            return {"status": "succeeded", "artifact_dir": str(artifact_dir)}

        monkeypatch.setattr(worker_mod, "run_deepread_job", fake_run_deepread_job)

        queue = JobQueue()
        job_id = queue.enqueue(paper_id="paper_internal_typeerror")
        claimed = queue.claim_next_job()
        assert claimed is not None

        worker = worker_mod.Worker()
        worker.process_job(claimed)

        done = queue.get_job(job_id)
        assert done is not None
        assert calls["count"] == 1
        assert done.status == "failed"
        assert done.error_message == "internal parser bug"
    finally:
        db_utils.DB_PATH = original_db_path


def test_worker_uses_real_job_runner_chain_smoke(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()

        library_dir = tmp_path / "Library"
        library_dir.mkdir(parents=True, exist_ok=True)
        vault_dir = tmp_path / "Vault"
        (vault_dir / "00_Index").mkdir(parents=True, exist_ok=True)
        (vault_dir / "Inbox").mkdir(parents=True, exist_ok=True)
        paper_id = "paper_chain_001"
        pdf_path = library_dir / f"{paper_id}.pdf"
        pdf_path.write_bytes(b"%PDF-1.4\n%fake\n")
        db_utils.save_paper_state(
            paper_id,
            "Smoke Title",
            "user_imported_pdf",
            "2026-05-10",
            local_pdf_path=pdf_path,
            status="NEW",
        )
        note_path = vault_dir / "Inbox" / "paper_chain_001.md"
        note_path.write_text("# Paper\n\nInitial\n", encoding="utf-8")
        (vault_dir / "00_Index" / "paper_collection.csv").write_text(
            "Paper_ID,DOI,Title,Note_Path\n"
            "paper_chain_001,10.1000/test,Smoke Title,Inbox/paper_chain_001.md\n",
            encoding="utf-8",
        )

        # Keep worker path real; only patch heavy agent internals inside job_runner.
        monkeypatch.setattr(
            job_runner_mod,
            "load_config",
            lambda: SimpleNamespace(
                paths=SimpleNamespace(
                    library_dir=library_dir,
                    obsidian_vault=vault_dir,
                    index_all=Path("00_Index/paper_collection.csv"),
                ),
                ingest=SimpleNamespace(parser_backend="fitz_pdfplumber", enable_docling=True),
            ),
        )

        class FakeIngestAgent:
            def __init__(self, parser_backend: str = "fitz_pdfplumber", **_kwargs):
                self.last_table_extraction_meta = {
                    "requested_parser_backend": parser_backend,
                    "parser_backend": "fitz_pdfplumber",
                    "parser_backend_fallback_used": parser_backend == "docling",
                    "table_extraction_pass": "pass1",
                    "table_failure_taxonomy": [],
                    "fallback_used": False,
                    "fallback_pages": [],
                }

            def process_v2(self, pdf_path: str):
                return DocumentArtifactV2(
                    document_id=paper_id,
                    meta=ArtifactMetaV2(
                        title="Smoke Title",
                        authors=["A"],
                        source_ref=pdf_path,
                    ),
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
                    chunks=[
                        DocumentChunk(
                            chunk_id="p01_c01",
                            text="smoke claim supporting quote",
                            section_name="Results",
                            page_hint=1,
                        )
                    ],
                )

        class FakeReaderAgent:
            def __init__(self):
                self.last_analysis_metrics = {
                    "model_name": "fake-reader",
                    "attempt_count": 1,
                    "attempts": [
                        {
                            "attempt_idx": 1,
                            "label": "primary",
                            "context_chars": 10,
                            "prompt_chars": 20,
                            "estimated_prompt_tokens": 5,
                            "response_chars": 30,
                            "estimated_response_tokens": 7,
                            "status": "parsed",
                            "parsed_claim_count": 1,
                        }
                    ],
                    "return_mode": "success",
                    "selected_attempt": 1,
                    "selected_attempt_label": "primary",
                    "final_claim_count": 1,
                    "used_heuristic_fallback": False,
                }

            def analyze(self, doc):
                return ClaimSet(
                    doc_id=doc.document_id,
                    claims=[
                        ScientificClaim(
                            claim_id="c1",
                            type="efficacy",
                            statement="smoke claim",
                            confidence=0.9,
                            evidence_spans=[
                                EvidenceSpan(
                                    quote="supporting quote",
                                    raw_text="supporting quote",
                                    rationale="direct quote",
                                    page=0,
                                    section="Results",
                                    chunk_id="chunk_legacy",
                                )
                            ],
                        )
                    ],
                )

        class FakeStatsAgent:
            def run(self, job_id: str, doc, claims: ClaimSet):
                return StatsReport(
                    doc_id=doc.document_id,
                    run_id=job_id,
                    checks=[
                        StatCheckEntry(
                            check_id="c1",
                            test_type="t-test",
                            code="print('ok')",
                            outputs="ok",
                            verdict=VerificationStatus.VERIFIED,
                        )
                    ],
                )

        monkeypatch.setattr(job_runner_mod, "IngestAgent", FakeIngestAgent)
        monkeypatch.setattr(job_runner_mod, "IndexerAgent", FakeIndexerAgent)
        monkeypatch.setattr(job_runner_mod, "ReaderAgent", FakeReaderAgent)
        monkeypatch.setattr(job_runner_mod, "StatsVerificationAgent", FakeStatsAgent)

        queue = JobQueue()
        job_id_1 = queue.enqueue(
            paper_id=paper_id,
            clean_reindex=False,
            run_verify=True,
            persona_id="smoke-persona",
            parser_backend="docling",
        )
        claimed = queue.claim_next_job()
        assert claimed is not None
        assert claimed.job_id == job_id_1

        worker = worker_mod.Worker()
        worker.process_job(claimed)

        done = queue.get_job(job_id_1)
        assert done is not None
        assert done.status == "completed"
        assert done.stage == "completed"
        assert done.progress == 100
        assert done.artifact_dir is not None
        conn = sqlite3.connect(db_utils.DB_PATH)
        paper_row = conn.execute("SELECT status FROM papers WHERE paper_id = ?", (paper_id,)).fetchone()
        conn.close()
        assert paper_row is not None
        assert paper_row[0] == "INDEXED"

        artifact_dir = Path(done.artifact_dir)
        assert (artifact_dir / "document_artifact.json").exists()
        assert (artifact_dir / "index_artifact.json").exists()
        assert (artifact_dir / "claimset.json").exists()
        assert (artifact_dir / "claimset.resolved.json").exists()
        assert (artifact_dir / "visual_evidence_ledger.json").exists()
        assert (artifact_dir / "claimset_coverage.json").exists()
        assert (artifact_dir / "stats_report.json").exists()
        assert (artifact_dir / "bootstrap_meta.json").exists()
        assert (artifact_dir / "run_meta.json").exists()
        assert (artifact_dir / "evidence_extraction_bundle.json").exists()
        assert (artifact_dir / "acceptance_contract.json").exists()
        assert (artifact_dir / "quality_gate.json").exists()
        assert (artifact_dir / "context_manifest.json").exists()
        meta = json.loads((artifact_dir / "bootstrap_meta.json").read_text(encoding="utf-8"))
        resolved_claimset = json.loads((artifact_dir / "claimset.resolved.json").read_text(encoding="utf-8"))
        evidence_bundle = json.loads((artifact_dir / "evidence_extraction_bundle.json").read_text(encoding="utf-8"))
        visual_evidence_ledger = json.loads((artifact_dir / "visual_evidence_ledger.json").read_text(encoding="utf-8"))
        claimset_coverage = json.loads((artifact_dir / "claimset_coverage.json").read_text(encoding="utf-8"))
        run_meta = json.loads((artifact_dir / "run_meta.json").read_text(encoding="utf-8"))
        quality_gate = json.loads((artifact_dir / "quality_gate.json").read_text(encoding="utf-8"))
        context_manifest = json.loads((artifact_dir / "context_manifest.json").read_text(encoding="utf-8"))
        assert meta["paper_id"] == paper_id
        assert run_meta["paper_id"] == paper_id
        assert run_meta["status"] == "succeeded"
        assert meta["requested_parser_backend"] == "docling"
        assert meta["parser_backend"] == "fitz_pdfplumber"
        assert meta["parser_backend_fallback_used"] is True
        assert run_meta["requested_parser_backend"] == "docling"
        assert run_meta["parser_backend"] == "fitz_pdfplumber"
        assert run_meta["parser_backend_fallback_used"] is True
        assert isinstance(run_meta.get("pdf_sha256"), str)
        assert len(run_meta["pdf_sha256"]) == 64
        assert "models_used" in run_meta
        assert "llm_params" in run_meta
        assert "embed_params" in run_meta
        assert run_meta["tool_policy_version"] == "v1"
        assert run_meta["reader_attempt_order"] == "current"
        assert run_meta["handoff_artifacts"]["context_manifest_path"].endswith("context_manifest.json")
        assert run_meta["reader_timeout_budget_sec"] >= 60
        assert run_meta["reader_timeout_triggered"] is False
        assert run_meta["reader_max_context_chars"] == 16000
        assert run_meta["selected_backend"] == "local"
        assert run_meta["payload_class"] == "local_only"
        assert run_meta["redaction_applied"] is False
        assert run_meta["inference_lanes"]["reader"]["selected_backend"] == "local"
        assert run_meta["inference_lanes"]["reader"]["payload_class"] == "local_only"
        assert run_meta["reader_analysis"]["return_mode"] == "success"
        assert run_meta["reader_analysis"]["attempt_count"] == 1
        performance = run_meta["performance"]
        assert performance["schema_version"] == "performance_profile.v1"
        assert [entry["stage"] for entry in performance["stage_timings"]] == [
            "ingest",
            "index",
            "reader",
            "verify",
        ]
        assert all(isinstance(entry["wall_seconds"], float) for entry in performance["stage_timings"])
        assert performance["summary"]["stage_count"] == 4
        assert performance["summary"]["timed_stage_count"] == 4
        assert performance["summary"]["total_observed_wall_seconds"] >= 0.0
        assert meta["performance_summary"] == performance["summary"]
        assert "persona_id" in meta
        assert "similar_feedback_count" in meta
        assert meta["run_verify"] is True
        assert meta["verifier_used"] is True
        assert meta["verifier_status"] == "completed"
        assert meta["stats_report_written"] is True
        assert meta["artifact_document_written"] is True
        assert meta["artifact_figure_captions_written"] is True
        assert meta["figure_caption_artifact"].endswith("figure_captions.json")
        assert meta["figure_caption_count"] == 0
        assert run_meta["figure_caption_artifact"].endswith("figure_captions.json")
        assert run_meta["figure_caption_count"] == 0
        assert meta["artifact_index_written"] is True
        assert meta["artifact_claimset_written"] is True
        assert meta["artifact_claimset_resolved_written"] is True
        assert meta["artifact_visual_evidence_ledger_written"] is True
        assert meta["visual_evidence_ledger_artifact"].endswith("visual_evidence_ledger.json")
        assert meta["visual_evidence_entry_count"] == 0
        assert run_meta["visual_evidence_ledger"]["artifact"].endswith("visual_evidence_ledger.json")
        assert run_meta["visual_evidence_ledger"]["entry_count"] == 0
        assert run_meta["visual_evidence_ledger"]["generation_replay_required"] is True
        assert visual_evidence_ledger["schema_version"] == "visual_evidence_ledger.v1"
        assert visual_evidence_ledger["generation_replay_required"] is True
        assert visual_evidence_ledger["entries"] == []
        assert meta["artifact_claimset_coverage_written"] is True
        assert meta["claimset_coverage_status"] == "pass"
        assert meta["claimset_coverage_artifact"].endswith("claimset_coverage.json")
        assert meta["artifact_evidence_extraction_bundle_written"] is True
        assert meta["artifact_acceptance_contract_written"] is True
        assert meta["artifact_quality_gate_written"] is True
        assert meta["artifact_stats_written"] is True
        assert meta["evidence_extraction_record_count"] >= 1
        assert quality_gate["step_stability_summary"]["status"] == "pass"
        assert quality_gate["step_stability_summary"]["reason_codes"] == []
        assert quality_gate["failure_recovery_summary"]["status"] == "pass"
        assert quality_gate["failure_recovery_summary"]["reason_codes"] == []
        assert any(check["name"] == "step_stability" for check in quality_gate["checks"])
        assert any(check["name"] == "failure_recovery" for check in quality_gate["checks"])
        section_signal_check = next(
            check for check in quality_gate["checks"] if check["name"] == "section_navigation_signal"
        )
        assert section_signal_check["status"] == "pass"
        assert "claimset_section_count=1" in section_signal_check["detail"]
        assert context_manifest["goal_drift_summary"]["status"] == "pass"
        assert context_manifest["goal_drift_summary"]["reason_codes"] == []
        assert meta["evidence_extraction_claim_record_count"] == 1
        assert meta["reader_model"] is not None
        assert meta["reader_timeout_base_sec"] >= 60
        assert meta["reader_attempt_order"] == "current"
        assert meta["reader_timeout_budget_sec"] >= meta["reader_timeout_base_sec"]
        assert meta["reader_timeout_adaptive"] is True
        assert meta["reader_page_count"] == 1
        assert meta["reader_table_count"] == 0
        assert meta["reader_timeout_triggered"] is False
        assert meta["reader_max_context_chars"] == 16000
        assert "reader_provider_timeout_sec" in meta
        assert meta["reader_analysis"]["selected_attempt_label"] == "primary"
        assert meta["claimset_readiness"] == "ready"
        assert meta["claimset_ready"] is True
        assert meta["claimset_claim_count"] == 1
        assert meta["claimset_section_count"] == 1
        assert meta["claimset_readiness_reason"] == "claims_present"
        assert meta["claimset_readiness_badge"] == "READY"
        assert meta["claimset_ops_action"] == "none"
        assert meta["claimset_ops_alert"] is False
        assert meta["claimset_ops_note"] == "ready"
        assert meta["claimset_grounded_span_count"] == 1
        assert meta["claimset_unresolved_span_count"] == 0
        span = resolved_claimset["claims"][0]["evidence_spans"][0]
        assert span["chunk_id"] == "p01_c01"
        assert span["page"] == 0
        assert span["section"] == "Results"
        assert span["grounded"] is True
        assert span["resolution"] == "OK"
        assert run_meta["section_count"] == 1
        assert run_meta["claimset_coverage"]["status"] == "pass"
        assert run_meta["claimset_coverage"]["artifact"].endswith("claimset_coverage.json")
        assert claimset_coverage["coverage_status"] == "pass"
        assert claimset_coverage["page_summary"]["covered_pages"] == [1]
        assert len(run_meta["section_summary"]) == 1
        section_entry = run_meta["section_summary"][0]
        assert section_entry["key"] == "results"
        assert section_entry["label"] == "Results"
        assert section_entry["claim_count"] == 1
        assert section_entry["evidence_count"] == 1
        assert section_entry["page_start"] == 0
        assert section_entry["page_end"] == 0
        assert isinstance(section_entry["representative_claim_id"], str)
        assert isinstance(section_entry["representative_evidence_id"], str)
        assert quality_gate["overall_status"] == "pass"
        assert quality_gate["review_ready"] is True
        assert quality_gate["current_promotion_candidate"] is True
        assert quality_gate["hard_fail_codes"] == []
        assert context_manifest["selected_attempt_label"] == "primary"
        assert context_manifest["attempt_count"] == 1
        assert evidence_bundle["metrics"]["claim_record_count"] == 1
        assert evidence_bundle["records"][0]["record_type"] == "claim"

        # Re-run on same paper and ensure note keeps a single Deep Read section.
        job_id_2 = queue.enqueue(
            paper_id=paper_id,
            clean_reindex=False,
            run_verify=True,
            persona_id="smoke-persona",
        )
        claimed2 = queue.claim_next_job()
        assert claimed2 is not None
        assert claimed2.job_id == job_id_2
        worker.process_job(claimed2)
        done2 = queue.get_job(job_id_2)
        assert done2 is not None
        assert done2.status == "completed"

        note_content = note_path.read_text(encoding="utf-8")
        assert note_content.count("## 🤖 Agent Deep Read") == 1
        assert "smoke claim" in note_content
        structured_path = vault_dir / ".pp" / "paper_chain_001" / "state.json"
        assert structured_path.exists()
        structured_state = json.loads(structured_path.read_text(encoding="utf-8"))
        assert structured_state["signals"]["state_source"] == "deep_read_promotion"
        assert structured_state["runs"][0]["action"] == "deep_read"
        assert structured_state["runs"][0]["id"] == done2.run_id
    finally:
        db_utils.DB_PATH = original_db_path


def test_worker_not_ready_claimset_queues_manual_review_followup(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()
        conn = sqlite3.connect(db_utils.DB_PATH)
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS review_queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                paper_id TEXT NOT NULL,
                decision TEXT NOT NULL,
                reason TEXT,
                owner TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                resolved_at TIMESTAMP,
                resolution TEXT
            )
            """
        )
        conn.commit()
        conn.close()

        library_dir = tmp_path / "Library"
        library_dir.mkdir(parents=True, exist_ok=True)
        vault_dir = tmp_path / "Vault"
        (vault_dir / "00_Index").mkdir(parents=True, exist_ok=True)
        (vault_dir / "Inbox").mkdir(parents=True, exist_ok=True)
        paper_id = "paper_not_ready_001"
        (library_dir / f"{paper_id}.pdf").write_bytes(b"%PDF-1.4\n%fake\n")
        (vault_dir / "Inbox" / "paper_not_ready_001.md").write_text("# Paper\n", encoding="utf-8")
        (vault_dir / "00_Index" / "paper_collection.csv").write_text(
            "Paper_ID,DOI,Title,Note_Path\n"
            "paper_not_ready_001,10.1000/test,Smoke Title,Inbox/paper_not_ready_001.md\n",
            encoding="utf-8",
        )

        monkeypatch.setattr(
            job_runner_mod,
            "load_config",
            lambda: SimpleNamespace(
                paths=SimpleNamespace(
                    library_dir=library_dir,
                    obsidian_vault=vault_dir,
                    index_all=Path("00_Index/paper_collection.csv"),
                )
            ),
        )

        class FakeIngestAgent:
            def process_v2(self, pdf_path: str):
                return DocumentArtifactV2(
                    document_id=paper_id,
                    meta=ArtifactMetaV2(title="Smoke Title", authors=["A"], source_ref=pdf_path),
                    pages=[
                        PageV2(
                            page_index=0,
                            width=595.0,
                            height=842.0,
                            blocks=[BlockV2(block_id="b1", lines=[LineV2(line_id="l1", text="x", spans=[SpanV2(span_id="s1", text="x")])])],
                        )
                    ],
                    tables=[],
                )

        class FakeIndexerAgent:
            def process(self, doc):
                return IndexArtifact(doc_id=doc.document_id, vector_store_id="smoke", chunk_count=1, chunks=[])

        class FakeReaderEmptyClaimSet:
            def analyze(self, doc):
                return ClaimSet(doc_id=doc.document_id, claims=[])

        monkeypatch.setattr(job_runner_mod, "IngestAgent", FakeIngestAgent)
        monkeypatch.setattr(job_runner_mod, "IndexerAgent", FakeIndexerAgent)
        monkeypatch.setattr(job_runner_mod, "ReaderAgent", FakeReaderEmptyClaimSet)

        queue = JobQueue()
        job_id = queue.enqueue(
            paper_id=paper_id,
            clean_reindex=False,
            run_verify=False,
            persona_id="smoke-persona",
        )
        claimed = queue.claim_next_job()
        assert claimed is not None
        worker = worker_mod.Worker()
        worker.process_job(claimed)

        done = queue.get_job(job_id)
        assert done is not None
        assert done.status == "completed"
        artifact_dir = Path(done.artifact_dir)
        meta = json.loads((artifact_dir / "bootstrap_meta.json").read_text(encoding="utf-8"))
        quality_gate = json.loads((artifact_dir / "quality_gate.json").read_text(encoding="utf-8"))
        assert meta["claimset_readiness"] == "not_ready"
        assert meta["claimset_ready"] is False
        assert meta["claimset_claim_count"] == 0
        assert meta["claimset_readiness_badge"] == "NOT_READY"
        assert meta["claimset_ops_action"] == "manual_review_queued"
        assert meta["claimset_ops_alert"] is False
        assert meta["claimset_ops_note"] in {"queued", "already_open"}
        assert meta["artifact_acceptance_contract_written"] is True
        assert meta["artifact_quality_gate_written"] is True
        assert quality_gate["overall_status"] == "warn"
        assert quality_gate["current_promotion_candidate"] is True
        assert quality_gate["review_ready"] is False
        assert quality_gate["hard_fail_codes"] == []
        assert quality_gate["step_stability_summary"]["status"] == "pass"
        assert quality_gate["failure_recovery_summary"]["status"] == "pass"

        conn = sqlite3.connect(db_utils.DB_PATH)
        row = conn.execute(
            "SELECT decision, reason, resolved_at FROM review_queue WHERE paper_id = ? ORDER BY id DESC LIMIT 1",
            (paper_id,),
        ).fetchone()
        conn.close()
        assert row is not None
        assert row[0] == "NEEDS_READER"
        assert "claims=0" in (row[1] or "")
        assert row[2] is None
    finally:
        db_utils.DB_PATH = original_db_path


def test_worker_reader_timeout_budget_is_recorded_and_failed_explicitly(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()

        library_dir = tmp_path / "Library"
        library_dir.mkdir(parents=True, exist_ok=True)
        vault_dir = tmp_path / "Vault"
        (vault_dir / "00_Index").mkdir(parents=True, exist_ok=True)
        (vault_dir / "Inbox").mkdir(parents=True, exist_ok=True)
        paper_id = "paper_timeout_001"
        (library_dir / f"{paper_id}.pdf").write_bytes(b"%PDF-1.4\n%fake\n")
        (vault_dir / "Inbox" / "paper_timeout_001.md").write_text("# Paper\n", encoding="utf-8")
        (vault_dir / "00_Index" / "paper_collection.csv").write_text(
            "Paper_ID,DOI,Title,Note_Path\n"
            "paper_timeout_001,10.1000/test,Timeout Title,Inbox/paper_timeout_001.md\n",
            encoding="utf-8",
        )

        monkeypatch.setattr(
            job_runner_mod,
            "load_config",
            lambda: SimpleNamespace(
                paths=SimpleNamespace(
                    library_dir=library_dir,
                    obsidian_vault=vault_dir,
                    index_all=Path("00_Index/paper_collection.csv"),
                ),
                llm=SimpleNamespace(timeout_seconds=20),
            ),
        )

        class FakeIngestAgent:
            def process_v2(self, pdf_path: str):
                return DocumentArtifactV2(
                    document_id=paper_id,
                    meta=ArtifactMetaV2(title="Timeout Title", authors=["A"], source_ref=pdf_path),
                    pages=[
                        PageV2(
                            page_index=0,
                            width=595.0,
                            height=842.0,
                            blocks=[BlockV2(block_id="b1", lines=[LineV2(line_id="l1", text="x", spans=[SpanV2(span_id="s1", text="x")])])],
                        )
                    ],
                    tables=[],
                )

        class FakeIndexerAgent:
            def process(self, doc):
                return IndexArtifact(doc_id=doc.document_id, vector_store_id="smoke", chunk_count=1, chunks=[])

        class ReadTimeout(Exception):
            pass

        class FakeReaderTimeoutAgent:
            def __init__(self, *args, **kwargs):
                self.adapter = SimpleNamespace(provider=None)

            def analyze(self, doc):
                raise ReadTimeout("timed out")

        captured: dict[str, int] = {}

        @contextmanager
        def fake_time_limit(seconds: int):
            captured["seconds"] = int(seconds)
            yield

        monkeypatch.setattr(job_runner_mod, "IngestAgent", FakeIngestAgent)
        monkeypatch.setattr(job_runner_mod, "IndexerAgent", FakeIndexerAgent)
        monkeypatch.setattr(job_runner_mod, "ReaderAgent", FakeReaderTimeoutAgent)
        monkeypatch.setattr(job_runner_mod, "estimate_reader_timeout_seconds", lambda *args, **kwargs: 123)
        monkeypatch.setattr(job_runner_mod, "time_limit", fake_time_limit)

        queue = JobQueue()
        job_id = queue.enqueue(
            paper_id=paper_id,
            clean_reindex=False,
            run_verify=False,
            persona_id="default",
        )
        claimed = queue.claim_next_job()
        assert claimed is not None

        worker = worker_mod.Worker()
        worker.process_job(claimed)

        done = queue.get_job(job_id)
        assert done is not None
        assert done.status == "failed"
        assert done.error_message == "Reader step timed out after 123s (pages=1, tables=0)"
        assert captured["seconds"] == 123

        artifact_dir = job_runner_mod.artifact_run_dir(paper_id, done.run_id)
        assert done.artifact_dir == str(artifact_dir)
        meta = json.loads((artifact_dir / "bootstrap_meta.json").read_text(encoding="utf-8"))
        run_meta = json.loads((artifact_dir / "run_meta.json").read_text(encoding="utf-8"))
        assert meta["reader_timeout_base_sec"] == 120
        assert meta["reader_timeout_budget_sec"] == 123
        assert meta["reader_timeout_adaptive"] is True
        assert meta["reader_page_count"] == 1
        assert meta["reader_table_count"] == 0
        assert meta["reader_timeout_triggered"] is True
        assert meta["reader_timeout_error_type"] == "ReadTimeout"
        assert meta["reader_provider_timeout_override_applied"] is False
        assert meta["artifact_reader_timeout_written"] is True
        assert meta["reader_timeout_artifact"].endswith("reader_timeout.json")
        assert run_meta["status"] == "failed"
        assert run_meta["reader_timeout_budget_sec"] == 123
        assert run_meta["reader_timeout_triggered"] is True
        assert run_meta["reader_timeout_error_type"] == "ReadTimeout"
        assert run_meta["reader_timeout_artifact"].endswith("reader_timeout.json")
        timeout_sidecar = json.loads((artifact_dir / "reader_timeout.json").read_text(encoding="utf-8"))
        assert timeout_sidecar["schema_version"] == "reader_timeout.v1"
        assert timeout_sidecar["layer"] == "review_gate_artifact"
        assert timeout_sidecar["canonical_status"] == "non_canonical"
        assert timeout_sidecar["paper_id"] == paper_id
        assert timeout_sidecar["status"] == "timeout"
        assert timeout_sidecar["timeout_budget_sec"] == 123
        assert timeout_sidecar["page_count"] == 1
        assert timeout_sidecar["table_count"] == 0
        assert timeout_sidecar["error_type"] == "ReadTimeout"
        assert timeout_sidecar["recommended_action"] == "retry_with_larger_reader_timeout_or_focused_first_reader_context"
        quality_gate = json.loads((artifact_dir / "quality_gate.json").read_text(encoding="utf-8"))
        assert quality_gate["overall_status"] == "fail"
        assert quality_gate["step_stability_summary"]["status"] == "fail"
        assert quality_gate["failure_recovery_summary"]["status"] == "pass"
        assert quality_gate["failure_recovery_summary"]["reason_codes"] == []
    finally:
        db_utils.DB_PATH = original_db_path


def test_worker_clean_reindex_prunes_after_successful_index(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()

        library_dir = tmp_path / "Library"
        library_dir.mkdir(parents=True, exist_ok=True)
        vault_dir = tmp_path / "Vault"
        (vault_dir / "00_Index").mkdir(parents=True, exist_ok=True)
        (vault_dir / "Inbox").mkdir(parents=True, exist_ok=True)
        paper_id = "paper_clean_idx_001"
        (library_dir / f"{paper_id}.pdf").write_bytes(b"%PDF-1.4\n%fake\n")
        (vault_dir / "Inbox" / "paper_clean_idx_001.md").write_text("# Paper\n", encoding="utf-8")
        (vault_dir / "00_Index" / "paper_collection.csv").write_text(
            "Paper_ID,DOI,Title,Note_Path\n"
            "paper_clean_idx_001,10.1000/test,Smoke Title,Inbox/paper_clean_idx_001.md\n",
            encoding="utf-8",
        )

        monkeypatch.setattr(
            job_runner_mod,
            "load_config",
            lambda: SimpleNamespace(
                paths=SimpleNamespace(
                    library_dir=library_dir,
                    obsidian_vault=vault_dir,
                    index_all=Path("00_Index/paper_collection.csv"),
                )
            ),
        )

        class FakeIngestAgent:
            def process_v2(self, pdf_path: str):
                return DocumentArtifactV2(
                    document_id=paper_id,
                    meta=ArtifactMetaV2(title="Smoke Title", authors=["A"], source_ref=pdf_path),
                    pages=[
                        PageV2(
                            page_index=0,
                            width=595.0,
                            height=842.0,
                            blocks=[BlockV2(block_id="b1", lines=[LineV2(line_id="l1", text="x", spans=[SpanV2(span_id="s1", text="x")])])],
                        )
                    ],
                    tables=[],
                )

        indexer_calls: list[tuple[str, str]] = []

        class FakeIndexerAgent:
            def process(self, doc):
                indexer_calls.append(("process", doc.document_id))
                return IndexArtifact(
                    doc_id=doc.document_id,
                    vector_store_id="smoke",
                    chunk_count=1,
                    chunks=[
                        DocumentChunk(
                            chunk_id="p01_c01",
                            text="x",
                            vector_id="doc_hash__p01_c01",
                            section_name="abstract",
                            page_hint=1,
                        )
                    ],
                )

            def prune_doc_index(self, doc_id: str, *, keep_ids: list[str]) -> int:
                indexer_calls.append(("prune", f"{doc_id}:{','.join(keep_ids)}"))
                return 3

        class FakeReaderAgent:
            def analyze(self, doc):
                return ClaimSet(
                    doc_id=doc.document_id,
                    claims=[ScientificClaim(claim_id="c1", type="efficacy", statement="claim", confidence=0.9)],
                )

        monkeypatch.setattr(job_runner_mod, "IngestAgent", FakeIngestAgent)
        monkeypatch.setattr(job_runner_mod, "IndexerAgent", FakeIndexerAgent)
        monkeypatch.setattr(job_runner_mod, "ReaderAgent", FakeReaderAgent)

        queue = JobQueue()
        job_id = queue.enqueue(
            paper_id=paper_id,
            clean_reindex=True,
            run_verify=False,
            persona_id="default",
        )
        claimed = queue.claim_next_job()
        assert claimed is not None
        worker = worker_mod.Worker()
        worker.process_job(claimed)

        done = queue.get_job(job_id)
        assert done is not None
        assert done.status == "completed"
        assert done.clean_reindex == 1
        assert indexer_calls == [
            ("process", paper_id),
            ("prune", f"{paper_id}:doc_hash__p01_c01"),
        ]

        artifact_dir = Path(done.artifact_dir)
        meta = json.loads((artifact_dir / "bootstrap_meta.json").read_text(encoding="utf-8"))
        assert meta["clean_reindex_requested"] is True
        assert meta["clean_reindex_applied"] is True
        assert meta["clean_reindex_removed_chunks"] == 3
    finally:
        db_utils.DB_PATH = original_db_path


def test_worker_clean_reindex_skips_prune_after_partial_index(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()

        library_dir = tmp_path / "Library"
        library_dir.mkdir(parents=True, exist_ok=True)
        vault_dir = tmp_path / "Vault"
        (vault_dir / "00_Index").mkdir(parents=True, exist_ok=True)
        (vault_dir / "Inbox").mkdir(parents=True, exist_ok=True)
        paper_id = "paper_partial_clean_idx_001"
        (library_dir / f"{paper_id}.pdf").write_bytes(b"%PDF-1.4\n%fake\n")
        (vault_dir / "Inbox" / f"{paper_id}.md").write_text("# Paper\n", encoding="utf-8")
        (vault_dir / "00_Index" / "paper_collection.csv").write_text(
            "Paper_ID,DOI,Title,Note_Path\n"
            f"{paper_id},10.1000/test,Smoke Title,Inbox/{paper_id}.md\n",
            encoding="utf-8",
        )

        monkeypatch.setattr(
            job_runner_mod,
            "load_config",
            lambda: SimpleNamespace(
                paths=SimpleNamespace(
                    library_dir=library_dir,
                    obsidian_vault=vault_dir,
                    index_all=Path("00_Index/paper_collection.csv"),
                )
            ),
        )

        class FakeIngestAgent:
            def process_v2(self, pdf_path: str):
                return DocumentArtifactV2(
                    document_id=paper_id,
                    meta=ArtifactMetaV2(title="Smoke Title", authors=["A"], source_ref=pdf_path),
                    pages=[
                        PageV2(
                            page_index=0,
                            width=595.0,
                            height=842.0,
                            blocks=[BlockV2(block_id="b1", lines=[LineV2(line_id="l1", text="x", spans=[SpanV2(span_id="s1", text="x")])])],
                        )
                    ],
                    tables=[],
                )

        indexer_calls: list[str] = []

        class FakeIndexerAgent:
            last_index_complete = False
            last_index_attempted_chunks = 2
            last_index_skipped_chunks = 1

            def process(self, doc):
                indexer_calls.append("process")
                return IndexArtifact(
                    doc_id=doc.document_id,
                    vector_store_id="smoke",
                    chunk_count=1,
                    chunks=[
                        DocumentChunk(
                            chunk_id="p01_c01",
                            text="x",
                            vector_id="doc_hash__p01_c01",
                            section_name="abstract",
                            page_hint=1,
                        )
                    ],
                )

            def prune_doc_index(self, doc_id: str, *, keep_ids: list[str]) -> int:
                indexer_calls.append("prune")
                return 3

        class FakeReaderAgent:
            def analyze(self, doc):
                return ClaimSet(
                    doc_id=doc.document_id,
                    claims=[ScientificClaim(claim_id="c1", type="efficacy", statement="claim", confidence=0.9)],
                )

        monkeypatch.setattr(job_runner_mod, "IngestAgent", FakeIngestAgent)
        monkeypatch.setattr(job_runner_mod, "IndexerAgent", FakeIndexerAgent)
        monkeypatch.setattr(job_runner_mod, "ReaderAgent", FakeReaderAgent)

        queue = JobQueue()
        job_id = queue.enqueue(paper_id=paper_id, clean_reindex=True)
        claimed = queue.claim_next_job()
        assert claimed is not None
        worker = worker_mod.Worker()
        worker.process_job(claimed)

        done = queue.get_job(job_id)
        assert done is not None
        assert done.status == "completed"
        assert indexer_calls == ["process"]

        artifact_dir = Path(done.artifact_dir)
        meta = json.loads((artifact_dir / "bootstrap_meta.json").read_text(encoding="utf-8"))
        assert meta["clean_reindex_requested"] is True
        assert meta["clean_reindex_applied"] is False
        assert meta["clean_reindex_skip_reason"] == "partial_replacement_vectors"
        assert meta["clean_reindex_attempted_chunks"] == 2
        assert meta["clean_reindex_skipped_chunks"] == 1
    finally:
        db_utils.DB_PATH = original_db_path


def test_resolve_note_path_for_paper_falls_back_to_db_obsidian_path(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()

        vault_dir = tmp_path / "Vault"
        vault_dir.mkdir(parents=True, exist_ok=True)
        note_path = vault_dir / "Inbox" / "paper_db_note_001.md"
        note_path.parent.mkdir(parents=True, exist_ok=True)
        note_path.write_text("# Paper\n", encoding="utf-8")

        conn = sqlite3.connect(db_utils.DB_PATH)
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS papers (
                paper_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                status TEXT DEFAULT 'NEW',
                obsidian_path TEXT
            )
            """
        )
        conn.execute(
            """
            INSERT INTO papers (paper_id, title, status, obsidian_path)
            VALUES (?, ?, ?, ?)
            """,
            (
                "paper_db_note_001",
                "DB-backed note path",
                "INDEXED",
                "Inbox/paper_db_note_001.md",
            ),
        )
        conn.commit()
        conn.close()

        config = SimpleNamespace(
            paths=SimpleNamespace(
                obsidian_vault=vault_dir,
                index_all=Path("00_Index/paper_collection.csv"),
            )
        )

        resolved = job_runner_mod._resolve_note_path_for_paper(config, "paper_db_note_001")
        assert resolved == note_path
    finally:
        db_utils.DB_PATH = original_db_path


def test_resolve_note_path_for_paper_rejects_escaping_db_obsidian_path(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()

        vault_dir = tmp_path / "Vault"
        vault_dir.mkdir(parents=True, exist_ok=True)
        outside_note = tmp_path / "outside.md"
        outside_note.write_text("# Outside\n", encoding="utf-8")

        conn = sqlite3.connect(db_utils.DB_PATH)
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS papers (
                paper_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                status TEXT DEFAULT 'NEW',
                obsidian_path TEXT
            )
            """
        )
        conn.execute(
            """
            INSERT INTO papers (paper_id, title, status, obsidian_path)
            VALUES (?, ?, ?, ?)
            """,
            (
                "paper_escape_note",
                "Escaping note path",
                "INDEXED",
                "../outside.md",
            ),
        )
        conn.commit()
        conn.close()

        config = SimpleNamespace(
            paths=SimpleNamespace(
                obsidian_vault=vault_dir,
                index_all=Path("00_Index/paper_collection.csv"),
            )
        )

        resolved = job_runner_mod._resolve_note_path_for_paper(config, "paper_escape_note")
        assert resolved is None
    finally:
        db_utils.DB_PATH = original_db_path
