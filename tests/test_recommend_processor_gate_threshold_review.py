from __future__ import annotations

import csv
import json
import os
import subprocess
import sys
from pathlib import Path

from scripts.eval.recommend_processor_gate_threshold_review import (
    build_processor_gate_threshold_review_summary,
    render_processor_gate_threshold_manual_review_checklist_csv,
    render_processor_gate_threshold_manual_review_crosscheck_packet_markdown,
    render_processor_gate_threshold_manual_review_frontier_csv,
    render_processor_gate_threshold_manual_review_frontier_notes_markdown,
    render_processor_gate_threshold_manual_review_seed_csv,
    run_processor_gate_threshold_review,
)
from src.services.processor_gate_replay_drift import (
    build_processor_gate_threshold_review_viewer_command,
    latest_processor_gate_threshold_review_run,
    load_processor_gate_threshold_review_summary,
    resolve_processor_gate_threshold_review_drift_artifacts,
)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _drift_summary(
    *,
    run_id: str,
    high_threshold: float,
    low_threshold: float,
    candidate_count: int,
    promotable_count: int,
    drift_count: int,
    drift_rate: float,
    decision_transition_counts: dict[str, int],
    probable_drift_cause_counts: dict[str, int],
    gate_reason_category_counts: dict[str, int],
    confidence_band_counts: dict[str, int],
) -> dict:
    return {
        "schema_version": "processor_gate_replay_drift_summary.v5",
        "generated_at": "2026-04-21T00:00:00Z",
        "run_id": run_id,
        "inputs": {
            "db_path": "storage/state.db",
            "row_count": 54,
            "high_threshold": high_threshold,
            "low_threshold": low_threshold,
        },
        "metrics": {
            "candidate_count": candidate_count,
            "promotable_count": promotable_count,
            "drift_count": drift_count,
            "drift_rate": drift_rate,
            "decision_transition_counts": decision_transition_counts,
            "probable_drift_cause_counts": probable_drift_cause_counts,
            "gate_reason_category_counts": gate_reason_category_counts,
            "confidence_band_counts": confidence_band_counts,
        },
        "documents_with_drift": [],
    }


def _drift_details(*, documents: list[dict]) -> dict:
    return {
        "schema_version": "processor_gate_replay_drift_details.v1",
        "generated_at": "2026-04-21T00:00:00Z",
        "run_id": "processor_gate_replay_drift_details_test",
        "documents": documents,
    }


