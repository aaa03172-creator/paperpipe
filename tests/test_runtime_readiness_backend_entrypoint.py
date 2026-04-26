from types import SimpleNamespace

from src.services import runtime_readiness


def test_backend_entrypoint_check_surfaces_missing_dependency(monkeypatch):
    def fake_import_module(name: str):
        assert name == "backend.main"
        raise ModuleNotFoundError("No module named 'fastapi'", name="fastapi")

    monkeypatch.setattr(runtime_readiness.importlib, "import_module", fake_import_module)

    check = runtime_readiness._backend_entrypoint_check()

    assert check.name == "backend_entrypoint"
    assert check.status == "error"
    assert "fastapi" in check.detail
    assert "bootstrap_verification_env.py" in check.detail


def test_cli_entrypoint_check_warns_when_no_launcher_is_detected(monkeypatch):
    monkeypatch.setattr(runtime_readiness, "_resolved_cli_entrypoint_command", lambda: None)

    check = runtime_readiness._cli_entrypoint_check()

    assert check.name == "cli_entrypoint"
    assert check.status == "warn"
    assert "no repo-local or packaged launcher detected" in check.detail


def test_cli_entrypoint_check_surfaces_nonzero_exit(monkeypatch):
    monkeypatch.setattr(
        runtime_readiness,
        "_resolved_cli_entrypoint_command",
        lambda: ["/tmp/paperpipe"],
    )
    monkeypatch.setattr(
        runtime_readiness.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=1,
            stdout="",
            stderr="ModuleNotFoundError: No module named 'src'",
        ),
    )

    check = runtime_readiness._cli_entrypoint_check()

    assert check.name == "cli_entrypoint"
    assert check.status == "error"
    assert check.path == "/tmp/paperpipe"
    assert "CLI entrypoint failed for `--help`" in check.detail
    assert "No module named 'src'" in check.detail


def test_cli_entrypoint_check_reports_success(monkeypatch):
    monkeypatch.setattr(
        runtime_readiness,
        "_resolved_cli_entrypoint_command",
        lambda: ["/tmp/paperpipe"],
    )
    monkeypatch.setattr(
        runtime_readiness.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout="Usage: paperpipe", stderr=""),
    )

    check = runtime_readiness._cli_entrypoint_check()

    assert check.name == "cli_entrypoint"
    assert check.status == "ok"
    assert check.path == "/tmp/paperpipe"
    assert check.detail == "CLI entrypoint responds to `--help`"


def test_privacy_preflight_config_check_defaults_to_off(monkeypatch):
    monkeypatch.delenv("LATTICE_PRIVACY_PREFLIGHT_MODE", raising=False)

    check = runtime_readiness._privacy_preflight_config_check()

    assert check.name == "privacy_preflight_config"
    assert check.status == "ok"
    assert "rollback mode" in check.detail
    assert check.metadata["rollback_flag"] == "LATTICE_PRIVACY_PREFLIGHT_MODE"
    assert check.metadata["configured"] is False
    assert check.metadata["effective_mode"] == "off"
    assert check.metadata["mode_valid"] is True


def test_privacy_preflight_config_check_reports_report_only(monkeypatch):
    monkeypatch.setenv("LATTICE_PRIVACY_PREFLIGHT_MODE", "report_only")

    check = runtime_readiness._privacy_preflight_config_check()

    assert check.status == "ok"
    assert "report-only" in check.detail
    assert check.metadata["configured"] is True
    assert check.metadata["effective_mode"] == "report_only"
    assert check.metadata["pilot_scope"] == "clinical_extraction_external_payload"
    assert check.metadata["mutation_allowed"] is False


def test_privacy_preflight_config_check_rejects_invalid_mode_without_echoing_value(monkeypatch):
    monkeypatch.setenv("LATTICE_PRIVACY_PREFLIGHT_MODE", "secret-looking-surprise")

    check = runtime_readiness._privacy_preflight_config_check()

    assert check.name == "privacy_preflight_config"
    assert check.status == "error"
    assert "LATTICE_PRIVACY_PREFLIGHT_MODE is invalid" in check.detail
    assert "secret-looking-surprise" not in check.detail
    assert "secret-looking-surprise" not in str(check.metadata)
    assert check.metadata["configured"] is True
    assert check.metadata["mode_valid"] is False
    assert check.metadata["effective_mode"] is None


