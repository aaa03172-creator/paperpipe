from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from scripts.backfill_operational_outputs import (
    BackfillCandidate,
    collect_backfill_candidates,
    enqueue_claimset_backfill,
)


def test_collect_backfill_candidates_detects_missing_markdown_and_claimset(tmp_path: Path, monkeypatch):
    vault = tmp_path / "vault"
    (vault / "Inbox/PaperPipe").mkdir(parents=True, exist_ok=True)
    existing = vault / "Inbox/PaperPipe/OK.md"
    existing.write_text("# ok", encoding="utf-8")

    artifacts = tmp_path / "artifacts"
    (artifacts / "doi:10.1000/ok" / "run_a").mkdir(parents=True, exist_ok=True)
    (artifacts / "doi:10.1000/ok" / "run_a" / "claimset.json").write_text(
        json.dumps({"claims": [{"statement": "ok"}]}),
        encoding="utf-8",
    )
    monkeypatch.setenv("PAPERPIPE_ARTIFACTS_DIR", str(artifacts))

    rows = [
        {
            "paper_id": "doi:10.1000/missing",
            "title": "Missing",
            "obsidian_path": "Inbox/PaperPipe/Missing.md",
            "feedback_json": "{}",
            "pdf_path": None,
        },
        {
            "paper_id": "doi:10.1000/ok",
            "title": "OK",
            "obsidian_path": "Inbox/PaperPipe/OK.md",
            "feedback_json": json.dumps({"claims": [{"statement": "x"}]}),
            "pdf_path": None,
        },
        {
            "paper_id": "local--fixture",
            "title": "Fixture",
            "obsidian_path": "Inbox/PaperPipe/Fixture.md",
            "feedback_json": "{}",
            "pdf_path": None,
        },
    ]

    candidates = collect_backfill_candidates(rows, vault_path=vault, include_test_fixtures=False)
    assert len(candidates) == 1
    assert candidates[0].paper_id == "doi:10.1000/missing"
    assert candidates[0].pdf_ready is False
    assert candidates[0].markdown_missing is True
    assert candidates[0].claimset_missing is True


def test_enqueue_claimset_backfill_skips_open_jobs(monkeypatch):
    conn = sqlite3.connect(":memory:")
    try:
        conn.execute("CREATE TABLE jobs (job_id TEXT, paper_id TEXT, status TEXT)")
        conn.execute("INSERT INTO jobs (job_id, paper_id, status) VALUES ('j1', 'p_open', 'queued')")
        conn.commit()

        enqueued_ids: list[str] = []

        class DummyQueue:
            def enqueue(self, paper_id: str, clean_reindex: bool = False, run_verify: bool = False, persona_id: str = "default"):
                enqueued_ids.append(paper_id)
                return f"job-{paper_id}"

        monkeypatch.setattr("scripts.backfill_operational_outputs.JobQueue", DummyQueue)

        candidates = [
            BackfillCandidate("p_open", "Open", pdf_ready=True, markdown_missing=True, claimset_missing=True),
            BackfillCandidate("p_new", "New", pdf_ready=True, markdown_missing=False, claimset_missing=True),
            BackfillCandidate("p_pdf_missing", "NoPDF", pdf_ready=False, markdown_missing=False, claimset_missing=True),
            BackfillCandidate("p_md_only", "MD", pdf_ready=True, markdown_missing=True, claimset_missing=False),
        ]
        enqueued, skipped_open, skipped_pdf = enqueue_claimset_backfill(
            conn,
            candidates=candidates,
            limit=10,
            require_pdf_ready=True,
            run_verify=False,
            persona_id="default",
        )

        assert enqueued == 1
        assert skipped_open == 1
        assert skipped_pdf == 1
        assert enqueued_ids == ["p_new"]
    finally:
        conn.close()
