from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from src.profiles.research_dna_schema import PilotConfig, QueryVersion
from src.profiles.research_dna_service import (
    ResearchDNAStateError,
    approve_pilot,
    create_research_dna,
    lock_research_dna,
    log_interview_response,
    run_pilot,
    refine_query_version,
    submit_screening_decision,
    unlock_research_dna,
    update_research_dna,
)
from src.profiles.research_dna_schema import ResearchDNAUpdate
from src.profiles.research_dna_store import load_research_dna, research_dna_log_path
from src.schemas import Paper


def _read_jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


class _FakeFetcher:
    def __init__(self, papers):
        self._papers = papers

    def fetch(self, query: str, max_results: int):
        return self._papers[:max_results]


class _FailingFetcher:
    def fetch(self, query: str, max_results: int):
        raise RuntimeError("fetch failed")


def test_create_approve_refine_lock_unlock_flow(tmp_path):
    root = tmp_path / "research_dna"

    dna = create_research_dna(
        topic="Mild cognitive impairment and medium-chain triglycerides",
        intent="systematic_review",
        actor_type="human_cli",
        actor_id="tester",
        reason="create draft",
        root=root,
        available_databases=["pubmed"],
        recommended_databases=["pubmed", "embase"],
    )
    assert dna.id == "dna_mild_cognitive_impairment_and_medium_chain_triglycerides"
    assert dna.status == "DRAFT"

    approved = approve_pilot(
        dna.id,
        actor_type="human_cli",
        actor_id="tester",
        reason="ready for pilot",
        root=root,
    )
    assert approved.status == "PILOT"
    assert approved.governance.approved_for_pilot_by == "human_cli:tester"

    refined = refine_query_version(
        dna.id,
        query_version=QueryVersion(
            version="v2",
            mode="precision",
            per_db={"pubmed": "(\"mild cognitive impairment\") AND (\"medium chain triglyceride oil\")"},
            change_summary="reduce broad acronym noise",
            created_at=datetime(2026, 3, 11, tzinfo=timezone.utc),
            created_by="human_cli:tester",
        ),
        actor_type="human_cli",
        actor_id="tester",
        reason="reason-code refinement",
        root=root,
    )
    assert refined.query_versions[-1].version == "v2"

    submit_screening_decision(
        dna.id,
        run_id="pilot_001",
        candidate_id="pmid:123",
        decision="exclude",
        reason_code="wrong_population",
        actor_type="human_cli",
        actor_id="tester",
        root=root,
    )

    locked = lock_research_dna(
        dna.id,
        actor_type="human_cli",
        actor_id="tester",
        reason="pilot stabilized",
        root=root,
    )
    assert locked.status == "LOCKED"

    unlocked = unlock_research_dna(
        dna.id,
        actor_type="human_cli",
        actor_id="tester",
        reason="explicit reopen for major update",
        root=root,
    )
    assert unlocked.status == "PILOT"

    reloaded = load_research_dna(dna.id, root)
    assert reloaded.status == "PILOT"
    approval_rows = _read_jsonl(research_dna_log_path(dna.id, "approval_audit", root))
    actions = [row["action"] for row in approval_rows]
    assert actions == ["create", "approve_pilot", "refine", "submit_screening", "lock", "unlock"]


def test_service_rejects_invalid_state_transitions(tmp_path):
    root = tmp_path / "research_dna"
    dna = create_research_dna(
        topic="Mild cognitive impairment and medium-chain triglycerides",
        intent="systematic_review",
        actor_type="human_cli",
        actor_id="tester",
        reason="create draft",
        root=root,
    )

    with pytest.raises(ResearchDNAStateError):
        lock_research_dna(
            dna.id,
            actor_type="human_cli",
            actor_id="tester",
            reason="cannot lock draft",
            root=root,
        )

    with pytest.raises(ResearchDNAStateError):
        submit_screening_decision(
            dna.id,
            run_id="pilot_001",
            candidate_id="pmid:123",
            decision="exclude",
            reason_code="wrong_population",
            actor_type="human_cli",
            actor_id="tester",
            root=root,
        )


