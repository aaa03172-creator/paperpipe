from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from scripts.eval.check_artifact_history_capture_candidates import (
    build_artifact_history_capture_candidate_summary,
    run_artifact_history_capture_candidate_audit,
)
from src.meeting_packs.store import save_meeting_pack
from src.protocol_cards.store import save_protocol_card
from src.schemas.meeting_pack import MeetingPack
from src.schemas.protocol_card import ProtocolCard


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n", encoding="utf-8")


def _write_policy(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "schema_version": "artifact_history_promotion_policy.v1",
                "status": "active",
                "policy_mode": "manual_review_only",
                "required_families": ["meeting_pack", "protocol_card"],
                "thresholds": {
                    "required_families": ["meeting_pack", "protocol_card"],
                    "min_review_feedback_events": 2,
                    "min_generation_outcome_events": 2,
                    "min_paired_artifacts": 1,
                },
                "requires_real_operator_history": True,
                "discussion_ready_when_gate_passes": True,
                "allows_default_owner_change": False,
                "allows_automatic_runtime_promotion": False,
                "required_manual_actions": [
                    "review_recent_samples",
                    "write_promotion_note",
                    "open_explicit_rfc_before_default_owner_change",
                ],
                "notes": ["Manual-review-only posture for selected artifact families."],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def _sample_meeting_pack(*, pack_id: str, title: str, created_at: datetime) -> MeetingPack:
    return MeetingPack(
        id=pack_id,
        mode="journal_club",
        title=title,
        created_at=created_at,
    )


def _sample_protocol_card(*, protocol_id: str, title: str, updated_at: datetime) -> ProtocolCard:
    return ProtocolCard(
        protocol_id=protocol_id,
        title=title,
        source_kind="paper_derived",
        linked_paper_ids=["paper-001"],
        linked_note_slugs=[],
        current_version_id=None,
        validation_status="draft",
        created_at=updated_at,
        updated_at=updated_at,
        version_summaries=[],
    )


def test_build_artifact_history_capture_candidate_summary_reports_candidates(
    tmp_path: Path,
    monkeypatch,
) -> None:
    meeting_root = tmp_path / "meeting_packs"
    protocol_root = tmp_path / "protocol_cards"
    review_log = tmp_path / "storage" / "artifact_review_feedback.jsonl"
    outcome_log = tmp_path / "storage" / "artifact_generation_outcomes.jsonl"
    policy_path = tmp_path / "artifact_history_promotion_policy.json"

    save_meeting_pack(
        _sample_meeting_pack(
            pack_id="meetingpack_20260414T100000Z_candidate_alpha",
            title="Real candidate pack",
            created_at=datetime(2026, 4, 14, 10, 0, tzinfo=timezone.utc),
        ),
        root=meeting_root,
    )
    save_meeting_pack(
        _sample_meeting_pack(
            pack_id="meetingpack_20260414T090000Z_fixture_demo",
            title="Fixture review pack",
            created_at=datetime(2026, 4, 14, 9, 0, tzinfo=timezone.utc),
        ),
        root=meeting_root,
    )
    save_protocol_card(
        _sample_protocol_card(
            protocol_id="protocol_candidate_alpha",
            title="Protocol candidate",
            updated_at=datetime(2026, 4, 14, 11, 0, tzinfo=timezone.utc),
        ),
        root=protocol_root,
    )

    _write_jsonl(
        review_log,
        [
            {
                "feedback_id": "feedback-protocol-1",
                "artifact_type": "protocol_card",
                "artifact_id": "protocol_candidate_alpha",
                "paper_id": "paper-001",
                "decision": "correct",
                "reason_code": "missing_detail",
                "actor_id": "reviewer_001",
                "note": "Needs one more detail.",
            }
        ],
    )
    _write_jsonl(
        outcome_log,
        [
            {
                "outcome_id": "outcome-protocol-1",
                "artifact_type": "protocol_card",
                "artifact_id": "protocol_candidate_alpha",
                "paper_id": "paper-001",
                "review_feedback_id": "feedback-protocol-1",
                "decision": "reused_after_correction",
                "downstream_use": "supporting_context",
                "actor_id": "reviewer_001",
                "note": "Used once.",
            }
        ],
    )
    _write_policy(policy_path)

    monkeypatch.setenv("PAPERPIPE_MEETING_PACKS_DIR", str(meeting_root))
    monkeypatch.setenv("PAPERPIPE_PROTOCOL_CARDS_DIR", str(protocol_root))
    monkeypatch.setenv("PAPERPIPE_ARTIFACT_REVIEW_FEEDBACK_LOG_PATH", str(review_log))
    monkeypatch.setenv("PAPERPIPE_ARTIFACT_GENERATION_OUTCOME_LOG_PATH", str(outcome_log))
    monkeypatch.setenv("PAPERPIPE_ARTIFACT_HISTORY_PROMOTION_POLICY_PATH", str(policy_path))

    summary = build_artifact_history_capture_candidate_summary(
        run_id="artifact_history_capture_candidates_test",
        max_candidates_per_family=5,
    )

    assert summary["decision"]["history_capture_candidates_present"] is True
    assert summary["decision"]["required_families_needing_more_history"] == [
        "meeting_pack",
        "protocol_card",
    ]
    assert summary["families"]["meeting_pack"]["artifact_count"] == 1
    assert summary["families"]["meeting_pack"]["candidate_count"] == 1
    assert summary["families"]["meeting_pack"]["candidates"][0]["artifact_id"] == "meetingpack_20260414T100000Z_candidate_alpha"
    assert summary["families"]["meeting_pack"]["candidates"][0]["candidate_kind"] == "review_candidate"
    assert summary["families"]["protocol_card"]["artifact_count"] == 1
    assert summary["families"]["protocol_card"]["artifacts_with_partial_history"] == 1
    assert summary["families"]["protocol_card"]["candidate_count"] == 1
    assert summary["families"]["protocol_card"]["candidates"][0]["history_status"] == "partial"
    assert summary["families"]["protocol_card"]["candidates"][0]["candidate_kind"] == "review_candidate"
    assert summary["families"]["protocol_card"]["verification_or_smoke_candidate_count"] == 0
    assert "paperpipe artifact-history protocol-card-review" in summary["families"]["protocol_card"]["candidates"][0]["commands"]["review"]


def test_run_artifact_history_capture_candidate_audit_writes_summary_and_cli(
    tmp_path: Path,
    monkeypatch,
) -> None:
    meeting_root = tmp_path / "meeting_packs"
    protocol_root = tmp_path / "protocol_cards"
    review_log = tmp_path / "storage" / "artifact_review_feedback.jsonl"
    outcome_log = tmp_path / "storage" / "artifact_generation_outcomes.jsonl"
    policy_path = tmp_path / "artifact_history_promotion_policy.json"

    save_meeting_pack(
        _sample_meeting_pack(
            pack_id="meetingpack_20260414T100000Z_candidate_alpha",
            title="Real candidate pack",
            created_at=datetime(2026, 4, 14, 10, 0, tzinfo=timezone.utc),
        ),
        root=meeting_root,
    )
    save_protocol_card(
        _sample_protocol_card(
            protocol_id="protocol_candidate_alpha",
            title="Protocol candidate",
            updated_at=datetime(2026, 4, 14, 11, 0, tzinfo=timezone.utc),
        ),
        root=protocol_root,
    )
    _write_jsonl(review_log, [])
    _write_jsonl(outcome_log, [])
    _write_policy(policy_path)

    monkeypatch.setenv("PAPERPIPE_MEETING_PACKS_DIR", str(meeting_root))
    monkeypatch.setenv("PAPERPIPE_PROTOCOL_CARDS_DIR", str(protocol_root))
    monkeypatch.setenv("PAPERPIPE_ARTIFACT_REVIEW_FEEDBACK_LOG_PATH", str(review_log))
    monkeypatch.setenv("PAPERPIPE_ARTIFACT_GENERATION_OUTCOME_LOG_PATH", str(outcome_log))
    monkeypatch.setenv("PAPERPIPE_ARTIFACT_HISTORY_PROMOTION_POLICY_PATH", str(policy_path))

    run_root = run_artifact_history_capture_candidate_audit(
        out_dir=tmp_path / "out",
        run_id="artifact_history_capture_candidates_run",
        max_candidates_per_family=2,
    )
    payload = json.loads((run_root / "summary.json").read_text(encoding="utf-8"))
    assert payload["run_id"] == "artifact_history_capture_candidates_run"
    assert payload["families"]["meeting_pack"]["candidate_count"] == 1

    repo_root = Path(__file__).resolve().parents[1]
    script = repo_root / "scripts" / "eval" / "check_artifact_history_capture_candidates.py"
    out_dir = tmp_path / "cli-out"

    completed = subprocess.run(
        [
            "python3",
            str(script),
            "--run-id",
            "artifact_history_capture_candidates_cli",
            "--out-dir",
            str(out_dir),
            "--max-candidates-per-family",
            "2",
        ],
        cwd=repo_root,
        check=False,
        capture_output=True,
        text=True,
        env={
            **os.environ,
            "PAPERPIPE_MEETING_PACKS_DIR": str(meeting_root),
            "PAPERPIPE_PROTOCOL_CARDS_DIR": str(protocol_root),
            "PAPERPIPE_ARTIFACT_REVIEW_FEEDBACK_LOG_PATH": str(review_log),
            "PAPERPIPE_ARTIFACT_GENERATION_OUTCOME_LOG_PATH": str(outcome_log),
            "PAPERPIPE_ARTIFACT_HISTORY_PROMOTION_POLICY_PATH": str(policy_path),
        },
    )

    assert completed.returncode == 0, completed.stderr
    cli_payload = json.loads(
        (out_dir / "artifact_history_capture_candidates_cli" / "summary.json").read_text(encoding="utf-8")
    )
    assert cli_payload["decision"]["history_capture_candidates_present"] is True


def test_build_artifact_history_capture_candidate_summary_marks_verification_protocols(
    tmp_path: Path,
    monkeypatch,
) -> None:
    protocol_root = tmp_path / "protocol_cards"
    review_log = tmp_path / "storage" / "artifact_review_feedback.jsonl"
    outcome_log = tmp_path / "storage" / "artifact_generation_outcomes.jsonl"
    policy_path = tmp_path / "artifact_history_promotion_policy.json"

    save_protocol_card(
        _sample_protocol_card(
            protocol_id="protocol_review_smoke_alpha",
            title="Protocol review smoke",
            updated_at=datetime(2026, 4, 14, 11, 0, tzinfo=timezone.utc),
        ).model_copy(
            update={
                "purpose": "Verification-only protocol smoke check",
                "context": "Created from a smoke verification surface.",
                "linked_paper_ids": ["paper-review-smoke"],
                "linked_note_slugs": ["reviewProtocolSmoke"],
            }
        ),
        root=protocol_root,
    )
    _write_jsonl(review_log, [])
    _write_jsonl(outcome_log, [])
    _write_policy(policy_path)

    monkeypatch.setenv("PAPERPIPE_PROTOCOL_CARDS_DIR", str(protocol_root))
    monkeypatch.setenv("PAPERPIPE_ARTIFACT_REVIEW_FEEDBACK_LOG_PATH", str(review_log))
    monkeypatch.setenv("PAPERPIPE_ARTIFACT_GENERATION_OUTCOME_LOG_PATH", str(outcome_log))
    monkeypatch.setenv("PAPERPIPE_ARTIFACT_HISTORY_PROMOTION_POLICY_PATH", str(policy_path))

    summary = build_artifact_history_capture_candidate_summary(
        run_id="artifact_history_capture_candidates_protocol_kind_test",
        max_candidates_per_family=5,
    )

    protocol_family = summary["families"]["protocol_card"]
    assert protocol_family["candidate_count"] == 1
    assert protocol_family["verification_or_smoke_candidate_count"] == 1
    assert protocol_family["candidates"][0]["candidate_kind"] == "verification_or_smoke"
