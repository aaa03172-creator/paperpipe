from pathlib import Path
import json
from types import SimpleNamespace

import src.db_utils as db_utils
import src.jobs.worker as worker_mod
from src.jobs.queue import JobQueue
import backend.services.job_runner as job_runner_mod

from src.contracts.document_artifact_v2 import ArtifactMetaV2, BlockV2, DocumentArtifactV2, LineV2, PageV2, SpanV2
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
from src.services.stats_fallback_eval_sidecar import build_stats_fallback_eval_sidecar


def test_build_stats_fallback_eval_sidecar_summarizes_taxonomy():
    report = StatsReport(
        doc_id="paper-1",
        run_id="run-1",
        checks=[
            StatCheckEntry(
                check_id="c1",
                test_type="unknown",
                method="auto_fallback",
                code="N/A",
                outputs="skip",
                verdict=VerificationStatus.UNVERIFIABLE,
                notes="auto_fallback_degenerate_table_shape",
            ),
            StatCheckEntry(
                check_id="c2",
                test_type="unknown",
                method="no_table_data",
                code="N/A",
                outputs="no table",
                verdict=VerificationStatus.UNVERIFIABLE,
                notes="no_table_data",
            ),
            StatCheckEntry(
                check_id="c3",
                test_type="t-test",
                code="print('ok')",
                outputs="ok",
                verdict=VerificationStatus.VERIFIED,
            ),
        ],
    )
    sidecar = build_stats_fallback_eval_sidecar(
        paper_id="paper-1",
        stats_report=report,
        bootstrap_meta={
            "table_extraction_pass": "pass3",
            "table_failure_taxonomy": ["LOW_ACCURACY", "NO_API"],
            "fallback_used": True,
            "fallback_pages": [2, 4],
        },
    )

    assert sidecar.schema_version == "stats_fallback_eval.v1"
    assert sidecar.table_extraction_pass == "pass3"
    assert sidecar.fallback_used is True
    assert sidecar.metrics.check_count == 3
    assert sidecar.metrics.unverifiable_count == 2
    assert sidecar.metrics.auto_fallback_count == 1
    assert sidecar.metrics.no_table_count == 1
    assert sidecar.metrics.no_api_context_count == 0
    assert sidecar.metrics.degenerate_table_shape_count == 1
    assert sidecar.metrics.verified_count == 1


def test_build_stats_fallback_eval_sidecar_infers_no_api_context_from_bootstrap_meta():
    report = StatsReport(
        doc_id="paper-1",
        run_id="run-1",
        checks=[
            StatCheckEntry(
                check_id="c1",
                test_type="anova",
                code="print('na')",
                outputs="na",
                verdict=VerificationStatus.UNVERIFIABLE,
            ),
        ],
    )

    sidecar = build_stats_fallback_eval_sidecar(
        paper_id="paper-1",
        stats_report=report,
        bootstrap_meta={
            "anchor_verify_summary": {"pass": 0, "warn": 0, "fail": 0, "no_api": 1},
            "anchor_verify_api": {"reason_codes": ["NO_API"]},
        },
    )

    assert sidecar.metrics.unverifiable_count == 1
    assert sidecar.metrics.unspecified_unverifiable_count == 0
    assert sidecar.metrics.no_api_context_count == 1
    assert sidecar.checks[0].fallback_reason == "NO_API_CONTEXT"


def test_job_runner_writes_stats_fallback_eval_sidecar(tmp_path, monkeypatch):
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
        paper_id = "paper_stats_eval_001"
        (library_dir / f"{paper_id}.pdf").write_bytes(b"%PDF-1.4\n%fake\n")
        note_path = vault_dir / "Inbox" / "paper_stats_eval_001.md"
        note_path.write_text("# Paper\n\nInitial\n", encoding="utf-8")
        (vault_dir / "00_Index" / "paper_collection.csv").write_text(
            "Paper_ID,DOI,Title,Note_Path\n"
            "paper_stats_eval_001,10.1000/test,Stats Eval Title,Inbox/paper_stats_eval_001.md\n",
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
            def __init__(self, *args, **kwargs):
                self.last_table_extraction_meta = {
                    "table_extraction_pass": "pass3",
                    "table_failure_taxonomy": ["LOW_ACCURACY", "NO_API"],
                    "fallback_used": True,
                    "fallback_pages": [1],
                }

            def process_v2(self, pdf_path: str):
                return DocumentArtifactV2(
                    document_id=paper_id,
                    meta=ArtifactMetaV2(title="Stats Eval Title", authors=["A"], source_ref=pdf_path),
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
                                            text="Drug A improved memory score in the treatment arm.",
                                            spans=[SpanV2(span_id="s1", text="Drug A improved memory score in the treatment arm.")],
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
                            text="Drug A improved memory score in the treatment arm.",
                            section_name="page_1",
                            page_hint=1,
                        )
                    ],
                )

        class FakeReaderAgent:
            def analyze(self, doc):
                return ClaimSet(
                    doc_id=doc.document_id,
                    claims=[
                        ScientificClaim(
                            claim_id="c1",
                            type="efficacy",
                            statement="Drug A improved memory score.",
                            confidence=0.9,
                            evidence_spans=[
                                EvidenceSpan(
                                    page=0,
                                    quote="improved memory score",
                                    raw_text="Drug A improved memory score in the treatment arm.",
                                    rationale="direct quote",
                                    chunk_id="p01_c01",
                                    section="page_1",
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
                            test_type="unknown",
                            method="auto_fallback",
                            code="N/A",
                            outputs="skip",
                            verdict=VerificationStatus.UNVERIFIABLE,
                            notes="auto_fallback_degenerate_table_shape",
                        )
                    ],
                )

        monkeypatch.setattr(job_runner_mod, "IngestAgent", FakeIngestAgent)
        monkeypatch.setattr(job_runner_mod, "IndexerAgent", FakeIndexerAgent)
        monkeypatch.setattr(job_runner_mod, "ReaderAgent", FakeReaderAgent)
        monkeypatch.setattr(job_runner_mod, "StatsVerificationAgent", FakeStatsAgent)

        queue = JobQueue()
        job_id = queue.enqueue(paper_id=paper_id, clean_reindex=False, run_verify=True, persona_id="default")
        claimed = queue.claim_next_job()
        assert claimed is not None

        worker = worker_mod.Worker()
        worker.process_job(claimed)

        done = queue.get_job(job_id)
        assert done is not None
        assert done.status == "completed"
        artifact_dir = Path(done.artifact_dir)
        sidecar = json.loads((artifact_dir / "stats_fallback_eval.json").read_text(encoding="utf-8"))
        meta = json.loads((artifact_dir / "bootstrap_meta.json").read_text(encoding="utf-8"))
        assert sidecar["schema_version"] == "stats_fallback_eval.v1"
        assert sidecar["table_extraction_pass"] == "pass3"
        assert sidecar["fallback_used"] is True
        assert sidecar["metrics"]["check_count"] == 1
        assert sidecar["metrics"]["unverifiable_count"] == 1
        assert sidecar["metrics"]["degenerate_table_shape_count"] == 1
        assert sidecar["metrics"]["no_api_context_count"] == 0
        assert sidecar["checks"][0]["fallback_reason"] == "degenerate_table_shape"
        assert meta["artifact_stats_fallback_eval_written"] is True
        assert meta["stats_fallback_eval_check_count"] == 1
        assert meta["stats_fallback_eval_unverifiable_count"] == 1
        assert meta["stats_fallback_eval_auto_fallback_count"] == 1
    finally:
        db_utils.DB_PATH = original_db_path
