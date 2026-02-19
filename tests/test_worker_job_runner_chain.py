from pathlib import Path
from types import SimpleNamespace

import src.db_utils as db_utils
import src.jobs.worker as worker_mod
from src.jobs.queue import JobQueue
import backend.services.job_runner as job_runner_mod

from src.contracts.document_artifact_v2 import (
    DocumentArtifactV2,
    ArtifactMetaV2,
    PageV2,
    BlockV2,
    LineV2,
    SpanV2,
)
from src.schemas.agent_artifacts import (
    IndexArtifact,
    ClaimSet,
    ScientificClaim,
    StatsReport,
    StatCheckEntry,
    VerificationStatus,
)


def test_worker_uses_real_job_runner_chain_smoke(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()

        library_dir = tmp_path / "Library"
        library_dir.mkdir(parents=True, exist_ok=True)
        paper_id = "paper_chain_001"
        (library_dir / f"{paper_id}.pdf").write_bytes(b"%PDF-1.4\n%fake\n")

        # Keep worker path real; only patch heavy agent internals inside job_runner.
        monkeypatch.setattr(
            job_runner_mod,
            "load_config",
            lambda: SimpleNamespace(paths=SimpleNamespace(library_dir=library_dir)),
        )

        class FakeIngestAgent:
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
                    chunks=[],
                )

        class FakeReaderAgent:
            def analyze(self, doc):
                return ClaimSet(
                    doc_id=doc.document_id,
                    claims=[
                        ScientificClaim(
                            claim_id="c1",
                            type="efficacy",
                            statement="smoke claim",
                            confidence=0.9,
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
        job_id = queue.enqueue(
            paper_id=paper_id,
            clean_reindex=False,
            run_verify=True,
            persona_id="smoke-persona",
        )
        claimed = queue.claim_next_job()
        assert claimed is not None
        assert claimed.job_id == job_id

        worker = worker_mod.Worker()
        worker.process_job(claimed)

        done = queue.get_job(job_id)
        assert done is not None
        assert done.status == "completed"
        assert done.stage == "completed"
        assert done.progress == 100
        assert done.artifact_dir is not None

        artifact_dir = Path(done.artifact_dir)
        assert (artifact_dir / "document_artifact.json").exists()
        assert (artifact_dir / "index_artifact.json").exists()
        assert (artifact_dir / "claimset.json").exists()
        assert (artifact_dir / "stats_report.json").exists()
    finally:
        db_utils.DB_PATH = original_db_path
