from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from typer.testing import CliRunner

from backend import main as api_main
import src.cli as cli


def _last_json_block(output: str) -> dict:
    start = output.find("{")
    end = output.rfind("}")
    assert start >= 0 and end >= start
    return json.loads(output[start : end + 1])


def _read_jsonl_rows(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _write_config(path: Path, vault_path: Path) -> None:
    path.write_text(
        "\n".join(
            [
                "system:",
                "  log_level: INFO",
                "paths:",
                f"  zotero_base_dir: {vault_path}",
                f"  obsidian_vault: {vault_path}",
                "search:",
                "  constraints:",
                "    min_pubmed: 2",
                "    max_preprint: 1",
                "  slots:",
                "    primary:",
                '      query: "test"',
                "llm:",
                "  mode: local",
                "  features:",
                "    specialty_trial_extraction:",
                "      enabled: false",
                "    slot_classification:",
                "      enabled: false",
                "    one_liner:",
                "      enabled: false",
            ]
        ),
        encoding="utf-8",
    )


def _write_state(vault_path: Path, slug: str) -> None:
    state_path = vault_path / ".pp" / slug / "state.json"
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(
        json.dumps(
            {
                "paper_slug": slug,
                "updated_at": "2026-04-10T09:00:00Z",
                "runs": [
                    {
                        "id": "run-current",
                        "action": "deep_read",
                        "ts": "2026-04-10T09:00:00Z",
                        "status": "succeeded",
                        "summary": "Canonical state snapshot",
                    }
                ],
                "signals": {"last_run_id": "run-current"},
                "claimset": [
                    {
                        "id": "claim-001",
                        "run_id": "run-current",
                        "claim": "Short-chain fatty acids improved outcome.",
                        "evidence": [
                            {
                                "id": "evidence-001",
                                "claim_id": "claim-001",
                                "run_id": "run-current",
                                "text": "Evidence text",
                                "locator": {"page": 2, "section": "Results", "source": "state.json"},
                            }
                        ],
                    }
                ],
                "entities": ["short-chain fatty acids"],
                "outcomes": ["gut barrier function"],
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def test_artifact_history_cli_records_meeting_pack_review_and_outcome(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runner = CliRunner()
    vault_path = tmp_path / "vault"
    vault_path.mkdir(parents=True, exist_ok=True)
    slug = "wenzelShortchainFattyAcids2020"
    _write_state(vault_path, slug)

    config_path = tmp_path / "config.yaml"
    _write_config(config_path, vault_path)

    review_log = tmp_path / "storage" / "artifact_review_feedback.jsonl"
    outcome_log = tmp_path / "storage" / "artifact_generation_outcomes.jsonl"
    monkeypatch.setenv("PAPERPIPE_CONFIG_PATH", str(config_path))
    monkeypatch.setenv("PAPERPIPE_MEETING_PACKS_DIR", str(tmp_path / "meeting_packs"))
    monkeypatch.setenv("PAPERPIPE_ARTIFACT_REVIEW_FEEDBACK_LOG_PATH", str(review_log))
    monkeypatch.setenv("PAPERPIPE_ARTIFACT_GENERATION_OUTCOME_LOG_PATH", str(outcome_log))
    monkeypatch.delenv("LATTICE_API_KEY", raising=False)
    monkeypatch.delenv("PAPERPIPE_API_KEY", raising=False)

    client = TestClient(api_main.app)
    generate = client.post(
        "/meeting-packs/generate",
        json={"mode": "journal_club", "source_items": [{"type": "paper_slug", "ref": slug}]},
    )
    assert generate.status_code == 200
    pack_id = generate.json()["pack"]["id"]

    review_result = runner.invoke(
        cli.app,
        [
            "artifact-history",
            "meeting-pack-review",
            pack_id,
            "--run-id",
            "run_meeting_pack_cli_001",
            "--decision",
            "correct",
            "--reason-code",
            "missing_context",
            "--actor-id",
            "reviewer_cli",
            "--note",
            "Needs stronger context in the opening section.",
        ],
    )
    assert review_result.exit_code == 0
    review_payload = _last_json_block(review_result.output)
    assert review_payload["status"] == "saved"
    assert review_payload["feedback"]["artifact_type"] == "meeting_pack"
    assert review_payload["feedback"]["artifact_id"] == pack_id

    outcome_result = runner.invoke(
        cli.app,
        [
            "artifact-history",
            "meeting-pack-outcome",
            pack_id,
            "--run-id",
            "run_meeting_pack_cli_001",
            "--review-feedback-id",
            review_payload["feedback"]["feedback_id"],
            "--decision",
            "reused_after_correction",
            "--downstream-use",
            "final_deliverable",
            "--actor-id",
            "reviewer_cli",
            "--note",
            "Used after tightening the discussion framing.",
        ],
    )
    assert outcome_result.exit_code == 0
    outcome_payload = _last_json_block(outcome_result.output)
    assert outcome_payload["status"] == "saved"
    assert outcome_payload["outcome"]["artifact_type"] == "meeting_pack"
    assert outcome_payload["outcome"]["artifact_id"] == pack_id

    review_rows = _read_jsonl_rows(review_log)
    outcome_rows = _read_jsonl_rows(outcome_log)
    assert len(review_rows) == 1
    assert len(outcome_rows) == 1
    assert review_rows[0]["decision"] == "correct"
    assert outcome_rows[0]["decision"] == "reused_after_correction"
    assert outcome_rows[0]["review_feedback_id"] == review_payload["feedback"]["feedback_id"]


def test_artifact_history_cli_records_protocol_card_review_and_outcome(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runner = CliRunner()
    review_log = tmp_path / "storage" / "artifact_review_feedback.jsonl"
    outcome_log = tmp_path / "storage" / "artifact_generation_outcomes.jsonl"
    monkeypatch.setenv("PAPERPIPE_PROTOCOL_CARDS_DIR", str(tmp_path / "protocol_cards"))
    monkeypatch.setenv("PAPERPIPE_ARTIFACT_REVIEW_FEEDBACK_LOG_PATH", str(review_log))
    monkeypatch.setenv("PAPERPIPE_ARTIFACT_GENERATION_OUTCOME_LOG_PATH", str(outcome_log))
    monkeypatch.delenv("LATTICE_API_KEY", raising=False)
    monkeypatch.delenv("PAPERPIPE_API_KEY", raising=False)

    client = TestClient(api_main.app)
    created = client.post(
        "/protocol-cards",
        json={
            "protocol_id": "protocol_cli_review",
            "title": "CLI review protocol",
            "source_kind": "paper_derived",
            "linked_paper_ids": ["paper-001"],
            "versions": [
                {
                    "version_id": "protver_cli_review_v1",
                    "version_number": 1,
                    "content_snapshot": "Step 1: seed cells",
                    "status": "active",
                    "created_by": "operator",
                }
            ],
        },
    )
    assert created.status_code == 200

    review_result = runner.invoke(
        cli.app,
        [
            "artifact-history",
            "protocol-card-review",
            "protocol_cli_review",
            "--paper-id",
            "paper-001",
            "--decision",
            "correct",
            "--reason-code",
            "missing_detail",
            "--actor-id",
            "reviewer_cli",
            "--note",
            "Needs one more procedural detail before reuse.",
        ],
    )
    assert review_result.exit_code == 0
    review_payload = _last_json_block(review_result.output)
    assert review_payload["feedback"]["artifact_type"] == "protocol_card"
    assert review_payload["feedback"]["artifact_id"] == "protocol_cli_review"

    outcome_result = runner.invoke(
        cli.app,
        [
            "artifact-history",
            "protocol-card-outcome",
            "protocol_cli_review",
            "--paper-id",
            "paper-001",
            "--review-feedback-id",
            review_payload["feedback"]["feedback_id"],
            "--decision",
            "reused",
            "--downstream-use",
            "supporting_context",
            "--actor-id",
            "reviewer_cli",
            "--note",
            "Used as supporting context for the next lab packet.",
        ],
    )
    assert outcome_result.exit_code == 0
    outcome_payload = _last_json_block(outcome_result.output)
    assert outcome_payload["outcome"]["artifact_type"] == "protocol_card"
    assert outcome_payload["outcome"]["artifact_id"] == "protocol_cli_review"

    review_rows = _read_jsonl_rows(review_log)
    outcome_rows = _read_jsonl_rows(outcome_log)
    assert len(review_rows) == 1
    assert len(outcome_rows) == 1
    assert review_rows[0]["reason_code"] == "missing_detail"
    assert outcome_rows[0]["downstream_use"] == "supporting_context"
