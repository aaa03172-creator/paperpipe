from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from backend import main as api_main
from src.profiles.profile_store import load_profiles
from src.schemas import Paper


class _FakeFetcher:
    def __init__(self, papers):
        self._papers = papers

    def fetch(self, query: str, max_results: int):
        return self._papers[:max_results]


def test_research_dna_api_roundtrip_and_pilot(tmp_path, monkeypatch):
    monkeypatch.setenv("PAPERPIPE_RESEARCH_DNA_DIR", str(tmp_path / "research_dna"))
    monkeypatch.setenv("PAPERPIPE_SEARCH_EVAL_DIR", str(tmp_path / "search_eval"))
    monkeypatch.delenv("LATTICE_API_KEY", raising=False)
    monkeypatch.delenv("PAPERPIPE_API_KEY", raising=False)

    fake_papers = [
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
    monkeypatch.setattr(api_main, "run_pilot", api_main.run_pilot)
    monkeypatch.setattr(
        "src.profiles.research_dna_service._default_source_fetchers",
        lambda: {"pubmed": _FakeFetcher(fake_papers)},
    )

    client = TestClient(api_main.app)

    created = client.post(
        "/research-dna",
        json={
            "topic": "Mild cognitive impairment and medium-chain triglycerides",
            "intent": "systematic_review",
            "actor_type": "human_api",
            "actor_id": "tester",
            "reason": "create via api",
            "available_databases": ["pubmed"],
            "recommended_databases": ["pubmed", "embase"],
        },
    )
    assert created.status_code == 200
    assert created.json()["dna"]["status"] == "DRAFT"
    assert created.json()["dna"]["revision"] == 0
    dna_id = created.json()["dna"]["id"]

    interview = client.post(
        f"/research-dna/{dna_id}/interview",
        json={
            "round": "researcher",
            "question_id": "researcher_1",
            "question": "What is the intent?",
            "answer": "systematic_review",
            "actor_type": "human_api",
            "actor_id": "tester",
        },
    )
    assert interview.status_code == 200
    assert interview.json()["interview"]["round"] == "researcher"

    approved = client.post(
        f"/research-dna/{dna_id}/approve-pilot",
        json={"actor_type": "human_api", "actor_id": "tester", "reason": "approve pilot"},
    )
    assert approved.status_code == 200
    assert approved.json()["dna"]["status"] == "PILOT"
    assert approved.json()["dna"]["governance"]["approved_for_pilot_by"] == "human_api:tester"
    resume_before_pilot = client.get(f"/research-dna/{dna_id}/resume")
    assert resume_before_pilot.status_code == 200
    assert resume_before_pilot.json()["resume"]["has_runs"] is False
    assert resume_before_pilot.json()["resume"]["run_count"] == 0
    assert resume_before_pilot.json()["resume"]["latest_run_id"] is None
    assert resume_before_pilot.json()["resume"]["latest_run"] is None

    refined = client.post(
        f"/research-dna/{dna_id}/refine",
        json={
            "actor_type": "human_api",
            "actor_id": "tester",
            "reason": "set initial v1 query",
            "query_version": {
                "version": "v1",
                "mode": "recall",
                "per_db": {"pubmed": "(\"mild cognitive impairment\") AND (\"medium-chain triglycerides\")"},
                "change_summary": "initial query draft",
                "created_at": "2026-03-12T00:00:00Z",
                "created_by": "human_api:tester",
            },
        },
    )
    assert refined.status_code == 200
    assert refined.json()["dna"]["query_versions"][-1]["version"] == "v1"

    pilot = client.post(
        f"/research-dna/{dna_id}/pilot",
        json={"actor_type": "human_api", "actor_id": "tester", "run_id": "pilot_api_001"},
    )
    assert pilot.status_code == 200
    assert pilot.json()["pilot_run"]["run_id"] == "pilot_api_001"
    assert Path(pilot.json()["pilot_run"]["screening_queue_path"]).exists()
    run_index_after_pilot = client.get(
        f"/research-dna/{dna_id}/runs",
        params={"limit": 20},
    )
    assert run_index_after_pilot.status_code == 200
    assert run_index_after_pilot.json()["run_index"]["run_count"] == 1
    assert run_index_after_pilot.json()["run_index"]["latest_run_id"] == "pilot_api_001"
    assert run_index_after_pilot.json()["run_index"]["runs"][0]["run_id"] == "pilot_api_001"
    assert run_index_after_pilot.json()["run_index"]["runs"][0]["screening_started"] is False

    rerank = client.post(
        f"/research-dna/{dna_id}/rerank",
        json={"actor_type": "human_api", "actor_id": "tester", "run_id": "pilot_api_001"},
    )
    assert rerank.status_code == 200
    assert Path(rerank.json()["rerank"]["reranked_screening_queue_path"]).exists()

    guidance_materialized = client.post(
        f"/research-dna/{dna_id}/guidance/materialize",
        json={"actor_type": "human_api", "actor_id": "tester", "run_id": "pilot_api_001"},
    )
    assert guidance_materialized.status_code == 200
    assert Path(guidance_materialized.json()["guidance_artifact"]["artifact_path"]).exists()
    assert guidance_materialized.json()["guidance_artifact"]["recommendation"]["recommended_variant"] == "original"
    assert guidance_materialized.json()["guidance_artifact"]["gate"]["gate_status"] == "insufficient_signal"
    guidance_artifact_read = client.get(
        f"/research-dna/{dna_id}/runs/pilot_api_001/screening-guidance-artifact",
    )
    assert guidance_artifact_read.status_code == 200
    assert guidance_artifact_read.json()["guidance_artifact"]["artifact_path"] == guidance_materialized.json()["guidance_artifact"]["artifact_path"]
    assert guidance_artifact_read.json()["guidance_artifact"]["gate"]["gate_status"] == "insufficient_signal"

    queue = client.get(
        f"/research-dna/{dna_id}/runs/pilot_api_001/screening-queue",
        params={"variant": "reranked"},
    )
    assert queue.status_code == 200
    assert queue.json()["screening_queue"]["variant"] == "reranked"
    assert queue.json()["screening_queue"]["row_count"] == 2

    next_candidate = client.get(
        f"/research-dna/{dna_id}/runs/pilot_api_001/next-screening-candidate",
        params={"variant": "reranked"},
    )
    assert next_candidate.status_code == 200
    assert next_candidate.json()["next_candidate"]["candidate"]["candidate_id"] == "pmid:123"
    assert next_candidate.json()["next_candidate"]["queue_position"] == 1

    session_before = client.get(
        f"/research-dna/{dna_id}/runs/pilot_api_001/screening-session",
        params={"variant": "reranked", "recent_limit": 5},
    )
    assert session_before.status_code == 200
    assert session_before.json()["session"]["available_variants"] == ["original", "reranked"]
    assert session_before.json()["session"]["next_candidate"]["candidate_id"] == "pmid:123"
    assert session_before.json()["session"]["recent_decisions"] == []
    assert session_before.json()["recommendation"]["owner_variant"] == "original"
    assert session_before.json()["recommendation"]["recommended_variant"] == "original"
    assert session_before.json()["recommendation"]["primary_reason_code"] == "no_position_change"
    assert session_before.json()["recommendation"]["recommendation_summary"] == "Keep the original queue because reranking did not change candidate positions."
    assert session_before.json()["recommendation"]["changed_position_ratio"] == 0.0
    assert session_before.json()["gate"]["gate_status"] == "insufficient_signal"
    assert session_before.json()["gate"]["primary_reason_code"] == "no_position_change"
    assert session_before.json()["gate"]["gate_summary"] == "Reranked queue is not yet eligible because reranking did not change candidate positions."
    assert session_before.json()["gate"]["changed_position_ratio"] == 0.0

    recommendation_before = client.get(
        f"/research-dna/{dna_id}/runs/pilot_api_001/screening-recommendation",
    )
    assert recommendation_before.status_code == 200
    assert recommendation_before.json()["recommendation"]["owner_variant"] == "original"
    assert recommendation_before.json()["recommendation"]["recommended_variant"] == "original"
    assert recommendation_before.json()["recommendation"]["primary_reason_code"] == "no_position_change"
    assert recommendation_before.json()["recommendation"]["reason_codes"] == ["no_position_change"]
    guidance_before = client.get(
        f"/research-dna/{dna_id}/runs/pilot_api_001/screening-guidance",
    )
    assert guidance_before.status_code == 200
    assert guidance_before.json()["recommendation"]["recommended_variant"] == "original"
    assert guidance_before.json()["gate"]["gate_status"] == "insufficient_signal"
    guidance_history_before = client.get(
        f"/research-dna/{dna_id}/runs/pilot_api_001/screening-guidance-history",
        params={"limit": 20},
    )
    assert guidance_history_before.status_code == 200
    assert guidance_history_before.json()["guidance_index"]["entry_count"] == 1
    assert len(guidance_history_before.json()["guidance_index"]["entries"]) == 1
    rerank_gate_before = client.get(
        f"/research-dna/{dna_id}/runs/pilot_api_001/rerank-gate",
    )
    assert rerank_gate_before.status_code == 200
    assert rerank_gate_before.json()["gate"]["gate_status"] == "insufficient_signal"
    assert rerank_gate_before.json()["gate"]["primary_reason_code"] == "no_position_change"
    assert rerank_gate_before.json()["gate"]["reason_codes"] == ["no_position_change"]
    invalid_latest_selector = client.post(
        f"/research-dna/{dna_id}/screening/current",
        json={
            "run_id": "pilot_api_001",
            "latest_run": True,
            "decision": "exclude",
            "reason_code": "wrong_population",
            "actor_type": "human_api",
            "actor_id": "tester",
        },
    )
    assert invalid_latest_selector.status_code == 422

    screening = client.post(
        f"/research-dna/{dna_id}/screening/current",
        json={
            "latest_run": True,
            "decision": "exclude",
            "reason_code": "wrong_population",
            "variant": "reranked",
            "expected_candidate_id": "pmid:123",
            "recent_limit": 5,
            "note": "Decision note Authorization: Bearer dnascreeningtoken123 and sk-proj-dnascreeningsecret123456.",
            "actor_type": "human_api",
            "actor_id": "tester",
        },
    )
    assert screening.status_code == 200
    assert screening.json()["screened_candidate_id"] == "pmid:123"
    assert screening.json()["session"]["exclude_count"] == 1
    assert screening.json()["session"]["next_candidate"]["candidate_id"] == "doi:10.1000/abc"
    assert screening.json()["session"]["recent_decisions"][0]["variant"] == "reranked"
    assert screening.json()["session"]["recent_decisions"][0]["recommended_variant"] == "original"
    assert screening.json()["session"]["recent_decisions"][0]["guidance_gate_status"] == "insufficient_signal"
    assert screening.json()["session"]["recent_decisions"][0]["guidance_primary_reason_code"] == "no_position_change"
    assert screening.json()["session"]["recent_decisions"][0]["followed_guidance"] is False
    assert (
        screening.json()["session"]["recent_decisions"][0]["note"]
        == "Decision note Authorization: <redacted> and <redacted>."
    )
    assert screening.json()["session"]["guidance_follow_summary"]["evaluated_decision_count"] == 1
    assert screening.json()["session"]["guidance_follow_summary"]["telemetry_count"] == 1
    assert screening.json()["session"]["guidance_follow_summary"]["followed_guidance_count"] == 0
    assert screening.json()["session"]["guidance_follow_summary"]["diverged_guidance_count"] == 1
    assert screening.json()["session"]["guidance_follow_summary"]["followed_guidance_ratio"] == 0.0
    assert screening.json()["recommendation"]["recommended_variant"] == "original"
    assert screening.json()["recommendation"]["recommendation_summary"] == "Keep the original queue because screening is already in progress."
    assert screening.json()["recommendation"]["reason_codes"] == ["screening_in_progress"]
    assert screening.json()["gate"]["gate_status"] == "not_eligible"
    assert screening.json()["gate"]["gate_summary"] == "Reranked queue is not eligible because screening is already in progress."

    next_after_screening = client.get(
        f"/research-dna/{dna_id}/runs/pilot_api_001/next-screening-candidate",
        params={"variant": "reranked"},
    )
    assert next_after_screening.status_code == 200
    assert next_after_screening.json()["next_candidate"]["candidate"]["candidate_id"] == "doi:10.1000/abc"
    assert next_after_screening.json()["next_candidate"]["labeled_count"] == 1

    session_after = client.get(
        f"/research-dna/{dna_id}/runs/pilot_api_001/screening-session",
        params={"variant": "reranked", "recent_limit": 5},
    )
    assert session_after.status_code == 200
    assert session_after.json()["session"]["include_count"] == 0
    assert session_after.json()["session"]["exclude_count"] == 1
    assert session_after.json()["session"]["next_candidate"]["candidate_id"] == "doi:10.1000/abc"
    assert session_after.json()["session"]["recent_decisions"][0]["candidate_id"] == "pmid:123"
    assert session_after.json()["recommendation"]["recommended_variant"] == "original"
    assert session_after.json()["recommendation"]["reason_codes"] == ["screening_in_progress"]
    assert session_after.json()["gate"]["gate_status"] == "not_eligible"
    progress_after = client.get(
        f"/research-dna/{dna_id}/runs/pilot_api_001/screening-progress",
        params={"variant": "reranked"},
    )
    assert progress_after.status_code == 200
    assert progress_after.json()["progress"]["variant"] == "reranked"
    assert progress_after.json()["progress"]["owner_variant"] == "original"
    assert progress_after.json()["progress"]["recommended_variant"] == "original"
    assert progress_after.json()["progress"]["gate_status"] == "not_eligible"
    assert progress_after.json()["progress"]["primary_reason_code"] == "screening_in_progress"
    assert progress_after.json()["progress"]["labeled_count"] == 1
    assert progress_after.json()["progress"]["remaining_count"] == 1
    assert progress_after.json()["progress"]["precision_proxy"] == 0.0
    assert progress_after.json()["progress"]["next_candidate_id"] == "doi:10.1000/abc"
    assert progress_after.json()["progress"]["top_reason_codes"] == ["wrong_population"]
    assert progress_after.json()["progress"]["guidance_follow_summary"]["diverged_guidance_count"] == 1
    assert Path(progress_after.json()["progress"]["manifest_path"]).exists()
    assert Path(progress_after.json()["progress"]["metrics_path"]).exists()
    assert Path(progress_after.json()["progress"]["guidance_artifact_path"]).exists()

    recommendation_after = client.get(
        f"/research-dna/{dna_id}/runs/pilot_api_001/screening-recommendation",
    )
    assert recommendation_after.status_code == 200
    assert recommendation_after.json()["recommendation"]["recommended_variant"] == "original"
    assert recommendation_after.json()["recommendation"]["screening_started"] is True
    assert recommendation_after.json()["recommendation"]["reason_codes"] == ["screening_in_progress"]
    rerank_gate_after = client.get(
        f"/research-dna/{dna_id}/runs/pilot_api_001/rerank-gate",
    )
    assert rerank_gate_after.status_code == 200
    assert rerank_gate_after.json()["gate"]["gate_status"] == "not_eligible"
    assert rerank_gate_after.json()["gate"]["reason_codes"] == ["screening_in_progress"]

    advance = client.post(
        f"/research-dna/{dna_id}/screening/advance",
        json={
            "latest_run": True,
            "candidate_id": "doi:10.1000/abc",
            "decision": "include",
            "reason_code": "other_noise",
            "variant": "reranked",
            "recent_limit": 1,
            "actor_type": "human_api",
            "actor_id": "tester",
        },
    )
    assert advance.status_code == 200
    assert advance.json()["screened_candidate_id"] == "doi:10.1000/abc"
    assert advance.json()["next_candidate"]["candidate"] is None
    assert advance.json()["next_candidate"]["remaining_count"] == 0
    assert advance.json()["session"]["session_complete"] is True
    assert advance.json()["session"]["next_candidate"] is None
    assert advance.json()["session"]["include_count"] == 1
    assert advance.json()["recommendation"]["recommended_variant"] == "original"
    assert advance.json()["recommendation"]["reason_codes"] == ["screening_in_progress"]
    assert advance.json()["gate"]["gate_status"] == "not_eligible"
    assert len(advance.json()["session"]["recent_decisions"]) == 1
    assert advance.json()["session"]["recent_decisions"][0]["candidate_id"] == "doi:10.1000/abc"
    assert advance.json()["session"]["recent_decisions"][0]["variant"] == "reranked"
    assert advance.json()["session"]["recent_decisions"][0]["recommended_variant"] == "original"
    assert advance.json()["session"]["recent_decisions"][0]["guidance_gate_status"] == "not_eligible"
    assert advance.json()["session"]["recent_decisions"][0]["guidance_primary_reason_code"] == "screening_in_progress"
    assert advance.json()["session"]["recent_decisions"][0]["followed_guidance"] is False
    assert advance.json()["session"]["guidance_follow_summary"]["evaluated_decision_count"] == 2
    assert advance.json()["session"]["guidance_follow_summary"]["telemetry_count"] == 2
    assert advance.json()["session"]["guidance_follow_summary"]["followed_guidance_count"] == 0
    assert advance.json()["session"]["guidance_follow_summary"]["diverged_guidance_count"] == 2
    assert advance.json()["session"]["guidance_follow_summary"]["followed_guidance_ratio"] == 0.0

    completed_session = client.get(
        f"/research-dna/{dna_id}/runs/pilot_api_001/screening-session",
        params={"variant": "reranked", "recent_limit": 1},
    )
    assert completed_session.status_code == 200
    assert completed_session.json()["session"]["session_complete"] is True
    assert completed_session.json()["session"]["next_candidate"] is None
    assert completed_session.json()["session"]["include_count"] == 1
    assert completed_session.json()["session"]["exclude_count"] == 1
    assert completed_session.json()["recommendation"]["recommended_variant"] == "original"
    assert completed_session.json()["gate"]["gate_status"] == "not_eligible"
    assert len(completed_session.json()["session"]["recent_decisions"]) == 1
    assert completed_session.json()["session"]["recent_decisions"][0]["candidate_id"] == "doi:10.1000/abc"
    completed_progress = client.get(
        f"/research-dna/{dna_id}/runs/pilot_api_001/screening-progress",
        params={"variant": "reranked"},
    )
    assert completed_progress.status_code == 200
    assert completed_progress.json()["progress"]["session_complete"] is True
    assert completed_progress.json()["progress"]["remaining_count"] == 0
    assert completed_progress.json()["progress"]["precision_proxy"] == 0.5
    assert completed_progress.json()["progress"]["next_candidate_id"] is None
    assert completed_progress.json()["progress"]["guidance_follow_summary"]["diverged_guidance_count"] == 2
    run_index_after_completion = client.get(
        f"/research-dna/{dna_id}/runs",
        params={"limit": 20},
    )
    assert run_index_after_completion.status_code == 200
    assert run_index_after_completion.json()["run_index"]["latest_run_id"] == "pilot_api_001"
    assert run_index_after_completion.json()["run_index"]["runs"][0]["session_complete"] is True
    assert run_index_after_completion.json()["run_index"]["runs"][0]["screening_variant"] == "reranked"
    assert run_index_after_completion.json()["run_index"]["runs"][0]["labeled_count"] == 2
    assert run_index_after_completion.json()["run_index"]["runs"][0]["precision_proxy"] == 0.5
    assert run_index_after_completion.json()["run_index"]["runs"][0]["top_reason_codes"] == [
        "other_noise",
        "wrong_population",
    ]
    assert Path(run_index_after_completion.json()["run_index"]["runs"][0]["metrics_path"]).exists()
    assert Path(run_index_after_completion.json()["run_index"]["runs"][0]["screening_queue_path"]).exists()
    resume_after_completion = client.get(
        f"/research-dna/{dna_id}/resume",
        params={"variant": "reranked", "recent_limit": 1},
    )
    assert resume_after_completion.status_code == 200
    assert resume_after_completion.json()["resume"]["has_runs"] is True
    assert resume_after_completion.json()["resume"]["latest_run_id"] == "pilot_api_001"
    assert resume_after_completion.json()["resume"]["latest_run"]["run_id"] == "pilot_api_001"
    assert resume_after_completion.json()["resume"]["latest_run"]["session_complete"] is True
    assert resume_after_completion.json()["resume"]["session"]["session_complete"] is True
    assert resume_after_completion.json()["resume"]["session"]["variant"] == "reranked"
    assert resume_after_completion.json()["resume"]["progress"]["session_complete"] is True
    assert resume_after_completion.json()["resume"]["progress"]["precision_proxy"] == 0.5
    assert resume_after_completion.json()["resume"]["recommendation"]["recommended_variant"] == "original"
    assert resume_after_completion.json()["resume"]["gate"]["gate_status"] == "not_eligible"

    locked = client.post(
        f"/research-dna/{dna_id}/lock",
        json={"actor_type": "human_api", "actor_id": "tester", "reason": "stable enough"},
    )
    assert locked.status_code == 200
    assert locked.json()["dna"]["status"] == "LOCKED"

    fetched = client.get(f"/research-dna/{dna_id}")
    assert fetched.status_code == 200
    assert fetched.json()["dna"]["status"] == "LOCKED"


def test_research_dna_api_rejects_invalid_state_transition(tmp_path, monkeypatch):
    monkeypatch.setenv("PAPERPIPE_RESEARCH_DNA_DIR", str(tmp_path / "research_dna"))
    monkeypatch.delenv("LATTICE_API_KEY", raising=False)
    monkeypatch.delenv("PAPERPIPE_API_KEY", raising=False)
    client = TestClient(api_main.app)

    created = client.post(
        "/research-dna",
        json={
            "topic": "Mild cognitive impairment and medium-chain triglycerides",
            "intent": "systematic_review",
            "actor_type": "human_api",
            "actor_id": "tester",
            "reason": "create via api",
        },
    )
    dna_id = created.json()["dna"]["id"]

    locked = client.post(
        f"/research-dna/{dna_id}/lock",
        json={"actor_type": "human_api", "actor_id": "tester", "reason": "invalid lock"},
    )
    assert locked.status_code == 409


def test_research_dna_api_allows_update_and_draft_query_version(tmp_path, monkeypatch):
    monkeypatch.setenv("PAPERPIPE_RESEARCH_DNA_DIR", str(tmp_path / "research_dna"))
    monkeypatch.setenv("PAPERPIPE_PROFILES_PATH", str(tmp_path / "profiles.yaml"))
    monkeypatch.delenv("LATTICE_API_KEY", raising=False)
    monkeypatch.delenv("PAPERPIPE_API_KEY", raising=False)
    client = TestClient(api_main.app)

    created = client.post(
        "/research-dna",
        json={
            "topic": "Mild cognitive impairment and medium-chain triglycerides",
            "intent": "systematic_review",
            "actor_type": "human_api",
            "actor_id": "tester",
            "reason": "create via api",
        },
    )
    dna_id = created.json()["dna"]["id"]

    updated = client.post(
        f"/research-dna/{dna_id}/update",
        json={
            "actor_type": "human_api",
            "actor_id": "tester",
            "reason": "set available databases",
            "patch": {
                "available_databases": ["pubmed"],
                "recommended_databases": ["pubmed", "embase"],
            },
        },
    )
    assert updated.status_code == 200
    assert updated.json()["dna"]["available_databases"] == ["pubmed"]

    refined = client.post(
        f"/research-dna/{dna_id}/refine",
        json={
            "actor_type": "human_api",
            "actor_id": "tester",
            "reason": "draft v1 query",
            "query_version": {
                "version": "v1",
                "mode": "recall",
                "per_db": {"pubmed": "(\"mild cognitive impairment\") AND (\"medium-chain triglycerides\")"},
                "change_summary": "initial query draft",
                "created_at": "2026-03-12T00:00:00Z",
                "created_by": "human_api:tester",
            },
        },
    )
    assert refined.status_code == 200
    assert refined.json()["dna"]["status"] == "DRAFT"
    assert refined.json()["dna"]["query_versions"][-1]["version"] == "v1"

    projected = client.post(
        f"/research-dna/{dna_id}/project-profile",
        json={
            "actor_type": "human_api",
            "actor_id": "tester",
            "reason": "materialize compatibility profile",
        },
    )
    assert projected.status_code == 200
    payload = projected.json()["projection"]
    assert payload["query_version"] == "v1"
    assert payload["selected_database"] == "pubmed"
    assert Path(payload["profile_path"]).exists()
    config = load_profiles(Path(payload["profile_path"]))
    assert config.profiles[0].enabled is False
    assert config.profiles[0].schedule == "manual"


def test_research_dna_api_rejects_duplicate_create_for_same_dna_id(tmp_path, monkeypatch):
    monkeypatch.setenv("PAPERPIPE_RESEARCH_DNA_DIR", str(tmp_path / "research_dna"))
    monkeypatch.delenv("LATTICE_API_KEY", raising=False)
    monkeypatch.delenv("PAPERPIPE_API_KEY", raising=False)
    client = TestClient(api_main.app)

    payload = {
        "topic": "Mild cognitive impairment and medium-chain triglycerides",
        "intent": "systematic_review",
        "dna_id": "dna_dup_test",
        "actor_type": "human_api",
        "actor_id": "tester",
        "reason": "create via api",
    }
    first = client.post("/research-dna", json=payload)
    assert first.status_code == 200

    second = client.post("/research-dna", json=payload)
    assert second.status_code == 409


def test_research_dna_interview_sanitizes_answer_in_response_and_log(tmp_path, monkeypatch):
    research_dna_root = tmp_path / "research_dna"
    monkeypatch.setenv("PAPERPIPE_RESEARCH_DNA_DIR", str(research_dna_root))
    monkeypatch.delenv("LATTICE_API_KEY", raising=False)
    monkeypatch.delenv("PAPERPIPE_API_KEY", raising=False)
    client = TestClient(api_main.app)

    created = client.post(
        "/research-dna",
        json={
            "topic": "Mild cognitive impairment and ketogenic diets",
            "intent": "systematic_review",
            "actor_type": "human_api",
            "actor_id": "tester",
            "reason": "create via api",
            "available_databases": ["pubmed"],
            "recommended_databases": ["pubmed"],
        },
    )
    assert created.status_code == 200
    dna_id = created.json()["dna"]["id"]

    interview = client.post(
        f"/research-dna/{dna_id}/interview",
        json={
            "round": "researcher",
            "question_id": "researcher_secret",
            "question": "Which token was used?",
            "answer": "Authorization: Bearer dnaapitoken123 and sk-proj-dnaapisecret123456.",
            "actor_type": "human_api",
            "actor_id": "tester",
        },
    )
    assert interview.status_code == 200
    assert interview.json()["interview"]["answer"] == "Authorization: <redacted> and <redacted>."

    interview_log = research_dna_root / dna_id / "logs" / "interview.jsonl"
    raw_log = interview_log.read_text(encoding="utf-8")
    assert "dnaapitoken123" not in raw_log
    assert "sk-proj-dnaapisecret123456" not in raw_log
    saved = json.loads(raw_log.strip())
    assert saved["answer"] == "Authorization: <redacted> and <redacted>."


def test_research_dna_api_blocks_interview_logging_when_locked(tmp_path, monkeypatch):
    monkeypatch.setenv("PAPERPIPE_RESEARCH_DNA_DIR", str(tmp_path / "research_dna"))
    monkeypatch.delenv("LATTICE_API_KEY", raising=False)
    monkeypatch.delenv("PAPERPIPE_API_KEY", raising=False)
    client = TestClient(api_main.app)

    created = client.post(
        "/research-dna",
        json={
            "topic": "Mild cognitive impairment and medium-chain triglycerides",
            "intent": "systematic_review",
            "actor_type": "human_api",
            "actor_id": "tester",
            "reason": "create via api",
        },
    )
    dna_id = created.json()["dna"]["id"]

    approved = client.post(
        f"/research-dna/{dna_id}/approve-pilot",
        json={"actor_type": "human_api", "actor_id": "tester", "reason": "approve pilot"},
    )
    assert approved.status_code == 200

    locked = client.post(
        f"/research-dna/{dna_id}/lock",
        json={"actor_type": "human_api", "actor_id": "tester", "reason": "lock dna"},
    )
    assert locked.status_code == 200

    interview = client.post(
        f"/research-dna/{dna_id}/interview",
        json={
            "round": "librarian",
            "question_id": "librarian_1",
            "question": "Which databases are available?",
            "answer": "pubmed",
            "actor_type": "human_api",
            "actor_id": "tester",
        },
    )
    assert interview.status_code == 409
