from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from src.services.slot_classification_tuning_review import (
    build_slot_classification_tuning_review_summary,
    latest_slot_classification_tuning_review_run,
    run_slot_classification_tuning_review,
)


def test_build_slot_classification_tuning_review_blocks_on_regression_and_rerun_drift() -> None:
    payload = build_slot_classification_tuning_review_summary(
        paired_compare_summary=_paired_compare_summary(
            run_id="slot_compare",
            passed=False,
            failed_checks=["default_template_accuracy"],
            regressions=["default_template_accuracy"],
            error_migration_detected=True,
        ),
        paired_compare_summary_path=Path("/tmp/slot_compare/summary.json"),
        default_rerun_drift_summary=_rerun_drift_summary(
            run_id="default_rerun",
            drift_count=1,
            drift_rate=0.0909,
        ),
        default_rerun_drift_summary_path=Path("/tmp/default_rerun/summary.json"),
        boundary_rerun_drift_summary=_rerun_drift_summary(
            run_id="boundary_rerun",
            drift_count=1,
            drift_rate=0.25,
        ),
        boundary_rerun_drift_summary_path=Path("/tmp/boundary_rerun/summary.json"),
        run_id="slot_tuning_review_test",
        max_default_rerun_drift_rate=0.0,
        max_boundary_rerun_drift_rate=0.0,
    )

    decision = payload["decision"]
    assert decision["recommended_action"] == "hold_current_prompt_policy"
    assert decision["review_ready"] is False
    assert decision["paired_compare_status"] == "regressed"
    assert decision["default_rerun_status"] == "warn"
    assert decision["boundary_rerun_status"] == "warn"
    assert decision["prompt_change_ready"] is False
    assert decision["tuning_targets"] == ["slot_classification"]
    assert decision["action_plan"][0]["action"] == "hold_current_prompt_policy"
    assert any(item["action"] == "collect_boundary_rerun_stability_evidence" for item in decision["action_plan"])


def test_slot_classification_tuning_review_script_writes_snapshot(tmp_path: Path) -> None:
    paired_compare_run = _write_json(
        tmp_path / "paired" / "summary.json",
        _paired_compare_summary(
            run_id="slot_compare_pass",
            passed=True,
            failed_checks=[],
            regressions=[],
            error_migration_detected=False,
        ),
    )
    default_rerun_run = _write_json(
        tmp_path / "default_rerun" / "summary.json",
        _rerun_drift_summary(run_id="default_rerun_pass", drift_count=0, drift_rate=0.0),
    )
    boundary_rerun_run = _write_json(
        tmp_path / "boundary_rerun" / "summary.json",
        _rerun_drift_summary(run_id="boundary_rerun_pass", drift_count=0, drift_rate=0.0),
    )

    run_root = run_slot_classification_tuning_review(
        paired_compare_summary_path=paired_compare_run.parent,
        default_rerun_drift_summary_path=default_rerun_run.parent,
        boundary_rerun_drift_summary_path=boundary_rerun_run.parent,
        out_dir=tmp_path / "out",
        run_id="slot_tuning_review_fixture",
        max_default_rerun_drift_rate=0.0,
        max_boundary_rerun_drift_rate=0.0,
    )

    assert run_root == tmp_path / "out" / "slot_tuning_review_fixture"
    summary = json.loads((run_root / "summary.json").read_text(encoding="utf-8"))
    assert summary["decision"]["review_ready"] is True
    assert summary["decision"]["recommended_action"] == "manual_slot_tuning_review"
    markdown = (run_root / "audit.md").read_text(encoding="utf-8")
    assert "- Review Ready: True" in markdown
    assert "- Recommended Action: manual_slot_tuning_review" in markdown


