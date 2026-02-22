from __future__ import annotations

import sqlite3
from pathlib import Path

import src.db_utils as db_utils
from backend.services.stats_runtime import (
    build_stats_cache_key,
    load_cached_stats_report,
    resolve_stats_trigger_for_paper,
    save_cached_stats_report,
)
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
    ScientificClaim,
    StatCheckEntry,
    StatsReport,
    VerificationStatus,
)


def _make_doc() -> DocumentArtifactV2:
    return DocumentArtifactV2(
        document_id="paper_runtime",
        meta=ArtifactMetaV2(
            title="Runtime Test",
            authors=["A"],
            source_ref="paper_runtime.pdf",
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
                                text="runtime text",
                                spans=[SpanV2(span_id="s1", text="runtime text")],
                            )
                        ],
                    )
                ],
            )
        ],
        tables=[],
    )


def _make_claims() -> ClaimSet:
    return ClaimSet(
        doc_id="paper_runtime",
        claims=[
            ScientificClaim(
                claim_id="c1",
                type="efficacy",
                statement="runtime claim",
                confidence=0.9,
            )
        ],
    )


def _make_report() -> StatsReport:
    return StatsReport(
        doc_id="paper_runtime",
        run_id="job_runtime",
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


def test_resolve_stats_trigger_from_feedback_tags(tmp_path):
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
        ("paper_tag_trigger", "Tag Trigger", '{"soft_tags":["#important"]}'),
    )
    conn.commit()
    conn.close()

    old_db = db_utils.DB_PATH
    db_utils.DB_PATH = db_path
    try:
        should_run, reason = resolve_stats_trigger_for_paper(
            "paper_tag_trigger",
            run_verify=False,
            run_profile="grounded_read",
        )
        assert should_run is True
        assert "#important" in reason

        skip, skip_reason = resolve_stats_trigger_for_paper(
            "paper_tag_trigger",
            run_verify=True,
            run_profile="fast_ingest",
        )
        assert skip is False
        assert skip_reason == "profile:fast_ingest_skip"
    finally:
        db_utils.DB_PATH = old_db


def test_stats_cache_roundtrip(tmp_path):
    doc = _make_doc()
    claims = _make_claims()
    report = _make_report()

    cache_dir = tmp_path / "stats_cache"
    cache_key, paper_hash = build_stats_cache_key(
        doc_artifact=doc,
        claim_set=claims,
        stats_profile="deep_verify",
        schema_version="1.0",
    )
    assert cache_key
    assert paper_hash

    save_path = save_cached_stats_report(cache_dir, cache_key, report)
    assert save_path.exists()

    loaded, loaded_path = load_cached_stats_report(cache_dir, cache_key)
    assert loaded is not None
    assert loaded_path == save_path
    assert loaded.doc_id == "paper_runtime"
    assert len(loaded.checks) == 1
