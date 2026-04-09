import json
from pathlib import Path

from scripts.eval.compare_deepread_handoff_audits import compare_deepread_handoff_audits


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


def test_compare_deepread_handoff_audits_passes_and_promotes(tmp_path: Path) -> None:
    baseline_dir = tmp_path / "baseline"
    new_dir = tmp_path / "new"
    promote_dir = tmp_path / "promoted"
    out = tmp_path / "compare" / "report.json"

    _write_json(
        baseline_dir / "summary.json",
        _summary(
            run_id="baseline",
            run_count=10,
            review_ready_count=7,
            goal_warn=3,
            step_warn=2,
            recovery_warn=1,
            context_missing=2,
        ),
    )
    _write_json(baseline_dir / "details.json", {"runs": []})
    _write_json(
        new_dir / "summary.json",
        _summary(
            run_id="new",
            run_count=10,
            review_ready_count=8,
            goal_warn=2,
            step_warn=1,
            recovery_warn=1,
            context_missing=1,
        ),
    )
    _write_json(new_dir / "details.json", {"runs": []})

    report = compare_deepread_handoff_audits(
        baseline=baseline_dir,
        new=new_dir,
        out=out,
        promote_dir=promote_dir,
    )

    assert report["decision"]["passed"] is True
    assert report["promotion"]["promoted"] is True
    promoted_dir = Path(report["promotion"]["path"])
    assert (promoted_dir / "summary.json").exists()
    assert (promoted_dir / "details.json").exists()
    assert report["decision"]["failed_checks"] == []


def test_compare_deepread_handoff_audits_rejects_regression(tmp_path: Path) -> None:
    baseline_dir = tmp_path / "baseline"
    new_dir = tmp_path / "new"
    out = tmp_path / "compare" / "report.json"

    _write_json(
        baseline_dir / "summary.json",
        _summary(
            run_id="baseline",
            run_count=10,
            review_ready_count=8,
            goal_warn=1,
            step_warn=1,
            recovery_warn=0,
            context_missing=0,
        ),
    )
    _write_json(
        new_dir / "summary.json",
        _summary(
            run_id="new",
            run_count=10,
            review_ready_count=6,
            goal_warn=3,
            step_warn=2,
            recovery_warn=2,
            context_missing=1,
        ),
    )

    report = compare_deepread_handoff_audits(
        baseline=baseline_dir,
        new=new_dir,
        out=out,
    )

    assert report["decision"]["passed"] is False
    assert "review_ready_rate" in report["decision"]["failed_checks"]
    assert "goal_drift_warn_or_fail_rate" in report["decision"]["failed_checks"]
    assert "step_stability_warn_or_fail_rate" in report["decision"]["failed_checks"]
    assert "failure_recovery_warn_or_fail_rate" in report["decision"]["failed_checks"]
    assert "context_manifest_missing_rate" in report["decision"]["failed_checks"]


def test_compare_deepread_handoff_audits_rejects_missing_summary_regression(tmp_path: Path) -> None:
    baseline_dir = tmp_path / "baseline"
    new_dir = tmp_path / "new"
    out = tmp_path / "compare" / "report.json"

    _write_json(
        baseline_dir / "summary.json",
        _summary(
            run_id="baseline",
            run_count=10,
            review_ready_count=8,
            goal_warn=1,
            step_warn=1,
            recovery_warn=1,
            goal_missing=0,
            step_missing=0,
            recovery_missing=0,
            context_missing=0,
        ),
    )
    _write_json(
        new_dir / "summary.json",
        _summary(
            run_id="new",
            run_count=10,
            review_ready_count=8,
            goal_warn=1,
            step_warn=1,
            recovery_warn=1,
            goal_missing=2,
            step_missing=3,
            recovery_missing=1,
            context_missing=0,
        ),
    )

    report = compare_deepread_handoff_audits(
        baseline=baseline_dir,
        new=new_dir,
        out=out,
    )

    assert report["decision"]["passed"] is False
    assert "goal_drift_missing_rate" in report["decision"]["failed_checks"]
    assert "step_stability_missing_rate" in report["decision"]["failed_checks"]
    assert "failure_recovery_missing_rate" in report["decision"]["failed_checks"]