def test_latest_slot_classification_tuning_review_run_prefers_generated_at_over_name_tiebreak(
    tmp_path: Path,
) -> None:
    review_root = tmp_path / "snapshots" / "slot_classification_tuning_review"
    earlier_run = _write_json(
        review_root
        / "slot_classification_tuning_review_prompt_policy_20260422_r1"
        / "summary.json",
        {
            "schema_version": "slot_classification_tuning_review.v1",
            "generated_at": "2026-04-22T01:49:08.825091Z",
            "run_id": "slot_classification_tuning_review_prompt_policy_20260422_r1",
            "decision": {"recommended_action": "review_boundary_rubric_and_expand_goldset"},
        },
    )
    later_run = _write_json(
        review_root / "slot_classification_tuning_review_20260422_r1" / "summary.json",
        {
            "schema_version": "slot_classification_tuning_review.v1",
            "generated_at": "2026-04-22T01:49:08.825177Z",
            "run_id": "slot_classification_tuning_review_20260422_r1",
            "decision": {"recommended_action": "hold_current_prompt_policy"},
        },
    )

    os.utime(earlier_run, (100, 100))
    os.utime(later_run, (100, 100))

    latest_run = latest_slot_classification_tuning_review_run(review_root)

    assert latest_run == later_run.parent


def test_tuning_review_script_emits_compact_status_on_stderr(tmp_path: Path) -> None:
    paired_compare_run = _write_json(
        tmp_path / "paired" / "summary.json",
        _paired_compare_summary(
            run_id="slot_compare_regressed",
            passed=False,
            failed_checks=["default_template_accuracy"],
            regressions=["default_template_accuracy"],
            error_migration_detected=True,
        ),
    )
    default_rerun_run = _write_json(
        tmp_path / "default_rerun" / "summary.json",
        _rerun_drift_summary(run_id="default_rerun_warn", drift_count=1, drift_rate=0.0909),
    )
    boundary_rerun_run = _write_json(
        tmp_path / "boundary_rerun" / "summary.json",
        _rerun_drift_summary(run_id="boundary_rerun_warn", drift_count=1, drift_rate=0.25),
    )

    script = Path(__file__).resolve().parents[1] / "scripts" / "eval" / "recommend_slot_classification_tuning_review.py"
    completed = subprocess.run(
        [
            sys.executable,
            str(script),
            "--paired-compare-summary",
            str(paired_compare_run.parent),
            "--default-rerun-drift-summary",
            str(default_rerun_run.parent),
            "--boundary-rerun-drift-summary",
            str(boundary_rerun_run.parent),
            "--out-dir",
            str(tmp_path / "out"),
            "--run-id",
            "slot_tuning_review_cli",
        ],
        cwd=Path(__file__).resolve().parents[1],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    emitted = json.loads(completed.stdout)
    normalized_stderr = " ".join(completed.stderr.split())
    assert emitted["run_root"] == str((tmp_path / "out") / "slot_tuning_review_cli")
    assert emitted["summary_path"] == str((tmp_path / "out") / "slot_tuning_review_cli" / "summary.json")
    assert emitted["markdown_path"] == str((tmp_path / "out") / "slot_tuning_review_cli" / "audit.md")
    assert "[recommend_slot_classification_tuning_review]" in completed.stderr
    assert "review_ready=False" in normalized_stderr
    assert "action=hold_current_prompt_policy" in normalized_stderr
    assert "paired_compare=regressed" in normalized_stderr
    assert "default_rerun=warn" in normalized_stderr
    assert "boundary_rerun=warn" in normalized_stderr
    assert "compare_run=slot_compare_regressed" in normalized_stderr


def _paired_compare_summary(
    *,
    run_id: str,
    passed: bool,
    failed_checks: list[str],
    regressions: list[str],
    error_migration_detected: bool,
) -> dict:
    return {
        "schema_version": "slot_classification_paired_compare.v1",
        "generated_at": "2026-04-22T00:00:00Z",
        "run_id": run_id,
        "decision": {
            "passed": passed,
            "failed_checks": failed_checks,
            "regressions": regressions,
            "error_migration_detected": error_migration_detected,
            "tradeoff_review_required": error_migration_detected,
        },
    }


def _rerun_drift_summary(*, run_id: str, drift_count: int, drift_rate: float) -> dict:
    return {
        "schema_version": "slot_classification_rerun_drift.v1",
        "generated_at": "2026-04-22T00:00:00Z",
        "run_id": run_id,
        "metrics": {
            "document_count": 4,
            "drift_count": drift_count,
            "drift_rate": drift_rate,
            "mismatch_status_changed_count": 0,
            "predicted_slot_changed_count": drift_count,
            "prediction_status_changed_count": 0,
            "missing_in_prior_count": 0,
            "missing_in_new_count": 0,
        },
    }


def _write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path