def test_latest_intake_override_audit_check_reports_latest_run(monkeypatch):
    monkeypatch.setattr(runtime_readiness, "latest_intake_override_audit_run", lambda: runtime_readiness.Path("/tmp/audit-run"))
    monkeypatch.setattr(
        runtime_readiness,
        "latest_intake_override_audit_summary",
        lambda: SimpleNamespace(
            generated_at=SimpleNamespace(isoformat=lambda: "2026-04-20T05:00:00+00:00"),
            inputs=SimpleNamespace(source="rows_jsonl", row_count=7),
            metrics=SimpleNamespace(
                audited_document_count=3,
                triage_override_rate=0.25,
                slot_disagreement_rate=0.5,
                selection_fallback_count=1,
                selection_fallback_rate=0.333,
                slot_disagreement_count=2,
                llm_slot_adjudication_rate=0.5,
                llm_tagging_adjudication_rate=0.25,
                analysis_unavailable_rate=0.0,
                issues_state_unavailable_rate=0.25,
            ),
        ),
    )

    check = runtime_readiness._latest_intake_override_audit_check()

    assert check.name == "latest_intake_override_audit"
    assert check.status == "ok"
    assert check.path == "/tmp/audit-run/audit.md"
    assert "latest intake override audit is available" in check.detail
    assert check.metadata == {
        "available": True,
        "run_id": "audit-run",
        "generated_at": "2026-04-20T05:00:00+00:00",
        "source": "rows_jsonl",
        "row_count": 7,
        "audited_document_count": 3,
        "triage_override_rate": 0.25,
        "slot_disagreement_rate": 0.5,
        "selection_fallback_count": 1,
        "selection_fallback_rate": 0.333,
        "slot_disagreement_count": 2,
        "llm_slot_adjudication_rate": 0.5,
        "llm_tagging_adjudication_rate": 0.25,
        "analysis_unavailable_rate": 0.0,
        "issues_state_unavailable_rate": 0.25,
        "quality_signals": [
            "slot_disagreement_present",
            "selection_fallback_present",
            "triage_override_present",
            "slot_adjudication_present",
            "tagging_adjudication_present",
            "issues_state_unavailable_present",
        ],
    }


def test_latest_intake_override_audit_check_reports_empty_root(monkeypatch):
    monkeypatch.setattr(runtime_readiness, "latest_intake_override_audit_run", lambda: None)
    monkeypatch.setattr(runtime_readiness, "latest_intake_override_audit_summary", lambda: None)
    monkeypatch.setattr(
        runtime_readiness,
        "default_intake_override_audits_root",
        lambda: runtime_readiness.Path("/tmp/intake-audits"),
    )

    check = runtime_readiness._latest_intake_override_audit_check()

    assert check.name == "latest_intake_override_audit"
    assert check.status == "ok"
    assert check.path == "/tmp/intake-audits"
    assert check.detail == "no intake override audit runs found yet"
    assert check.metadata == {"available": False, "quality_signals": []}


def test_latest_intake_override_audit_quality_check_warns_when_rates_cross_threshold(monkeypatch) -> None:
    monkeypatch.setattr(
        runtime_readiness,
        "_intake_override_audit_calibration_metadata",
        lambda: {
            "total_runs": 2,
            "eligible_runs": 1,
            "warn_runs": 1,
            "calibration_target_runs": 3,
            "target_met": False,
            "advice": "Keep the current 25% warning threshold for now.",
        },
    )
    latest_check = runtime_readiness.RuntimeReadinessCheck(
        name="latest_intake_override_audit",
        status="ok",
        detail="latest intake override audit is available (audit-run)",
        metadata={
            "available": True,
            "audited_document_count": 3,
            "quality_signals": [
                "slot_disagreement_present",
                "triage_override_present",
                "slot_adjudication_present",
                "tagging_adjudication_present",
            ],
            "triage_override_rate": 0.333,
            "slot_disagreement_rate": 0.5,
            "llm_slot_adjudication_rate": 0.5,
            "llm_tagging_adjudication_rate": 0.25,
            "selection_fallback_rate": 0.0,
            "analysis_unavailable_rate": 0.1,
            "issues_state_unavailable_rate": 0.0,
        },
    )

    check = runtime_readiness._latest_intake_override_audit_quality_check(latest_check)

    assert check.name == "latest_intake_override_audit_quality"
    assert check.status == "warn"
    assert "triage=33.3%" in check.detail
    assert "slot=50.0%" in check.detail
    assert "slot_adjudication=50.0%" in check.detail
    assert "tagging_adjudication=25.0%" in check.detail
    assert check.metadata["warn_threshold"] == runtime_readiness.LATEST_INTAKE_OVERRIDE_AUDIT_WARN_RATE
    assert check.metadata["min_audited_docs"] == runtime_readiness.LATEST_INTAKE_OVERRIDE_AUDIT_MIN_AUDITED_DOCS
    assert check.metadata["sample_sufficient"] is True
    assert check.metadata["calibration"]["eligible_runs"] == 1
    assert check.metadata["calibration"]["target_met"] is False


