from pathlib import Path
import json
from types import SimpleNamespace

import src.db_utils as db_utils
import src.jobs.worker as worker_mod
from src.jobs.queue import JobQueue
import backend.services.job_runner as job_runner_mod

from src.contracts.document_artifact_v2 import ArtifactMetaV2, BlockV2, DocumentArtifactV2, LineV2, PageV2, SpanV2
from src.schemas.agent_artifacts import ClaimSet, DocumentChunk, EvidenceSpan, IndexArtifact, ScientificClaim
from src.services.citation_grounding import resolve_claimset_grounding
from src.services.reader_eval_sidecar import build_reader_eval_sidecar


def test_build_reader_eval_sidecar_summarizes_grounding_and_heuristics():
    claimset = ClaimSet(
        doc_id="paper-1",
        claims=[
            ScientificClaim(
                claim_id="c1",
                type="efficacy",
                statement="Drug A improved memory score.",
                confidence=0.9,
                evidence_spans=[
                    EvidenceSpan(
                        chunk_id="p01_c01",
                        quote="improved memory score",
                        raw_text="Drug A improved memory score in the treatment arm.",
                        rationale="quoted directly",
                    )
                ],
                limitations=["single-center study"],
            ),
            ScientificClaim(
                claim_id="c2",
                type="efficacy",
                statement="Fallback sentence selected by heuristic.",
                confidence=0.4,
                evidence_spans=[
                    EvidenceSpan(
                        chunk_id="p01_c02",
                        quote="Fallback sentence selected by heuristic.",
                        raw_text="Fallback sentence selected by heuristic.",
                        rationale="Heuristic fallback: sentence selected from source text by statistical/result cue.",
                    )
                ],
                limitations=["Heuristic fallback extraction; manual review recommended."],
                unknown=True,
                unknown_reason="HEURISTIC_BACKFILL",
            ),
        ],
    )
    index_artifact = IndexArtifact(
        doc_id="paper-1",
        vector_store_id="v1",
        chunk_count=2,
        chunks=[
            DocumentChunk(
                chunk_id="p01_c01",
                text="Drug A improved memory score in the treatment arm. This single-center study may limit generalizability.",
                section_name="Results",
                page_hint=1,
            ),
            DocumentChunk(
                chunk_id="p01_c02",
                text="Fallback sentence selected by heuristic.",
                section_name="Discussion",
                page_hint=1,
            ),
        ],
    )
    resolved = resolve_claimset_grounding(claimset, index_artifact)

    sidecar = build_reader_eval_sidecar(
        paper_id="paper-1",
        run_id="run-1",
        claimset=claimset,
        resolved_claimset=resolved,
        index_artifact=index_artifact,
    )

    assert sidecar.schema_version == "reader_eval.v1"
    assert sidecar.metrics.claim_count == 2
    assert sidecar.metrics.supported_claim_count == 1
    assert sidecar.metrics.unknown_claim_count == 1
    assert sidecar.metrics.heuristic_backfill_claim_count == 1
    assert sidecar.metrics.text_match_span_count == 2
    assert sidecar.metrics.bbox_span_count == 0
    assert sidecar.metrics.approx_span_count == 0
    assert sidecar.metrics.grounded_span_count == 2
    assert sidecar.metrics.grounded_limitation_count == 1
    first = sidecar.claims[0]
    assert first.supported is True
    assert first.grounding_resolutions == ["OK"]
    assert first.text_match_span_count == 1
    assert first.grounded_limitation_count == 1
    second = sidecar.claims[1]
    assert second.heuristic_backfill is True
    assert second.unknown is True
    assert second.unknown_reason == "HEURISTIC_BACKFILL"
    assert second.text_match_span_count == 1