def test_build_processor_gate_threshold_review_summary_warns_when_drift_is_high() -> None:
    payload = build_processor_gate_threshold_review_summary(
        drift_summary=_drift_summary(
            run_id="processor_gate_replay_drift_preapply_20260421_r11",
            high_threshold=0.9,
            low_threshold=0.7,
            candidate_count=54,
            promotable_count=28,
            drift_count=26,
            drift_rate=0.481481,
            decision_transition_counts={
                "APPROVED->PENDING_REVIEW": 23,
                "PENDING_REVIEW->APPROVED": 1,
                "PENDING_REVIEW->PENDING_REVIEW": 2,
            },
            probable_drift_cause_counts={
                "legacy_mid_confidence_approval": 21,
                "legacy_high_confidence_pending": 1,
                "legacy_indexed_pending_review": 2,
                "manual_or_human_override_mid_confidence": 2,
            },
            gate_reason_category_counts={"confidence_threshold": 2, "manual_or_human": 2, "none": 22},
            confidence_band_counts={"high": 1, "mid": 25},
        ),
        drift_summary_path=Path("/tmp/drift/summary.json"),
        drift_details=_drift_details(
            documents=[
                {
                    "paper_id": "paper-mid-1",
                    "eligible_for_apply": False,
                    "probable_drift_cause": "legacy_mid_confidence_approval",
                    "current_gate_decision": "APPROVED",
                    "replay_gate_decision": "PENDING_REVIEW",
                    "confidence_band": "mid",
                },
                {
                    "paper_id": "paper-mid-2",
                    "eligible_for_apply": False,
                    "probable_drift_cause": "legacy_mid_confidence_approval",
                    "current_gate_decision": "APPROVED",
                    "replay_gate_decision": "PENDING_REVIEW",
                    "confidence_band": "mid",
                },
                {
                    "paper_id": "paper-manual",
                    "eligible_for_apply": False,
                    "probable_drift_cause": "manual_or_human_override_mid_confidence",
                    "current_gate_decision": "APPROVED",
                    "replay_gate_decision": "PENDING_REVIEW",
                    "confidence_band": "mid",
                },
                {
                    "paper_id": "paper-indexed",
                    "eligible_for_apply": False,
                    "probable_drift_cause": "legacy_indexed_pending_review",
                    "current_gate_decision": "PENDING_REVIEW",
                    "replay_gate_decision": "PENDING_REVIEW",
                    "confidence_band": "mid",
                },
                {
                    "paper_id": "paper-fixture",
                    "eligible_for_apply": False,
                    "probable_drift_cause": "legacy_high_confidence_pending",
                    "current_gate_decision": "PENDING_REVIEW",
                    "replay_gate_decision": "APPROVED",
                    "confidence_band": "high",
                    "local_provenance_hint": "test_fixture_row",
                },
            ]
        ),
        drift_details_path=Path("/tmp/drift/details.json"),
        run_id="gate_threshold_review_warn",
        min_candidate_rows=20,
        drift_warn_threshold=0.25,
    )

    assert payload["decision"]["recommended_action"] == "manual_gate_threshold_review"
    assert payload["decision"]["review_ready"] is True
    assert payload["decision"]["latest_run_status"] == "warn"
    assert payload["decision"]["next_step"] == "review_gate_thresholds_and_mid_confidence_policy"
    assert payload["decision"]["focus_areas"] == [
        "high_threshold",
        "mid_confidence_escalation",
        "high_confidence_pending_policy",
        "indexed_pending_policy",
        "manual_override_boundary",
    ]
    assert payload["inputs"]["high_threshold"] == 0.9
    assert payload["inputs"]["low_threshold"] == 0.7
    assert payload["inputs"]["drift_details_path"] == "/tmp/drift/details.json"
    assert payload["decision"]["tuning_targets"] == [
        "mid_confidence_escalation",
        "manual_override_boundary",
        "indexed_pending_policy",
    ]
    assert payload["decision"]["tuning_actions"] == [
        {
            "target": "mid_confidence_escalation",
            "action": "review_mid_confidence_escalation_policy",
            "summary": "Review whether historical mid-confidence approvals should now escalate to pending review before changing the high threshold.",
        },
        {
            "target": "manual_override_boundary",
            "action": "exclude_manual_override_rows_from_threshold_tuning",
            "summary": "Keep manual or human override rows out of threshold changes and review them as explicit policy exceptions.",
        },
        {
            "target": "indexed_pending_policy",
            "action": "exclude_indexed_pending_rows_from_threshold_tuning",
            "summary": "Keep indexed-pending rows out of raw threshold changes and review their status policy separately.",
        },
    ]
    assert payload["decision"]["action_plan"] == [
        {
            "order": 1,
            "action": "review_gate_thresholds_and_mid_confidence_policy",
            "target": None,
            "blocking": True,
            "summary": "Use the threshold-relevant bucket as the primary manual-review basis before applying gate threshold changes.",
        },
        {
            "order": 2,
            "action": "review_mid_confidence_escalation_policy",
            "target": "mid_confidence_escalation",
            "blocking": True,
            "summary": "Review whether historical mid-confidence approvals should now escalate to pending review before changing the high threshold.",
        },
        {
            "order": 3,
            "action": "exclude_manual_override_rows_from_threshold_tuning",
            "target": "manual_override_boundary",
            "blocking": False,
            "summary": "Keep manual or human override rows out of threshold changes and review them as explicit policy exceptions.",
        },
        {
            "order": 4,
            "action": "exclude_indexed_pending_rows_from_threshold_tuning",
            "target": "indexed_pending_policy",
            "blocking": False,
            "summary": "Keep indexed-pending rows out of raw threshold changes and review their status policy separately.",
        },
    ]
    assert payload["decision"]["tuning_recommendations"] == [
        "Current threshold-relevant drift is entirely mid-confidence approval debt, so review the mid-confidence escalation policy before lowering the high threshold.",
        "Keep the current high threshold unchanged unless manual review of the threshold-relevant bucket shows true high-threshold misses.",
        "Manual or human override rows should stay outside raw threshold tuning and be reviewed as explicit policy exceptions.",
        "Indexed-pending rows should stay outside raw threshold changes and be reviewed against the pending/indexed state contract.",
        "Fixture or test rows should not influence threshold changes.",
    ]
    assert payload["decision"]["threshold_change_ready"] is False
    assert payload["decision"]["threshold_change_status"] == "blocked_policy_only"
    assert payload["decision"]["threshold_change_next_step"] == "review_mid_confidence_escalation_policy"
    assert payload["decision"]["threshold_change_blocker"] == (
        "All 2 threshold-relevant row(s) are mid-confidence legacy approvals replaying to pending review; "
        "none support a high-threshold boundary change from this evidence alone."
    )
    assert payload["signal_summary"]["drift_count"] == 26
    assert payload["manual_review_scope"]["threshold_relevant"]["count"] == 2
    assert payload["manual_review_scope"]["excluded"]["manual_override"]["count"] == 1
    assert payload["manual_review_scope"]["excluded"]["indexed_pending"]["count"] == 1
    assert payload["manual_review_scope"]["excluded"]["fixture_or_test"]["count"] == 1
    assert payload["manual_review_scope"]["worksheet_summary"] == {
        "pending_count": 2,
        "review_bucket": "threshold_relevant",
        "primary_review_target": "mid_confidence_escalation_policy",
        "excluded_count": 3,
        "summary": "2 threshold-relevant row(s) are queued for mid-confidence escalation policy review; exclude 3 non-threshold row(s) from raw threshold changes.",
    }
    assert payload["manual_review_scope"]["prefill_summary"] == {
        "threshold_relevant_count": 2,
        "policy_only_review_count": 2,
        "boundary_review_count": 0,
        "manual_triage_count": 0,
        "priority_review_now_count": 0,
        "priority_review_first_count": 2,
        "priority_review_later_count": 0,
        "supports_mid_confidence_policy_review_count": 2,
        "supports_high_threshold_change_count": 0,
        "summary": "Default prefills: policy_only=2, boundary=0, triage=0. Priority: now=0, first=2, later=0.",
    }
    assert payload["manual_review_basis"] == {
        "preliminary_call": "mid_confidence_policy_only",
        "summary": "All 2 threshold-relevant row(s) are mid-confidence legacy approvals replaying to pending review; none support a high-threshold boundary change from this evidence alone.",
        "threshold_relevant_count": 2,
        "policy_edge_case_count": 0,
        "mid_confidence_policy_support_count": 2,
        "high_threshold_support_count": 0,
        "evidence_source_counts": {"unknown": 2},
        "historical_rewrite_hint_counts": {"none": 2},
        "exact_confidence_counts": {"unknown": 2},
        "decision_transition_counts": {"APPROVED->PENDING_REVIEW": 2},
        "probable_drift_cause_counts": {"legacy_mid_confidence_approval": 2},
        "sample_titles": [],
    }
    assert "review the mid-confidence escalation policy before lowering the high threshold" in payload["decision"]["decision_reason"]
    assert any(
        "Focus threshold tuning on 2 threshold-relevant row(s) first" in item
        for item in payload["recommendations"]
    )
    assert "high threshold and mid-confidence escalation policy first" in payload["recommendations"][0]
    assert any(
        "none support a high-threshold boundary change from this evidence alone." in item
        for item in payload["recommendations"]
    )


def test_build_processor_gate_threshold_review_summary_holds_for_small_samples() -> None:
    payload = build_processor_gate_threshold_review_summary(
        drift_summary=_drift_summary(
            run_id="processor_gate_replay_drift_small",
            high_threshold=0.9,
            low_threshold=0.7,
            candidate_count=12,
            promotable_count=11,
            drift_count=1,
            drift_rate=0.0833,
            decision_transition_counts={"APPROVED->PENDING_REVIEW": 1},
            probable_drift_cause_counts={"legacy_mid_confidence_approval": 1},
            gate_reason_category_counts={"confidence_threshold": 1},
            confidence_band_counts={"mid": 1},
        ),
        drift_summary_path=Path("/tmp/drift/summary.json"),
        run_id="gate_threshold_review_small",
        min_candidate_rows=20,
        drift_warn_threshold=0.25,
    )

    assert payload["decision"]["recommended_action"] == "hold_current_gate_thresholds"
    assert payload["decision"]["review_ready"] is False
    assert payload["decision"]["latest_run_status"] == "small_sample"
    assert payload["decision"]["next_step"] == "collect_more_processor_gate_drift_evidence"
    assert payload["decision"]["threshold_change_ready"] is False
    assert payload["decision"]["threshold_change_status"] == "blocked_small_sample"
    assert payload["decision"]["threshold_change_next_step"] == "collect_more_processor_gate_drift_evidence"