def test_update_and_initial_query_version_are_allowed_in_draft(tmp_path):
    root = tmp_path / "research_dna"
    dna = create_research_dna(
        topic="Mild cognitive impairment and medium-chain triglycerides",
        intent="systematic_review",
        actor_type="human_cli",
        actor_id="tester",
        reason="create draft",
        root=root,
    )

    updated = update_research_dna(
        dna.id,
        patch=ResearchDNAUpdate(
            available_databases=["pubmed"],
            recommended_databases=["pubmed", "embase"],
            pilot=PilotConfig(
                n=30,
                goldset_kind="retrospective_provisional",
                goldset=["doi:10.1002/alz.12206"],
                goldset_sources=["https://pmc.ncbi.nlm.nih.gov/articles/PMC12122782/"],
                goldset_note="provisional search sanity set",
            ),
        ),
        actor_type="human_cli",
        actor_id="tester",
        reason="set source policy in draft",
        root=root,
    )
    assert updated.available_databases == ["pubmed"]
    assert updated.pilot.goldset_kind == "retrospective_provisional"
    assert updated.pilot.goldset_sources == ["https://pmc.ncbi.nlm.nih.gov/articles/PMC12122782/"]
    approval_rows = _read_jsonl(research_dna_log_path(dna.id, "approval_audit", root))
    assert approval_rows[-1]["action"] == "change_goldset_kind"

    refined = refine_query_version(
        dna.id,
        query_version=QueryVersion(
            version="v1",
            mode="recall",
            per_db={"pubmed": "(\"mild cognitive impairment\") AND (\"medium-chain triglycerides\")"},
            change_summary="initial draft query",
            created_at=datetime(2026, 3, 12, tzinfo=timezone.utc),
            created_by="human_cli:tester",
        ),
        actor_type="human_cli",
        actor_id="tester",
        reason="draft v1 query",
        root=root,
    )
    assert refined.status == "DRAFT"
    assert refined.query_versions[-1].version == "v1"


def test_update_without_goldset_kind_change_stays_generic_update(tmp_path):
    root = tmp_path / "research_dna"
    dna = create_research_dna(
        topic="Mild cognitive impairment and medium-chain triglycerides",
        intent="systematic_review",
        actor_type="human_cli",
        actor_id="tester",
        reason="create draft",
        root=root,
    )

    updated = update_research_dna(
        dna.id,
        patch=ResearchDNAUpdate(title="Revised title only"),
        actor_type="human_cli",
        actor_id="tester",
        reason="rename draft",
        root=root,
    )

    assert updated.title == "Revised title only"
    approval_rows = _read_jsonl(research_dna_log_path(dna.id, "approval_audit", root))
    assert approval_rows[-1]["action"] == "update"


def test_interview_logging_is_allowed_before_lock_and_blocked_after_lock(tmp_path):
    root = tmp_path / "research_dna"
    dna = create_research_dna(
        topic="Mild cognitive impairment and medium-chain triglycerides",
        intent="systematic_review",
        actor_type="human_cli",
        actor_id="tester",
        reason="create draft",
        root=root,
    )

    logged_dna, interview = log_interview_response(
        dna.id,
        round="researcher",
        question_id="researcher_1",
        question="What is the intent?",
        answer="systematic_review",
        actor_type="human_cli",
        actor_id="tester",
        root=root,
    )
    assert logged_dna.id == dna.id
    assert interview.round == "researcher"

    approve_pilot(
        dna.id,
        actor_type="human_cli",
        actor_id="tester",
        reason="ready for pilot",
        root=root,
    )
    lock_research_dna(
        dna.id,
        actor_type="human_cli",
        actor_id="tester",
        reason="lock after pilot review",
        root=root,
    )

    with pytest.raises(ResearchDNAStateError):
        log_interview_response(
            dna.id,
            round="librarian",
            question_id="librarian_1",
            question="Which databases are available?",
            answer="pubmed",
            actor_type="human_cli",
            actor_id="tester",
            root=root,
        )


