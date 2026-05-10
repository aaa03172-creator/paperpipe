from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.eval.run_recommended_deepread_handoff_gate import run_recommended_deepread_handoff_gate


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
    section_warn: int = 0,
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
        "section_navigation_signal_status_counts": {
            "pass": max(run_count - section_warn, 0),
            "warn": section_warn,
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


def test_run_recommended_deepread_handoff_gate_skips_when_not_applicable(tmp_path: Path) -> None:
    run_root = run_recommended_deepread_handoff_gate(
        changed_files=["docs/DEEPREAD_HANDOFF_QUALITY_LOOP.md"],
        coric_new=None,
        multicase_new=None,
        coric_baseline=tmp_path / "coric_baseline",
        multicase_baseline=tmp_path / "multicase_baseline",
        out_dir=tmp_path / "out",
        run_id="docs_only",
    )

    payload = json.loads((run_root / "summary.json").read_text(encoding="utf-8"))
    assert payload["recommendation"]["mode"] == "not_applicable"
    assert payload["gate"]["attempted"] is False
    assert payload["gate"]["path"] is None


def test_run_recommended_deepread_handoff_gate_runs_continuity_gate(tmp_path: Path) -> None:
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

    run_root = run_recommended_deepread_handoff_gate(
        changed_files=["goldset/manifests/deepread_handoff_coric_regression_20260408.json"],
        coric_new=coric_new,
        multicase_new=None,
        coric_baseline=coric_baseline,
        multicase_baseline=multicase_baseline,
        out_dir=tmp_path / "out",
        run_id="continuity",
    )

    payload = json.loads((run_root / "summary.json").read_text(encoding="utf-8"))
    assert payload["recommendation"]["mode"] == "continuity"
    assert payload["gate"]["attempted"] is True
    assert payload["gate"]["passed"] is True
    assert payload["gate"]["mode"] == "continuity"


def test_run_recommended_deepread_handoff_gate_requires_multicase_for_cross_paper(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="multicase_new_required_for_cross_paper"):
        run_recommended_deepread_handoff_gate(
            changed_files=["src/services/deepread_handoff_artifacts.py"],
            coric_new=tmp_path / "coric_new",
            multicase_new=None,
            coric_baseline=tmp_path / "coric_baseline",
            multicase_baseline=tmp_path / "multicase_baseline",
            out_dir=tmp_path / "out",
            run_id="cross_paper_missing",
        )