def test_run_processor_gate_threshold_review_uses_latest_summary_from_root(tmp_path: Path) -> None:
    drift_root = tmp_path / "processor_gate_replay_drift"
    older_run = drift_root / "processor_gate_replay_drift_old"
    newer_run = drift_root / "processor_gate_replay_drift_new"
    older_summary = older_run / "summary.json"
    newer_summary = newer_run / "summary.json"
    _write_json(
        older_summary,
        _drift_summary(
            run_id="processor_gate_replay_drift_old",
            high_threshold=0.9,
            low_threshold=0.7,
            candidate_count=30,
            promotable_count=29,
            drift_count=1,
            drift_rate=0.0333,
            decision_transition_counts={"APPROVED->PENDING_REVIEW": 1},
            probable_drift_cause_counts={"legacy_mid_confidence_approval": 1},
            gate_reason_category_counts={"confidence_threshold": 1},
            confidence_band_counts={"mid": 1},
        ),
    )
    _write_json(
        newer_summary,
        _drift_summary(
            run_id="processor_gate_replay_drift_new",
            high_threshold=0.9,
            low_threshold=0.7,
            candidate_count=54,
            promotable_count=28,
            drift_count=26,
            drift_rate=0.481481,
            decision_transition_counts={"APPROVED->PENDING_REVIEW": 23},
            probable_drift_cause_counts={"legacy_mid_confidence_approval": 21},
            gate_reason_category_counts={"none": 22},
            confidence_band_counts={"mid": 25},
        ),
    )
    _write_json(
        newer_run / "details.json",
        _drift_details(
            documents=[
                {
                    "paper_id": "paper-mid-1",
                    "eligible_for_apply": False,
                    "probable_drift_cause": "legacy_mid_confidence_approval",
                    "current_gate_decision": "APPROVED",
                    "replay_gate_decision": "PENDING_REVIEW",
                    "confidence_band": "mid",
                },
                {
                    "paper_id": "paper-manual",
                    "eligible_for_apply": False,
                    "probable_drift_cause": "manual_or_human_override_mid_confidence",
                    "current_gate_decision": "APPROVED",
                    "replay_gate_decision": "PENDING_REVIEW",
                    "confidence_band": "mid",
                },
            ]
        ),
    )
    (newer_run / "audit.md").write_text("# replay drift markdown\n", encoding="utf-8")
    os.utime(older_summary, (1_700_000_000, 1_700_000_000))
    os.utime(newer_summary, (1_800_000_000, 1_800_000_000))

    run_root = run_processor_gate_threshold_review(
        drift_root=drift_root,
        drift_summary_path=None,
        out_dir=tmp_path / "out",
        run_id="gate_threshold_review_python",
        min_candidate_rows=20,
        drift_warn_threshold=0.25,
    )

    payload = json.loads((run_root / "summary.json").read_text(encoding="utf-8"))
    manual_review_rows = json.loads((run_root / "manual_review_rows.json").read_text(encoding="utf-8"))
    manual_review_markdown = (run_root / "manual_review.md").read_text(encoding="utf-8")
    manual_review_checklist = list(
        csv.DictReader((run_root / "manual_review_checklist.csv").read_text(encoding="utf-8").splitlines())
    )
    manual_review_seed = list(
        csv.DictReader((run_root / "manual_review_seed.csv").read_text(encoding="utf-8").splitlines())
    )
    manual_review_frontier = list(
        csv.DictReader((run_root / "manual_review_frontier.csv").read_text(encoding="utf-8").splitlines())
    )
    manual_review_frontier_notes = (run_root / "manual_review_frontier_notes.md").read_text(encoding="utf-8")
    manual_review_frontier_crosscheck = (run_root / "manual_review_frontier_crosscheck_packet.md").read_text(encoding="utf-8")
    manual_review_decision = (run_root / "manual_review_decision.md").read_text(encoding="utf-8")
    assert payload["run_id"] == "gate_threshold_review_python"
    assert payload["decision"]["latest_run_id"] == "processor_gate_replay_drift_new"
    assert payload["decision"]["recommended_action"] == "manual_gate_threshold_review"
    assert payload["decision"]["tuning_targets"] == [
        "mid_confidence_escalation",
        "manual_override_boundary",
    ]
    assert payload["manual_review_scope"]["threshold_relevant"]["count"] == 1
    assert payload["manual_review_scope"]["excluded"]["manual_override"]["count"] == 1
    assert payload["manual_review_scope"]["worksheet_summary"] == {
        "pending_count": 1,
        "review_bucket": "threshold_relevant",
        "primary_review_target": "mid_confidence_escalation_policy",
        "excluded_count": 1,
        "summary": "1 threshold-relevant row(s) are queued for mid-confidence escalation policy review; exclude 1 non-threshold row(s) from raw threshold changes.",
    }
    assert payload["manual_review_scope"]["prefill_summary"] == {
        "threshold_relevant_count": 1,
        "policy_only_review_count": 1,
        "boundary_review_count": 0,
        "manual_triage_count": 0,
        "priority_review_now_count": 0,
        "priority_review_first_count": 1,
        "priority_review_later_count": 0,
        "supports_mid_confidence_policy_review_count": 1,
        "supports_high_threshold_change_count": 0,
        "summary": "Default prefills: policy_only=1, boundary=0, triage=0. Priority: now=0, first=1, later=0.",
    }
    assert payload["manual_review_basis"] == {
        "preliminary_call": "mid_confidence_policy_only",
        "summary": "All 1 threshold-relevant row(s) are mid-confidence legacy approvals replaying to pending review; none support a high-threshold boundary change from this evidence alone.",
        "threshold_relevant_count": 1,
        "policy_edge_case_count": 0,
        "mid_confidence_policy_support_count": 1,
        "high_threshold_support_count": 0,
        "evidence_source_counts": {"unknown": 1},
        "historical_rewrite_hint_counts": {"none": 1},
        "exact_confidence_counts": {"unknown": 1},
        "decision_transition_counts": {"APPROVED->PENDING_REVIEW": 1},
        "probable_drift_cause_counts": {"legacy_mid_confidence_approval": 1},
        "sample_titles": [],
    }
    assert manual_review_rows["threshold_relevant"]["count"] == 1
    assert manual_review_rows["threshold_relevant"]["rows"][0]["paper_id"] == "paper-mid-1"
    assert manual_review_rows["excluded"]["manual_override"]["rows"][0]["paper_id"] == "paper-manual"
    assert "## Threshold Relevant (1)" in manual_review_markdown
    assert "paper-mid-1" in manual_review_markdown
    assert len(manual_review_checklist) == 1
    assert manual_review_checklist[0]["paper_id"] == "paper-mid-1"
    assert manual_review_checklist[0]["review_target"] == "mid_confidence_escalation_policy"
    assert manual_review_checklist[0]["default_reviewer_disposition"] == "policy_only_review"
    assert manual_review_checklist[0]["default_supports_mid_confidence_policy_review"] == "yes"
    assert manual_review_checklist[0]["default_supports_high_threshold_change"] == "no"
    assert manual_review_checklist[0]["default_review_priority"] == "review_first"
    assert "historical rewrite hint is missing" in manual_review_checklist[0]["default_review_priority_reason"]
    assert "Legacy mid-confidence approval replayed to pending review" in manual_review_checklist[0]["default_reviewer_note"]
    assert manual_review_checklist[0]["reviewer_disposition"] == ""
    assert "## Current Call" in manual_review_decision
    assert "Prefill Summary: Default prefills: policy_only=1, boundary=0, triage=0. Priority: now=0, first=1, later=0." in manual_review_decision
    assert "Threshold Change Status: blocked_policy_only" in manual_review_decision
    assert "Treat the current residual bucket as mid-confidence escalation policy debt" in manual_review_decision
    assert len(manual_review_seed) == 1
    assert manual_review_seed[0]["paper_id"] == "paper-mid-1"
    assert manual_review_seed[0]["reviewer_disposition"] == "policy_only_review"
    assert manual_review_seed[0]["supports_mid_confidence_policy_review"] == "yes"
    assert manual_review_seed[0]["supports_high_threshold_change"] == "no"
    assert manual_review_seed[0]["default_review_priority"] == "review_first"
    assert "Legacy mid-confidence approval replayed to pending review" in manual_review_seed[0]["reviewer_notes"]
    assert len(manual_review_frontier) == 1
    assert manual_review_frontier[0]["paper_id"] == "paper-mid-1"
    assert manual_review_frontier[0]["reviewer_disposition"] == "policy_only_review"
    assert manual_review_frontier[0]["default_review_priority"] == "review_first"
    assert "Frontier Rows: 1" in manual_review_frontier_notes
    assert "Current frontier rows are front-loaded because corroborating historical rewrite hints are missing" in manual_review_frontier_notes
    assert "### paper-mid-1" in manual_review_frontier_notes
    assert "Default Priority: review_first" in manual_review_frontier_notes
    assert "Historical Rewrite Hint: none" in manual_review_frontier_notes
    assert "Local Precheck: policy_only_supported=1, boundary_signal_present=0, manual_triage_needed=0" in manual_review_frontier_notes
    assert "Local Precheck: policy_only_supported" in manual_review_frontier_notes
    assert "## Instructions For Independent Reviewer" in manual_review_frontier_crosscheck
    assert "Do not assume missing history implies a threshold miss." in manual_review_frontier_crosscheck
    assert "Current Codex Default: policy_only_review" in manual_review_frontier_crosscheck
    assert "Suggested Response Template" in manual_review_frontier_crosscheck


