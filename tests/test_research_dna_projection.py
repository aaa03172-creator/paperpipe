from __future__ import annotations

import json

from src.profiles.profile_store import load_profiles
from src.profiles.research_dna_projection import (
    build_projected_profile,
    projected_profile_id,
    sync_research_dna_profile,
)
from src.profiles.research_dna_schema import QueryVersion, ResearchDNAUpdate
from src.profiles.research_dna_service import create_research_dna, refine_query_version, update_research_dna


def _read_jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_build_projected_profile_uses_deterministic_manual_snapshot(tmp_path):
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
    dna = update_research_dna(
        dna.id,
        patch=ResearchDNAUpdate(
            scope={
                "population": ["mild cognitive impairment"],
                "intervention_or_exposure": ["medium-chain triglycerides"],
                "outcomes": ["cognition"],
            },
            criteria={"exclude": ["animal-only studies"]},
        ),
        actor_type="human_cli",
        actor_id="tester",
        reason="add scope and criteria",
        root=root,
    )
    dna = refine_query_version(
        dna.id,
        query_version=QueryVersion(
            version="v1",
            mode="recall",
            per_db={"pubmed": "(\"mild cognitive impairment\") AND (\"medium-chain triglycerides\")"},
            change_summary="initial query",
            created_at="2026-03-13T00:00:00Z",
            created_by="human_cli:tester",
        ),
        actor_type="human_cli",
        actor_id="tester",
        reason="add v1 query",
        root=root,
    )

    projection = build_projected_profile(dna, root=root)
    projection_again = build_projected_profile(dna, root=root)
    assert projection.profile.id == projected_profile_id(dna.id)
    assert projection.profile.enabled is False
    assert projection.profile.schedule == "manual"
    assert projection.profile.limits.max_results_per_run == dna.pilot.n
    assert projection.profile.query.must == ["mild cognitive impairment", "medium-chain triglycerides"]
    assert projection.profile.query.should == ["cognition"]
    assert projection.profile.query.must_not == ["animal-only studies"]
    assert "schema_version: research_dna.profile_projection.v1" in (projection.profile.notes or "")
    assert f"source_dna_id: {dna.id}" in (projection.profile.notes or "")
    assert "exact_query:" in (projection.profile.notes or "")
    assert "mild cognitive impairment" in (projection.profile.notes or "")
    assert "medium-chain triglycerides" in (projection.profile.notes or "")
    assert projection.profile.model_dump() == projection_again.profile.model_dump()


def test_sync_research_dna_profile_upserts_projection_and_logs_action(tmp_path):
    root = tmp_path / "research_dna"
    profiles_path = tmp_path / "profiles.yaml"
    dna = create_research_dna(
        topic="Mild cognitive impairment and medium-chain triglycerides",
        intent="systematic_review",
        actor_type="human_cli",
        actor_id="tester",
        reason="create draft",
        root=root,
        available_databases=["pubmed"],
    )
    refine_query_version(
        dna.id,
        query_version=QueryVersion(
            version="v1",
            mode="recall",
            per_db={"pubmed": "(\"mild cognitive impairment\") AND (\"medium-chain triglycerides\")"},
            change_summary="initial query",
            created_at="2026-03-13T00:00:00Z",
            created_by="human_cli:tester",
        ),
        actor_type="human_cli",
        actor_id="tester",
        reason="add v1 query",
        root=root,
    )

    projection = sync_research_dna_profile(
        dna.id,
        actor_type="human_cli",
        actor_id="tester",
        reason="materialize compatibility profile",
        root=root,
        profiles_path=profiles_path,
    )
    assert projection.profile_path == str(profiles_path.resolve())
    config = load_profiles(profiles_path)
    assert len(config.profiles) == 1
    assert config.profiles[0].id == projected_profile_id(dna.id)
    assert config.profiles[0].revision == 0
    assert projection.profile.revision == 0

    projection2 = sync_research_dna_profile(
        dna.id,
        actor_type="human_cli",
        actor_id="tester",
        reason="refresh compatibility profile",
        root=root,
        profiles_path=profiles_path,
    )
    config = load_profiles(profiles_path)
    assert len(config.profiles) == 1
    assert config.profiles[0].id == projection2.profile.id
    assert config.profiles[0].revision == 1
    assert projection2.profile.revision == 1

    approval_rows = _read_jsonl(root / dna.id / "logs" / "approval_audit.jsonl")
    assert approval_rows[-1]["action"] == "project_profile"
