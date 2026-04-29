from __future__ import annotations

import json
from pathlib import Path

from scripts.eval.summarize_processor_gate_manual_review import (
    run_processor_gate_manual_review_outcome,
)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _review_summary(run_id: str) -> dict:
    return {
        "schema_version": "processor_gate_threshold_review.v1",
        "generated_at": "2026-04-22T00:00:00Z",
        "run_id": run_id,
        "inputs": {
            "high_threshold": 0.9,
            "low_threshold": 0.7,
            "min_candidate_rows": 20,
            "drift_warn_threshold": 0.25,
        },
        "decision": {
            "recommended_action": "manual_gate_threshold_review",
            "review_ready": True,
            "next_step": "review_mid_confidence_escalation_policy",
            "threshold_change_ready": False,
            "threshold_change_status": "blocked_policy_only",
        },
    }


def test_run_processor_gate_manual_review_outcome_prefers_blank_checklist_by_default(
    tmp_path: Path,
) -> None:
    run_root = tmp_path / "processor_gate_threshold_review_run"
    _write_json(run_root / "summary.json", _review_summary("processor_gate_threshold_review_run"))
    (run_root / "manual_review_checklist.csv").write_text(
        "\n".join(
            [
                "paper_id,default_reviewer_disposition,default_supports_mid_confidence_policy_review,default_supports_high_threshold_change,reviewer_disposition,supports_mid_confidence_policy_review,supports_high_threshold_change,reviewer_notes",
                "paper-1,policy_only_review,yes,no,,,,",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (run_root / "manual_review_frontier.csv").write_text(
        "\n".join(
            [
                "paper_id,default_reviewer_disposition,default_supports_mid_confidence_policy_review,default_supports_high_threshold_change,reviewer_disposition,supports_mid_confidence_policy_review,supports_high_threshold_change,reviewer_notes",
                "paper-1,policy_only_review,yes,no,policy_only_review,yes,no,confirmed",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    payload = run_processor_gate_manual_review_outcome(review_run=run_root)
    outcome = json.loads((run_root / "manual_review_outcome.json").read_text(encoding="utf-8"))
    threshold_decision = json.loads((run_root / "threshold_change_decision.json").read_text(encoding="utf-8"))
    mid_policy_decision = json.loads((run_root / "mid_confidence_policy_decision.json").read_text(encoding="utf-8"))
    policy_debt_reconciliation = json.loads(
        (run_root / "mid_confidence_policy_debt_reconciliation.json").read_text(
            encoding="utf-8"
        )
    )
    manual_override_policy_decision = json.loads(
        (run_root / "manual_override_policy_decision.json").read_text(encoding="utf-8")
    )
    indexed_pending_policy_decision = json.loads(
        (run_root / "indexed_pending_policy_decision.json").read_text(encoding="utf-8")
    )
    fixture_or_test_policy_decision = json.loads(
        (run_root / "fixture_or_test_policy_decision.json").read_text(encoding="utf-8")
    )
    audit_markdown = (run_root / "audit.md").read_text(encoding="utf-8")

    assert payload["worksheet_path"] == str(run_root / "manual_review_checklist.csv")
    assert payload["status"] == "not_reviewed"
    assert payload["review_ready"] is False
    assert outcome["worksheet_name"] == "manual_review_checklist.csv"
    assert outcome["total_row_count"] == 1
    assert outcome["completed_row_count"] == 0
    assert outcome["rows_with_any_review_input_count"] == 0
    assert outcome["status"] == "not_reviewed"
    assert threshold_decision["final_status"] == "manual_review_incomplete"
    assert threshold_decision["threshold_change_ready"] is False
    assert mid_policy_decision["final_status"] == "manual_review_incomplete"
    assert mid_policy_decision["policy_decision_ready"] is False
    assert policy_debt_reconciliation["final_status"] == "manual_review_incomplete"
    assert policy_debt_reconciliation["reconciliation_ready"] is False
    assert policy_debt_reconciliation["historical_mutation_ready"] is False
    assert manual_override_policy_decision["final_status"] == "no_manual_override_rows"
    assert manual_override_policy_decision["threshold_change_ready"] is False
    assert manual_override_policy_decision["historical_mutation_ready"] is False
    assert indexed_pending_policy_decision["final_status"] == "no_indexed_pending_rows"
    assert indexed_pending_policy_decision["threshold_change_ready"] is False
    assert indexed_pending_policy_decision["historical_mutation_ready"] is False
    assert fixture_or_test_policy_decision["final_status"] == "no_fixture_or_test_rows"
    assert fixture_or_test_policy_decision["threshold_change_ready"] is False
    assert fixture_or_test_policy_decision["historical_mutation_ready"] is False
    assert fixture_or_test_policy_decision["archive_action_ready"] is False
    assert "manual_review_outcome.json" in audit_markdown
    assert "manual_review_outcome.md" in audit_markdown
    assert "threshold_change_decision.json" in audit_markdown
    assert "threshold_change_decision.md" in audit_markdown
    assert "mid_confidence_policy_decision.json" in audit_markdown
    assert "mid_confidence_policy_decision.md" in audit_markdown
    assert "mid_confidence_policy_debt_reconciliation.json" in audit_markdown
    assert "mid_confidence_policy_debt_reconciliation.md" in audit_markdown
    assert "manual_override_policy_decision.json" in audit_markdown
    assert "manual_override_policy_decision.md" in audit_markdown
    assert "indexed_pending_policy_decision.json" in audit_markdown
    assert "indexed_pending_policy_decision.md" in audit_markdown
    assert "fixture_or_test_policy_decision.json" in audit_markdown
    assert "fixture_or_test_policy_decision.md" in audit_markdown


def test_run_processor_gate_manual_review_outcome_writes_policy_only_sidecars(
    tmp_path: Path,
) -> None:
    run_root = tmp_path / "processor_gate_threshold_review_run"
    review_summary = _review_summary("processor_gate_threshold_review_run")
    review_summary["manual_review_scope"] = {
        "excluded": {
            "manual_override": {
                "count": 1,
                "paper_ids": ["paper-manual"],
            },
            "indexed_pending": {
                "count": 1,
                "paper_ids": ["paper-indexed"],
            },
            "fixture_or_test": {
                "count": 1,
                "paper_ids": ["paper-fixture"],
            },
        }
    }
    _write_json(run_root / "summary.json", review_summary)
    worksheet_path = run_root / "manual_review_frontier.csv"
    worksheet_path.write_text(
        "\n".join(
            [
                "paper_id,default_reviewer_disposition,default_supports_mid_confidence_policy_review,default_supports_high_threshold_change,reviewer_disposition,supports_mid_confidence_policy_review,supports_high_threshold_change,reviewer_notes",
                "paper-1,policy_only_review,yes,no,policy_only_review,yes,no,confirmed",
                "paper-2,policy_only_review,yes,no,policy_only_review,yes,no,confirmed",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    payload = run_processor_gate_manual_review_outcome(
        review_run=run_root,
        worksheet=worksheet_path,
    )
    outcome = json.loads((run_root / "manual_review_outcome.json").read_text(encoding="utf-8"))
    outcome_markdown = (run_root / "manual_review_outcome.md").read_text(encoding="utf-8")
    threshold_decision = json.loads((run_root / "threshold_change_decision.json").read_text(encoding="utf-8"))
    threshold_decision_markdown = (run_root / "threshold_change_decision.md").read_text(encoding="utf-8")
    mid_policy_decision = json.loads((run_root / "mid_confidence_policy_decision.json").read_text(encoding="utf-8"))
    mid_policy_decision_markdown = (run_root / "mid_confidence_policy_decision.md").read_text(encoding="utf-8")
    policy_debt_reconciliation = json.loads(
        (run_root / "mid_confidence_policy_debt_reconciliation.json").read_text(
            encoding="utf-8"
        )
    )
    policy_debt_reconciliation_markdown = (
        run_root / "mid_confidence_policy_debt_reconciliation.md"
    ).read_text(encoding="utf-8")
    manual_override_policy_decision = json.loads(
        (run_root / "manual_override_policy_decision.json").read_text(encoding="utf-8")
    )
    manual_override_policy_decision_markdown = (
        run_root / "manual_override_policy_decision.md"
    ).read_text(encoding="utf-8")
    indexed_pending_policy_decision = json.loads(
        (run_root / "indexed_pending_policy_decision.json").read_text(encoding="utf-8")
    )
    indexed_pending_policy_decision_markdown = (
        run_root / "indexed_pending_policy_decision.md"
    ).read_text(encoding="utf-8")
    fixture_or_test_policy_decision = json.loads(
        (run_root / "fixture_or_test_policy_decision.json").read_text(encoding="utf-8")
    )
    fixture_or_test_policy_decision_markdown = (
        run_root / "fixture_or_test_policy_decision.md"
    ).read_text(encoding="utf-8")
    audit_markdown = (run_root / "audit.md").read_text(encoding="utf-8")

    assert payload["status"] == "policy_only_confirmed"
    assert payload["review_ready"] is True
    assert payload["outcome_path"] == str(run_root / "manual_review_outcome.json")
    assert payload["outcome_markdown_path"] == str(run_root / "manual_review_outcome.md")
    assert payload["threshold_change_decision_path"] == str(run_root / "threshold_change_decision.json")
    assert payload["threshold_change_decision_markdown_path"] == str(run_root / "threshold_change_decision.md")
    assert payload["mid_confidence_policy_decision_path"] == str(run_root / "mid_confidence_policy_decision.json")
    assert payload["mid_confidence_policy_decision_markdown_path"] == str(run_root / "mid_confidence_policy_decision.md")
    assert payload["mid_confidence_policy_debt_reconciliation_path"] == str(run_root / "mid_confidence_policy_debt_reconciliation.json")
    assert payload["mid_confidence_policy_debt_reconciliation_markdown_path"] == str(run_root / "mid_confidence_policy_debt_reconciliation.md")
    assert payload["manual_override_policy_decision_path"] == str(run_root / "manual_override_policy_decision.json")
    assert payload["manual_override_policy_decision_markdown_path"] == str(run_root / "manual_override_policy_decision.md")
    assert payload["indexed_pending_policy_decision_path"] == str(run_root / "indexed_pending_policy_decision.json")
    assert payload["indexed_pending_policy_decision_markdown_path"] == str(run_root / "indexed_pending_policy_decision.md")
    assert payload["fixture_or_test_policy_decision_path"] == str(run_root / "fixture_or_test_policy_decision.json")
    assert payload["fixture_or_test_policy_decision_markdown_path"] == str(run_root / "fixture_or_test_policy_decision.md")
    assert outcome["worksheet_name"] == "manual_review_frontier.csv"
    assert outcome["completed_row_count"] == 2
    assert outcome["supports_mid_confidence_policy_review_count"] == 2
    assert outcome["supports_high_threshold_change_count"] == 0
    assert outcome["policy_only_confirmed_ids"] == ["paper-1", "paper-2"]
    assert outcome["default_divergence_ids"] == []
    assert threshold_decision["final_status"] == "no_threshold_change_supported"
    assert threshold_decision["recommended_action"] == "keep_current_high_threshold"
    assert threshold_decision["threshold_change_ready"] is False
    assert threshold_decision["threshold_change_next_step"] == "continue_mid_confidence_escalation_policy_review"
    assert threshold_decision["manual_review_counts"] == {
        "total": 2,
        "completed": 2,
        "supports_mid_confidence_policy_review": 2,
        "supports_high_threshold_change": 0,
        "default_divergence": 0,
    }
    assert threshold_decision["high_threshold_candidate_ids"] == []
    assert mid_policy_decision["final_status"] == "mid_confidence_escalation_policy_confirmed"
    assert mid_policy_decision["recommended_action"] == "keep_mid_confidence_pending_review_policy"
    assert mid_policy_decision["policy_decision_ready"] is True
    assert mid_policy_decision["runtime_change_ready"] is False
    assert mid_policy_decision["next_step"] == "treat_legacy_mid_confidence_approvals_as_policy_debt"
    assert policy_debt_reconciliation["final_status"] == "legacy_policy_debt_confirmed"
    assert policy_debt_reconciliation["recommended_action"] == "keep_historical_approvals_as_legacy_policy_debt"
    assert policy_debt_reconciliation["reconciliation_ready"] is True
    assert policy_debt_reconciliation["runtime_change_ready"] is False
    assert policy_debt_reconciliation["historical_mutation_ready"] is False
    assert policy_debt_reconciliation["future_policy"] == "mid_confidence_rows_remain_pending_review"
    assert policy_debt_reconciliation["historical_row_policy"] == "do_not_mass_rewrite_historical_approved_rows"
    assert policy_debt_reconciliation["policy_debt_ids"] == ["paper-1", "paper-2"]
    assert manual_override_policy_decision["final_status"] == "manual_override_exception_policy_confirmed"
    assert manual_override_policy_decision["recommended_action"] == "exclude_manual_override_rows_from_threshold_tuning"
    assert manual_override_policy_decision["policy_decision_ready"] is True
    assert manual_override_policy_decision["threshold_change_ready"] is False
    assert manual_override_policy_decision["runtime_change_ready"] is False
    assert manual_override_policy_decision["historical_mutation_ready"] is False
    assert manual_override_policy_decision["manual_override_count"] == 1
    assert manual_override_policy_decision["indexed_pending_count"] == 1
    assert manual_override_policy_decision["manual_override_ids"] == ["paper-manual"]
    assert manual_override_policy_decision["next_step"] == "review_indexed_pending_status_contract"
    assert indexed_pending_policy_decision["final_status"] == "indexed_pending_status_contract_confirmed"
    assert indexed_pending_policy_decision["recommended_action"] == "keep_indexed_pending_rows_out_of_threshold_tuning"
    assert indexed_pending_policy_decision["policy_decision_ready"] is True
    assert indexed_pending_policy_decision["threshold_change_ready"] is False
    assert indexed_pending_policy_decision["runtime_change_ready"] is False
    assert indexed_pending_policy_decision["historical_mutation_ready"] is False
    assert indexed_pending_policy_decision["indexed_pending_count"] == 1
    assert indexed_pending_policy_decision["manual_override_count"] == 1
    assert indexed_pending_policy_decision["indexed_pending_ids"] == ["paper-indexed"]
    assert indexed_pending_policy_decision["next_step"] == "monitor_processor_gate_excluded_policy_buckets"
    assert fixture_or_test_policy_decision["final_status"] == "fixture_or_test_hygiene_exclusion_confirmed"
    assert fixture_or_test_policy_decision["recommended_action"] == "keep_fixture_or_test_rows_out_of_threshold_tuning"
    assert fixture_or_test_policy_decision["policy_decision_ready"] is True
    assert fixture_or_test_policy_decision["threshold_change_ready"] is False
    assert fixture_or_test_policy_decision["runtime_change_ready"] is False
    assert fixture_or_test_policy_decision["historical_mutation_ready"] is False
    assert fixture_or_test_policy_decision["archive_action_ready"] is False
    assert fixture_or_test_policy_decision["fixture_or_test_count"] == 1
    assert fixture_or_test_policy_decision["manual_override_count"] == 1
    assert fixture_or_test_policy_decision["indexed_pending_count"] == 1
    assert fixture_or_test_policy_decision["fixture_or_test_ids"] == ["paper-fixture"]
    assert fixture_or_test_policy_decision["next_step"] == "monitor_processor_gate_excluded_policy_buckets"
    assert "policy_only_confirmed" in outcome_markdown
    assert "no_threshold_change_supported" in threshold_decision_markdown
    assert "keep_current_high_threshold" in threshold_decision_markdown
    assert "mid_confidence_escalation_policy_confirmed" in mid_policy_decision_markdown
    assert "keep_mid_confidence_pending_review_policy" in mid_policy_decision_markdown
    assert "legacy_policy_debt_confirmed" in policy_debt_reconciliation_markdown
    assert "keep_historical_approvals_as_legacy_policy_debt" in policy_debt_reconciliation_markdown
    assert "Historical Mutation Ready: no" in policy_debt_reconciliation_markdown
    assert "manual_override_exception_policy_confirmed" in manual_override_policy_decision_markdown
    assert "exclude_manual_override_rows_from_threshold_tuning" in manual_override_policy_decision_markdown
    assert "Manual Override Count: 1" in manual_override_policy_decision_markdown
    assert "indexed_pending_status_contract_confirmed" in indexed_pending_policy_decision_markdown
    assert "keep_indexed_pending_rows_out_of_threshold_tuning" in indexed_pending_policy_decision_markdown
    assert "Indexed Pending Count: 1" in indexed_pending_policy_decision_markdown
    assert "fixture_or_test_hygiene_exclusion_confirmed" in fixture_or_test_policy_decision_markdown
    assert "keep_fixture_or_test_rows_out_of_threshold_tuning" in fixture_or_test_policy_decision_markdown
    assert "Fixture/Test Count: 1" in fixture_or_test_policy_decision_markdown
    assert "Archive Action Ready: no" in fixture_or_test_policy_decision_markdown
    assert "paper-1" in outcome_markdown
    assert "paper-2" in outcome_markdown
    assert "manual_review_outcome.json" in audit_markdown
    assert "manual_review_outcome.md" in audit_markdown
    assert "threshold_change_decision.json" in audit_markdown
    assert "threshold_change_decision.md" in audit_markdown
    assert "mid_confidence_policy_decision.json" in audit_markdown
    assert "mid_confidence_policy_decision.md" in audit_markdown
    assert "mid_confidence_policy_debt_reconciliation.json" in audit_markdown
    assert "mid_confidence_policy_debt_reconciliation.md" in audit_markdown
    assert "manual_override_policy_decision.json" in audit_markdown
    assert "manual_override_policy_decision.md" in audit_markdown
    assert "indexed_pending_policy_decision.json" in audit_markdown
    assert "indexed_pending_policy_decision.md" in audit_markdown
    assert "fixture_or_test_policy_decision.json" in audit_markdown
    assert "fixture_or_test_policy_decision.md" in audit_markdown


def test_run_processor_gate_manual_review_outcome_blocks_threshold_change_without_validation_replay(
    tmp_path: Path,
) -> None:
    run_root = tmp_path / "processor_gate_threshold_review_run"
    _write_json(run_root / "summary.json", _review_summary("processor_gate_threshold_review_run"))
    worksheet_path = run_root / "manual_review_frontier.csv"
    worksheet_path.write_text(
        "\n".join(
            [
                "paper_id,default_reviewer_disposition,default_supports_mid_confidence_policy_review,default_supports_high_threshold_change,reviewer_disposition,supports_mid_confidence_policy_review,supports_high_threshold_change,reviewer_notes",
                "paper-1,policy_only_review,yes,no,boundary_review,no,yes,reviewed high-threshold boundary",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    payload = run_processor_gate_manual_review_outcome(
        review_run=run_root,
        worksheet=worksheet_path,
    )
    threshold_decision = json.loads(
        (run_root / "threshold_change_decision.json").read_text(encoding="utf-8")
    )
    threshold_decision_markdown = (run_root / "threshold_change_decision.md").read_text(
        encoding="utf-8"
    )
    audit_markdown = (run_root / "audit.md").read_text(encoding="utf-8")

    assert threshold_decision["final_status"] == "threshold_change_validation_replay_required"
    assert threshold_decision["recommended_action"] == "run_threshold_change_validation_replay_before_decision"
    assert threshold_decision["threshold_change_ready"] is False
    assert threshold_decision["threshold_change_next_step"] == "run_threshold_change_validation_replay"
    assert payload["threshold_change_ready"] is False
    assert payload["threshold_change_status"] == "threshold_change_validation_replay_required"
    assert payload["threshold_change_next_step"] == "run_threshold_change_validation_replay"
    assert threshold_decision["threshold_change_preflight"] == {
        "required": True,
        "ready": False,
        "status": "missing_threshold_change_proposal",
        "blocker": "missing_threshold_change_proposal",
        "validation_replay_status": "not_applicable",
        "validation_replay_matches_proposal": False,
    }
    assert payload["threshold_change_preflight"] == threshold_decision["threshold_change_preflight"]
    assert payload["threshold_change_preflight_text"] == (
        "required=yes, ready=no, status=missing_threshold_change_proposal, "
        "blocker=missing_threshold_change_proposal"
    )
    assert "Threshold Change Preflight: required=yes, ready=no" in threshold_decision_markdown
    assert "missing_threshold_change_proposal" in threshold_decision_markdown
    assert (
        "Threshold Decision: status=threshold_change_validation_replay_required"
        in audit_markdown
    )
    assert "preflight=missing_threshold_change_proposal" in audit_markdown
    assert "blocker=missing_threshold_change_proposal" in audit_markdown


def test_run_processor_gate_manual_review_outcome_allows_threshold_change_after_validation_replay(
    tmp_path: Path,
) -> None:
    run_root = tmp_path / "processor_gate_threshold_review_run"
    validation_run_id = "processor_gate_threshold_review_run__threshold_validation_replay"
    validation_root = tmp_path / "processor_gate_replay_drift" / validation_run_id
    validation_root.mkdir(parents=True, exist_ok=True)
    (validation_root / "summary.json").write_text("{}", encoding="utf-8")
    (validation_root / "details.json").write_text("{}", encoding="utf-8")
    _write_json(
        validation_root / "threshold_replay.json",
        {
            "threshold_replay_mode": "threshold_change_proposal_replay",
            "proposal_run_id": "processor_gate_threshold_review_run",
            "high_threshold": 0.85,
            "low_threshold": 0.7,
            "reviewed_high_threshold": 0.85,
        },
    )
    review_summary = _review_summary("processor_gate_threshold_review_run")
    review_summary["inputs"]["drift_summary_path"] = str(validation_root / "summary.json")
    review_summary["inputs"]["drift_details_path"] = str(validation_root / "details.json")
    _write_json(run_root / "summary.json", review_summary)
    _write_json(
        run_root / "threshold_change_proposal.json",
        {
            "run_id": "processor_gate_threshold_review_run",
            "validation_replay_run_id": validation_run_id,
        },
    )
    worksheet_path = run_root / "manual_review_frontier.csv"
    worksheet_path.write_text(
        "\n".join(
            [
                "paper_id,default_reviewer_disposition,default_supports_mid_confidence_policy_review,default_supports_high_threshold_change,reviewer_disposition,supports_mid_confidence_policy_review,supports_high_threshold_change,reviewer_notes",
                "paper-1,policy_only_review,yes,no,boundary_review,no,yes,reviewed high-threshold boundary",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    payload = run_processor_gate_manual_review_outcome(
        review_run=run_root,
        worksheet=worksheet_path,
    )
    threshold_decision = json.loads(
        (run_root / "threshold_change_decision.json").read_text(encoding="utf-8")
    )
    threshold_decision_markdown = (run_root / "threshold_change_decision.md").read_text(
        encoding="utf-8"
    )
    audit_markdown = (run_root / "audit.md").read_text(encoding="utf-8")

    assert threshold_decision["final_status"] == "high_threshold_boundary_review_needed"
    assert threshold_decision["recommended_action"] == "review_high_threshold_boundary_candidates"
    assert threshold_decision["threshold_change_ready"] is True
    assert payload["threshold_change_ready"] is True
    assert payload["threshold_change_status"] == "high_threshold_boundary_review_needed"
    assert threshold_decision["threshold_change_preflight"] == {
        "required": True,
        "ready": True,
        "status": "ready",
        "blocker": None,
        "validation_replay_status": "matched",
        "validation_replay_matches_proposal": True,
    }
    assert payload["threshold_change_preflight"] == threshold_decision["threshold_change_preflight"]
    assert payload["threshold_change_preflight_text"] == "required=yes, ready=yes, status=ready"
    assert "validation replay matched the proposal" in threshold_decision["summary"]
    assert "Threshold Change Preflight: required=yes, ready=yes, status=ready" in threshold_decision_markdown
    assert "Threshold Decision: status=high_threshold_boundary_review_needed" in audit_markdown
    assert "reviewed=1/1" in audit_markdown
    assert "high=1" in audit_markdown
    assert "preflight=ready" in audit_markdown
