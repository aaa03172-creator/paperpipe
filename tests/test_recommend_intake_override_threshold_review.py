from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from scripts.eval.recommend_intake_override_threshold_review import (
    build_intake_override_threshold_review_summary,
    run_intake_override_threshold_review,
)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _audit_summary(
    *,
    run_id: str,
    generated_at: str,
    source: str,
    row_count: int,
    audited_document_count: int,
    triage_override_rate: float,
    slot_disagreement_rate: float,
    selection_fallback_rate: float,
    analysis_unavailable_rate: float,
    issues_state_unavailable_rate: float,
    llm_slot_adjudication_rate: float = 0.0,
    llm_tagging_adjudication_rate: float = 0.0,
) -> dict:
    return {
        "schema_version": "intake_override_audit_summary.v1",
        "generated_at": generated_at,
        "run_id": run_id,
        "inputs": {"source": source, "row_count": row_count},
        "metrics": {
            "audited_document_count": audited_document_count,
            "triage_override_rate": triage_override_rate,
            "slot_disagreement_rate": slot_disagreement_rate,
            "llm_slot_adjudication_rate": llm_slot_adjudication_rate,
            "llm_tagging_adjudication_rate": llm_tagging_adjudication_rate,
            "selection_fallback_rate": selection_fallback_rate,
            "analysis_unavailable_rate": analysis_unavailable_rate,
            "issues_state_unavailable_rate": issues_state_unavailable_rate,
        },
        "producer_metrics": [],
        "documents_with_slot_disagreement": [],
        "documents_with_tag_disagreement": [],
        "documents_with_missing_log": [],
        "documents_with_missing_log_non_fixture": [],
        "documents_with_invalid_log": [],
        "documents_with_selection_context": [],
        "documents_with_selection_fallback": [],
    }


def test_build_intake_override_threshold_review_summary_holds_until_target_runs(tmp_path: Path) -> None:
    audit_root = tmp_path / "audits"
    _write_json(
        audit_root / "audit_latest" / "summary.json",
        _audit_summary(
            run_id="audit_latest",
            generated_at="2026-04-20T05:00:00Z",
            source="rows_jsonl",
            row_count=4,
            audited_document_count=3,
            triage_override_rate=0.3333,
            slot_disagreement_rate=0.5,
            selection_fallback_rate=0.0,
            analysis_unavailable_rate=0.0,
            issues_state_unavailable_rate=0.0,
        ),
    )
    _write_json(
        audit_root / "audit_small" / "summary.json",
        _audit_summary(
            run_id="audit_small",
            generated_at="2026-04-19T05:00:00Z",
            source="runtime_db",
            row_count=8,
            audited_document_count=2,
            triage_override_rate=1.0,
            slot_disagreement_rate=1.0,
            selection_fallback_rate=0.0,
            analysis_unavailable_rate=0.0,
            issues_state_unavailable_rate=0.0,
        ),
    )

    payload = build_intake_override_threshold_review_summary(
        audit_root=audit_root,
        run_id="review_hold",
        warn_threshold=0.25,
        min_audited_docs=3,
        calibration_target_runs=3,
    )

    assert payload["provenance"] == {
        "kind": "operator",
        "latest_eligible": True,
        "producer": "recommend_intake_override_threshold_review",
    }
    assert payload["decision"]["recommended_action"] == "hold_current_threshold"
    assert payload["decision"]["review_ready"] is False
    assert payload["decision"]["next_step"] == "collect_more_audit_runs"
    assert payload["decision"]["latest_run_id"] == "audit_latest"
    assert payload["decision"]["latest_run_status"] == "warn"
    assert payload["decision"]["focus_signals"] == ["slot", "triage"]
    assert payload["decision"]["latest_warn_signals"] == ["triage", "slot"]
    assert payload["decision"]["blocking_summary"] == (
        "1.collect_more_audit_runs: 1/3 sufficiently-audited runs currently meet the review floor, "
        "so threshold changes should stay blocked until more audit evidence accumulates."
    )
    assert payload["decision"]["blocking_action"] == {
        "order": 1,
        "action": "collect_more_audit_runs",
        "target": None,
        "blocking": True,
        "signals": [],
        "summary": "Gather more sufficiently-audited runs before promoting this threshold review into manual threshold changes.",
        "evidence": "1/3 sufficiently-audited runs currently meet the review floor, so threshold changes should stay blocked until more audit evidence accumulates.",
    }
    assert payload["decision"]["tuning_targets"] == []
    assert payload["decision"]["tuning_actions"] == []
    assert payload["decision"]["action_plan"] == [
        {
            "order": 1,
            "action": "collect_more_audit_runs",
            "target": None,
            "blocking": True,
            "signals": [],
            "summary": "Gather more sufficiently-audited runs before promoting this threshold review into manual threshold changes.",
            "evidence": "1/3 sufficiently-audited runs currently meet the review floor, so threshold changes should stay blocked until more audit evidence accumulates.",
        }
    ]
    assert payload["decision"]["tuning_recommendations"] == []
    assert payload["snapshot"]["eligible_runs"] == 1
    assert payload["snapshot"]["warn_runs"] == 1