def test_run_pilot_writes_search_eval_artifacts_and_run_log(tmp_path):
    root = tmp_path / "research_dna"
    eval_root = tmp_path / "search_eval"
    dna = create_research_dna(
        topic="Mild cognitive impairment and medium-chain triglycerides",
        intent="systematic_review",
        actor_type="human_cli",
        actor_id="tester",
        reason="create draft",
        root=root,
        available_databases=["pubmed"],
        recommended_databases=["pubmed", "embase"],
    )
    approve_pilot(
        dna.id,
        actor_type="human_cli",
        actor_id="tester",
        reason="ready for pilot",
        root=root,
    )
    refine_query_version(
        dna.id,
        query_version=QueryVersion(
            version="v1",
            mode="recall",
            per_db={"pubmed": "(\"mild cognitive impairment\") AND (\"medium-chain triglycerides\")"},
            change_summary="initial query draft",
            created_at=datetime(2026, 3, 12, tzinfo=timezone.utc),
            created_by="human_cli:tester",
        ),
        actor_type="human_cli",
        actor_id="tester",
        reason="set initial pilot query",
        root=root,
    )

    papers = [
        Paper(
            id="PMID:123",
            title="Study A",
            authors=["Kim J"],
            published="2024-01-01",
            source="PubMed",
            summary="A",
            link="https://pubmed.ncbi.nlm.nih.gov/123/",
            doi=None,
        ),
        Paper(
            id="PMID:124",
            title="Study A",
            authors=["Kim J"],
            published="2024-01-01",
            source="PubMed",
            summary="Duplicate title-year",
            link="https://pubmed.ncbi.nlm.nih.gov/124/",
            doi=None,
        ),
        Paper(
            id="10.1000/abc",
            doi="10.1000/abc",
            title="Study B",
            authors=["Lee H"],
            published="2023-05-02",
            source="PubMed",
            summary="B",
            link="https://example.org/doi/10.1000/abc",
        ),
    ]

    result = run_pilot(
        dna.id,
        actor_type="human_cli",
        actor_id="tester",
        root=root,
        search_eval_root=eval_root,
        run_id="pilot_test_001",
        source_fetchers={"pubmed": _FakeFetcher(papers)},
    )

    assert result.run_id == "pilot_test_001"
    assert Path(result.run_dir).exists()
    assert Path(result.screening_queue_path).exists()
    assert Path(result.metrics_path).exists()

    screening_rows = _read_jsonl(Path(result.screening_queue_path))
    assert len(screening_rows) == 3

    metrics = json.loads(Path(result.metrics_path).read_text(encoding="utf-8"))
    assert metrics["retrieved_count"] == 3
    assert metrics["deduped_count"] == 3

    manifest = json.loads((eval_root / "pilot_test_001" / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["actor_id"] == "tester"
    assert manifest["active_sources"] == ["pubmed"]

    run_rows = _read_jsonl(research_dna_log_path(dna.id, "runs", root))
    assert run_rows[0]["actor_id"] == "tester"
    assert run_rows[0]["run_id"] == "pilot_test_001"
    assert run_rows[0]["status"] == "completed"


def test_run_pilot_records_partial_status_when_source_fetch_fails(tmp_path):
    root = tmp_path / "research_dna"
    eval_root = tmp_path / "search_eval"
    dna = create_research_dna(
        topic="Mild cognitive impairment and medium-chain triglycerides",
        intent="systematic_review",
        actor_type="human_cli",
        actor_id="tester",
        reason="create draft",
        root=root,
        available_databases=["pubmed"],
        recommended_databases=["pubmed"],
    )
    approve_pilot(
        dna.id,
        actor_type="human_cli",
        actor_id="tester",
        reason="ready for pilot",
        root=root,
    )
    refine_query_version(
        dna.id,
        query_version=QueryVersion(
            version="v1",
            mode="recall",
            per_db={"pubmed": "(\"mild cognitive impairment\") AND (\"medium-chain triglycerides\")"},
            change_summary="initial query draft",
            created_at=datetime(2026, 3, 12, tzinfo=timezone.utc),
            created_by="human_cli:tester",
        ),
        actor_type="human_cli",
        actor_id="tester",
        reason="set initial pilot query",
        root=root,
    )

    run_pilot(
        dna.id,
        actor_type="human_cli",
        actor_id="tester",
        root=root,
        search_eval_root=eval_root,
        run_id="pilot_partial_001",
        source_fetchers={"pubmed": _FailingFetcher()},
    )

    manifest = json.loads((eval_root / "pilot_partial_001" / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["status"] == "partial"

    run_rows = _read_jsonl(research_dna_log_path(dna.id, "runs", root))
    assert run_rows[0]["run_id"] == "pilot_partial_001"
    assert run_rows[0]["status"] == "partial"
