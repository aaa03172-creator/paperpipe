from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.eval.check_deepread_handoff_gate import (
    build_deepread_handoff_gate_summary,
    run_deepread_handoff_gate,
)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _summary(
    *,
    run_id: str,
    run_count: int,
    review_ready_count: int,
    goal_warn: int,
    step_warn: int,
    recovery_warn: int,
    goal_missing: int = 0,
    step_missing: int = 0,
    recovery_missing: int = 0,
    context_missing: int,
) -> dict:
    return {
        "schema_version": "deepread_handoff_audit.v1",
        "run_id": run_id,
        "run_count": run_count,
        "review_ready_count": review_ready_count,
        "promotion_candidate_count": run_count,
        "context_manifest_missing_count": context_missing,
        "overall_status_counts": {"pass": review_ready_count, "warn": max(run_count - review_ready_count, 0)},
        "goal_drift_status_counts": {
            "pass": max(run_count - goal_warn - goal_missing, 0),
            "warn": goal_warn,
            **({"missing": goal_missing} if goal_missing else {}),
        },
        "step_stability_status_counts": {
            "pass": max(run_count - step_warn - step_missing, 0),
            "warn": step_warn,
            **({"missing": step_missing} if step_missing else {}),
        },
        "failure_recovery_status_counts": {
            "pass": max(run_count - recovery_warn - recovery_missing, 0),
            "warn": recovery_warn,
            **({"missing": recovery_missing} if recovery_missing else {}),
        },
    }


def test_build_deepread_handoff_gate_summary_requires_expected_cases() -> None:
    with pytest.raises(ValueError, match="missing_case_reports=multicase"):
        build_deepread_handoff_gate_summary(
            mode="cross-paper",
            case_reports={"coric": {"decision": {"passed": True}}},
            run_id="missing_multicase",
        )


def test_run_deepread_handoff_gate_continuity_runs_coric_only(tmp_path: Path) -> None:
    coric_baseline = tmp_path / "coric_baseline"
    coric_new = tmp_path / "coric_new"
    multicase_baseline = tmp_path / "multicase_baseline"

    _write_json(
        coric_baseline / "summary.json",
        _summary(
            run_id="coric_baseline",
            run_count=10,
            review_ready_count=7,
            goal_warn=1,
            step_warn=2,
            recovery_warn=0,
            context_missing=1,
        ),
    )
    _write_json(
        coric_new / "summary.json",
        _summary(
            run_id="coric_new",
            run_count=10,
            review_ready_count=8,
            goal_warn=1,
            step_warn=1,
            recovery_warn=0,
            context_missing=1,
        ),
    )
    _write_json(
        multicase_baseline / "summary.json",
        _summary(
            run_id="multicase_baseline",
            run_count=8,
            review_ready_count=1,
            goal_warn=1,
            step_warn=6,
            recovery_warn=0,
            context_missing=0,
        ),
    )

    run_root = run_deepread_handoff_gate(
        mode="continuity",
        coric_baseline=coric_baseline,
        coric_new=coric_new,
        multicase_baseline=multicase_baseline,
        multicase_new=None,
        out_dir=tmp_path / "out",
        run_id="continuity_gate",
    )

    payload = json.loads((run_root / "summary.json").read_text(encoding="utf-8"))
    assert payload["decision"]["passed"] is True
    assert payload["decision"]["required_cases"] == ["coric"]
    assert payload["decision"]["failed_cases"] == []
    assert payload["cases"]["coric"]["passed"] is True
    assert "multicase" not in payload["cases"]
    assert (run_root / "cases" / "coric" / "report.json").exists()


def test_run_deepread_handoff_gate_cross_paper_requires_multicase_and_fails_on_regression(tmp_path: Path) -> None:
    coric_baseline = tmp_path / "coric_baseline"
    coric_new = tmp_path / "coric_new"
    multicase_baseline = tmp_path / "multicase_baseline"
    multicase_new = tmp_path / "multicase_new"

    _write_json(
        coric_baseline / "summary.json",
        _summary(
            run_id="coric_baseline",
            run_count=10,
            review_ready_count=7,
            goal_warn=1,
            step_warn=2,
            recovery_warn=0,
            context_missing=1,
        ),
    )
    _write_json(
        coric_new / "summary.json",
        _summary(
            run_id="coric_new",
            run_count=10,
            review_ready_count=7,
            goal_warn=1,
            step_warn=2,
            recovery_warn=0,
            context_missing=1,
        ),
    )
    _write_json(
        multicase_baseline / "summary.json",
        _summary(
            run_id="multicase_baseline",
            run_count=8,
            review_ready_count=1,
            goal_warn=1,
            step_warn=6,
            recovery_warn=0,
            context_missing=0,
        ),
    )
    _write_json(
        multicase_new / "summary.json",
        _summary(
            run_id="multicase_new",
            run_count=8,
            review_ready_count=0,
            goal_warn=3,
            step_warn=6,
            recovery_warn=1,
            context_missing=1,
        ),
    )

    run_root = run_deepread_handoff_gate(
        mode="cross-paper",
        coric_baseline=coric_baseline,
        coric_new=coric_new,
        multicase_baseline=multicase_baseline,
        multicase_new=multicase_new,
        out_dir=tmp_path / "out",
        run_id="cross_paper_gate",
    )

    payload = json.loads((run_root / "summary.json").read_text(encoding="utf-8"))
    assert payload["decision"]["passed"] is False
    assert payload["decision"]["required_cases"] == ["coric", "multicase"]
    assert payload["decision"]["failed_cases"] == ["multicase"]
    assert payload["cases"]["coric"]["passed"] is True
    assert payload["cases"]["multicase"]["passed"] is False
    assert "review_ready_rate" in payload["cases"]["multicase"]["failed_checks"]
    assert (run_root / "cases" / "coric" / "report.json").exists()
    assert (run_root / "cases" / "multicase" / "report.json").exists()


def test_run_deepread_handoff_gate_rejects_cross_paper_without_multicase_input(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="multicase_new_required_for_cross_paper"):
        run_deepread_handoff_gate(
            mode="cross-paper",
            coric_baseline=tmp_path / "coric_baseline",
            coric_new=tmp_path / "coric_new",
            multicase_baseline=tmp_path / "multicase_baseline",
            multicase_new=None,
            out_dir=tmp_path / "out",
            run_id="cross_paper_missing_multicase",
        )