def test_build_intake_override_threshold_review_summary_becomes_review_ready(tmp_path: Path) -> None:
    audit_root = tmp_path / "audits"
    for idx, generated_at, triage_rate, slot_rate in (
        (1, "2026-04-20T05:00:00Z", 0.3333, 0.5),
        (2, "2026-04-19T05:00:00Z", 0.25, 0.0),
        (3, "2026-04-18T05:00:00Z", 0.0, 0.3),
    ):
        _write_json(
            audit_root / f"audit_{idx}" / "summary.json",
            _audit_summary(
                run_id=f"audit_{idx}",
                generated_at=generated_at,
                source="rows_jsonl",
                row_count=6,
                audited_document_count=3,
                triage_override_rate=triage_rate,
                slot_disagreement_rate=slot_rate,
                selection_fallback_rate=0.0,
                analysis_unavailable_rate=0.0,
                issues_state_unavailable_rate=0.0,
            ),
        )

    payload = build_intake_override_threshold_review_summary(
        audit_root=audit_root,
        run_id="review_ready",
        warn_threshold=0.25,
        min_audited_docs=3,
        calibration_target_runs=3,
        provenance_kind="synthetic",
    )

    assert payload["provenance"] == {
        "kind": "synthetic",
        "latest_eligible": False,
        "producer": "recommend_intake_override_threshold_review",
    }
    assert payload["decision"]["recommended_action"] == "manual_threshold_review"
    assert payload["decision"]["review_ready"] is True
    assert payload["decision"]["next_step"] == "review_warn_threshold_and_sample_floor_manually"
    assert payload["decision"]["blocking_summary"] == (
        "1.review_warn_threshold_and_sample_floor_manually: 3/3 sufficiently-audited runs meet the review floor, "
        "so manual threshold review can proceed if operators agree with the evidence."
    )
    assert "meet the 3-run review floor" in payload["decision"]["decision_reason"]
    assert payload["snapshot"]["eligible_runs"] == 3


def test_build_intake_override_threshold_review_summary_surfaces_persistent_adjudication_signals(tmp_path: Path) -> None:
    audit_root = tmp_path / "audits"
    _write_json(
        audit_root / "audit_latest" / "summary.json",
        _audit_summary(
            run_id="audit_latest",
            generated_at="2026-04-20T05:00:00Z",
            source="rows_jsonl",
            row_count=4,
            audited_document_count=3,
            triage_override_rate=0.3333,
            slot_disagreement_rate=0.5,
            llm_slot_adjudication_rate=0.5,
            llm_tagging_adjudication_rate=0.25,
            selection_fallback_rate=0.0,
            analysis_unavailable_rate=0.0,
            issues_state_unavailable_rate=0.0,
        ),
    )

    payload = build_intake_override_threshold_review_summary(
        audit_root=audit_root,
        run_id="review_adjudication_focus",
        warn_threshold=0.25,
        min_audited_docs=3,
        calibration_target_runs=3,
    )

    assert payload["decision"]["focus_signals"] == ["slot_adjudication", "slot", "triage", "tagging_adjudication"]
    assert payload["decision"]["latest_warn_signals"] == [
        "triage",
        "slot",
        "slot_adjudication",
        "tagging_adjudication",
    ]
    assert payload["decision"]["blocking_summary"] == (
        "1.collect_more_audit_runs: 1/3 sufficiently-audited runs currently meet the review floor, "
        "so threshold changes should stay blocked until more audit evidence accumulates."
    )
    assert payload["decision"]["blocking_action"] == {
        "order": 1,
        "action": "collect_more_audit_runs",
        "target": None,
        "blocking": True,
        "signals": [],
        "summary": "Gather more sufficiently-audited runs before promoting this threshold review into manual threshold changes.",
        "evidence": "1/3 sufficiently-audited runs currently meet the review floor, so threshold changes should stay blocked until more audit evidence accumulates.",
    }
    assert payload["decision"]["tuning_targets"] == [
        "slot_classification",
        "tagging_first_pass",
    ]
    assert payload["decision"]["tuning_actions"] == [
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
    ]
    assert payload["decision"]["action_plan"] == [
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
    ]
    assert payload["decision"]["tuning_recommendations"] == [
        "Audit slot-classification ambiguity thresholds and evidence-bundle cues before widening the warning-threshold review policy.",
        "Audit first-pass tagging robustness, soft-tag formatting, and evidence-span quality before changing warning-threshold heuristics.",
    ]
    assert "persistent adjudication signals: slot_adjudication, tagging_adjudication" in payload["decision"]["decision_reason"]