def test_build_reader_eval_sidecar_tracks_locator_source_mix():
    claimset = ClaimSet(
        doc_id="paper-locator",
        claims=[
            ScientificClaim(
                claim_id="c-bbox",
                type="finding",
                statement="BBox-backed claim.",
                confidence=0.9,
                evidence_spans=[
                    EvidenceSpan(
                        quote="bbox evidence",
                        raw_text="bbox evidence",
                        highlight_source="bbox",
                        grounded=True,
                        resolution="OK",
                    )
                ],
            ),
            ScientificClaim(
                claim_id="c-text",
                type="finding",
                statement="Text-match claim.",
                confidence=0.8,
                evidence_spans=[
                    EvidenceSpan(
                        quote="text match evidence",
                        raw_text="text match evidence",
                        highlight_source="text_match",
                        grounded=True,
                        resolution="NORMALIZED_MATCH",
                    )
                ],
            ),
            ScientificClaim(
                claim_id="c-approx",
                type="finding",
                statement="Approximate claim.",
                confidence=0.5,
                evidence_spans=[
                    EvidenceSpan(
                        quote="approx evidence",
                        raw_text="approx evidence",
                        highlight_source="approx",
                        grounded=False,
                        resolution="FAILED_MATCH",
                    )
                ],
                unknown=True,
                unknown_reason="EVIDENCE_LOCATION_MISSING",
            ),
        ],
    )
    resolved_claimset = claimset.model_copy(deep=True)
    index_artifact = IndexArtifact(doc_id="paper-locator", vector_store_id="v1", chunk_count=0, chunks=[])

    sidecar = build_reader_eval_sidecar(
        paper_id="paper-locator",
        run_id="run-locator",
        claimset=claimset,
        resolved_claimset=resolved_claimset,
        index_artifact=index_artifact,
    )

    assert sidecar.metrics.evidence_span_count == 3
    assert sidecar.metrics.bbox_span_count == 1
    assert sidecar.metrics.text_match_span_count == 1
    assert sidecar.metrics.approx_span_count == 1
    assert sidecar.metrics.unresolved_span_count == 1
    assert sidecar.metrics.failed_grounding_span_count == 1


def test_job_runner_writes_reader_eval_sidecar(tmp_path, monkeypatch):
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
        paper_id = "paper_reader_eval_001"
        (library_dir / f"{paper_id}.pdf").write_bytes(b"%PDF-1.4\n%fake\n")
        note_path = vault_dir / "Inbox" / "paper_reader_eval_001.md"
        note_path.write_text("# Paper\n\nInitial\n", encoding="utf-8")
        (vault_dir / "00_Index" / "paper_collection.csv").write_text(
            "Paper_ID,DOI,Title,Note_Path\n"
            "paper_reader_eval_001,10.1000/test,Reader Eval Title,Inbox/paper_reader_eval_001.md\n",
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
                    meta=ArtifactMetaV2(title="Reader Eval Title", authors=["A"], source_ref=pdf_path),
                    pages=[
                        PageV2(
                            page_index=0,
                            width=595.0,
                            height=842.0,
                            blocks=[
                                BlockV2(
                                    block_id="b1",
                                    bbox_pdf=[0.0, 0.0, 595.0, 842.0],
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

        monkeypatch.setattr(job_runner_mod, "IngestAgent", FakeIngestAgent)
        monkeypatch.setattr(job_runner_mod, "IndexerAgent", FakeIndexerAgent)
        monkeypatch.setattr(job_runner_mod, "ReaderAgent", FakeReaderAgent)

        queue = JobQueue()
        job_id = queue.enqueue(paper_id=paper_id, clean_reindex=False, run_verify=False, persona_id="default")
        claimed = queue.claim_next_job()
        assert claimed is not None

        worker = worker_mod.Worker()
        worker.process_job(claimed)

        done = queue.get_job(job_id)
        assert done is not None
        assert done.status == "completed"
        artifact_dir = Path(done.artifact_dir)
        sidecar = json.loads((artifact_dir / "reader_eval.json").read_text(encoding="utf-8"))
        meta = json.loads((artifact_dir / "bootstrap_meta.json").read_text(encoding="utf-8"))
        resolved_claimset = json.loads((artifact_dir / "claimset.resolved.json").read_text(encoding="utf-8"))
        assert sidecar["schema_version"] == "reader_eval.v1"
        assert sidecar["metrics"]["claim_count"] == 1
        assert sidecar["metrics"]["bbox_span_count"] == 1
        assert sidecar["metrics"]["text_match_span_count"] == 0
        assert sidecar["metrics"]["grounded_span_count"] == 1
        assert sidecar["claims"][0]["supported"] is True
        assert sidecar["claims"][0]["grounding_resolutions"] == ["OK"]
        assert meta["artifact_reader_eval_written"] is True
        assert meta["reader_eval_claim_count"] == 1
        assert meta["reader_eval_supported_claim_count"] == 1
        assert meta["reader_eval_unsupported_claim_count"] == 0
        assert meta["reader_eval_bbox_span_count"] == 1
        assert meta["reader_eval_text_match_span_count"] == 0
        assert meta["reader_eval_approx_span_count"] == 0
        span = resolved_claimset["claims"][0]["evidence_spans"][0]
        assert span["highlight_source"] == "bbox"
        assert span["bbox_pdf"] == [0.0, 0.0, 595.0, 842.0]
    finally:
        db_utils.DB_PATH = original_db_path
