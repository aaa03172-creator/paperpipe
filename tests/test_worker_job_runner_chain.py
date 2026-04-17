from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
import json
import sqlite3

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
    DocumentChunk,
    EvidenceSpan,
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
        vault_dir = tmp_path / "Vault"
        (vault_dir / "00_Index").mkdir(parents=True, exist_ok=True)
        (vault_dir / "Inbox").mkdir(parents=True, exist_ok=True)
        paper_id = "paper_chain_001"
        (library_dir / f"{paper_id}.pdf").write_bytes(b"%PDF-1.4\n%fake\n")
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
                )
            ),
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
                    chunks=[
                        DocumentChunk(
                            chunk_id="p01_c01",
                            text="smoke text",
                            section_name="page_1",
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
                                    page=0,
                                    quote="smoke text",
                                    raw_text="smoke text",
                                    rationale="direct quote",
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

        artifact_dir = Path(done.artifact_dir)
        assert (artifact_dir / "document_artifact.json").exists()
        assert (artifact_dir / "index_artifact.json").exists()
        assert (artifact_dir / "claimset.json").exists()
        assert (artifact_dir / "claimset.resolved.json").exists()
        assert (artifact_dir / "reader_eval.json").exists()
        assert (artifact_dir / "stats_report.json").exists()
        assert (artifact_dir / "bootstrap_meta.json").exists()
        assert (artifact_dir / "run_meta.json").exists()
        assert (artifact_dir / "acceptance_contract.json").exists()
        assert (artifact_dir / "quality_gate.json").exists()
        assert (artifact_dir / "context_manifest.json").exists()
        meta = json.loads((artifact_dir / "bootstrap_meta.json").read_text(encoding="utf-8"))
        resolved_claimset = json.loads((artifact_dir / "claimset.resolved.json").read_text(encoding="utf-8"))
        run_meta = json.loads((artifact_dir / "run_meta.json").read_text(encoding="utf-8"))
        quality_gate = json.loads((artifact_dir / "quality_gate.json").read_text(encoding="utf-8"))
        context_manifest = json.loads((artifact_dir / "context_manifest.json").read_text(encoding="utf-8"))
        assert meta["paper_id"] == paper_id
        assert run_meta["paper_id"] == paper_id
        assert run_meta["status"] == "succeeded"
        assert isinstance(run_meta.get("pdf_sha256"), str)
        assert len(run_meta["pdf_sha256"]) == 64
        assert "models_used" in run_meta
        assert "llm_params" in run_meta
        assert "embed_params" in run_meta
        assert run_meta["tool_policy_version"] == "v1"
        assert run_meta["reader_analysis"]["return_mode"] == "success"
        assert run_meta["reader_analysis"]["attempt_count"] == 1
        assert run_meta["handoff_artifacts"]["context_manifest_path"].endswith("context_manifest.json")
        assert "persona_id" in meta
        assert "similar_feedback_count" in meta
        assert meta["run_verify"] is True
        assert meta["verifier_used"] is True
        assert meta["verifier_status"] == "completed"
        assert meta["stats_report_written"] is True
        assert meta["artifact_document_written"] is True
        assert meta["artifact_index_written"] is True
        assert meta["artifact_claimset_written"] is True
        assert meta["artifact_claimset_resolved_written"] is True
        assert meta["artifact_reader_eval_written"] is True
        assert meta["artifact_acceptance_contract_written"] is True
        assert meta["artifact_quality_gate_written"] is True
        assert meta["artifact_stats_written"] is True
        assert meta["reader_model"] is not None
        assert meta["reader_analysis"]["selected_attempt_label"] == "primary"
        assert meta["claimset_readiness"] == "ready"
        assert meta["claimset_ready"] is True
        assert meta["claimset_claim_count"] == 1
        assert meta["claimset_grounded_span_count"] == 1
        assert meta["claimset_unresolved_span_count"] == 0
        assert meta["reader_eval_claim_count"] == 1
        assert meta["reader_eval_supported_claim_count"] == 1
        assert meta["reader_eval_unsupported_claim_count"] == 0
        assert meta["claimset_readiness_reason"] == "claims_present"
        assert meta["claimset_readiness_badge"] == "READY"
        assert meta["claimset_ops_action"] == "none"
        assert meta["claimset_ops_alert"] is False
        assert meta["claimset_ops_note"] == "ready"

        conn = sqlite3.connect(db_utils.DB_PATH)
        completion = conn.execute(
            """
            SELECT event_type, level, message, payload_json
            FROM job_events
            WHERE job_id = ?
            ORDER BY rowid DESC
            LIMIT 1
            """,
            (job_id_1,),
        ).fetchone()
        conn.close()
        assert completion is not None
        assert completion[0] == "job_completed"
        assert completion[1] == "INFO"
        assert completion[2] == "completed"
        assert json.loads(completion[3])["status"] == "completed"
        span = resolved_claimset["claims"][0]["evidence_spans"][0]
        assert span["chunk_id"] == "p01_c01"
        assert span["page"] == 0
        assert span["grounded"] is True
        assert span["resolution"] == "OK"
        assert quality_gate["overall_status"] == "pass"
        assert quality_gate["review_ready"] is True
        assert quality_gate["current_promotion_candidate"] is True
        assert context_manifest["selected_attempt_label"] == "primary"
        assert context_manifest["selected_attempt_summary"]["label"] == "primary"

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

        note_content = note_path.read_text(encoding="utf-8")
        assert note_content.count("## 🤖 Agent Deep Read") == 1
        assert "smoke claim" in note_content
        structured_path = vault_dir / ".pp" / "paper_chain_001" / "state.json"
        assert structured_path.exists()
        structured_state = json.loads(structured_path.read_text(encoding="utf-8"))
        assert structured_state["signals"]["state_source"] == "deep_read_promotion"
        assert structured_state["runs"][0]["action"] == "deep_read"
        assert structured_state["runs"][0]["id"] == done.run_id
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
        config_dir = tmp_path / "config"
        config_dir.mkdir(parents=True, exist_ok=True)
        profiles_path = config_dir / "profiles.yaml"
        profiles_path.write_text(
            "# local runtime profiles\nprofiles: []\n",
            encoding="utf-8",
        )
        monkeypatch.setenv("PAPERPIPE_PROFILES_PATH", str(profiles_path))
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
                            blocks=[
                                BlockV2(
                                    block_id="b1",
                                    lines=[LineV2(line_id="l1", text="x", spans=[SpanV2(span_id="s1", text="x")])],
                                )
                            ],
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
        assert run_meta["status"] == "failed"
        assert run_meta["reader_timeout_budget_sec"] == 123
        assert run_meta["reader_timeout_triggered"] is True
        assert run_meta["reader_timeout_error_type"] == "ReadTimeout"
        prompts_snapshot = Path(str(run_meta["prompts_snapshot"]))
        assert prompts_snapshot.exists()
        assert prompts_snapshot.read_text(encoding="utf-8") == "# local runtime profiles\nprofiles: []\n"

        conn = sqlite3.connect(db_utils.DB_PATH)
        failure = conn.execute(
            """
            SELECT event_type, level, message, payload_json
            FROM job_events
            WHERE job_id = ?
            ORDER BY rowid DESC
            LIMIT 1
            """,
            (job_id,),
        ).fetchone()
        conn.close()
        assert failure is not None
        assert failure[0] == "job_failed"
        assert failure[1] == "ERROR"
        assert failure[2] == "Reader step timed out after 123s (pages=1, tables=0)"
        assert json.loads(failure[3])["status"] == "failed"
    finally:
        db_utils.DB_PATH = original_db_path


def test_worker_clean_reindex_requests_index_reset(tmp_path, monkeypatch):
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

        reset_calls: list[str] = []

        class FakeIndexerAgent:
            def reset_doc_index(self, doc_id: str) -> int:
                reset_calls.append(doc_id)
                return 3

            def process(self, doc):
                return IndexArtifact(doc_id=doc.document_id, vector_store_id="smoke", chunk_count=1, chunks=[])

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
        assert reset_calls == [paper_id]

        artifact_dir = Path(done.artifact_dir)
        meta = json.loads((artifact_dir / "bootstrap_meta.json").read_text(encoding="utf-8"))
        assert meta["clean_reindex_requested"] is True
        assert meta["clean_reindex_applied"] is True
        assert meta["clean_reindex_removed_chunks"] == 3
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
