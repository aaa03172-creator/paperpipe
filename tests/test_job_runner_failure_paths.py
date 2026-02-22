import asyncio
import json
import sqlite3
from pathlib import Path
from types import SimpleNamespace

import backend.services.job_runner as job_runner_mod
import src.db_utils as db_utils

from src.contracts.document_artifact_v2 import (
    ArtifactMetaV2,
    BlockV2,
    DocumentArtifactV2,
    LineV2,
    PageV2,
    SpanV2,
)
from src.schemas.agent_artifacts import (
    ClaimSet,
    IndexArtifact,
    ScientificClaim,
    StatCheckEntry,
    StatsReport,
    VerificationStatus,
)


def _make_config(tmp_path: Path, paper_id: str) -> SimpleNamespace:
    library_dir = tmp_path / "Library"
    library_dir.mkdir(parents=True, exist_ok=True)
    vault_dir = tmp_path / "Vault"
    vault_dir.mkdir(parents=True, exist_ok=True)
    return SimpleNamespace(
        paths=SimpleNamespace(
            library_dir=library_dir,
            obsidian_vault=vault_dir,
            index_all=Path("00_Index/paper_collection.csv"),
        )
    )


def _make_doc_artifact(paper_id: str, pdf_path: str) -> DocumentArtifactV2:
    return DocumentArtifactV2(
        document_id=paper_id,
        meta=ArtifactMetaV2(title="Smoke Title", authors=["A"], source_ref=pdf_path),
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


def test_run_deepread_job_fails_fast_when_pdf_missing(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    paper_id = "missing_pdf_case"
    config = _make_config(tmp_path, paper_id)
    monkeypatch.setattr(job_runner_mod, "load_config", lambda: config)
    monkeypatch.setattr(job_runner_mod, "_load_similar_feedback_top3", lambda query_text, limit=3: [])

    events = []

    async def on_progress(event: dict):
        events.append(event)

    result = asyncio.run(
        job_runner_mod.run_deepread_job(
            job_id="job_missing_pdf",
            paper_id=paper_id,
            run_id="run_missing_pdf",
            progress_callback=on_progress,
        )
    )

    assert result["status"] == "failed"
    assert "PDF not found" in result["error"]
    assert any(e.get("level") == "ERROR" for e in events)
    assert not (tmp_path / "storage" / "artifacts" / paper_id).exists()


def test_run_deepread_job_sets_runtime_error_meta_on_reader_exception(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    paper_id = "reader_failure_case"
    config = _make_config(tmp_path, paper_id)
    pdf_path = config.paths.library_dir / f"{paper_id}.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n%fake\n")

    class FakeIngestAgent:
        def process_v2(self, path: str):
            return _make_doc_artifact(paper_id, path)

    class FakeIndexerAgent:
        def process(self, doc):
            return IndexArtifact(doc_id=doc.document_id, vector_store_id="smoke", chunk_count=1, chunks=[])

    class FailingReaderAgent:
        def __init__(self, *args, **kwargs):
            pass

        def analyze(self, doc):
            raise RuntimeError("reader exploded")

    monkeypatch.setattr(job_runner_mod, "load_config", lambda: config)
    monkeypatch.setattr(job_runner_mod, "_load_similar_feedback_top3", lambda query_text, limit=3: [])
    monkeypatch.setattr(job_runner_mod, "IngestAgent", FakeIngestAgent)
    monkeypatch.setattr(job_runner_mod, "IndexerAgent", FakeIndexerAgent)
    monkeypatch.setattr(job_runner_mod, "ReaderAgent", FailingReaderAgent)

    result = asyncio.run(
        job_runner_mod.run_deepread_job(
            job_id="job_reader_failure",
            paper_id=paper_id,
            run_id="run_reader_failure",
            run_verify=False,
        )
    )

    assert result["status"] == "failed"
    assert "reader exploded" in result["error"]

    artifact_dir = tmp_path / "storage" / "artifacts" / paper_id / "run_reader_failure"
    meta_path = artifact_dir / "bootstrap_meta.json"
    assert meta_path.exists()
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    assert meta["artifact_document_written"] is True
    assert meta["artifact_index_written"] is True
    assert meta["artifact_claimset_written"] is False
    assert meta["claimset_readiness"] == "unknown"
    assert meta["claimset_readiness_reason"] == "runtime_error"
    assert meta["claimset_readiness_badge"] == "UNKNOWN"
    assert meta["claimset_ops_action"] == "retry_suggested"
    assert meta["claimset_ops_alert"] is True
    assert meta["claimset_ops_note"] == "runtime_error:RuntimeError"


def test_run_deepread_job_keeps_success_when_verifier_fails(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    paper_id = "verifier_failure_case"
    config = _make_config(tmp_path, paper_id)
    pdf_path = config.paths.library_dir / f"{paper_id}.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n%fake\n")

    class FakeIngestAgent:
        def process_v2(self, path: str):
            return _make_doc_artifact(paper_id, path)

    class FakeIndexerAgent:
        def process(self, doc):
            return IndexArtifact(doc_id=doc.document_id, vector_store_id="smoke", chunk_count=1, chunks=[])

    class FakeReaderAgent:
        def __init__(self, *args, **kwargs):
            pass

        def analyze(self, doc):
            return ClaimSet(
                doc_id=doc.document_id,
                claims=[
                    ScientificClaim(
                        claim_id="c1",
                        type="efficacy",
                        statement="claim text",
                        confidence=0.9,
                    )
                ],
            )

    class FailingStatsAgent:
        def run(self, job_id: str, doc, claims: ClaimSet):
            raise ValueError("verify failed")

    monkeypatch.setattr(job_runner_mod, "load_config", lambda: config)
    monkeypatch.setattr(job_runner_mod, "_load_similar_feedback_top3", lambda query_text, limit=3: [])
    monkeypatch.setattr(job_runner_mod, "IngestAgent", FakeIngestAgent)
    monkeypatch.setattr(job_runner_mod, "IndexerAgent", FakeIndexerAgent)
    monkeypatch.setattr(job_runner_mod, "ReaderAgent", FakeReaderAgent)
    monkeypatch.setattr(job_runner_mod, "StatsVerificationAgent", FailingStatsAgent)

    result = asyncio.run(
        job_runner_mod.run_deepread_job(
            job_id="job_verifier_failure",
            paper_id=paper_id,
            run_id="run_verifier_failure",
            run_verify=True,
        )
    )

    assert result["status"] == "succeeded"

    artifact_dir = tmp_path / "storage" / "artifacts" / paper_id / "run_verifier_failure"
    meta_path = artifact_dir / "bootstrap_meta.json"
    assert meta_path.exists()
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    assert meta["artifact_claimset_written"] is True
    assert meta["claimset_readiness"] == "ready"
    assert meta["verifier_status"] == "failed"
    assert meta["stats_report_written"] is False
    assert meta["artifact_stats_written"] is False


def test_run_deepread_job_can_cancel_after_artifact_init(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    paper_id = "cancel_after_artifact_init"
    config = _make_config(tmp_path, paper_id)
    pdf_path = config.paths.library_dir / f"{paper_id}.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n%fake\n")

    monkeypatch.setattr(job_runner_mod, "load_config", lambda: config)
    monkeypatch.setattr(job_runner_mod, "_load_similar_feedback_top3", lambda query_text, limit=3: [])

    checks = {"count": 0}

    def cancel_check() -> bool:
        checks["count"] += 1
        return checks["count"] >= 2

    result = asyncio.run(
        job_runner_mod.run_deepread_job(
            job_id="job_cancel_case",
            paper_id=paper_id,
            run_id="run_cancel_case",
            cancel_check=cancel_check,
        )
    )

    assert result["status"] == "cancelled"
    artifact_dir = tmp_path / "storage" / "artifacts" / paper_id / "run_cancel_case"
    meta_path = artifact_dir / "bootstrap_meta.json"
    assert meta_path.exists()
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    assert meta["claimset_readiness"] == "unknown"
    assert meta["claimset_readiness_reason"] == "not_evaluated"


def test_run_deepread_job_not_ready_without_review_queue_flags_manual_action(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    paper_id = "not_ready_without_review_queue"
    config = _make_config(tmp_path, paper_id)
    pdf_path = config.paths.library_dir / f"{paper_id}.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n%fake\n")

    class FakeIngestAgent:
        def process_v2(self, path: str):
            return _make_doc_artifact(paper_id, path)

    class FakeIndexerAgent:
        def process(self, doc):
            return IndexArtifact(doc_id=doc.document_id, vector_store_id="smoke", chunk_count=1, chunks=[])

    class EmptyReaderAgent:
        def __init__(self, *args, **kwargs):
            pass

        def analyze(self, doc):
            return ClaimSet(doc_id=doc.document_id, claims=[])

    monkeypatch.setattr(job_runner_mod, "load_config", lambda: config)
    monkeypatch.setattr(job_runner_mod, "_load_similar_feedback_top3", lambda query_text, limit=3: [])
    monkeypatch.setattr(job_runner_mod, "IngestAgent", FakeIngestAgent)
    monkeypatch.setattr(job_runner_mod, "IndexerAgent", FakeIndexerAgent)
    monkeypatch.setattr(job_runner_mod, "ReaderAgent", EmptyReaderAgent)

    result = asyncio.run(
        job_runner_mod.run_deepread_job(
            job_id="job_not_ready_no_queue",
            paper_id=paper_id,
            run_id="run_not_ready_no_queue",
            run_verify=False,
        )
    )

    assert result["status"] == "succeeded"
    artifact_dir = tmp_path / "storage" / "artifacts" / paper_id / "run_not_ready_no_queue"
    meta_path = artifact_dir / "bootstrap_meta.json"
    assert meta_path.exists()
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    assert meta["claimset_readiness"] == "not_ready"
    assert meta["claimset_ready"] is False
    assert meta["claimset_claim_count"] == 0
    assert meta["claimset_ops_action"] == "manual_review_required"
    assert meta["claimset_ops_alert"] is True
    assert meta["claimset_ops_note"] == "queue_unavailable"


def test_run_deepread_job_fast_ingest_skips_reader_and_verify(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    paper_id = "fast_ingest_case"
    config = _make_config(tmp_path, paper_id)
    pdf_path = config.paths.library_dir / f"{paper_id}.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n%fake\n")

    class FakeIngestAgent:
        def process_v2(self, path: str):
            return _make_doc_artifact(paper_id, path)

    class FakeIndexerAgent:
        def process(self, doc):
            return IndexArtifact(doc_id=doc.document_id, vector_store_id="smoke", chunk_count=1, chunks=[])

    class FailingReaderAgent:
        def __init__(self, *args, **kwargs):
            pass

        def analyze(self, doc):
            raise RuntimeError("reader should not run in fast_ingest")

    monkeypatch.setattr(job_runner_mod, "load_config", lambda: config)
    monkeypatch.setattr(job_runner_mod, "_load_similar_feedback_top3", lambda query_text, limit=3: [])
    monkeypatch.setattr(job_runner_mod, "IngestAgent", FakeIngestAgent)
    monkeypatch.setattr(job_runner_mod, "IndexerAgent", FakeIndexerAgent)
    monkeypatch.setattr(job_runner_mod, "ReaderAgent", FailingReaderAgent)

    result = asyncio.run(
        job_runner_mod.run_deepread_job(
            job_id="job_fast_ingest",
            paper_id=paper_id,
            run_id="run_fast_ingest",
            run_profile="fast_ingest",
            run_verify=True,  # profile should take precedence
        )
    )

    assert result["status"] == "succeeded"
    artifact_dir = tmp_path / "storage" / "artifacts" / paper_id / "run_fast_ingest"
    meta_path = artifact_dir / "bootstrap_meta.json"
    assert meta_path.exists()
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    assert meta["run_profile"] == "fast_ingest"
    assert meta["run_verify"] is False
    assert meta["artifact_document_written"] is True
    assert meta["artifact_index_written"] is True
    assert meta["artifact_claimset_written"] is False


def test_run_deepread_job_tag_trigger_runs_verify_and_reuses_stats_cache(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    paper_id = "tag_trigger_cache_case"
    config = _make_config(tmp_path, paper_id)
    pdf_path = config.paths.library_dir / f"{paper_id}.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n%fake\n")

    db_path = tmp_path / "state.db"
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE papers (
            paper_id TEXT PRIMARY KEY,
            doi TEXT,
            title TEXT NOT NULL,
            feedback_json TEXT
        )
        """
    )
    conn.execute(
        "INSERT INTO papers (paper_id, title, feedback_json) VALUES (?, ?, ?)",
        (paper_id, "Tag Trigger Cache", '{"soft_tags":["#action/stats_check"]}'),
    )
    conn.commit()
    conn.close()

    class FakeIngestAgent:
        def process_v2(self, path: str):
            return _make_doc_artifact(paper_id, path)

    class FakeIndexerAgent:
        def process(self, doc):
            return IndexArtifact(doc_id=doc.document_id, vector_store_id="smoke", chunk_count=1, chunks=[])

    class FakeReaderAgent:
        def __init__(self, *args, **kwargs):
            pass

        def analyze(self, doc):
            return ClaimSet(
                doc_id=doc.document_id,
                claims=[
                    ScientificClaim(
                        claim_id="c1",
                        type="efficacy",
                        statement="claim text",
                        confidence=0.9,
                    )
                ],
            )

    class CountingStatsAgent:
        calls = 0

        def run(self, job_id: str, doc, claims):
            CountingStatsAgent.calls += 1
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

    old_db = db_utils.DB_PATH
    db_utils.DB_PATH = db_path
    monkeypatch.setattr(job_runner_mod, "load_config", lambda: config)
    monkeypatch.setattr(job_runner_mod, "_load_similar_feedback_top3", lambda query_text, limit=3: [])
    monkeypatch.setattr(job_runner_mod, "IngestAgent", FakeIngestAgent)
    monkeypatch.setattr(job_runner_mod, "IndexerAgent", FakeIndexerAgent)
    monkeypatch.setattr(job_runner_mod, "ReaderAgent", FakeReaderAgent)
    monkeypatch.setattr(job_runner_mod, "StatsVerificationAgent", CountingStatsAgent)
    try:
        first = asyncio.run(
            job_runner_mod.run_deepread_job(
                job_id="job_tag_cache_1",
                paper_id=paper_id,
                run_id="run_tag_cache_1",
                run_verify=False,
                run_profile="grounded_read",
            )
        )
        assert first["status"] == "succeeded"
        assert CountingStatsAgent.calls == 1
        meta1 = json.loads(
            (tmp_path / "storage" / "artifacts" / paper_id / "run_tag_cache_1" / "bootstrap_meta.json").read_text(
                encoding="utf-8"
            )
        )
        assert meta1["run_verify"] is True
        assert "tags:#action/stats_check" in meta1["stats_trigger_reason"]
        assert meta1["stats_cache_hit"] is False
        assert meta1["verifier_status"] == "completed"
        assert meta1["stats_cache_key"]

        second = asyncio.run(
            job_runner_mod.run_deepread_job(
                job_id="job_tag_cache_2",
                paper_id=paper_id,
                run_id="run_tag_cache_2",
                run_verify=False,
                run_profile="grounded_read",
            )
        )
        assert second["status"] == "succeeded"
        assert CountingStatsAgent.calls == 1
        meta2 = json.loads(
            (tmp_path / "storage" / "artifacts" / paper_id / "run_tag_cache_2" / "bootstrap_meta.json").read_text(
                encoding="utf-8"
            )
        )
        assert meta2["stats_cache_hit"] is True
        assert meta2["verifier_status"] == "cache_hit"
        assert meta2["stats_cache_key"] == meta1["stats_cache_key"]
    finally:
        db_utils.DB_PATH = old_db
