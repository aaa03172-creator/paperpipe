import json
from pathlib import Path

from typer.testing import CliRunner

import src.cli as cli


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def test_show_processor_gate_threshold_review_renders_summary(tmp_path: Path) -> None:
    runner = CliRunner()
    run_root = tmp_path / "processor_gate_threshold_review_run"
    drift_root = tmp_path / "drift"
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
    _write_json(
        run_root / "summary.json",
        {
            "schema_version": "processor_gate_threshold_review.v1",
            "generated_at": "2026-04-21T00:00:00Z",
            "run_id": "gate_threshold_review_test",
            "inputs": {
                "drift_summary_path": str(drift_root / "summary.json"),
                "drift_details_path": str(drift_root / "details.json"),
                "high_threshold": 0.9,
                "low_threshold": 0.7,
                "min_candidate_rows": 20,
                "drift_warn_threshold": 0.25,
            },
            "decision": {
                "recommended_action": "manual_gate_threshold_review",
                "review_ready": True,
                "decision_reason": "latest drift run shows 26/54 drift row(s) (48.1%), above the 25% warning threshold; threshold-relevant drift is concentrated in historical mid-confidence approvals, so review the mid-confidence escalation policy before lowering the high threshold",
                "next_step": "review_gate_thresholds_and_mid_confidence_policy",
                "focus_areas": [
                    "high_threshold",
                    "mid_confidence_escalation",
                    "high_confidence_pending_policy",
                    "indexed_pending_policy",
                    "manual_override_boundary",
                ],
                "latest_run_id": "processor_gate_replay_drift_preapply_20260421_r11",
                "latest_run_status": "warn",
                "tuning_targets": [
                    "mid_confidence_escalation",
                    "manual_override_boundary",
                    "indexed_pending_policy",
                ],
                "tuning_actions": [
                    {
                        "target": "mid_confidence_escalation",
                        "action": "review_mid_confidence_escalation_policy",
                    },
                    {
                        "target": "manual_override_boundary",
                        "action": "exclude_manual_override_rows_from_threshold_tuning",
                    },
                    {
                        "target": "indexed_pending_policy",
                        "action": "exclude_indexed_pending_rows_from_threshold_tuning",
                    },
                ],
                "action_plan": [
                    {
                        "order": 1,
                        "action": "review_gate_thresholds_and_mid_confidence_policy",
                    },
                    {
                        "order": 2,
                        "action": "review_mid_confidence_escalation_policy",
                        "target": "mid_confidence_escalation",
                    },
                    {
                        "order": 3,
                        "action": "exclude_manual_override_rows_from_threshold_tuning",
                        "target": "manual_override_boundary",
                    },
                ],
                "tuning_recommendations": [
                    "Current threshold-relevant drift is entirely mid-confidence approval debt, so review the mid-confidence escalation policy before lowering the high threshold.",
                    "Keep the current high threshold unchanged unless manual review of the threshold-relevant bucket shows true high-threshold misses.",
                ],
                "threshold_change_ready": False,
                "threshold_change_status": "blocked_policy_only",
                "threshold_change_next_step": "review_mid_confidence_escalation_policy",
                "threshold_change_blocker": "All 21 threshold-relevant row(s) are mid-confidence legacy approvals replaying to pending review; none support a high-threshold boundary change from this evidence alone.",
            },
            "signal_summary": {
                "candidate_count": 54,
                "promotable_count": 28,
                "drift_count": 26,
                "drift_rate": 0.481481,
                "decision_transition_counts": {
                    "APPROVED->PENDING_REVIEW": 23,
                    "PENDING_REVIEW->APPROVED": 1,
                },
                "probable_drift_cause_counts": {
                    "legacy_mid_confidence_approval": 21,
                    "legacy_high_confidence_pending": 1,
                },
                "gate_reason_category_counts": {
                    "none": 22,
                    "confidence_threshold": 2,
                },
                "confidence_band_counts": {
                    "mid": 25,
                    "high": 1,
                },
            },
            "manual_review_scope": {
                "threshold_relevant": {
                    "count": 21,
                    "paper_ids": [
                        "zotero:bialystokBilingualismConsequencesMind2012",
                        "zotero:chandraGutMicrobiomeAlzheimers2023",
                        "zotero:coricTargetingProdromalAlzheimer2015",
                        "zotero:craftSafetyEfficacyFeasibility2020",
                    ],
                },
                "policy_edge_cases": {
                    "count": 0,
                    "paper_ids": [],
                },
                "excluded": {
                    "manual_override": {
                        "count": 2,
                        "paper_ids": [
                            "zotero:duboisAmnesticMCIProdromal2004",
                            "zotero:grandeBloodbasedBiomarkersAlzheimers2025",
                        ],
                    },
                    "indexed_pending": {
                        "count": 2,
                        "paper_ids": [
                            "zotero:kowalskiBrainGutMicrobiotaAxisAlzheimers2019",
                            "zotero:sochockaGutMicrobiomeAlterations2019",
                        ],
                    },
                    "fixture_or_test": {
                        "count": 1,
                        "paper_ids": ["phase0_test"],
                    },
                    "other": {
                        "count": 0,
                        "paper_ids": [],
                    },
                },
                "focus_recommendation": "Focus threshold tuning on 21 threshold-relevant row(s) first; exclude 5 manual-override, indexed-pending, or fixture/test row(s) from raw threshold changes.",
                "worksheet_summary": {
                    "pending_count": 21,
                    "review_bucket": "threshold_relevant",
                    "primary_review_target": "mid_confidence_escalation_policy",
                    "excluded_count": 5,
                    "summary": "21 threshold-relevant row(s) are queued for mid-confidence escalation policy review; exclude 5 non-threshold row(s) from raw threshold changes.",
                },
                "prefill_summary": {
                    "threshold_relevant_count": 21,
                    "policy_only_review_count": 21,
                    "boundary_review_count": 0,
                    "manual_triage_count": 0,
                    "priority_review_now_count": 0,
                    "priority_review_first_count": 2,
                    "priority_review_later_count": 19,
                    "supports_mid_confidence_policy_review_count": 21,
                    "supports_high_threshold_change_count": 0,
                    "summary": "Default prefills: policy_only=21, boundary=0, triage=0. Priority: now=0, first=2, later=19.",
                },
            },
            "manual_review_basis": {
                "preliminary_call": "mid_confidence_policy_only",
                "summary": "All 21 threshold-relevant row(s) are mid-confidence legacy approvals replaying to pending review; none support a high-threshold boundary change from this evidence alone.",
                "threshold_relevant_count": 21,
                "policy_edge_case_count": 0,
                "mid_confidence_policy_support_count": 21,
                "high_threshold_support_count": 0,
                "evidence_source_counts": {"evidence_span": 21},
                "historical_rewrite_hint_counts": {
                    "post_feedback_precanonical_confidence_overwrite_candidate": 19,
                    "none": 2,
                },
                "exact_confidence_counts": {"0.8": 21},
                "decision_transition_counts": {"APPROVED->PENDING_REVIEW": 21},
                "probable_drift_cause_counts": {"legacy_mid_confidence_approval": 21},
                "sample_titles": [
                    "Bilingualism: consequences for mind and brain",
                    "The gut microbiome in Alzheimer’s disease: what we know and what remains to be explored",
                ],
            },
            "recommendations": [
                "Review the high threshold and mid-confidence escalation policy first; 21 drift row(s) are historical mid-confidence approvals replaying to pending review.",
                "Latest drift is above the 25% review threshold and is dominated by APPROVED->PENDING_REVIEW transitions (23).",
                "Focus threshold tuning on 21 threshold-relevant row(s) first; exclude 5 manual-override, indexed-pending, or fixture/test row(s) from raw threshold changes.",
            ],
        },
    )
    (run_root / "audit.md").write_text("# threshold review markdown\n", encoding="utf-8")
    (run_root / "manual_review_rows.json").write_text("{}", encoding="utf-8")
    (run_root / "manual_review.md").write_text("# manual review\n", encoding="utf-8")
    (run_root / "manual_review_checklist.csv").write_text("paper_id\npaper-1\n", encoding="utf-8")
    (run_root / "manual_review_seed.csv").write_text("paper_id\npaper-1\n", encoding="utf-8")
    (run_root / "manual_review_frontier.csv").write_text("paper_id\npaper-1\n", encoding="utf-8")
    (run_root / "manual_review_frontier_notes.md").write_text("# frontier notes\n", encoding="utf-8")
    (run_root / "manual_review_frontier_crosscheck_packet.md").write_text("# frontier crosscheck packet\n", encoding="utf-8")
    (run_root / "manual_review_frontier_claude_crosscheck.md").write_text("# claude crosscheck\n", encoding="utf-8")
    (run_root / "manual_review_frontier_claude_crosscheck.json").write_text("{}\n", encoding="utf-8")
    (run_root / "manual_review_basis.md").write_text("# manual review basis\n", encoding="utf-8")
    (run_root / "manual_review_decision.md").write_text("# manual review decision\n", encoding="utf-8")
    _write_json(
        run_root / "manual_review_outcome.json",
        {
            "schema_version": "processor_gate_manual_review_outcome.v1",
            "generated_at": "2026-04-22T00:00:00Z",
            "run_id": "gate_threshold_review_test",
            "worksheet_name": "manual_review_frontier.csv",
            "total_row_count": 2,
            "completed_row_count": 2,
            "supports_high_threshold_change_count": 0,
            "default_divergence_count": 0,
            "status": "policy_only_confirmed",
            "summary": "All 2 reviewed row(s) support policy-only treatment and none support a high-threshold change.",
        },
    )
    (run_root / "manual_review_outcome.md").write_text("# manual review outcome\n", encoding="utf-8")
    _write_json(
        run_root / "threshold_change_decision.json",
        {
            "schema_version": "processor_gate_threshold_change_decision.v1",
            "generated_at": "2026-04-22T00:00:00Z",
            "run_id": "gate_threshold_review_test",
            "final_status": "no_threshold_change_supported",
            "recommended_action": "keep_current_high_threshold",
            "threshold_change_ready": False,
            "threshold_change_next_step": "continue_mid_confidence_escalation_policy_review",
            "summary": "Manual review confirmed 2/2 threshold-relevant row(s) as policy-only; none support a high-threshold change.",
            "manual_review_counts": {
                "total": 2,
                "completed": 2,
                "supports_mid_confidence_policy_review": 2,
                "supports_high_threshold_change": 0,
                "default_divergence": 0,
            },
        },
    )
    (run_root / "threshold_change_decision.md").write_text("# threshold change decision\n", encoding="utf-8")
    _write_json(
        run_root / "mid_confidence_policy_decision.json",
        {
            "schema_version": "processor_gate_mid_confidence_policy_decision.v1",
            "generated_at": "2026-04-22T00:00:00Z",
            "run_id": "gate_threshold_review_test",
            "final_status": "mid_confidence_escalation_policy_confirmed",
            "recommended_action": "keep_mid_confidence_pending_review_policy",
            "policy_decision_ready": True,
            "runtime_change_ready": False,
            "next_step": "treat_legacy_mid_confidence_approvals_as_policy_debt",
            "summary": "Manual review confirmed 2/2 reviewed row(s) as mid-confidence policy debt; keep the current pending-review behavior for mid-confidence rows.",
            "manual_review_counts": {
                "total": 2,
                "completed": 2,
                "supports_mid_confidence_policy_review": 2,
                "supports_high_threshold_change": 0,
            },
        },
    )
    (run_root / "mid_confidence_policy_decision.md").write_text("# mid-confidence policy decision\n", encoding="utf-8")
    _write_json(
        run_root / "mid_confidence_policy_debt_reconciliation.json",
        {
            "schema_version": "processor_gate_mid_confidence_policy_debt_reconciliation.v1",
            "generated_at": "2026-04-22T00:00:00Z",
            "run_id": "gate_threshold_review_test",
            "final_status": "legacy_policy_debt_confirmed",
            "recommended_action": "keep_historical_approvals_as_legacy_policy_debt",
            "reconciliation_ready": True,
            "runtime_change_ready": False,
            "historical_mutation_ready": False,
            "next_step": "monitor_future_mid_confidence_pending_review",
            "summary": "Manual review confirmed 2/2 historical mid-confidence approval row(s) as policy debt. Keep the current pending-review behavior for future mid-confidence rows and do not mass-rewrite historical approvals from this artifact.",
            "manual_review_counts": {
                "total": 2,
                "completed": 2,
                "supports_mid_confidence_policy_review": 2,
                "supports_high_threshold_change": 0,
            },
        },
    )
    (run_root / "mid_confidence_policy_debt_reconciliation.md").write_text(
        "# policy debt reconciliation\n",
        encoding="utf-8",
    )
    _write_json(
        run_root / "manual_override_policy_decision.json",
        {
            "schema_version": "processor_gate_manual_override_policy_decision.v1",
            "generated_at": "2026-04-22T00:00:00Z",
            "run_id": "gate_threshold_review_test",
            "final_status": "manual_override_exception_policy_confirmed",
            "recommended_action": "exclude_manual_override_rows_from_threshold_tuning",
            "policy_decision_ready": True,
            "threshold_change_ready": False,
            "runtime_change_ready": False,
            "historical_mutation_ready": False,
            "manual_override_count": 2,
            "indexed_pending_count": 2,
            "next_step": "review_indexed_pending_status_contract",
            "summary": "2 manual or human override row(s) remain explicit policy exceptions and should stay outside raw threshold tuning.",
        },
    )
    (run_root / "manual_override_policy_decision.md").write_text(
        "# manual override policy decision\n",
        encoding="utf-8",
    )
    _write_json(
        run_root / "indexed_pending_policy_decision.json",
        {
            "schema_version": "processor_gate_indexed_pending_policy_decision.v1",
            "generated_at": "2026-04-22T00:00:00Z",
            "run_id": "gate_threshold_review_test",
            "final_status": "indexed_pending_status_contract_confirmed",
            "recommended_action": "keep_indexed_pending_rows_out_of_threshold_tuning",
            "policy_decision_ready": True,
            "threshold_change_ready": False,
            "runtime_change_ready": False,
            "historical_mutation_ready": False,
            "indexed_pending_count": 2,
            "manual_override_count": 2,
            "next_step": "monitor_processor_gate_excluded_policy_buckets",
            "summary": "2 indexed-pending row(s) remain status-contract cases and should stay outside raw threshold tuning.",
        },
    )
    (run_root / "indexed_pending_policy_decision.md").write_text(
        "# indexed pending policy decision\n",
        encoding="utf-8",
    )
    _write_json(
        run_root / "fixture_or_test_policy_decision.json",
        {
            "schema_version": "processor_gate_fixture_or_test_policy_decision.v1",
            "generated_at": "2026-04-22T00:00:00Z",
            "run_id": "gate_threshold_review_test",
            "final_status": "fixture_or_test_hygiene_exclusion_confirmed",
            "recommended_action": "keep_fixture_or_test_rows_out_of_threshold_tuning",
            "policy_decision_ready": True,
            "threshold_change_ready": False,
            "runtime_change_ready": False,
            "historical_mutation_ready": False,
            "archive_action_ready": False,
            "fixture_or_test_count": 1,
            "manual_override_count": 2,
            "indexed_pending_count": 2,
            "next_step": "monitor_processor_gate_excluded_policy_buckets",
            "summary": "1 fixture/test row(s) remain hygiene-scope cases and should stay outside raw threshold tuning.",
        },
    )
    (run_root / "fixture_or_test_policy_decision.md").write_text(
        "# fixture/test policy decision\n",
        encoding="utf-8",
    )

    result = runner.invoke(cli.app, ["show-processor-gate-threshold-review", str(run_root)])
    normalized_output = " ".join(result.output.split())

    assert result.exit_code == 0
    assert "Processor Gate Threshold Review" in result.output
    assert "gate_threshold_review_test" in result.output
    assert "Markdown:" in result.output
    assert "audit.md" in result.output
    assert "Manual Review Rows:" in result.output
    assert "manual_review_rows.json" in result.output
    assert "Manual Review Markdown:" in result.output
    assert "manual_review.md" in result.output
    assert "Manual Review Checklist:" in result.output
    assert "manual_review_checklist.csv" in result.output
    assert "Manual Review Seed:" in result.output
    assert "manual_review_seed.csv" in result.output
    assert "Manual Review Frontier:" in result.output
    assert "manual_review_frontier.csv" in result.output
    assert "Manual Review Frontier Notes:" in result.output
    assert "manual_review_frontier_notes.md" in result.output
    assert "Manual Review Frontier Crosscheck Packet:" in result.output
    assert "manual_review_frontier_crosscheck_packet.md" in result.output
    assert "Manual Review Frontier Claude Crosscheck:" in result.output
    assert "manual_review_frontier_claude_crosscheck.md" in result.output
    assert "Manual Review Frontier Claude Crosscheck JSON:" in result.output
    assert "manual_review_frontier_claude_crosscheck.json" in result.output
    assert "Manual Review Basis:" in result.output
    assert "manual_review_basis.md" in result.output
    assert "Manual Review Decision:" in result.output
    assert "manual_review_decision.md" in result.output
    assert "Manual Review Outcome:" in result.output
    assert "manual_review_outcome.json" in result.output
    assert "Manual Review Outcome Markdown:" in result.output
    assert "manual_review_outcome.md" in result.output
    assert "Threshold Change Decision:" in result.output
    assert "threshold_change_decision.json" in result.output
    assert "Threshold Change Decision Markdown:" in result.output
    assert "threshold_change_decision.md" in result.output
    assert "Mid-Confidence Policy Decision:" in result.output
    assert "mid_confidence_policy_decision.json" in result.output
    assert "Mid-Confidence Policy Decision Markdown:" in result.output
    assert "mid_confidence_policy_decision.md" in result.output
    assert "Mid-Confidence Policy Debt Reconciliation:" in result.output
    assert "mid_confidence_policy_debt_reconciliation.json" in result.output
    assert "Mid-Confidence Policy Debt Reconciliation Markdown:" in result.output
    assert "mid_confidence_policy_debt_reconciliation.md" in result.output
    assert "Manual Override Policy Decision:" in result.output
    assert "manual_override_policy_decision.json" in result.output
    assert "Manual Override Policy Decision Markdown:" in result.output
    assert "manual_override_policy_decision.md" in result.output
    assert "Indexed Pending Policy Decision:" in result.output
    assert "indexed_pending_policy_decision.json" in result.output
    assert "Indexed Pending Policy Decision Markdown:" in result.output
    assert "indexed_pending_policy_decision.md" in result.output
    assert "Fixture/Test Policy Decision:" in result.output
    assert "fixture_or_test_policy_decision.json" in result.output
    assert "Fixture/Test Policy Decision Markdown:" in result.output
    assert "fixture_or_test_policy_decision.md" in result.output
    assert "Replay Drift Summary:" in result.output
    assert "drift/summary.json" in normalized_output
    assert "Replay Drift Details:" in result.output
    assert "drift/details.json" in normalized_output
    assert "Replay Drift Markdown:" in result.output
    assert "drift/audit.md" in normalized_output
    assert "Threshold Replay Context:" in result.output
    assert "drift/threshold_replay.json" in normalized_output
    assert "Threshold Replay Context Markdown:" in result.output
    assert "drift/threshold_replay.md" in normalized_output
    assert "Threshold Replay: mode=threshold_change_proposal_replay, high=0.85, low=0.70, reviewed_high=0.85, proposal=gate_threshold_review_ready" in normalized_output
    assert "Threshold Replay Review Command:" in result.output
    assert "recommend_processor_gate_threshold_review.py" in result.output
    assert "Heuristic: warn >= 25.0% | sample >= 20 candidate rows" in normalized_output
    assert "Thresholds: high=0.90 | low=0.70" in normalized_output
    assert "manual_gate_threshold_review" in result.output
    assert "review_gate_thresholds_and_mid_confidence_policy" in result.output
    assert "processor_gate_replay_drift_preapply_20260421_r11" in normalized_output
    assert "(warn)" in normalized_output
    for focus_area in [
        "high_threshold",
        "mid_confidence_escalation",
        "high_confidence_pending_policy",
        "indexed_pending_policy",
        "manual_override_boundary",
    ]:
        assert focus_area in normalized_output
    assert "Coverage: 54 candidates | 28 promotable | 26 drift | rate=48.1%" in normalized_output
    assert "APPROVED->PENDING_REVIEW" in result.output
    assert "legacy_mid_confidence_approval" in result.output
    assert "Manual Review Scope" in result.output
    assert "threshold_relevant" in result.output
    assert "excluded.manual_override" in result.output
    assert "phase0_test" in result.output
    assert "Review Basis: Focus threshold tuning on 21 threshold-relevant row(s) first" in normalized_output
    assert "Worksheet: pending=21, target=mid_confidence_escalation_policy, excluded=5" in normalized_output
    assert "Worksheet Summary: 21 threshold-relevant row(s) are queued for mid-confidence escalation policy review; exclude 5 non-threshold row(s) from raw threshold changes." in normalized_output
    assert "Prefill: policy_only=21, boundary=0, triage=0, now=0, first=2, later=19" in normalized_output
    assert "Prefill Summary: Default prefills: policy_only=21, boundary=0, triage=0. Priority: now=0, first=2, later=19." in normalized_output
    assert "Basis: call=mid_confidence_policy_only, policy=21, high=0" in normalized_output
    assert "Basis Summary: All 21 threshold-relevant row(s) are mid-confidence legacy approvals replaying to pending review; none support a high-threshold boundary change from this evidence alone." in normalized_output
    assert "Outcome: status=policy_only_confirmed, completed=2/2, high=0, diverged=0" in normalized_output
    assert "Outcome Summary: All 2 reviewed row(s) support policy-only treatment and none support a high-threshold change." in normalized_output
    assert "Threshold Decision: status=no_threshold_change_supported, action=keep_current_high_threshold, reviewed=2/2, high=0" in normalized_output
    assert "Threshold Decision Summary: Manual review confirmed 2/2 threshold-relevant row(s) as policy-only; none support a high-threshold change." in normalized_output
    assert "Mid-Confidence Policy: status=mid_confidence_escalation_policy_confirmed, action=keep_mid_confidence_pending_review_policy, mid=2, high=0" in normalized_output
    assert "Mid-Confidence Policy Summary: Manual review confirmed 2/2 reviewed row(s) as mid-confidence policy debt; keep the current pending-review behavior for mid-confidence rows." in normalized_output
    assert "Policy Debt: status=legacy_policy_debt_confirmed, action=keep_historical_approvals_as_legacy_policy_debt, debt=2/2, mutate=no" in normalized_output
    assert "Policy Debt Summary: Manual review confirmed 2/2 historical mid-confidence approval row(s) as policy debt." in normalized_output
    assert "Manual Override Policy: status=manual_override_exception_policy_confirmed, action=exclude_manual_override_rows_from_threshold_tuning, manual=2, mutate=no" in normalized_output
    assert "Manual Override Policy Summary: 2 manual or human override row(s) remain explicit policy exceptions" in normalized_output
    assert "Indexed Pending Policy: status=indexed_pending_status_contract_confirmed, action=keep_indexed_pending_rows_out_of_threshold_tuning, indexed=2, mutate=no" in normalized_output
    assert "Indexed Pending Policy Summary: 2 indexed-pending row(s) remain status-contract cases" in normalized_output
    assert "Fixture/Test Policy: status=fixture_or_test_hygiene_exclusion_confirmed, action=keep_fixture_or_test_rows_out_of_threshold_tuning, fixture=1, archive=no, mutate=no" in normalized_output
    assert "Fixture/Test Policy Summary: 1 fixture/test row(s) remain hygiene-scope cases" in normalized_output
    assert "Tuning Targets" in result.output
    assert "mid_confidence_escalation" in normalized_output
    assert "manual_override_boundary" in normalized_output
    assert "indexed_pending_policy" in normalized_output
    assert "Tuning Actions" in result.output
    assert "review_mid_confidence_escalation_policy" in normalized_output
    assert "Action Plan" in result.output
    assert "Tuning Recommendations" in result.output
    assert "mid-confidence escalation policy" in normalized_output
    assert "Threshold Change Ready" in result.output
    assert "Threshold Change Status" in result.output
    assert "blocked_policy_only" in normalized_output
    assert "Threshold Change Next" in result.output
    assert "review_mid_confidence_escalation_policy" in normalized_output
    assert "Threshold Change Blocker" in result.output
    assert "none support a high-threshold boundary change from this evidence alone." in normalized_output
    assert "Review the high threshold and mid-confidence escalation policy first" in result.output