def test_latest_intake_override_audit_quality_check_skips_small_samples(monkeypatch) -> None:
    monkeypatch.setattr(
        runtime_readiness,
        "_intake_override_audit_calibration_metadata",
        lambda: {
            "total_runs": 2,
            "eligible_runs": 1,
            "warn_runs": 1,
            "calibration_target_runs": 3,
            "target_met": False,
            "advice": "Keep the current 25% warning threshold for now.",
        },
    )
    latest_check = runtime_readiness.RuntimeReadinessCheck(
        name="latest_intake_override_audit",
        status="ok",
        detail="latest intake override audit is available (audit-run)",
        metadata={
            "available": True,
            "audited_document_count": 2,
            "quality_signals": [
                "slot_disagreement_present",
                "triage_override_present",
            ],
            "triage_override_rate": 1.0,
            "slot_disagreement_rate": 1.0,
            "selection_fallback_rate": 0.0,
            "analysis_unavailable_rate": 0.0,
            "issues_state_unavailable_rate": 0.0,
        },
    )

    check = runtime_readiness._latest_intake_override_audit_quality_check(latest_check)

    assert check.name == "latest_intake_override_audit_quality"
    assert check.status == "ok"
    assert "sample is too small" in check.detail
    assert check.metadata["sample_sufficient"] is False
    assert check.metadata["audited_document_count"] == 2
    assert check.metadata["calibration"]["warn_runs"] == 1


def test_latest_intake_override_audit_quality_check_is_ok_when_no_audit_available() -> None:
    latest_check = runtime_readiness.RuntimeReadinessCheck(
        name="latest_intake_override_audit",
        status="ok",
        detail="no intake override audit runs found yet",
        metadata={"available": False, "quality_signals": []},
    )

    check = runtime_readiness._latest_intake_override_audit_quality_check(latest_check)

    assert check.name == "latest_intake_override_audit_quality"
    assert check.status == "ok"
    assert check.detail == "no intake override audit available for quality heuristic"
    assert check.metadata == {
        "available": False,
        "warn_threshold": runtime_readiness.LATEST_INTAKE_OVERRIDE_AUDIT_WARN_RATE,
        "min_audited_docs": runtime_readiness.LATEST_INTAKE_OVERRIDE_AUDIT_MIN_AUDITED_DOCS,
    }


def test_latest_intake_override_threshold_review_check_reports_latest_run(monkeypatch):
    monkeypatch.setattr(
        runtime_readiness,
        "latest_intake_override_threshold_review_run",
        lambda: runtime_readiness.Path("/tmp/threshold-review"),
    )
    monkeypatch.setattr(
        runtime_readiness,
        "latest_intake_override_threshold_review_summary",
        lambda: {
            "generated_at": "2026-04-21T07:30:00+00:00",
            "provenance": {"kind": "operator", "latest_eligible": True},
            "inputs": {
                "warn_threshold": 0.25,
                "min_audited_docs": 3,
                "calibration_target_runs": 3,
            },
            "decision": {
                "recommended_action": "hold_current_threshold",
                "review_ready": False,
                "decision_reason": "only 1 sufficiently-audited run exists",
                "next_step": "collect_more_audit_runs",
                "latest_run_id": "audit_latest",
                "latest_run_status": "warn",
                "focus_signals": ["slot", "triage"],
                "blocking_summary": "1.collect_more_audit_runs: 1/3 sufficiently-audited runs currently meet the review floor, so threshold changes should stay blocked until more audit evidence accumulates.",
                "blocking_action": {
                    "order": 1,
                    "action": "collect_more_audit_runs",
                    "target": None,
                    "blocking": True,
                    "signals": [],
                    "summary": "Gather more sufficiently-audited runs before promoting this threshold review into manual threshold changes.",
                    "evidence": "1/3 sufficiently-audited runs currently meet the review floor, so threshold changes should stay blocked until more audit evidence accumulates.",
                },
                "tuning_targets": [],
                "tuning_actions": [],
                "tuning_recommendations": [],
            },
        },
    )

    check = runtime_readiness._latest_intake_override_threshold_review_check()

    assert check.name == "latest_intake_override_threshold_review"
    assert check.status == "ok"
    assert check.path == "/tmp/threshold-review/summary.json"
    assert "latest intake override threshold review is available" in check.detail
    assert check.metadata == {
        "available": True,
        "run_id": "threshold-review",
        "provenance_kind": "operator",
        "latest_eligible": True,
        "warn_threshold": 0.25,
        "min_audited_docs": 3,
        "calibration_target_runs": 3,
        "generated_at": "2026-04-21T07:30:00+00:00",
        "recommended_action": "hold_current_threshold",
        "review_ready": False,
        "decision_reason": "only 1 sufficiently-audited run exists",
        "next_step": "collect_more_audit_runs",
        "latest_run_id": "audit_latest",
        "latest_run_status": "warn",
        "focus_signals": ["slot", "triage"],
        "latest_warn_signals": [],
        "blocking_summary": "1.collect_more_audit_runs: 1/3 sufficiently-audited runs currently meet the review floor, so threshold changes should stay blocked until more audit evidence accumulates.",
        "blocking_action": {
            "order": 1,
            "action": "collect_more_audit_runs",
            "target": "",
            "blocking": True,
            "signals": [],
            "summary": "Gather more sufficiently-audited runs before promoting this threshold review into manual threshold changes.",
            "evidence": "1/3 sufficiently-audited runs currently meet the review floor, so threshold changes should stay blocked until more audit evidence accumulates.",
        },
        "tuning_targets": [],
        "tuning_actions": [],
        "action_plan": [],
        "tuning_recommendations": [],
    }


