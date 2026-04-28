import json
from pathlib import Path

from typer.testing import CliRunner

import src.cli as cli


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def test_show_intake_override_threshold_review_renders_summary(tmp_path: Path) -> None:
    runner = CliRunner()
    run_root = tmp_path / "threshold_review_run"
    _write_json(
        run_root / "summary.json",
        {
            "schema_version": "intake_override_threshold_review.v1",
            "generated_at": "2026-04-21T00:00:00Z",
            "run_id": "threshold_review_test",
            "provenance": {"kind": "operator", "latest_eligible": True},
            "inputs": {
                "audit_root": str(tmp_path / "audits"),
                "warn_threshold": 0.25,
                "min_audited_docs": 3,
                "calibration_target_runs": 3,
            },
                "decision": {
                    "recommended_action": "hold_current_threshold",
                    "review_ready": False,
                    "decision_reason": "only 1 sufficiently-audited run(s) exist, below the 3-run review floor; persistent adjudication signals: slot_adjudication, tagging_adjudication",
                    "next_step": "collect_more_audit_runs",
                    "focus_signals": ["slot_adjudication", "slot", "triage", "tagging_adjudication"],
                    "latest_run_id": "audit_latest",
                    "latest_run_status": "warn",
                    "latest_warn_signals": ["triage", "slot", "slot_adjudication", "tagging_adjudication"],
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
                    "tuning_targets": ["slot_classification", "tagging_first_pass"],
                    "tuning_actions": [
                    {
                        "target": "slot_classification",
                        "action": "audit_slot_ambiguity_thresholds",
                        "summary": "Inspect ambiguity thresholds and evidence-bundle cues before policy changes.",
                    },
                    {
                        "target": "tagging_first_pass",
                        "action": "audit_tagging_first_pass_quality",
                        "summary": "Inspect first-pass tagging robustness, soft-tag formatting, and evidence-span quality before policy changes.",
                    },
                ],
                "action_plan": [
                    {
                        "order": 1,
                        "action": "collect_more_audit_runs",
                        "target": None,
                        "blocking": True,
                        "signals": [],
                        "summary": "Gather more sufficiently-audited runs before promoting this threshold review into manual threshold changes.",
                        "evidence": "1/3 sufficiently-audited runs currently meet the review floor, so threshold changes should stay blocked until more audit evidence accumulates.",
                    },
                    {
                        "order": 2,
                        "action": "audit_slot_ambiguity_thresholds",
                        "target": "slot_classification",
                        "blocking": False,
                        "signals": ["slot_adjudication"],
                        "summary": "Inspect ambiguity thresholds and evidence-bundle cues before policy changes.",
                        "evidence": "Triggered because slot adjudication remains present in the threshold-review focus/latest-warn signals, which points to slot-classification ambiguity rather than a pure threshold-only issue.",
                    },
                    {
                        "order": 3,
                        "action": "audit_tagging_first_pass_quality",
                        "target": "tagging_first_pass",
                        "blocking": False,
                        "signals": ["tagging_adjudication"],
                        "summary": "Inspect first-pass tagging robustness, soft-tag formatting, and evidence-span quality before policy changes.",
                        "evidence": "Triggered because tagging adjudication remains present in the threshold-review focus/latest-warn signals, which points to first-pass tagging robustness rather than a pure threshold-only issue.",
                    },
                ],
                "tuning_recommendations": [
                    "Audit slot-classification ambiguity thresholds and evidence-bundle cues before widening the warning-threshold review policy.",
                    "Audit first-pass tagging robustness, soft-tag formatting, and evidence-span quality before changing warning-threshold heuristics.",
                ],
            },
            "snapshot": {
                "total_runs": 2,
                "eligible_runs": 1,
                "warn_runs": 1,
                "signal_summary": [
                    {
                        "signal": "slot",
                        "latest_rate": 0.5,
                        "max_rate": 0.5,
                        "warn_run_count": 1,
                    }
                ],
                "recommendations": [
                    "Keep the current 25% warning threshold for now.",
                    "Most persistent sufficiently-audited signals: slot (1/1, max 50.0%).",
                ],
            },
        },
    )
    (run_root / "audit.md").write_text("# threshold review markdown\n", encoding="utf-8")

    result = runner.invoke(cli.app, ["show-intake-override-threshold-review", str(run_root)])
    normalized_output = " ".join(result.output.split())

    assert result.exit_code == 0
    assert "Intake Override Threshold Review" in result.output
    assert "threshold_review_test" in result.output
    assert "Markdown:" in result.output
    assert "Provenance: operator" in result.output
    assert "Latest Eligible: yes" in result.output
    assert "hold_current_threshold" in result.output
    assert "collect_more_audit_runs" in result.output
    assert "audit_latest (warn)" in result.output
    assert "slot_adjudication" in result.output
    assert "triage" in result.output
    assert "tagging_adjudication" in result.output
    assert "slot_classification" in result.output
    assert "tagging_first_pass" in result.output
    assert "audit_slot_ambiguity_thresholds" in result.output
    assert "audit_tagging_first_pass_quality" in result.output
    assert "Blocking Action" in result.output
    assert "Blocking Evidence" in result.output
    assert "Blocking Summary" in result.output
    assert "Plan Signals" in result.output
    assert "slot_adjudication" in result.output
    assert "tagging_adjudication" in result.output
    assert "Plan Evidence" in result.output
    assert "collect_more_audit_runs" in result.output
    assert "Audit slot-classification ambiguity thresholds" in result.output
    assert "soft-tag formatting" in result.output
    assert "persistent adjudication" in result.output
    assert "slot_adjudication" in result.output
    assert "tagging_adjudication" in result.output
    assert "Coverage: 2 total | 1 sufficient | 1 warn" in " ".join(result.output.split())
    assert "Keep the current 25% warning threshold for now." in result.output


def test_show_intake_override_threshold_review_supports_json_output(tmp_path: Path) -> None:
    runner = CliRunner()
    summary_path = tmp_path / "threshold_review_run" / "summary.json"
    _write_json(
        summary_path,
        {
            "schema_version": "intake_override_threshold_review.v1",
            "generated_at": "2026-04-21T00:00:00Z",
            "run_id": "threshold_review_json_test",
            "provenance": {"kind": "synthetic", "latest_eligible": False},
            "inputs": {"audit_root": str(tmp_path / "audits")},
            "decision": {"recommended_action": "manual_threshold_review"},
            "snapshot": {"eligible_runs": 3, "warn_runs": 2},
        },
    )
    (summary_path.parent / "audit.md").write_text("# threshold review markdown\n", encoding="utf-8")

    result = runner.invoke(
        cli.app,
        ["show-intake-override-threshold-review", str(summary_path), "--json"],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["run_id"] == "threshold_review_json_test"
    assert payload["markdown_path"].endswith("/threshold_review_run/audit.md")
    assert payload["provenance"]["kind"] == "synthetic"
    assert payload["provenance"]["latest_eligible"] is False
    assert payload["decision"]["recommended_action"] == "manual_threshold_review"
    assert payload["snapshot"]["eligible_runs"] == 3
