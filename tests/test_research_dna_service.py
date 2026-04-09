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
    load_next_screening_candidate,
    load_rerank_gate_report,
    load_screening_operator_guidance,
    load_screening_recommendation,
    load_screening_queue_artifact,
    load_screening_session,
    lock_research_dna,
    log_interview_response,
    materialize_screening_guidance_artifact,
    materialize_reranked_screening_queue,
    run_pilot,
    screen_current_candidate_and_load_session,
    refine_query_version,
    submit_screening_decision_and_load_next_candidate,
    submit_screening_decision_and_load_session,
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


def test_materialize_reranked_screening_queue_writes_sibling_artifacts(tmp_path):
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
        run_id="pilot_rerank_001",
        source_fetchers={
            "pubmed": _FakeFetcher(
                [
                    Paper(
                        id="PMID:200",
                        title="Dietary patterns in older adults",
                        authors=["Kim J"],
                        published="2024-01-01",
                        source="PubMed",
                        summary="Nutrition guidance without the target condition or intervention.",
                        link="https://pubmed.ncbi.nlm.nih.gov/200/",
                        doi=None,
                    ),
                    Paper(
                        id="PMID:201",
                        title="Mild cognitive impairment responds to medium-chain triglycerides",
                        authors=["Lee H"],
                        published="2023-05-02",
                        source="PubMed",
                        summary="A clinical study of medium-chain triglycerides in mild cognitive impairment.",
                        link="https://pubmed.ncbi.nlm.nih.gov/201/",
                        doi=None,
                    ),
                ]
            )
        },
    )

    rerank = materialize_reranked_screening_queue(
        dna.id,
        run_id="pilot_rerank_001",
        actor_type="human_cli",
        actor_id="tester",
        root=root,
        search_eval_root=eval_root,
    )

    assert Path(rerank.reranked_screening_queue_path).exists()
    assert Path(rerank.rerank_report_path).exists()
    assert rerank.top_candidate_id == "pmid:201"
    assert rerank.changed_position_count == 2

    reranked_rows = _read_jsonl(Path(rerank.reranked_screening_queue_path))
    assert reranked_rows[0]["candidate_id"] == "pmid:201"
    assert reranked_rows[0]["original_rank"] == 2
    assert reranked_rows[0]["rerank_rank"] == 1
    assert reranked_rows[0]["rerank_version"] == "research_dna.query_overlap.v1"

    manifest = json.loads((eval_root / "pilot_rerank_001" / "manifest.json").read_text(encoding="utf-8"))
    assert Path(manifest["artifact_paths"]["reranked_screening_queue"]).exists()
    assert Path(manifest["artifact_paths"]["rerank_report"]).exists()

    metrics = json.loads(Path(rerank.metrics_path).read_text(encoding="utf-8"))
    assert metrics["research_dna_rerank"]["top_candidate_id"] == "pmid:201"

    original_queue = load_screening_queue_artifact(
        dna.id,
        run_id="pilot_rerank_001",
        variant="original",
        root=root,
        search_eval_root=eval_root,
    )
    reranked_queue = load_screening_queue_artifact(
        dna.id,
        run_id="pilot_rerank_001",
        variant="reranked",
        root=root,
        search_eval_root=eval_root,
    )
    recommendation_before = load_screening_recommendation(
        dna.id,
        run_id="pilot_rerank_001",
        root=root,
        search_eval_root=eval_root,
    )

    assert original_queue.variant == "original"
    assert original_queue.rows[0]["candidate_id"] == "pmid:200"
    assert reranked_queue.variant == "reranked"
    assert reranked_queue.rows[0]["candidate_id"] == "pmid:201"
    assert recommendation_before.owner_variant == "original"
    assert recommendation_before.recommended_variant == "reranked"
    assert recommendation_before.advisory_only is True
    assert recommendation_before.screening_started is False
    assert recommendation_before.top_candidate_changed is True
    assert recommendation_before.changed_position_ratio == 1.0
    assert recommendation_before.rerank_top_score is not None
    assert recommendation_before.rerank_second_score is not None
    assert recommendation_before.rerank_top_score_margin is not None
    assert recommendation_before.rerank_top_score_margin > 0.0
    assert recommendation_before.primary_reason_code == "top_candidate_changed"
    assert recommendation_before.primary_warning_code is None
    assert recommendation_before.recommendation_summary == "Consider the reranked queue because the top candidate changed with positive rerank signal."
    assert recommendation_before.reason_codes == ["top_candidate_changed", "positive_query_overlap_signal"]
    assert recommendation_before.original_top_candidate_id == "pmid:200"
    assert recommendation_before.reranked_top_candidate_id == "pmid:201"
    combined_recommendation_before, combined_gate_before = load_screening_operator_guidance(
        dna.id,
        run_id="pilot_rerank_001",
        root=root,
        search_eval_root=eval_root,
    )
    assert combined_recommendation_before.recommended_variant == recommendation_before.recommended_variant
    assert combined_recommendation_before.primary_reason_code == recommendation_before.primary_reason_code
    gate_before = load_rerank_gate_report(
        dna.id,
        run_id="pilot_rerank_001",
        root=root,
        search_eval_root=eval_root,
    )
    assert gate_before.gate_status == "eligible"
    assert gate_before.recommended_variant == "reranked"
    assert gate_before.candidate_variant == "reranked"
    assert gate_before.changed_position_ratio == 1.0
    assert gate_before.primary_reason_code == "top_candidate_changed"
    assert gate_before.gate_summary == "Reranked queue is eligible for advisory operator use."
    assert gate_before.rerank_score_spread is not None
    assert gate_before.rerank_score_spread > 0.0
    assert gate_before.rerank_top_score_margin is not None
    assert gate_before.rerank_top_score_margin > 0.0
    assert combined_gate_before.gate_status == gate_before.gate_status
    assert combined_gate_before.primary_reason_code == gate_before.primary_reason_code

    guidance_artifact = materialize_screening_guidance_artifact(
        dna.id,
        run_id="pilot_rerank_001",
        actor_type="human_cli",
        actor_id="tester",
        root=root,
        search_eval_root=eval_root,
    )
    assert Path(guidance_artifact.artifact_path).exists()
    assert Path(guidance_artifact.artifact_path).name.startswith("screening_guidance_")
    guidance_payload = json.loads(Path(guidance_artifact.artifact_path).read_text(encoding="utf-8"))
    assert guidance_payload["recommendation"]["recommended_variant"] == "reranked"
    assert guidance_payload["gate"]["gate_status"] == "eligible"

    guidance_artifact_second = materialize_screening_guidance_artifact(
        dna.id,
        run_id="pilot_rerank_001",
        actor_type="human_cli",
        actor_id="tester",
        root=root,
        search_eval_root=eval_root,
    )
    assert Path(guidance_artifact_second.artifact_path).exists()
    assert guidance_artifact_second.artifact_path != guidance_artifact.artifact_path
    assert Path(guidance_artifact.artifact_path).exists()

    manifest_after_guidance = json.loads((eval_root / "pilot_rerank_001" / "manifest.json").read_text(encoding="utf-8"))
    assert Path(manifest_after_guidance["artifact_paths"]["screening_guidance"]).exists()
    assert Path(manifest_after_guidance["artifact_paths"]["screening_guidance_index"]).exists()
    assert manifest_after_guidance["artifact_paths"]["screening_guidance"] == guidance_artifact_second.artifact_path
    assert manifest_after_guidance["screening_guidance"]["artifact_path"] == guidance_artifact_second.artifact_path
    assert manifest_after_guidance["screening_guidance"]["index_path"] == manifest_after_guidance["artifact_paths"]["screening_guidance_index"]
    assert manifest_after_guidance["screening_guidance"]["history_count"] == 2
    assert manifest_after_guidance["screening_guidance"]["recommended_variant"] == "reranked"

    guidance_index_payload = json.loads(
        Path(manifest_after_guidance["artifact_paths"]["screening_guidance_index"]).read_text(encoding="utf-8")
    )
    assert guidance_index_payload["entry_count"] == 2
    assert guidance_index_payload["latest_artifact_path"] == guidance_artifact_second.artifact_path
    assert guidance_index_payload["entries"][0]["artifact_path"] == guidance_artifact.artifact_path
    assert guidance_index_payload["entries"][1]["artifact_path"] == guidance_artifact_second.artifact_path

    metrics_after_guidance = json.loads(Path(rerank.metrics_path).read_text(encoding="utf-8"))
    assert metrics_after_guidance["research_dna_guidance"]["artifact_path"] == guidance_artifact_second.artifact_path
    assert metrics_after_guidance["research_dna_guidance"]["index_path"] == manifest_after_guidance["artifact_paths"]["screening_guidance_index"]
    assert metrics_after_guidance["research_dna_guidance"]["history_count"] == 2
    assert metrics_after_guidance["research_dna_guidance"]["recommended_variant"] == "reranked"
    assert metrics_after_guidance["research_dna_guidance"]["gate_status"] == "eligible"

    guidance_index_path = Path(manifest_after_guidance["artifact_paths"]["screening_guidance_index"])
    tampered_index = json.loads(guidance_index_path.read_text(encoding="utf-8"))
    tampered_index["query_version"] = "v999"
    guidance_index_path.write_text(json.dumps(tampered_index, ensure_ascii=False, indent=2), encoding="utf-8")
    with pytest.raises(ResearchDNAStateError, match="guidance index is invalid"):
        materialize_screening_guidance_artifact(
            dna.id,
            run_id="pilot_rerank_001",
            actor_type="human_cli",
            actor_id="tester",
            root=root,
            search_eval_root=eval_root,
        )

    next_before_screening = load_next_screening_candidate(
        dna.id,
        run_id="pilot_rerank_001",
        variant="reranked",
        root=root,
        search_eval_root=eval_root,
    )
    assert next_before_screening.candidate is not None
    assert next_before_screening.candidate["candidate_id"] == "pmid:201"
    assert next_before_screening.queue_position == 1
    assert next_before_screening.remaining_count == 2

    dna_after_session, screened_candidate_id, next_after_session, session_after_first_screen = screen_current_candidate_and_load_session(
        dna.id,
        run_id="pilot_rerank_001",
        decision="include",
        reason_code="other_noise",
        variant="reranked",
        recent_limit=5,
        expected_candidate_id="pmid:201",
        actor_type="human_cli",
        actor_id="tester",
        root=root,
        search_eval_root=eval_root,
    )
    assert dna_after_session.id == dna.id
    assert screened_candidate_id == "pmid:201"
    assert next_after_session.candidate is not None
    assert next_after_session.candidate["candidate_id"] == "pmid:200"
    assert next_after_session.queue_position == 2
    assert next_after_session.labeled_count == 1
    assert next_after_session.remaining_count == 1
    assert session_after_first_screen.available_variants == ["original", "reranked"]
    assert session_after_first_screen.next_candidate is not None
    assert session_after_first_screen.next_candidate["candidate_id"] == "pmid:200"
    assert session_after_first_screen.include_count == 1
    assert session_after_first_screen.exclude_count == 0
    assert session_after_first_screen.unclear_count == 0
    assert session_after_first_screen.recent_decisions[0].candidate_id == "pmid:201"

    recommendation_after_first_screen = load_screening_recommendation(
        dna.id,
        run_id="pilot_rerank_001",
        root=root,
        search_eval_root=eval_root,
    )
    assert recommendation_after_first_screen.recommended_variant == "original"
    assert recommendation_after_first_screen.screening_started is True
    assert recommendation_after_first_screen.primary_reason_code == "screening_in_progress"
    assert recommendation_after_first_screen.recommendation_summary == "Keep the original queue because screening is already in progress."
    assert recommendation_after_first_screen.reason_codes == ["screening_in_progress"]
    gate_after_first_screen = load_rerank_gate_report(
        dna.id,
        run_id="pilot_rerank_001",
        root=root,
        search_eval_root=eval_root,
    )
    assert gate_after_first_screen.gate_status == "not_eligible"
    assert gate_after_first_screen.primary_reason_code == "screening_in_progress"
    assert gate_after_first_screen.gate_summary == "Reranked queue is not eligible because screening is already in progress."
    assert gate_after_first_screen.reason_codes == ["screening_in_progress"]

    with pytest.raises(ResearchDNAStateError, match="current next candidate mismatch"):
        screen_current_candidate_and_load_session(
            dna.id,
            run_id="pilot_rerank_001",
            decision="exclude",
            reason_code="duplicate",
            variant="reranked",
            expected_candidate_id="pmid:not_the_next_one",
            actor_type="human_cli",
            actor_id="tester",
            root=root,
            search_eval_root=eval_root,
        )

    dna_after_advance, next_after_advance = submit_screening_decision_and_load_next_candidate(
        dna.id,
        run_id="pilot_rerank_001",
        candidate_id="pmid:200",
        decision="exclude",
        reason_code="wrong_population",
        variant="reranked",
        actor_type="human_cli",
        actor_id="tester",
        root=root,
        search_eval_root=eval_root,
    )
    assert dna_after_advance.id == dna.id
    assert next_after_advance.candidate is None
    assert next_after_advance.remaining_count == 0
    assert next_after_advance.labeled_count == 2

    session_after_advance = load_screening_session(
        dna.id,
        run_id="pilot_rerank_001",
        variant="reranked",
        recent_limit=1,
        root=root,
        search_eval_root=eval_root,
    )
    assert session_after_advance.session_complete is True
    assert session_after_advance.next_candidate is None
    assert session_after_advance.exclude_count == 1
    assert len(session_after_advance.recent_decisions) == 1
    assert session_after_advance.recent_decisions[0].candidate_id == "pmid:200"

    completed_session = load_screening_session(
        dna.id,
        run_id="pilot_rerank_001",
        variant="reranked",
        recent_limit=1,
        root=root,
        search_eval_root=eval_root,
    )
    assert completed_session.session_complete is True
    assert completed_session.next_candidate is None
    assert completed_session.remaining_count == 0
    assert completed_session.include_count == 1
    assert completed_session.exclude_count == 1
    assert len(completed_session.recent_decisions) == 1
    assert completed_session.recent_decisions[0].candidate_id == "pmid:200"

    with pytest.raises(ResearchDNAStateError, match="no remaining screening candidates"):
        screen_current_candidate_and_load_session(
            dna.id,
            run_id="pilot_rerank_001",
            decision="exclude",
            reason_code="duplicate",
            variant="reranked",
            actor_type="human_cli",
            actor_id="tester",
            root=root,
            search_eval_root=eval_root,
        )

    with pytest.raises(ResearchDNAStateError, match="variant must be 'original' or 'reranked'"):
        load_screening_queue_artifact(
            dna.id,
            run_id="pilot_rerank_001",
            variant="bad_variant",  # type: ignore[arg-type]
            root=root,
            search_eval_root=eval_root,
        )

    with pytest.raises(ResearchDNAStateError, match="recent_limit must be >= 1"):
        load_screening_session(
            dna.id,
            run_id="pilot_rerank_001",
            variant="reranked",
            recent_limit=0,
            root=root,
            search_eval_root=eval_root,
        )