def test_latest_intake_override_threshold_review_check_reports_empty_root(monkeypatch):
    monkeypatch.setattr(runtime_readiness, "latest_intake_override_threshold_review_run", lambda: None)
    monkeypatch.setattr(runtime_readiness, "latest_intake_override_threshold_review_summary", lambda: None)
    monkeypatch.setattr(
        runtime_readiness,
        "default_intake_override_threshold_review_root",
        lambda: runtime_readiness.Path("/tmp/intake-threshold-review"),
    )

    check = runtime_readiness._latest_intake_override_threshold_review_check()

    assert check.name == "latest_intake_override_threshold_review"
    assert check.status == "ok"
    assert check.path == "/tmp/intake-threshold-review"
    assert check.detail == "no intake override threshold review runs found yet"
    assert check.metadata == {"available": False}


def test_latest_processor_gate_threshold_review_check_reports_latest_run(monkeypatch, tmp_path):
    drift_root = tmp_path / "processor_gate_replay_drift" / "processor_gate_replay_drift_preapply_20260421_r11"
    drift_root.mkdir(parents=True, exist_ok=True)
    (drift_root / "summary.json").write_text("{}", encoding="utf-8")
    (drift_root / "details.json").write_text("{}", encoding="utf-8")
    (drift_root / "audit.md").write_text("# replay drift markdown\n", encoding="utf-8")
    (drift_root / "threshold_replay.json").write_text(
        """
{
  "threshold_replay_mode": "threshold_change_proposal_replay",
  "high_threshold": 0.85,
  "low_threshold": 0.7,
  "reviewed_high_threshold": 0.85,
  "proposal_run_id": "gate_threshold_review_ready",
  "threshold_review_command": "python3 scripts/eval/recommend_processor_gate_threshold_review.py --drift-summary summary.json --run-id validation__threshold_review"
}
""".lstrip(),
        encoding="utf-8",
    )
    (drift_root / "threshold_replay.md").write_text(
        "# threshold replay context\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        runtime_readiness,
        "latest_processor_gate_threshold_review_run",
        lambda: runtime_readiness.Path("/tmp/processor-gate-threshold-review"),
    )
    monkeypatch.setattr(
        runtime_readiness,
        "load_processor_gate_threshold_review_summary",
        lambda path: {
            "generated_at": "2026-04-21T07:30:00+00:00",
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
                "decision_reason": "latest drift run shows 26/54 drift row(s) (48.1%), above the 25% warning threshold",
                "next_step": "review_gate_thresholds_and_mid_confidence_policy",
                "latest_run_id": "processor_gate_replay_drift_preapply_20260421_r11",
                "latest_run_status": "warn",
                "threshold_change_ready": False,
                "threshold_change_status": "blocked_policy_only",
                "threshold_change_next_step": "review_mid_confidence_escalation_policy",
                "threshold_change_blocker": "All 21 threshold-relevant row(s) are mid-confidence legacy approvals replaying to pending review; none support a high-threshold boundary change from this evidence alone.",
                "focus_areas": ["high_threshold", "mid_confidence_escalation"],
                "tuning_targets": ["mid_confidence_escalation"],
                "tuning_actions": [
                    {
                        "target": "mid_confidence_escalation",
                        "action": "review_mid_confidence_escalation_policy",
                        "summary": "Review whether historical mid-confidence approvals should now escalate to pending review before changing the high threshold.",
                    }
                ],
                "action_plan": [
                    {
                        "order": 1,
                        "action": "review_gate_thresholds_and_mid_confidence_policy",
                        "target": None,
                        "blocking": True,
                        "summary": "Use the threshold-relevant bucket as the primary manual-review basis before applying gate threshold changes.",
                    }
                ],
            },
            "signal_summary": {
                "candidate_count": 54,
                "promotable_count": 28,
                "drift_count": 26,
                "drift_rate": 0.481481,
            },
            "manual_review_scope": {
                "threshold_relevant": {"count": 21, "paper_ids": ["paper-a", "paper-b", "paper-c", "paper-d"]},
                "policy_edge_cases": {"count": 1},
                "excluded": {
                    "manual_override": {"count": 2, "paper_ids": ["manual-1", "manual-2"]},
                    "indexed_pending": {"count": 3, "paper_ids": ["indexed-1", "indexed-2", "indexed-3", "indexed-4"]},
                    "fixture_or_test": {"count": 4, "paper_ids": ["fixture-1"]},
                    "other": {"count": 5},
                },
                "focus_recommendation": "Focus threshold tuning on threshold-relevant rows first.",
                "worksheet_summary": {
                    "pending_count": 21,
                    "primary_review_target": "mid_confidence_escalation_policy",
                    "excluded_count": 9,
                    "summary": "21 threshold-relevant row(s) are queued for mid-confidence escalation policy review; exclude 9 non-threshold row(s) from raw threshold changes.",
                },
            },
            "manual_review_basis": {
                "preliminary_call": "mid_confidence_policy_only",
                "mid_confidence_policy_support_count": 21,
                "high_threshold_support_count": 0,
                "summary": "All 21 threshold-relevant row(s) are mid-confidence legacy approvals replaying to pending review; none support a high-threshold boundary change from this evidence alone.",
            },
        },
    )

    check = runtime_readiness._latest_processor_gate_threshold_review_check()

    assert check.name == "latest_processor_gate_threshold_review"
    assert check.status == "ok"
    assert check.path == "/tmp/processor-gate-threshold-review/summary.json"
    assert "latest processor gate threshold review is available" in check.detail
    assert check.metadata == {
        "available": True,
        "run_id": "processor-gate-threshold-review",
        "markdown_available": False,
        "manual_review_rows_available": False,
        "manual_review_markdown_available": False,
        "manual_review_checklist_available": False,
        "manual_review_basis_markdown_available": False,
        "threshold_change_proposal_available": False,
        "threshold_change_proposal_markdown_available": False,
        "threshold_change_validation_replay_command_available": False,
        "threshold_change_validation_replay_available": False,
        "threshold_change_validation_replay_matches_proposal": False,
        "threshold_change_validation_replay_needs_rerun": False,
        "threshold_change_validation_replay_status": "not_applicable",
        "threshold_change_manual_decision_ready": False,
        "threshold_change_manual_decision_status": "not_applicable",
        "threshold_change_manual_decision_blocker": None,
        "generated_at": "2026-04-21T07:30:00+00:00",
        "drift_summary_available": True,
        "drift_details_available": True,
        "drift_markdown_available": True,
        "threshold_replay_available": True,
        "threshold_replay_markdown_available": True,
        "threshold_replay_review_command_available": True,
        "threshold_replay_text": (
            "mode=threshold_change_proposal_replay, high=0.85, low=0.70, "
            "reviewed_high=0.85, proposal=gate_threshold_review_ready"
        ),
        "threshold_replay_mode": "threshold_change_proposal_replay",
        "threshold_replay_high_threshold": 0.85,
        "threshold_replay_low_threshold": 0.7,
        "threshold_replay_reviewed_high_threshold": 0.85,
        "threshold_replay_proposal_run_id": "gate_threshold_review_ready",
        "high_threshold": 0.9,
        "low_threshold": 0.7,
        "min_candidate_rows": 20,
        "drift_warn_threshold": 0.25,
        "recommended_action": "manual_gate_threshold_review",
        "review_ready": True,
        "decision_reason": "latest drift run shows 26/54 drift row(s) (48.1%), above the 25% warning threshold",
        "next_step": "review_gate_thresholds_and_mid_confidence_policy",
        "latest_run_id": "processor_gate_replay_drift_preapply_20260421_r11",
        "latest_run_status": "warn",
        "threshold_change_ready": False,
        "threshold_change_status": "blocked_policy_only",
        "threshold_change_next_step": "review_mid_confidence_escalation_policy",
        "threshold_change_blocker": "All 21 threshold-relevant row(s) are mid-confidence legacy approvals replaying to pending review; none support a high-threshold boundary change from this evidence alone.",
        "threshold_change_text": "ready=no, status=blocked_policy_only, next=review_mid_confidence_escalation_policy",
        "focus_areas": ["high_threshold", "mid_confidence_escalation"],
        "tuning_targets": ["mid_confidence_escalation"],
        "tuning_actions": [
            {
                "target": "mid_confidence_escalation",
                "action": "review_mid_confidence_escalation_policy",
                "summary": "Review whether historical mid-confidence approvals should now escalate to pending review before changing the high threshold.",
            }
        ],
        "action_plan": [
            {
                "order": 1,
                "action": "review_gate_thresholds_and_mid_confidence_policy",
                "target": None,
                "blocking": True,
                "summary": "Use the threshold-relevant bucket as the primary manual-review basis before applying gate threshold changes.",
            }
        ],
        "candidate_count": 54,
        "promotable_count": 28,
        "drift_count": 26,
        "drift_rate": 0.481481,
        "threshold_relevant_count": 21,
        "policy_edge_case_count": 1,
        "excluded_manual_override_count": 2,
        "excluded_indexed_pending_count": 3,
        "excluded_fixture_or_test_count": 4,
        "excluded_other_count": 5,
        "manual_review_scope_text": "relevant=21, policy=1, excluded.manual_override=2, excluded.indexed_pending=3, excluded.fixture_or_test=4, excluded.other=5",
        "manual_review_scope_samples_text": "relevant=paper-a, paper-b, paper-c (+1 more) | excluded.manual_override=manual-1, manual-2 | excluded.indexed_pending=indexed-1, indexed-2, indexed-3 (+1 more) | excluded.fixture_or_test=fixture-1",
        "threshold_relevant_sample_ids": ["paper-a", "paper-b", "paper-c"],
        "excluded_manual_override_sample_ids": ["manual-1", "manual-2"],
        "excluded_indexed_pending_sample_ids": ["indexed-1", "indexed-2", "indexed-3"],
        "excluded_fixture_or_test_sample_ids": ["fixture-1"],
        "manual_review_focus_recommendation": "Focus threshold tuning on threshold-relevant rows first.",
        "worksheet_pending_count": 21,
        "worksheet_primary_review_target": "mid_confidence_escalation_policy",
        "worksheet_excluded_count": 9,
        "worksheet_text": "pending=21, target=mid_confidence_escalation_policy, excluded=9",
        "worksheet_summary": "21 threshold-relevant row(s) are queued for mid-confidence escalation policy review; exclude 9 non-threshold row(s) from raw threshold changes.",
        "manual_review_basis_preliminary_call": "mid_confidence_policy_only",
        "manual_review_basis_policy_support_count": 21,
        "manual_review_basis_high_threshold_support_count": 0,
        "manual_review_basis_text": "call=mid_confidence_policy_only, policy=21, high=0",
        "manual_review_basis_summary": "All 21 threshold-relevant row(s) are mid-confidence legacy approvals replaying to pending review; none support a high-threshold boundary change from this evidence alone.",
    }


def test_latest_processor_gate_threshold_review_check_reports_empty_root(monkeypatch):
    monkeypatch.setattr(runtime_readiness, "latest_processor_gate_threshold_review_run", lambda: None)
    monkeypatch.setattr(runtime_readiness, "load_processor_gate_threshold_review_summary", lambda path: None)
    monkeypatch.setattr(
        runtime_readiness,
        "default_processor_gate_threshold_review_root",
        lambda: runtime_readiness.Path("/tmp/processor-gate-threshold-review"),
    )

    check = runtime_readiness._latest_processor_gate_threshold_review_check()

    assert check.name == "latest_processor_gate_threshold_review"
    assert check.status == "ok"
    assert check.path == "/tmp/processor-gate-threshold-review"
    assert check.detail == "no processor gate threshold review runs found yet"
    assert check.metadata == {"available": False}
