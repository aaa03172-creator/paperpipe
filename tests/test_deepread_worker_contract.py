from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient

import src.db_utils as db_utils
import src.jobs.worker as worker_mod
import backend.services.job_runner as job_runner_mod
from backend import main as api_main
from src.contracts.document_artifact_v2 import ArtifactMetaV2, BlockV2, DocumentArtifactV2, LineV2, PageV2, SpanV2
from src.jobs.queue import JobQueue
from src.schemas.agent_artifacts import (
    ClaimSet,
    DocumentChunk,
    EvidenceSpan,
    IndexArtifact,
    ScientificClaim,
    StatCheckEntry,
    StatsReport,
    VerificationStatus,
)


def test_deepread_api_enqueue_real_worker_contract_smoke(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("LATTICE_API_KEY", raising=False)
    monkeypatch.delenv("PAPERPIPE_API_KEY", raising=False)

    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()

        library_dir = tmp_path / "Library"
        vault_dir = tmp_path / "Vault"
        paper_id = "paper_contract_worker_001"
        library_dir.mkdir(parents=True, exist_ok=True)
        (vault_dir / "00_Index").mkdir(parents=True, exist_ok=True)
        (vault_dir / "Inbox").mkdir(parents=True, exist_ok=True)
        (library_dir / f"{paper_id}.pdf").write_bytes(b"%PDF-1.4\n%contract smoke\n")
        note_path = vault_dir / "Inbox" / f"{paper_id}.md"
        note_path.write_text("# Contract Worker Paper\n\nInitial note\n", encoding="utf-8")
        (vault_dir / "00_Index" / "paper_collection.csv").write_text(
            "Paper_ID,DOI,Title,Note_Path\n"
            f"{paper_id},10.1000/contract-worker,Contract Worker Paper,Inbox/{paper_id}.md\n",
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
                    meta=ArtifactMetaV2(
                        title="Contract Worker Paper",
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
                                            text="contract worker evidence quote",
                                            spans=[
                                                SpanV2(
                                                    span_id="s1",
                                                    text="contract worker evidence quote",
                                                )
                                            ],
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
                    vector_store_id="contract-worker",
                    chunk_count=1,
                    chunks=[
                        DocumentChunk(
                            chunk_id="p01_c01",
                            text="contract worker evidence quote",
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
                    "attempts": [],
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
                            statement="contract worker claim",
                            confidence=0.9,
                            evidence_spans=[
                                EvidenceSpan(
                                    quote="contract worker evidence quote",
                                    raw_text="contract worker evidence quote",
                                    rationale="direct fixture quote",
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
                            test_type="contract-smoke",
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

        client = TestClient(api_main.app)
        enqueued = client.post(
            "/jobs/deepread",
            json={
                "paper_id": paper_id,
                "run_verify": True,
                "reasoning_persona": "researcher",
                "profile_id": "contract-profile",
            },
        )
        assert enqueued.status_code == 200
        enqueue_payload = enqueued.json()
        job_id = enqueue_payload["job_id"]
        run_id = enqueue_payload["run_id"]
        assert enqueue_payload["status"] == "queued"

        claimed = JobQueue().claim_next_job()
        assert claimed is not None
        assert claimed.job_id == job_id

        worker_mod.Worker().process_job(claimed)

        job_response = client.get(f"/jobs/{job_id}")
        assert job_response.status_code == 200
        job_payload = job_response.json()
        assert job_payload["status"] == "completed"
        assert job_payload["progress"] == 100
        assert job_payload["stage"] == "completed"
        assert job_payload["paper_id"] == paper_id
        assert job_payload["run_id"] == run_id
        assert job_payload["reasoning_persona"] == "researcher"
        assert job_payload["profile_id"] == "contract-profile"
        assert job_payload["artifact_document_written"] is True
        assert job_payload["artifact_index_written"] is True
        assert job_payload["artifact_claimset_written"] is True
        assert job_payload["artifact_claimset_resolved_written"] is True
        assert job_payload["artifact_stats_written"] is True
        assert job_payload["claimset_readiness"] == "ready"
        assert job_payload["claimset_claim_count"] == 1
        assert job_payload["bootstrap_meta_path"].endswith("bootstrap_meta.json")

        run_response = client.get(f"/runs/{run_id}")
        assert run_response.status_code == 200
        assert run_response.json()["job_id"] == job_id

        bootstrap = client.get(f"/jobs/{job_id}/bootstrap-meta")
        assert bootstrap.status_code == 200
        bootstrap_payload = bootstrap.json()
        assert bootstrap_payload["paper_id"] == paper_id
        assert bootstrap_payload["run_id"] == run_id
        assert bootstrap_payload["claimset_readiness"] == "ready"

        artifacts = client.get(f"/artifacts/{paper_id}/{run_id}")
        assert artifacts.status_code == 200
        artifact_payload = artifacts.json()
        assert artifact_payload["paper_id"] == paper_id
        assert artifact_payload["run_id"] == run_id
        assert artifact_payload["files"]["document_artifact"]["exists"] is True
        assert artifact_payload["files"]["claimset"]["exists"] is True
        assert artifact_payload["files"]["stats_report"]["exists"] is True
        assert artifact_payload["files"]["run_meta"]["data"]["status"] == "succeeded"

        timeline = client.get(f"/runs/{run_id}/timeline")
        assert timeline.status_code == 200
        timeline_payload = timeline.json()
        assert timeline_payload["job_id"] == job_id
        assert timeline_payload["paper_id"] == paper_id
        assert any(event["event"] == "done" and event["message"] == "completed" for event in timeline_payload["events"])
        assert "contract worker claim" in note_path.read_text(encoding="utf-8")
    finally:
        db_utils.DB_PATH = original_db_path
