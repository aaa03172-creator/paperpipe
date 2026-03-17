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
        )
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
