from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

import src.cli as cli
from src.profiles.profile_store import load_profiles
from src.schemas import Paper


class _FakeFetcher:
    def __init__(self, papers):
        self._papers = papers

    def fetch(self, query: str, max_results: int):
        return self._papers[:max_results]


def _last_json_block(output: str) -> dict:
    start = output.find("{")
    end = output.rfind("}")
    assert start >= 0 and end >= start
    return json.loads(output[start : end + 1])


def test_research_dna_cli_roundtrip(tmp_path, monkeypatch):
    runner = CliRunner()
    monkeypatch.setenv("PAPERPIPE_RESEARCH_DNA_DIR", str(tmp_path / "research_dna"))
    monkeypatch.setenv("PAPERPIPE_SEARCH_EVAL_DIR", str(tmp_path / "search_eval"))
    monkeypatch.setenv("PAPERPIPE_PROFILES_PATH", str(tmp_path / "profiles.yaml"))

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
            title="General nutrition guidance",
            authors=["Lee H"],
            published="2023-05-02",
            source="PubMed",
            summary="Broad diet commentary without the target condition or intervention.",
            link="https://example.org/doi/10.1000/abc",
        ),
    ]
    monkeypatch.setattr(
        "src.profiles.research_dna_service._default_source_fetchers",
        lambda: {"pubmed": _FakeFetcher(fake_papers)},
    )

    create_result = runner.invoke(
        cli.app,
        [
            "research-dna",
            "create",
            "Mild cognitive impairment and medium-chain triglycerides",
            "--intent",
            "systematic_review",
            "--actor-id",
            "tester",
            "--reason",
            "create via cli",
            "--available-db",
            "pubmed",
            "--recommended-db",
            "pubmed",
        ],
    )
    assert create_result.exit_code == 0
    created = _last_json_block(create_result.output)
    dna_id = created["id"]

    interview_result = runner.invoke(
        cli.app,
        [
            "research-dna",
            "interview",
            dna_id,
            "--round",
            "researcher",
            "--question-id",
            "researcher_1",
            "--question",
            "What is the intent?",
            "--answer",
            "systematic_review",
            "--actor-id",
            "tester",
        ],
    )
    assert interview_result.exit_code == 0
    interview_payload = _last_json_block(interview_result.output)
    assert interview_payload["interview"]["round"] == "researcher"

    update_patch_file = tmp_path / "update.yaml"
    update_patch_file.write_text(
        "\n".join(
            [
                "available_databases:",
                "  - pubmed",
                "recommended_databases:",
                "  - pubmed",
                "  - embase",
            ]
        ),
        encoding="utf-8",
    )

    update_result = runner.invoke(
        cli.app,
        [
            "research-dna",
            "update",
            dna_id,
            "--patch-file",
            str(update_patch_file),
            "--actor-id",
            "tester",
            "--reason",
            "set source policy",
        ],
    )
    assert update_result.exit_code == 0

    approve_result = runner.invoke(
        cli.app,
        [
            "research-dna",
            "approve-pilot",
            dna_id,
            "--actor-id",
            "tester",
            "--reason",
            "approve via cli",
        ],
    )
    assert approve_result.exit_code == 0
    resume_before_pilot_result = runner.invoke(
        cli.app,
        [
            "research-dna",
            "resume",
            dna_id,
        ],
    )
    assert resume_before_pilot_result.exit_code == 0
    resume_before_pilot_payload = _last_json_block(resume_before_pilot_result.output)
    assert resume_before_pilot_payload["has_runs"] is False
    assert resume_before_pilot_payload["run_count"] == 0
    assert resume_before_pilot_payload["latest_run_id"] is None
    assert resume_before_pilot_payload["latest_run"] is None

    query_version_file = tmp_path / "v1.yaml"
    query_version_file.write_text(
        "\n".join(
            [
                "version: v1",
                "mode: recall",
                "per_db:",
                '  pubmed: "(\\"mild cognitive impairment\\") AND (\\"medium-chain triglycerides\\")"',
                "change_summary: initial query draft",
                'created_at: "2026-03-12T00:00:00Z"',
                'created_by: "human_cli:tester"',
            ]
        ),
        encoding="utf-8",
    )

    refine_result = runner.invoke(
        cli.app,
        [
            "research-dna",
            "refine",
            dna_id,
            "--query-version-file",
            str(query_version_file),
            "--actor-id",
            "tester",
            "--reason",
            "set initial query",
        ],
    )
    assert refine_result.exit_code == 0

    pilot_result = runner.invoke(
        cli.app,
        [
            "research-dna",
            "pilot",
            dna_id,
            "--actor-id",
            "tester",
            "--run-id",
            "pilot_cli_001",
        ],
    )
    assert pilot_result.exit_code == 0
    pilot_payload = _last_json_block(pilot_result.output)
    assert pilot_payload["run_id"] == "pilot_cli_001"
    assert Path(pilot_payload["screening_queue_path"]).exists()
    runs_after_pilot_result = runner.invoke(
        cli.app,
        [
            "research-dna",
            "runs",
            dna_id,
            "--limit",
            "20",
        ],
    )
    assert runs_after_pilot_result.exit_code == 0
    runs_after_pilot_payload = _last_json_block(runs_after_pilot_result.output)
    assert runs_after_pilot_payload["run_count"] == 1
    assert runs_after_pilot_payload["latest_run_id"] == "pilot_cli_001"
    assert runs_after_pilot_payload["runs"][0]["run_id"] == "pilot_cli_001"
    assert runs_after_pilot_payload["runs"][0]["screening_started"] is False

    rerank_result = runner.invoke(
        cli.app,
        [
            "research-dna",
            "rerank",
            dna_id,
            "--run-id",
            "pilot_cli_001",
            "--actor-id",
            "tester",
        ],
    )
    assert rerank_result.exit_code == 0
    rerank_payload = _last_json_block(rerank_result.output)
    assert rerank_payload["run_id"] == "pilot_cli_001"
    assert Path(rerank_payload["reranked_screening_queue_path"]).exists()

    guidance_materialize_result = runner.invoke(
        cli.app,
        [
            "research-dna",
            "materialize-guidance",
            dna_id,
            "--run-id",
            "pilot_cli_001",
            "--actor-id",
            "tester",
        ],
    )
    assert guidance_materialize_result.exit_code == 0
    guidance_materialize_payload = _last_json_block(guidance_materialize_result.output)
    assert Path(guidance_materialize_payload["artifact_path"]).exists()
    assert guidance_materialize_payload["recommendation"]["recommended_variant"] == "original"
    assert guidance_materialize_payload["gate"]["gate_status"] == "insufficient_signal"
    guidance_artifact_result = runner.invoke(
        cli.app,
        [
            "research-dna",
            "guidance-artifact",
            dna_id,
            "--run-id",
            "pilot_cli_001",
        ],
    )
    assert guidance_artifact_result.exit_code == 0
    guidance_artifact_payload = _last_json_block(guidance_artifact_result.output)
    assert guidance_artifact_payload["artifact_path"] == guidance_materialize_payload["artifact_path"]
    assert guidance_artifact_payload["gate"]["gate_status"] == "insufficient_signal"

    queue_result = runner.invoke(
        cli.app,
        [
            "research-dna",
            "queue",
            dna_id,
            "--run-id",
            "pilot_cli_001",
            "--variant",
            "reranked",
        ],
    )
    assert queue_result.exit_code == 0
    queue_payload = _last_json_block(queue_result.output)
    assert queue_payload["variant"] == "reranked"
    assert queue_payload["row_count"] == 2

    next_result = runner.invoke(
        cli.app,
        [
            "research-dna",
            "next",
            dna_id,
            "--run-id",
            "pilot_cli_001",
            "--variant",
            "reranked",
        ],
    )
    assert next_result.exit_code == 0
    next_payload = _last_json_block(next_result.output)
    assert next_payload["candidate"]["candidate_id"] == "pmid:123"
    assert next_payload["queue_position"] == 1

    session_result = runner.invoke(
        cli.app,
        [
            "research-dna",
            "session",
            dna_id,
            "--run-id",
            "pilot_cli_001",
            "--variant",
            "reranked",
            "--recent-limit",
            "5",
        ],
    )
    assert session_result.exit_code == 0
    session_payload = _last_json_block(session_result.output)
    assert session_payload["session"]["available_variants"] == ["original", "reranked"]
    assert session_payload["session"]["next_candidate"]["candidate_id"] == "pmid:123"
    assert session_payload["session"]["recent_decisions"] == []
    assert session_payload["recommendation"]["owner_variant"] == "original"
    assert session_payload["recommendation"]["recommended_variant"] == "original"
    assert session_payload["recommendation"]["primary_reason_code"] == "no_position_change"
    assert session_payload["recommendation"]["recommendation_summary"] == "Keep the original queue because reranking did not change candidate positions."
    assert session_payload["recommendation"]["changed_position_ratio"] == 0.0
    assert session_payload["gate"]["gate_status"] == "insufficient_signal"
    assert session_payload["gate"]["primary_reason_code"] == "no_position_change"
    assert session_payload["gate"]["gate_summary"] == "Reranked queue is not yet eligible because reranking did not change candidate positions."
    assert session_payload["gate"]["changed_position_ratio"] == 0.0

    recommendation_result = runner.invoke(
        cli.app,
        [
            "research-dna",
            "recommend",
            dna_id,
            "--run-id",
            "pilot_cli_001",
        ],
    )
    assert recommendation_result.exit_code == 0
    recommendation_payload = _last_json_block(recommendation_result.output)
    assert recommendation_payload["owner_variant"] == "original"
    assert recommendation_payload["recommended_variant"] == "original"
    assert recommendation_payload["primary_reason_code"] == "no_position_change"
    assert recommendation_payload["reason_codes"] == ["no_position_change"]
    guidance_result = runner.invoke(
        cli.app,
        [
            "research-dna",
            "guidance",
            dna_id,
            "--run-id",
            "pilot_cli_001",
        ],
    )
    assert guidance_result.exit_code == 0
    guidance_payload = _last_json_block(guidance_result.output)
    assert guidance_payload["recommendation"]["recommended_variant"] == "original"
    assert guidance_payload["gate"]["gate_status"] == "insufficient_signal"
    guidance_history_result = runner.invoke(
        cli.app,
        [
            "research-dna",
            "guidance-history",
            dna_id,
            "--run-id",
            "pilot_cli_001",
            "--limit",
            "20",
        ],
    )
    assert guidance_history_result.exit_code == 0
    guidance_history_payload = _last_json_block(guidance_history_result.output)
    assert guidance_history_payload["entry_count"] == 1
    assert len(guidance_history_payload["entries"]) == 1
    rerank_gate_result = runner.invoke(
        cli.app,
        [
            "research-dna",
            "rerank-gate",
            dna_id,
            "--run-id",
            "pilot_cli_001",
        ],
    )
    assert rerank_gate_result.exit_code == 0
    rerank_gate_payload = _last_json_block(rerank_gate_result.output)
    assert rerank_gate_payload["gate_status"] == "insufficient_signal"
    assert rerank_gate_payload["primary_reason_code"] == "no_position_change"
    assert rerank_gate_payload["reason_codes"] == ["no_position_change"]

    screen_current_result = runner.invoke(
        cli.app,
        [
            "research-dna",
            "screen-current",
            dna_id,
            "--latest",
            "--decision",
            "include",
            "--reason-code",
            "other_noise",
            "--actor-id",
            "tester",
            "--variant",
            "reranked",
            "--recent-limit",
            "5",
            "--expected-candidate-id",
            "pmid:123",
        ],
    )
    assert screen_current_result.exit_code == 0
    screen_current_payload = _last_json_block(screen_current_result.output)
    assert screen_current_payload["screened_candidate_id"] == "pmid:123"
    assert screen_current_payload["next_candidate"]["candidate"]["candidate_id"] == "doi:10.1000/abc"
    assert screen_current_payload["next_candidate"]["remaining_count"] == 1
    assert screen_current_payload["session"]["session_complete"] is False
    assert screen_current_payload["session"]["next_candidate"]["candidate_id"] == "doi:10.1000/abc"
    assert screen_current_payload["session"]["include_count"] == 1
    assert screen_current_payload["session"]["recent_decisions"][0]["variant"] == "reranked"
    assert screen_current_payload["session"]["recent_decisions"][0]["recommended_variant"] == "original"
    assert screen_current_payload["session"]["recent_decisions"][0]["guidance_gate_status"] == "insufficient_signal"
    assert screen_current_payload["session"]["recent_decisions"][0]["guidance_primary_reason_code"] == "no_position_change"
    assert screen_current_payload["session"]["recent_decisions"][0]["followed_guidance"] is False
    assert screen_current_payload["session"]["guidance_follow_summary"]["evaluated_decision_count"] == 1
    assert screen_current_payload["session"]["guidance_follow_summary"]["telemetry_count"] == 1
    assert screen_current_payload["session"]["guidance_follow_summary"]["followed_guidance_count"] == 0
    assert screen_current_payload["session"]["guidance_follow_summary"]["diverged_guidance_count"] == 1
    assert screen_current_payload["session"]["guidance_follow_summary"]["followed_guidance_ratio"] == 0.0
    assert screen_current_payload["recommendation"]["recommended_variant"] == "original"
    assert screen_current_payload["recommendation"]["recommendation_summary"] == "Keep the original queue because screening is already in progress."
    assert screen_current_payload["recommendation"]["reason_codes"] == ["screening_in_progress"]
    assert screen_current_payload["gate"]["gate_status"] == "not_eligible"
    assert screen_current_payload["gate"]["gate_summary"] == "Reranked queue is not eligible because screening is already in progress."
    assert len(screen_current_payload["session"]["recent_decisions"]) == 1
    assert screen_current_payload["session"]["recent_decisions"][0]["candidate_id"] == "pmid:123"
    progress_result = runner.invoke(
        cli.app,
        [
            "research-dna",
            "progress",
            dna_id,
            "--run-id",
            "pilot_cli_001",
            "--variant",
            "reranked",
        ],
    )
    assert progress_result.exit_code == 0
    progress_payload = _last_json_block(progress_result.output)
    assert progress_payload["variant"] == "reranked"
    assert progress_payload["owner_variant"] == "original"
    assert progress_payload["recommended_variant"] == "original"
    assert progress_payload["gate_status"] == "not_eligible"
    assert progress_payload["primary_reason_code"] == "screening_in_progress"
    assert progress_payload["labeled_count"] == 1
    assert progress_payload["remaining_count"] == 1
    assert progress_payload["precision_proxy"] == 1.0
    assert progress_payload["next_candidate_id"] == "doi:10.1000/abc"
    assert progress_payload["top_reason_codes"] == ["other_noise"]
    assert progress_payload["guidance_follow_summary"]["diverged_guidance_count"] == 1
    assert Path(progress_payload["manifest_path"]).exists()
    assert Path(progress_payload["metrics_path"]).exists()

    recommendation_after_result = runner.invoke(
        cli.app,
        [
            "research-dna",
            "recommend",
            dna_id,
            "--run-id",
            "pilot_cli_001",
        ],
    )
    assert recommendation_after_result.exit_code == 0
    recommendation_after_payload = _last_json_block(recommendation_after_result.output)
    assert recommendation_after_payload["recommended_variant"] == "original"
    assert recommendation_after_payload["screening_started"] is True
    assert recommendation_after_payload["reason_codes"] == ["screening_in_progress"]
    rerank_gate_after_result = runner.invoke(
        cli.app,
        [
            "research-dna",
            "rerank-gate",
            dna_id,
            "--run-id",
            "pilot_cli_001",
        ],
    )
    assert rerank_gate_after_result.exit_code == 0
    rerank_gate_after_payload = _last_json_block(rerank_gate_after_result.output)
    assert rerank_gate_after_payload["gate_status"] == "not_eligible"
    assert rerank_gate_after_payload["reason_codes"] == ["screening_in_progress"]

    invalid_screen_current_result = runner.invoke(
        cli.app,
        [
            "research-dna",
            "screen-current",
            dna_id,
            "--run-id",
            "pilot_cli_001",
            "--decision",
            "include",
            "--reason-code",
            "other_noise",
            "--actor-id",
            "tester",
            "--variant",
            "bad_variant",
        ],
    )
    assert invalid_screen_current_result.exit_code != 0
    assert "variant must be 'original' or 'reranked'" in invalid_screen_current_result.output
    invalid_screen_current_selector_result = runner.invoke(
        cli.app,
        [
            "research-dna",
            "screen-current",
            dna_id,
            "--run-id",
            "pilot_cli_001",
            "--latest",
            "--decision",
            "include",
            "--reason-code",
            "other_noise",
            "--actor-id",
            "tester",
        ],
    )
    assert invalid_screen_current_selector_result.exit_code != 0
    assert "provide either run_id or latest=true, not both" in invalid_screen_current_selector_result.output

    screen_next_result = runner.invoke(
        cli.app,
        [
            "research-dna",
            "screen-next",
            dna_id,
            "--latest",
            "--candidate-id",
            "doi:10.1000/abc",
            "--decision",
            "exclude",
            "--reason-code",
            "wrong_population",
            "--actor-id",
            "tester",
            "--variant",
            "reranked",
            "--recent-limit",
            "1",
        ],
    )
    assert screen_next_result.exit_code == 0
    screen_next_payload = _last_json_block(screen_next_result.output)
    assert screen_next_payload["screened_candidate_id"] == "doi:10.1000/abc"
    assert screen_next_payload["next_candidate"]["candidate"] is None
    assert screen_next_payload["next_candidate"]["remaining_count"] == 0
    assert screen_next_payload["session"]["session_complete"] is True
    assert screen_next_payload["session"]["next_candidate"] is None
    assert screen_next_payload["session"]["exclude_count"] == 1
    assert screen_next_payload["gate"]["gate_status"] == "not_eligible"
    assert len(screen_next_payload["session"]["recent_decisions"]) == 1
    assert screen_next_payload["session"]["recent_decisions"][0]["candidate_id"] == "doi:10.1000/abc"
    assert screen_next_payload["session"]["recent_decisions"][0]["variant"] == "reranked"
    assert screen_next_payload["session"]["recent_decisions"][0]["recommended_variant"] == "original"
    assert screen_next_payload["session"]["recent_decisions"][0]["guidance_gate_status"] == "not_eligible"
    assert screen_next_payload["session"]["recent_decisions"][0]["guidance_primary_reason_code"] == "screening_in_progress"
    assert screen_next_payload["session"]["recent_decisions"][0]["followed_guidance"] is False
    assert screen_next_payload["session"]["guidance_follow_summary"]["evaluated_decision_count"] == 2
    assert screen_next_payload["session"]["guidance_follow_summary"]["telemetry_count"] == 2
    assert screen_next_payload["session"]["guidance_follow_summary"]["followed_guidance_count"] == 0
    assert screen_next_payload["session"]["guidance_follow_summary"]["diverged_guidance_count"] == 2
    assert screen_next_payload["session"]["guidance_follow_summary"]["followed_guidance_ratio"] == 0.0

    completed_session_result = runner.invoke(
        cli.app,
        [
            "research-dna",
            "session",
            dna_id,
            "--run-id",
            "pilot_cli_001",
            "--variant",
            "reranked",
            "--recent-limit",
            "1",
        ],
    )
    assert completed_session_result.exit_code == 0
    completed_session_payload = _last_json_block(completed_session_result.output)
    assert completed_session_payload["session"]["session_complete"] is True
    assert completed_session_payload["session"]["next_candidate"] is None
    assert completed_session_payload["session"]["include_count"] == 1
    assert completed_session_payload["session"]["exclude_count"] == 1
    assert completed_session_payload["recommendation"]["recommended_variant"] == "original"
    assert completed_session_payload["gate"]["gate_status"] == "not_eligible"
    assert len(completed_session_payload["session"]["recent_decisions"]) == 1
    assert completed_session_payload["session"]["recent_decisions"][0]["candidate_id"] == "doi:10.1000/abc"
    completed_progress_result = runner.invoke(
        cli.app,
        [
            "research-dna",
            "progress",
            dna_id,
            "--run-id",
            "pilot_cli_001",
            "--variant",
            "reranked",
        ],
    )
    assert completed_progress_result.exit_code == 0
    completed_progress_payload = _last_json_block(completed_progress_result.output)
    assert completed_progress_payload["session_complete"] is True
    assert completed_progress_payload["remaining_count"] == 0
    assert completed_progress_payload["precision_proxy"] == 0.5
    assert completed_progress_payload["next_candidate_id"] is None
    assert completed_progress_payload["guidance_follow_summary"]["diverged_guidance_count"] == 2
    completed_runs_result = runner.invoke(
        cli.app,
        [
            "research-dna",
            "runs",
            dna_id,
            "--limit",
            "20",
        ],
    )
    assert completed_runs_result.exit_code == 0
    completed_runs_payload = _last_json_block(completed_runs_result.output)
    assert completed_runs_payload["latest_run_id"] == "pilot_cli_001"
    assert completed_runs_payload["runs"][0]["session_complete"] is True
    assert completed_runs_payload["runs"][0]["screening_variant"] == "reranked"
    assert completed_runs_payload["runs"][0]["labeled_count"] == 2
    assert completed_runs_payload["runs"][0]["precision_proxy"] == 0.5
    assert completed_runs_payload["runs"][0]["top_reason_codes"] == ["other_noise", "wrong_population"]
    assert Path(completed_runs_payload["runs"][0]["metrics_path"]).exists()
    completed_resume_result = runner.invoke(
        cli.app,
        [
            "research-dna",
            "resume",
            dna_id,
            "--variant",
            "reranked",
            "--recent-limit",
            "1",
        ],
    )
    assert completed_resume_result.exit_code == 0
    completed_resume_payload = _last_json_block(completed_resume_result.output)
    assert completed_resume_payload["has_runs"] is True
    assert completed_resume_payload["latest_run_id"] == "pilot_cli_001"
    assert completed_resume_payload["latest_run"]["run_id"] == "pilot_cli_001"
    assert completed_resume_payload["latest_run"]["session_complete"] is True
    assert completed_resume_payload["session"]["session_complete"] is True
    assert completed_resume_payload["session"]["variant"] == "reranked"
    assert completed_resume_payload["progress"]["session_complete"] is True
    assert completed_resume_payload["progress"]["precision_proxy"] == 0.5
    assert completed_resume_payload["recommendation"]["recommended_variant"] == "original"
    assert completed_resume_payload["gate"]["gate_status"] == "not_eligible"

    invalid_queue_result = runner.invoke(
        cli.app,
        [
            "research-dna",
            "queue",
            dna_id,
            "--run-id",
            "pilot_cli_001",
            "--variant",
            "bad_variant",
        ],
    )
    assert invalid_queue_result.exit_code != 0
    assert "variant must be 'original' or 'reranked'" in invalid_queue_result.output

    invalid_next_result = runner.invoke(
        cli.app,
        [
            "research-dna",
            "next",
            dna_id,
            "--run-id",
            "pilot_cli_001",
            "--variant",
            "bad_variant",
        ],
    )
    assert invalid_next_result.exit_code != 0
    assert "variant must be 'original' or 'reranked'" in invalid_next_result.output

    invalid_session_result = runner.invoke(
        cli.app,
        [
            "research-dna",
            "session",
            dna_id,
            "--run-id",
            "pilot_cli_001",
            "--variant",
            "bad_variant",
        ],
    )
    assert invalid_session_result.exit_code != 0
    assert "variant must be 'original' or 'reranked'" in invalid_session_result.output
    invalid_progress_result = runner.invoke(
        cli.app,
        [
            "research-dna",
            "progress",
            dna_id,
            "--run-id",
            "pilot_cli_001",
            "--variant",
            "bad_variant",
        ],
    )
    assert invalid_progress_result.exit_code != 0
    assert "variant must be 'original' or 'reranked'" in invalid_progress_result.output

    invalid_screen_next_result = runner.invoke(
        cli.app,
        [
            "research-dna",
            "screen-next",
            dna_id,
            "--run-id",
            "pilot_cli_001",
            "--candidate-id",
            "pmid:123",
            "--decision",
            "include",
            "--reason-code",
            "other_noise",
            "--actor-id",
            "tester",
            "--variant",
            "bad_variant",
        ],
    )
    assert invalid_screen_next_result.exit_code != 0
    assert "variant must be 'original' or 'reranked'" in invalid_screen_next_result.output

    show_result = runner.invoke(cli.app, ["research-dna", "show", dna_id])
    assert show_result.exit_code == 0
    shown = _last_json_block(show_result.output)
    assert shown["status"] == "PILOT"

    project_result = runner.invoke(
        cli.app,
        [
            "research-dna",
            "project-profile",
            dna_id,
            "--actor-id",
            "tester",
            "--reason",
            "materialize compatibility profile",
        ],
    )
    assert project_result.exit_code == 0
    projected = _last_json_block(project_result.output)
    assert projected["selected_database"] == "pubmed"
    profiles_path = Path(projected["profile_path"])
    assert profiles_path.exists()
    config = load_profiles(profiles_path)
    assert config.profiles[0].enabled is False
    assert config.profiles[0].schedule == "manual"