def test_show_processor_gate_threshold_review_supports_json_output(tmp_path: Path) -> None:
    runner = CliRunner()
    summary_path = tmp_path / "processor_gate_threshold_review_run" / "summary.json"
    drift_root = tmp_path / "drift"
    drift_root.mkdir(parents=True, exist_ok=True)
    (drift_root / "summary.json").write_text("{}", encoding="utf-8")
    (drift_root / "details.json").write_text("{}", encoding="utf-8")
    (drift_root / "audit.md").write_text("# replay drift markdown\n", encoding="utf-8")
    _write_json(
        summary_path,
        {
            "schema_version": "processor_gate_threshold_review.v1",
            "generated_at": "2026-04-21T00:00:00Z",
            "run_id": "gate_threshold_review_json_test",
            "inputs": {
                "drift_summary_path": str(drift_root / "summary.json"),
                "drift_details_path": str(drift_root / "details.json"),
                "high_threshold": 0.9,
                "low_threshold": 0.7,
            },
            "decision": {
                "recommended_action": "hold_current_gate_thresholds",
                "threshold_change_ready": False,
                "threshold_change_status": "blocked_small_sample",
                "threshold_change_next_step": "collect_more_processor_gate_drift_evidence",
            },
            "signal_summary": {"candidate_count": 12, "drift_count": 1},
            "manual_review_scope": {
                "threshold_relevant": {"count": 1, "paper_ids": ["paper-1"]},
                "worksheet_summary": {
                    "pending_count": 1,
                    "review_bucket": "threshold_relevant",
                    "primary_review_target": "mid_confidence_escalation_policy",
                    "excluded_count": 0,
                    "summary": "1 threshold-relevant row(s) are queued for mid-confidence escalation policy review; exclude 0 non-threshold row(s) from raw threshold changes.",
                },
            },
            "manual_review_basis": {
                "preliminary_call": "mid_confidence_policy_only",
                "summary": "All 1 threshold-relevant row(s) are mid-confidence legacy approvals replaying to pending review; none support a high-threshold boundary change from this evidence alone.",
                "threshold_relevant_count": 1,
                "policy_edge_case_count": 0,
                "mid_confidence_policy_support_count": 1,
                "high_threshold_support_count": 0,
            },
            "recommendations": ["Collect more drift evidence before reviewing thresholds."],
        },
    )
    (summary_path.parent / "audit.md").write_text("# threshold review markdown\n", encoding="utf-8")

    result = runner.invoke(
        cli.app,
        ["show-processor-gate-threshold-review", str(summary_path), "--json"],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["run_id"] == "gate_threshold_review_json_test"
    assert payload["markdown_path"].endswith("/processor_gate_threshold_review_run/audit.md")
    assert payload["manual_review_rows_path"] is None
    assert payload["manual_review_markdown_path"] is None
    assert payload["manual_review_checklist_path"] is None
    assert payload["manual_review_seed_path"] is None
    assert payload["manual_review_frontier_path"] is None
    assert payload["manual_review_frontier_notes_path"] is None
    assert payload["manual_review_frontier_crosscheck_packet_path"] is None
    assert payload["manual_review_frontier_claude_crosscheck_path"] is None
    assert payload["manual_review_frontier_claude_crosscheck_json_path"] is None
    assert payload["manual_review_basis_markdown_path"] is None
    assert payload["manual_review_decision_markdown_path"] is None
    assert payload["manual_review_outcome_path"] is None
    assert payload["manual_review_outcome_markdown_path"] is None
    assert payload["threshold_change_decision_path"] is None
    assert payload["threshold_change_decision_markdown_path"] is None
    assert payload["mid_confidence_policy_decision_path"] is None
    assert payload["mid_confidence_policy_decision_markdown_path"] is None
    assert payload["mid_confidence_policy_debt_reconciliation_path"] is None
    assert payload["mid_confidence_policy_debt_reconciliation_markdown_path"] is None
    assert payload["manual_override_policy_decision_path"] is None
    assert payload["manual_override_policy_decision_markdown_path"] is None
    assert payload["indexed_pending_policy_decision_path"] is None
    assert payload["indexed_pending_policy_decision_markdown_path"] is None
    assert payload["fixture_or_test_policy_decision_path"] is None
    assert payload["fixture_or_test_policy_decision_markdown_path"] is None
    assert payload["drift_summary_path"].endswith("/drift/summary.json")
    assert payload["drift_details_path"].endswith("/drift/details.json")
    assert payload["drift_markdown_path"].endswith("/drift/audit.md")
    assert payload["threshold_replay_review_command"] is None
    assert payload["inputs"]["high_threshold"] == 0.9
    assert payload["decision"]["recommended_action"] == "hold_current_gate_thresholds"
    assert payload["decision"]["threshold_change_status"] == "blocked_small_sample"
    assert payload["signal_summary"]["candidate_count"] == 12
    assert payload["manual_review_scope"]["threshold_relevant"]["count"] == 1
    assert payload["manual_review_scope"]["worksheet_summary"]["primary_review_target"] == "mid_confidence_escalation_policy"
    assert payload["manual_review_basis"]["preliminary_call"] == "mid_confidence_policy_only"
    assert payload["manual_review_outcome"] == {}
    assert payload["threshold_change_decision"] == {}
    assert payload["mid_confidence_policy_decision"] == {}
    assert payload["mid_confidence_policy_debt_reconciliation"] == {}
    assert payload["manual_override_policy_decision"] == {}
    assert payload["indexed_pending_policy_decision"] == {}
    assert payload["fixture_or_test_policy_decision"] == {}
    assert payload["recommendations"] == ["Collect more drift evidence before reviewing thresholds."]


def test_show_processor_gate_threshold_review_surfaces_threshold_decision_preflight(
    tmp_path: Path,
) -> None:
    runner = CliRunner()
    run_root = tmp_path / "processor_gate_threshold_review_preflight"
    _write_json(
        run_root / "summary.json",
        {
            "schema_version": "processor_gate_threshold_review.v1",
            "generated_at": "2026-04-21T00:00:00Z",
            "run_id": "gate_threshold_review_preflight",
            "inputs": {
                "high_threshold": 0.9,
                "low_threshold": 0.7,
            },
            "decision": {
                "recommended_action": "manual_gate_threshold_review",
                "review_ready": True,
                "threshold_change_ready": True,
                "threshold_change_status": "candidate_boundary_review",
            },
            "signal_summary": {"candidate_count": 4, "drift_count": 1},
            "manual_review_scope": {
                "threshold_relevant": {"count": 1, "paper_ids": ["paper-1"]}
            },
        },
    )
    _write_json(
        run_root / "threshold_change_decision.json",
        {
            "schema_version": "processor_gate_threshold_change_decision.v1",
            "generated_at": "2026-04-26T00:00:00Z",
            "run_id": "gate_threshold_review_preflight",
            "final_status": "threshold_change_validation_replay_required",
            "recommended_action": "run_threshold_change_validation_replay_before_decision",
            "threshold_change_ready": False,
            "threshold_change_next_step": "run_threshold_change_validation_replay",
            "summary": "Manual review found 1/1 row(s) that may support high-threshold boundary inspection, but validation replay is missing.",
            "manual_review_counts": {
                "total": 1,
                "completed": 1,
                "supports_mid_confidence_policy_review": 0,
                "supports_high_threshold_change": 1,
                "default_divergence": 1,
            },
            "threshold_change_preflight": {
                "required": True,
                "ready": False,
                "status": "missing_threshold_change_proposal",
                "blocker": "missing_threshold_change_proposal",
                "validation_replay_status": "not_applicable",
                "validation_replay_matches_proposal": False,
            },
        },
    )

    text_result = runner.invoke(cli.app, ["show-processor-gate-threshold-review", str(run_root)])
    json_result = runner.invoke(
        cli.app,
        ["show-processor-gate-threshold-review", str(run_root), "--json"],
    )

    assert text_result.exit_code == 0
    normalized_output = " ".join(text_result.output.split())
    assert (
        "Threshold Decision: status=threshold_change_validation_replay_required, "
        "action=run_threshold_change_validation_replay_before_decision, reviewed=1/1, "
        "high=1, preflight=missing_threshold_change_proposal, "
        "blocker=missing_threshold_change_proposal"
    ) in normalized_output
    assert json_result.exit_code == 0
    payload = json.loads(json_result.output)
    assert payload["threshold_change_decision"]["threshold_change_preflight"]["ready"] is False
    assert (
        payload["threshold_change_decision"]["threshold_change_preflight"]["blocker"]
        == "missing_threshold_change_proposal"
    )


def test_show_processor_gate_threshold_review_surfaces_threshold_change_proposal_paths(
    tmp_path: Path,
) -> None:
    runner = CliRunner()
    run_root = tmp_path / "processor_gate_threshold_review_ready"
    validation_run_id = "gate_threshold_review_ready__threshold_validation_replay"
    validation_replay_root = tmp_path / "processor_gate_replay_drift" / validation_run_id
    validation_replay_root.mkdir(parents=True, exist_ok=True)
    (validation_replay_root / "summary.json").write_text("{}", encoding="utf-8")
    (validation_replay_root / "details.json").write_text("{}", encoding="utf-8")
    (validation_replay_root / "threshold_replay.json").write_text(
        json.dumps(
            {
                "threshold_replay_mode": "threshold_change_proposal_replay",
                "high_threshold": 0.85,
                "low_threshold": 0.7,
                "reviewed_high_threshold": 0.85,
                "proposal_run_id": "gate_threshold_review_ready",
            }
        ),
        encoding="utf-8",
    )
    _write_json(
        run_root / "summary.json",
        {
            "schema_version": "processor_gate_threshold_review.v1",
            "generated_at": "2026-04-21T00:00:00Z",
            "run_id": "gate_threshold_review_ready",
            "inputs": {
                "drift_summary_path": str(validation_replay_root / "summary.json"),
                "drift_details_path": str(validation_replay_root / "details.json"),
                "high_threshold": 0.9,
                "low_threshold": 0.7,
            },
            "decision": {
                "recommended_action": "manual_gate_threshold_review",
                "threshold_change_ready": True,
                "threshold_change_status": "candidate_boundary_review",
                "threshold_change_next_step": "review_high_threshold_boundary",
            },
            "signal_summary": {"candidate_count": 24, "drift_count": 6},
            "manual_review_scope": {
                "threshold_relevant": {"count": 1, "paper_ids": ["paper-boundary-1"]}
            },
            "manual_review_basis": {
                "preliminary_call": "mixed_manual_review",
                "summary": "1 threshold-relevant row(s) need mixed manual review; 1 row(s) may still need high-threshold boundary inspection.",
                "threshold_relevant_count": 1,
                "policy_edge_case_count": 0,
                "mid_confidence_policy_support_count": 0,
                "high_threshold_support_count": 1,
            },
            "recommendations": ["Inspect the high-threshold boundary directly."],
        },
    )
    validation_command = (
        "python3 scripts/eval/audit_processor_gate_replay_drift.py "
        "--threshold-change-proposal threshold_change_proposal.json "
        "--reviewed-high-threshold '<REVIEWED_HIGH_THRESHOLD>' "
        f"--run-id {validation_run_id}"
    )
    _write_json(
        run_root / "threshold_change_proposal.json",
        {
            "run_id": "gate_threshold_review_ready",
            "validation_replay_run_id": "gate_threshold_review_ready__threshold_validation_replay",
            "validation_replay_command_template": validation_command,
        },
    )
    (run_root / "threshold_change_proposal.md").write_text(
        "# threshold change proposal\n",
        encoding="utf-8",
    )

    text_result = runner.invoke(cli.app, ["show-processor-gate-threshold-review", str(run_root)])
    json_result = runner.invoke(
        cli.app,
        ["show-processor-gate-threshold-review", str(run_root), "--json"],
    )

    assert text_result.exit_code == 0
    assert "Threshold Change Proposal:" in text_result.output
    assert "threshold_change_proposal.json" in text_result.output
    assert "Threshold Change Validation Replay:" in text_result.output
    assert "audit_processor_gate_replay_drift.py" in text_result.output
    assert "Threshold Change Validation Replay Status:" in text_result.output
    assert "Threshold Change Manual Decision:" in text_result.output
    normalized_text_output = " ".join(text_result.output.split())
    assert "matched (available=yes, matches=yes, needs_rerun=no)" in normalized_text_output
    assert "Threshold Change Manual Decision: ready=yes, status=ready" in normalized_text_output
    assert "Threshold Change Proposal Markdown:" in text_result.output
    assert "threshold_change_proposal.md" in text_result.output

    assert json_result.exit_code == 0
    payload = json.loads(json_result.output)
    assert payload["threshold_change_proposal_path"].endswith(
        "/processor_gate_threshold_review_ready/threshold_change_proposal.json"
    )
    assert payload["threshold_change_proposal_markdown_path"].endswith(
        "/processor_gate_threshold_review_ready/threshold_change_proposal.md"
    )
    assert payload["threshold_change_validation_replay_command_template"] == validation_command
    assert (
        payload["threshold_change_validation_replay_run_id"]
        == "gate_threshold_review_ready__threshold_validation_replay"
    )
    assert payload["threshold_change_validation_replay_available"] is True
    assert payload["threshold_change_validation_replay_matches_proposal"] is True
    assert payload["threshold_change_validation_replay_needs_rerun"] is False
    assert payload["threshold_change_validation_replay_status"] == "matched"
    assert payload["threshold_change_manual_decision_ready"] is True
    assert payload["threshold_change_manual_decision_status"] == "ready"
    assert payload["threshold_change_manual_decision_blocker"] is None