def test_processor_gate_threshold_review_cli_writes_summary(tmp_path: Path) -> None:
    drift_root = tmp_path / "processor_gate_replay_drift"
    summary_path = drift_root / "processor_gate_replay_drift_new" / "summary.json"
    _write_json(
        summary_path,
        _drift_summary(
            run_id="processor_gate_replay_drift_new",
            high_threshold=0.9,
            low_threshold=0.7,
            candidate_count=54,
            promotable_count=28,
            drift_count=26,
            drift_rate=0.481481,
            decision_transition_counts={"APPROVED->PENDING_REVIEW": 23},
            probable_drift_cause_counts={"legacy_mid_confidence_approval": 21},
            gate_reason_category_counts={"none": 22},
            confidence_band_counts={"mid": 25},
        ),
    )
    _write_json(
        summary_path.with_name("details.json"),
        _drift_details(
            documents=[
                {
                    "paper_id": "paper-mid-1",
                    "eligible_for_apply": False,
                    "probable_drift_cause": "legacy_mid_confidence_approval",
                    "current_gate_decision": "APPROVED",
                    "replay_gate_decision": "PENDING_REVIEW",
                    "confidence_band": "mid",
                },
                {
                    "paper_id": "paper-indexed",
                    "eligible_for_apply": False,
                    "probable_drift_cause": "legacy_indexed_pending_review",
                    "current_gate_decision": "PENDING_REVIEW",
                    "replay_gate_decision": "PENDING_REVIEW",
                    "confidence_band": "mid",
                },
            ]
        ),
    )
    summary_path.with_name("audit.md").write_text("# replay drift markdown\n", encoding="utf-8")
    summary_path.with_name("threshold_replay.json").write_text(
        json.dumps(
            {
                "threshold_replay_mode": "threshold_change_proposal_replay",
                "high_threshold": 0.85,
                "low_threshold": 0.7,
                "reviewed_high_threshold": 0.85,
                "proposal_run_id": "gate_threshold_review_ready",
                "threshold_review_command": (
                    "python3 scripts/eval/recommend_processor_gate_threshold_review.py "
                    "--drift-summary summary.json --run-id validation__threshold_review"
                ),
            }
        ),
        encoding="utf-8",
    )
    summary_path.with_name("threshold_replay.md").write_text(
        "# threshold replay context\n",
        encoding="utf-8",
    )

    script = Path(__file__).resolve().parents[1] / "scripts" / "eval" / "recommend_processor_gate_threshold_review.py"
    completed = subprocess.run(
        [
            sys.executable,
            str(script),
            "--drift-root",
            str(drift_root),
            "--out-dir",
            str(tmp_path / "out"),
            "--run-id",
            "gate_threshold_review_cli",
        ],
        cwd=Path(__file__).resolve().parents[1],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    emitted = json.loads(completed.stdout)
    normalized_stderr = " ".join(completed.stderr.split())
    payload = json.loads(((tmp_path / "out") / "gate_threshold_review_cli" / "summary.json").read_text(encoding="utf-8"))
    audit_markdown = ((tmp_path / "out") / "gate_threshold_review_cli" / "audit.md").read_text(encoding="utf-8")
    assert emitted["run_root"] == str((tmp_path / "out") / "gate_threshold_review_cli")
    assert emitted["summary_path"] == str((tmp_path / "out") / "gate_threshold_review_cli" / "summary.json")
    assert emitted["markdown_path"] == str((tmp_path / "out") / "gate_threshold_review_cli" / "audit.md")
    assert emitted["manual_review_rows_path"] == str((tmp_path / "out") / "gate_threshold_review_cli" / "manual_review_rows.json")
    assert emitted["manual_review_markdown_path"] == str((tmp_path / "out") / "gate_threshold_review_cli" / "manual_review.md")
    assert emitted["manual_review_checklist_path"] == str((tmp_path / "out") / "gate_threshold_review_cli" / "manual_review_checklist.csv")
    assert emitted["manual_review_seed_path"] == str((tmp_path / "out") / "gate_threshold_review_cli" / "manual_review_seed.csv")
    assert emitted["manual_review_frontier_path"] == str((tmp_path / "out") / "gate_threshold_review_cli" / "manual_review_frontier.csv")
    assert emitted["manual_review_frontier_notes_path"] == str((tmp_path / "out") / "gate_threshold_review_cli" / "manual_review_frontier_notes.md")
    assert emitted["manual_review_frontier_crosscheck_packet_path"] == str((tmp_path / "out") / "gate_threshold_review_cli" / "manual_review_frontier_crosscheck_packet.md")
    assert emitted["manual_review_basis_markdown_path"] == str((tmp_path / "out") / "gate_threshold_review_cli" / "manual_review_basis.md")
    assert emitted["manual_review_decision_markdown_path"] == str((tmp_path / "out") / "gate_threshold_review_cli" / "manual_review_decision.md")
    assert "show-processor-gate-threshold-review" in emitted["viewer_command"]
    assert "[recommend_processor_gate_threshold_review]" in completed.stderr
    assert "review_ready=True" in normalized_stderr
    assert "action=manual_gate_threshold_review" in normalized_stderr
    assert "latest_run_status=warn" in normalized_stderr
    assert "threshold_change=blocked_policy_only" in normalized_stderr
    assert "candidate_count=54" in normalized_stderr
    assert "drift_rate=0.4815" in normalized_stderr
    assert "latest_run=processor_gate_replay_drift_new" in normalized_stderr
    assert ((tmp_path / "out") / "gate_threshold_review_cli" / "audit.md").exists()
    assert ((tmp_path / "out") / "gate_threshold_review_cli" / "manual_review_basis.md").exists()
    assert ((tmp_path / "out") / "gate_threshold_review_cli" / "manual_review_decision.md").exists()
    assert "Manual Review Rows:" in audit_markdown
    assert "manual_review_rows.json" in audit_markdown
    assert "Manual Review Markdown:" in audit_markdown
    assert "manual_review.md" in audit_markdown
    assert "Manual Review Checklist:" in audit_markdown
    assert "manual_review_checklist.csv" in audit_markdown
    assert "Manual Review Seed:" in audit_markdown
    assert "manual_review_seed.csv" in audit_markdown
    assert "Manual Review Frontier:" in audit_markdown
    assert "manual_review_frontier.csv" in audit_markdown
    assert "Manual Review Frontier Notes:" in audit_markdown
    assert "manual_review_frontier_notes.md" in audit_markdown
    assert "Manual Review Frontier Crosscheck Packet:" in audit_markdown
    assert "manual_review_frontier_crosscheck_packet.md" in audit_markdown
    assert "Manual Review Basis:" in audit_markdown
    assert "manual_review_basis.md" in audit_markdown
    assert "Manual Review Decision:" in audit_markdown
    assert "manual_review_decision.md" in audit_markdown
    assert "Replay Drift Summary:" in audit_markdown
    assert str(summary_path) in audit_markdown
    assert "Replay Drift Details:" in audit_markdown
    assert str(summary_path.with_name("details.json")) in audit_markdown
    assert "Replay Drift Markdown:" in audit_markdown
    assert str(summary_path.with_name("audit.md")) in audit_markdown
    assert "Threshold Replay Context:" in audit_markdown
    assert str(summary_path.with_name("threshold_replay.json")) in audit_markdown
    assert "Threshold Replay Context Markdown:" in audit_markdown
    assert str(summary_path.with_name("threshold_replay.md")) in audit_markdown
    assert (
        "Threshold Replay: mode=threshold_change_proposal_replay, high=0.85, low=0.70, "
        "reviewed_high=0.85, proposal=gate_threshold_review_ready"
    ) in audit_markdown
    assert "Threshold Replay Review Command:" in audit_markdown
    assert "recommend_processor_gate_threshold_review.py" in audit_markdown
    assert "## Manual Review Scope" in audit_markdown
    assert "Sample IDs: paper-mid-1" in audit_markdown
    assert "Sample IDs: paper-indexed" in audit_markdown
    assert "Worksheet Target: mid_confidence_escalation_policy" in audit_markdown
    assert "Worksheet: 1 threshold-relevant row(s) are queued for mid-confidence escalation policy review; exclude 1 non-threshold row(s) from raw threshold changes." in audit_markdown
    assert "Basis Call: mid_confidence_policy_only" in audit_markdown
    assert "Basis Summary: All 1 threshold-relevant row(s) are mid-confidence legacy approvals replaying to pending review; none support a high-threshold boundary change from this evidence alone." in audit_markdown
    assert payload["decision"]["recommended_action"] == "manual_gate_threshold_review"
    assert payload["decision"]["latest_run_id"] == "processor_gate_replay_drift_new"
    assert payload["decision"]["tuning_targets"] == [
        "mid_confidence_escalation",
        "indexed_pending_policy",
    ]
    assert payload["manual_review_scope"]["threshold_relevant"]["count"] == 1
    assert payload["manual_review_scope"]["excluded"]["indexed_pending"]["count"] == 1
    assert payload["manual_review_scope"]["worksheet_summary"] == {
        "pending_count": 1,
        "review_bucket": "threshold_relevant",
        "primary_review_target": "mid_confidence_escalation_policy",
        "excluded_count": 1,
        "summary": "1 threshold-relevant row(s) are queued for mid-confidence escalation policy review; exclude 1 non-threshold row(s) from raw threshold changes.",
    }
    assert payload["manual_review_basis"] == {
        "preliminary_call": "mid_confidence_policy_only",
        "summary": "All 1 threshold-relevant row(s) are mid-confidence legacy approvals replaying to pending review; none support a high-threshold boundary change from this evidence alone.",
        "threshold_relevant_count": 1,
        "policy_edge_case_count": 0,
        "mid_confidence_policy_support_count": 1,
        "high_threshold_support_count": 0,
        "evidence_source_counts": {"unknown": 1},
        "historical_rewrite_hint_counts": {"none": 1},
        "exact_confidence_counts": {"unknown": 1},
        "decision_transition_counts": {"APPROVED->PENDING_REVIEW": 1},
        "probable_drift_cause_counts": {"legacy_mid_confidence_approval": 1},
        "sample_titles": [],
    }


def test_manual_review_checklist_defaults_high_threshold_like_rows() -> None:
    checklist_csv = render_processor_gate_threshold_manual_review_checklist_csv(
        {
            "threshold_relevant": {
                "rows": [
                    {
                        "paper_id": "paper-high-1",
                        "title": "High-threshold boundary candidate",
                        "current_gate_decision": "PENDING_REVIEW",
                        "replay_gate_decision": "APPROVED",
                        "confidence_band": "high",
                        "probable_drift_cause": "legacy_high_confidence_pending",
                    }
                ]
            }
        }
    )

    rows = list(csv.DictReader(checklist_csv.splitlines()))

    assert len(rows) == 1
    assert rows[0]["paper_id"] == "paper-high-1"
    assert rows[0]["default_reviewer_disposition"] == "boundary_review"
    assert rows[0]["default_supports_mid_confidence_policy_review"] == "no"
    assert rows[0]["default_supports_high_threshold_change"] == "yes"
    assert rows[0]["default_review_priority"] == "review_now"
    assert "High-confidence or high-threshold-like replay drift" in rows[0]["default_reviewer_note"]


def test_run_processor_gate_threshold_review_emits_threshold_change_proposal_when_ready(
    tmp_path: Path,
) -> None:
    drift_root = tmp_path / "processor_gate_replay_drift"
    latest_run = drift_root / "processor_gate_replay_drift_candidate_boundary"
    latest_run.mkdir(parents=True, exist_ok=True)
    _write_json(
        latest_run / "summary.json",
        _drift_summary(
            run_id="processor_gate_replay_drift_candidate_boundary",
            high_threshold=0.9,
            low_threshold=0.7,
            candidate_count=24,
            promotable_count=22,
            drift_count=6,
            drift_rate=0.25,
            decision_transition_counts={"PENDING_REVIEW->APPROVED": 1},
            probable_drift_cause_counts={"legacy_mid_confidence_approval": 1},
            gate_reason_category_counts={"confidence_threshold": 1},
            confidence_band_counts={"high": 1},
        ),
    )
    _write_json(
        latest_run / "details.json",
        _drift_details(
            documents=[
                {
                    "paper_id": "paper-boundary-1",
                    "title": "Boundary candidate",
                    "eligible_for_apply": False,
                    "probable_drift_cause": "legacy_mid_confidence_approval",
                    "current_gate_decision": "PENDING_REVIEW",
                    "replay_gate_decision": "APPROVED",
                    "confidence_band": "high",
                    "confidence": 0.93,
                    "evidence_source": "evidence_span",
                }
            ]
        ),
    )

    run_root = run_processor_gate_threshold_review(
        drift_root=drift_root,
        drift_summary_path=None,
        out_dir=tmp_path / "out",
        run_id="gate_threshold_review_ready",
        min_candidate_rows=20,
        drift_warn_threshold=0.2,
    )

    payload = json.loads((run_root / "summary.json").read_text(encoding="utf-8"))
    proposal = json.loads(
        (run_root / "threshold_change_proposal.json").read_text(encoding="utf-8")
    )
    proposal_markdown = (run_root / "threshold_change_proposal.md").read_text(
        encoding="utf-8"
    )
    audit_markdown = (run_root / "audit.md").read_text(encoding="utf-8")

    assert payload["decision"]["threshold_change_ready"] is True
    assert payload["decision"]["threshold_change_status"] == "candidate_boundary_review"
    assert payload["decision"]["threshold_change_next_step"] == "review_high_threshold_boundary"
    assert proposal["proposal_ready"] is True
    assert proposal["proposal_mode"] == "manual_apply_candidate"
    assert proposal["target_field"] == "confidence_thresholds.high"
    assert proposal["current_thresholds"] == {"high": 0.9, "low": 0.7}
    assert proposal["proposed_thresholds"] == {"high": None, "low": 0.7}
    assert proposal["reviewed_value_placeholder"] == "REVIEWED_HIGH_THRESHOLD"
    assert proposal["support_count"] == 1
    assert proposal["support_sample_ids"] == ["paper-boundary-1"]
    assert proposal["support_rows"][0]["paper_id"] == "paper-boundary-1"
    assert "<REVIEWED_HIGH_THRESHOLD>" in proposal["diff_template"]
    assert (
        proposal["validation_replay_run_id"]
        == "gate_threshold_review_ready__threshold_validation_replay"
    )
    validation_command = proposal["validation_replay_command_template"]
    assert "audit_processor_gate_replay_drift.py" in validation_command
    assert "--db-path storage/state.db" in validation_command
    assert "--threshold-change-proposal" in validation_command
    assert str((run_root / "threshold_change_proposal.json").resolve(strict=False)) in validation_command
    assert "--reviewed-high-threshold" in validation_command
    assert "<REVIEWED_HIGH_THRESHOLD>" in validation_command
    assert "gate_threshold_review_ready__threshold_validation_replay" in validation_command
    assert "Threshold Change Proposal:" in audit_markdown
    assert "threshold_change_proposal.json" in audit_markdown
    assert "threshold_change_proposal.md" in audit_markdown
    assert "## Validation Replay Command" in proposal_markdown
    assert "audit_processor_gate_replay_drift.py" in proposal_markdown
    assert "## Candidate Diff Template" in proposal_markdown
    assert "Boundary candidate" in proposal_markdown
    assert "confidence=0.93" in proposal_markdown


def test_manual_review_seed_prefills_reviewer_columns() -> None:
    seed_csv = render_processor_gate_threshold_manual_review_seed_csv(
        {
            "threshold_relevant": {
                "rows": [
                    {
                        "paper_id": "paper-mid-1",
                        "title": "Policy-only candidate",
                        "current_gate_decision": "APPROVED",
                        "replay_gate_decision": "PENDING_REVIEW",
                        "confidence_band": "mid",
                        "probable_drift_cause": "legacy_mid_confidence_approval",
                    }
                ]
            }
        }
    )

    rows = list(csv.DictReader(seed_csv.splitlines()))

    assert len(rows) == 1
    assert rows[0]["paper_id"] == "paper-mid-1"
    assert rows[0]["reviewer_disposition"] == "policy_only_review"
    assert rows[0]["supports_mid_confidence_policy_review"] == "yes"
    assert rows[0]["supports_high_threshold_change"] == "no"
    assert rows[0]["default_review_priority"] == "review_first"
    assert "Legacy mid-confidence approval replayed to pending review" in rows[0]["reviewer_notes"]


def test_manual_review_frontier_filters_review_now_and_first_rows() -> None:
    frontier_csv = render_processor_gate_threshold_manual_review_frontier_csv(
        {
            "threshold_relevant": {
                "rows": [
                    {
                        "paper_id": "paper-later",
                        "title": "Later policy-only row",
                        "current_gate_decision": "APPROVED",
                        "replay_gate_decision": "PENDING_REVIEW",
                        "confidence_band": "mid",
                        "probable_drift_cause": "legacy_mid_confidence_approval",
                        "historical_rewrite_hint": "post_feedback_precanonical_confidence_overwrite_candidate",
                    },
                    {
                        "paper_id": "paper-first",
                        "title": "First policy-only row",
                        "current_gate_decision": "APPROVED",
                        "replay_gate_decision": "PENDING_REVIEW",
                        "confidence_band": "mid",
                        "probable_drift_cause": "legacy_mid_confidence_approval",
                    },
                    {
                        "paper_id": "paper-now",
                        "title": "Boundary row",
                        "current_gate_decision": "PENDING_REVIEW",
                        "replay_gate_decision": "APPROVED",
                        "confidence_band": "high",
                        "probable_drift_cause": "legacy_high_confidence_pending",
                    },
                ]
            }
        }
    )

    rows = list(csv.DictReader(frontier_csv.splitlines()))

    assert [row["paper_id"] for row in rows] == ["paper-now", "paper-first"]
    assert rows[0]["default_review_priority"] == "review_now"
    assert rows[1]["default_review_priority"] == "review_first"


def test_manual_review_frontier_notes_explain_policy_only_priority() -> None:
    markdown = render_processor_gate_threshold_manual_review_frontier_notes_markdown(
        {
            "run_id": "gate_threshold_review_frontier_notes",
            "threshold_relevant": {
                "rows": [
                    {
                        "paper_id": "paper-policy-first",
                        "title": "Policy-only row",
                        "current_status": "INDEXED",
                        "replay_status": "PENDING_REVIEW",
                        "current_gate_decision": "APPROVED",
                        "replay_gate_decision": "PENDING_REVIEW",
                        "confidence": 0.8,
                        "confidence_band": "mid",
                        "probable_drift_cause": "legacy_mid_confidence_approval",
                        "precanonical_gate_reason": "Confidence 0.9",
                        "current_gate_reason": "Confidence 0.9",
                        "current_gate_reason_category": "confidence_threshold",
                        "evidence_source": "evidence_span",
                        "has_evidence_text": True,
                        "feedback_log_import_hint": "no_feedback_log_match",
                        "historical_path_hint": "explicit_confidence_gate_reason_present",
                        "historical_rewrite_hint": "",
                        "local_provenance_hint": "precanonical_explicit_gate_reason_preserved",
                    }
                ]
            },
        },
        review={
            "run_id": "gate_threshold_review_frontier_notes",
            "decision": {
                "threshold_change_status": "blocked_policy_only",
                "threshold_change_next_step": "review_mid_confidence_escalation_policy",
            },
            "manual_review_scope": {
                "prefill_summary": {
                    "summary": "Default prefills: policy_only=1, boundary=0, triage=0. Priority: now=0, first=1, later=0.",
                }
            },
            "manual_review_basis": {
                "preliminary_call": "mid_confidence_policy_only",
                "summary": "All 1 threshold-relevant row(s) are mid-confidence legacy approvals replaying to pending review; none support a high-threshold boundary change from this evidence alone.",
            },
        },
    )

    assert "Frontier Rows: 1" in markdown
    assert "Threshold Change Status: blocked_policy_only" in markdown
    assert "Current frontier rows are front-loaded because corroborating historical rewrite hints are missing" in markdown
    assert "### paper-policy-first" in markdown
    assert "Status: current=INDEXED, replay=PENDING_REVIEW" in markdown
    assert "Current Gate Reason: Confidence 0.9" in markdown
    assert "Feedback Log Import Hint: no_feedback_log_match" in markdown
    assert "Local Provenance Hint: precanonical_explicit_gate_reason_preserved" in markdown
    assert "Default Disposition: policy_only_review" in markdown
    assert "Local Precheck: policy_only_supported" in markdown


def test_manual_review_crosscheck_packet_includes_external_reviewer_prompt() -> None:
    markdown = render_processor_gate_threshold_manual_review_crosscheck_packet_markdown(
        {
            "run_id": "gate_threshold_review_crosscheck_packet",
            "threshold_relevant": {
                "rows": [
                    {
                        "paper_id": "paper-policy-first",
                        "title": "Policy-only row",
                        "current_status": "INDEXED",
                        "replay_status": "PENDING_REVIEW",
                        "current_gate_decision": "APPROVED",
                        "replay_gate_decision": "PENDING_REVIEW",
                        "confidence": 0.8,
                        "confidence_band": "mid",
                        "probable_drift_cause": "legacy_mid_confidence_approval",
                        "precanonical_gate_reason": "Confidence 0.9",
                        "current_gate_reason": "Confidence 0.9",
                        "current_gate_reason_category": "confidence_threshold",
                        "evidence_source": "evidence_span",
                        "has_evidence_text": True,
                        "feedback_log_import_hint": "no_feedback_log_match",
                        "historical_path_hint": "explicit_confidence_gate_reason_present",
                        "historical_rewrite_hint": "",
                        "local_provenance_hint": "precanonical_explicit_gate_reason_preserved",
                    }
                ]
            },
        },
        review={
            "run_id": "gate_threshold_review_crosscheck_packet",
            "decision": {
                "threshold_change_status": "blocked_policy_only",
                "threshold_change_next_step": "review_mid_confidence_escalation_policy",
            },
            "manual_review_basis": {
                "summary": "All 1 threshold-relevant row(s) are mid-confidence legacy approvals replaying to pending review; none support a high-threshold boundary change from this evidence alone.",
            },
        },
    )

    assert "## Goal" in markdown
    assert "## Instructions For Independent Reviewer" in markdown
    assert "## Questions" in markdown
    assert "Current Codex Default: policy_only_review" in markdown
    assert "Local Precheck: policy_only_supported" in markdown
    assert "High-threshold change justified now? yes/no" in markdown


def test_processor_gate_threshold_review_help_mentions_viewer(tmp_path: Path) -> None:
    script = Path(__file__).resolve().parents[1] / "scripts" / "eval" / "recommend_processor_gate_threshold_review.py"
    completed = subprocess.run(
        [sys.executable, str(script), "--help"],
        cwd=Path(__file__).resolve().parents[1],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    normalized_help = " ".join(completed.stdout.split())
    assert "show-processor-gate-" in normalized_help
    assert "threshold-review" in normalized_help
    assert "Writes summary.json into the run directory" in normalized_help


def test_processor_gate_threshold_review_helpers_select_latest_and_build_viewer(tmp_path: Path) -> None:
    review_root = tmp_path / "processor_gate_threshold_review"
    older_run = review_root / "older_run"
    newer_run = review_root / "newer_run"
    _write_json(older_run / "summary.json", {"run_id": "older_run"})
    _write_json(newer_run / "summary.json", {"run_id": "newer_run"})
    os.utime(older_run / "summary.json", (1_700_000_000, 1_700_000_000))
    os.utime(newer_run / "summary.json", (1_800_000_000, 1_800_000_000))

    latest_run = latest_processor_gate_threshold_review_run(review_root)

    assert latest_run == newer_run
    assert load_processor_gate_threshold_review_summary(newer_run)["run_id"] == "newer_run"

    viewer_command = build_processor_gate_threshold_review_viewer_command(
        newer_run,
        repo_root=tmp_path,
        python_executable=Path(sys.executable),
    )
    assert "show-processor-gate-threshold-review" in viewer_command
    assert str(newer_run) in viewer_command


def test_processor_gate_threshold_review_drift_artifact_helper_surfaces_sibling_markdown(
    tmp_path: Path,
) -> None:
    drift_root = tmp_path / "processor_gate_replay_drift" / "processor_gate_replay_drift_latest"
    drift_root.mkdir(parents=True, exist_ok=True)
    (drift_root / "summary.json").write_text("{}", encoding="utf-8")
    (drift_root / "details.json").write_text("{}", encoding="utf-8")
    (drift_root / "audit.md").write_text("# replay drift markdown\n", encoding="utf-8")
    (drift_root / "threshold_replay.json").write_text(
        json.dumps(
            {
                "threshold_replay_mode": "threshold_change_proposal_replay",
                "high_threshold": 0.85,
                "low_threshold": 0.7,
                "reviewed_high_threshold": 0.85,
                "proposal_run_id": "gate_threshold_review_ready",
                "threshold_review_command": (
                    "python3 scripts/eval/recommend_processor_gate_threshold_review.py "
                    "--drift-summary summary.json --run-id validation__threshold_review"
                ),
            }
        ),
        encoding="utf-8",
    )
    (drift_root / "threshold_replay.md").write_text(
        "# threshold replay context\n",
        encoding="utf-8",
    )

    artifacts = resolve_processor_gate_threshold_review_drift_artifacts(
        {
            "inputs": {
                "drift_summary_path": str(drift_root / "summary.json"),
                "drift_details_path": str(drift_root / "details.json"),
            }
        }
    )

    assert artifacts == {
        "drift_summary_path": str(drift_root / "summary.json"),
        "drift_details_path": str(drift_root / "details.json"),
        "drift_markdown_path": str(drift_root / "audit.md"),
        "threshold_replay_path": str(drift_root / "threshold_replay.json"),
        "threshold_replay_markdown_path": str(drift_root / "threshold_replay.md"),
        "threshold_replay_text": (
            "mode=threshold_change_proposal_replay, high=0.85, low=0.70, "
            "reviewed_high=0.85, proposal=gate_threshold_review_ready"
        ),
        "threshold_replay_review_command": (
            "python3 scripts/eval/recommend_processor_gate_threshold_review.py "
            "--drift-summary summary.json --run-id validation__threshold_review"
        ),
        "threshold_replay_mode": "threshold_change_proposal_replay",
        "threshold_replay_high_threshold": 0.85,
        "threshold_replay_low_threshold": 0.7,
        "threshold_replay_reviewed_high_threshold": 0.85,
        "threshold_replay_proposal_run_id": "gate_threshold_review_ready",
        "drift_summary_available": True,
        "drift_details_available": True,
        "drift_markdown_available": True,
        "threshold_replay_available": True,
        "threshold_replay_markdown_available": True,
        "threshold_change_validation_replay_run_id": None,
        "threshold_change_validation_replay_available": False,
        "threshold_change_validation_replay_matches_proposal": False,
        "threshold_change_validation_replay_needs_rerun": False,
        "threshold_change_validation_replay_status": "not_applicable",
        "threshold_change_manual_decision_ready": False,
        "threshold_change_manual_decision_status": "not_applicable",
        "threshold_change_manual_decision_blocker": None,
    }

    proposal_path = tmp_path / "threshold_change_proposal.json"
    proposal_path.write_text(
        json.dumps(
            {
                "run_id": "gate_threshold_review_ready",
                "validation_replay_run_id": drift_root.name,
            }
        ),
        encoding="utf-8",
    )

    validated_artifacts = resolve_processor_gate_threshold_review_drift_artifacts(
        {
            "inputs": {
                "drift_summary_path": str(drift_root / "summary.json"),
                "drift_details_path": str(drift_root / "details.json"),
            }
        },
        threshold_change_proposal_path=proposal_path,
    )
    assert validated_artifacts["threshold_change_validation_replay_run_id"] == drift_root.name
    assert validated_artifacts["threshold_change_validation_replay_available"] is True
    assert validated_artifacts["threshold_change_validation_replay_matches_proposal"] is True
    assert validated_artifacts["threshold_change_validation_replay_needs_rerun"] is False
    assert validated_artifacts["threshold_change_validation_replay_status"] == "matched"
    assert validated_artifacts["threshold_change_manual_decision_ready"] is True
    assert validated_artifacts["threshold_change_manual_decision_status"] == "ready"
    assert validated_artifacts["threshold_change_manual_decision_blocker"] is None