def test_run_intake_override_threshold_review_writes_summary_and_cli_runs(tmp_path: Path) -> None:
    audit_root = tmp_path / "audits"
    _write_json(
        audit_root / "audit_latest" / "summary.json",
        _audit_summary(
            run_id="audit_latest",
            generated_at="2026-04-20T05:00:00Z",
            source="rows_jsonl",
            row_count=4,
            audited_document_count=3,
            triage_override_rate=0.3333,
            slot_disagreement_rate=0.5,
            selection_fallback_rate=0.0,
            analysis_unavailable_rate=0.0,
            issues_state_unavailable_rate=0.0,
        ),
    )

    run_root = run_intake_override_threshold_review(
        audit_root=audit_root,
        out_dir=tmp_path / "out",
        run_id="review_python",
        warn_threshold=0.25,
        min_audited_docs=3,
        calibration_target_runs=3,
    )
    payload = json.loads((run_root / "summary.json").read_text(encoding="utf-8"))
    markdown = (run_root / "audit.md").read_text(encoding="utf-8")
    assert payload["run_id"] == "review_python"
    assert payload["provenance"]["kind"] == "operator"
    assert payload["provenance"]["latest_eligible"] is True
    assert payload["decision"]["recommended_action"] == "hold_current_threshold"
    assert "# Intake Override Threshold Review: review_python" in markdown
    assert "## Action Plan" in markdown
    assert "`collect_more_audit_runs`" in markdown
    assert "Blocking Action:" in markdown
    assert "Blocking Evidence:" in markdown
    assert "Blocking Summary:" in markdown
    assert "Evidence: 1/3 sufficiently-audited runs currently meet the review floor" in markdown

    script = Path(__file__).resolve().parents[1] / "scripts" / "eval" / "recommend_intake_override_threshold_review.py"
    cli_out_dir = tmp_path / "cli_out"
    completed = subprocess.run(
        [
            sys.executable,
            str(script),
            "--audit-root",
            str(audit_root),
            "--out-dir",
            str(cli_out_dir),
            "--run-id",
            "review_cli",
            "--provenance-kind",
            "synthetic",
        ],
        cwd=Path(__file__).resolve().parents[1],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    normalized_stderr = " ".join(completed.stderr.split())
    assert completed.stdout.strip() == str(cli_out_dir / "review_cli")
    assert "[recommend_intake_override_threshold_review]" in completed.stderr
    assert "review_ready=False" in normalized_stderr
    assert "action=hold_current_threshold" in normalized_stderr
    assert "latest_run_status=warn" in normalized_stderr
    assert "eligible_runs=1/3" in normalized_stderr
    assert "provenance=synthetic" in normalized_stderr
    assert "latest_eligible=False" in normalized_stderr
    assert "latest_run=audit_latest" in normalized_stderr
    cli_payload = json.loads((cli_out_dir / "review_cli" / "summary.json").read_text(encoding="utf-8"))
    cli_markdown = (cli_out_dir / "review_cli" / "audit.md").read_text(encoding="utf-8")
    assert cli_payload["provenance"]["kind"] == "synthetic"
    assert cli_payload["provenance"]["latest_eligible"] is False
    assert cli_payload["decision"]["recommended_action"] == "hold_current_threshold"
    assert cli_payload["inputs"]["audit_root"].endswith("/audits")
    assert "# Intake Override Threshold Review: review_cli" in cli_markdown
    assert "## Operator Flow" in cli_markdown
    assert "show-intake-override-threshold-review" in cli_markdown
    assert "## Action Plan" in cli_markdown


def test_threshold_review_script_help_mentions_latest_eligible_guidance() -> None:
    script = Path(__file__).resolve().parents[1] / "scripts" / "eval" / "recommend_intake_override_threshold_review.py"
    completed = subprocess.run(
        [sys.executable, str(script), "--help"],
        cwd=Path(__file__).resolve().parents[1],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    normalized_stdout = " ".join(completed.stdout.split())
    assert "--latest-eligible" in completed.stdout
    assert "--not-latest-eligible" in completed.stdout
    assert "--provenance-kind synthetic" in normalized_stdout
    assert "stay out of operator-facing latest selection" in normalized_stdout
