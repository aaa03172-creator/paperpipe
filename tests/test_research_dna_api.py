from __future__ import annotations

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

    screening = client.post(
        f"/research-dna/{dna_id}/screening",
        json={
            "run_id": "pilot_api_001",
            "candidate_id": "pmid:123",
            "decision": "exclude",
            "reason_code": "wrong_population",
            "actor_type": "human_api",
            "actor_id": "tester",
        },
    )
    assert screening.status_code == 200

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
