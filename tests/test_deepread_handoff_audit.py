import json
from pathlib import Path

from scripts.eval.audit_deepread_handoff import load_manifest_run_dirs, run_audit


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def test_run_audit_aggregates_handoff_statuses(tmp_path: Path) -> None:
    run_a = tmp_path / "runs" / "run_a"
    run_b = tmp_path / "runs" / "run_b"

    _write_json(
        run_a / "quality_gate.json",
        {
            "paper_id": "paper-a",
            "run_id": "run-a",
            "overall_status": "pass",
            "current_promotion_candidate": True,
            "review_ready": True,
            "reason_codes": [],
            "hard_fail_codes": [],
            "checks": [{"name": "section_navigation_signal", "status": "pass", "detail": "ok"}],
            "step_stability_summary": {"status": "pass", "reason_codes": [], "detail": "ok"},
            "failure_recovery_summary": {"status": "pass", "reason_codes": [], "detail": "ok"},
        },
    )
    _write_json(
        run_a / "context_manifest.json",
        {
            "paper_id": "paper-a",
            "run_id": "run-a",
            "goal_drift_summary": {"status": "pass", "reason_codes": [], "detail": "ok"},
        },
    )

    _write_json(
        run_b / "quality_gate.json",
        {
            "paper_id": "paper-b",
            "run_id": "run-b",
            "overall_status": "fail",
            "current_promotion_candidate": False,
            "review_ready": False,
            "reason_codes": ["RUN_NOT_SUCCEEDED"],
            "hard_fail_codes": ["RUN_NOT_SUCCEEDED"],
            "checks": [{"name": "section_navigation_signal", "status": "warn", "detail": "missing"}],
            "step_stability_summary": {
                "status": "fail",
                "reason_codes": ["RUN_NOT_SUCCEEDED", "READER_TIMEOUT_TRIGGERED"],
                "detail": "unstable",
            },
            "failure_recovery_summary": {
                "status": "warn",
                "reason_codes": ["MISSING_RECOVERY_GUIDANCE"],
                "detail": "warning",
            },
        },
    )
    _write_json(
        run_b / "context_manifest.json",
        {
            "paper_id": "paper-b",
            "run_id": "run-b",
            "goal_drift_summary": {
                "status": "warn",
                "reason_codes": ["HEURISTIC_FALLBACK_USED"],
                "detail": "drift",
            },
        },
    )

    run_root = run_audit(
        run_dirs=[run_a, run_b],
        out_dir=tmp_path / "out",
        run_id="audit_001",
    )

    summary = json.loads((run_root / "summary.json").read_text(encoding="utf-8"))
    details = json.loads((run_root / "details.json").read_text(encoding="utf-8"))

    assert summary["run_count"] == 2
    assert summary["overall_status_counts"] == {"fail": 1, "pass": 1}
    assert summary["step_stability_status_counts"] == {"fail": 1, "pass": 1}
    assert summary["failure_recovery_status_counts"] == {"pass": 1, "warn": 1}
    assert summary["goal_drift_status_counts"] == {"pass": 1, "warn": 1}
    assert summary["section_navigation_signal_status_counts"] == {"pass": 1, "warn": 1}
    assert summary["review_ready_count"] == 1
    assert summary["promotion_candidate_count"] == 1
    assert summary["runs_with_goal_drift_warn"] == ["run-b"]
    assert summary["runs_with_section_navigation_signal_warn_or_fail"] == ["run-b"]
    assert summary["runs_with_step_stability_warn_or_fail"] == ["run-b"]
    assert summary["runs_with_failure_recovery_warn_or_fail"] == ["run-b"]
    assert summary["reason_code_counts"]["RUN_NOT_SUCCEEDED"] == 2
    assert summary["reason_code_counts"]["READER_TIMEOUT_TRIGGERED"] == 1
    assert summary["reason_code_counts"]["HEURISTIC_FALLBACK_USED"] == 1
    assert summary["reason_code_counts"]["MISSING_RECOVERY_GUIDANCE"] == 1
    assert summary["hard_fail_code_counts"] == {"RUN_NOT_SUCCEEDED": 1}
    assert [row["run_id"] for row in details["runs"]] == ["run-a", "run-b"]


def test_run_audit_marks_missing_context_manifest(tmp_path: Path) -> None:
    run_dir = tmp_path / "runs" / "run_only"
    _write_json(
        run_dir / "quality_gate.json",
        {
            "paper_id": "paper-only",
            "run_id": "run-only",
            "overall_status": "warn",
            "current_promotion_candidate": True,
            "review_ready": False,
            "reason_codes": ["CLAIMSET_NOT_READY"],
            "hard_fail_codes": [],
            "checks": [],
            "step_stability_summary": {"status": "warn", "reason_codes": ["HEURISTIC_FALLBACK_USED"], "detail": "warn"},
            "failure_recovery_summary": {"status": "pass", "reason_codes": [], "detail": "ok"},
        },
    )

    run_root = run_audit(
        run_dirs=[run_dir],
        out_dir=tmp_path / "out",
        run_id="audit_missing_manifest",
    )
    summary = json.loads((run_root / "summary.json").read_text(encoding="utf-8"))
    details = json.loads((run_root / "details.json").read_text(encoding="utf-8"))

    assert summary["context_manifest_missing_count"] == 1
    assert summary["goal_drift_status_counts"] == {"missing": 1}
    assert summary["section_navigation_signal_status_counts"] == {"missing": 1}
    assert details["runs"][0]["context_manifest_present"] is False
    assert details["runs"][0]["goal_drift_status"] == "missing"
    assert details["runs"][0]["section_navigation_signal_status"] == "missing"


def test_run_audit_records_manifest_inputs_and_loads_run_dirs(tmp_path: Path) -> None:
    run_dir = tmp_path / "runs" / "run_manifest"
    manifest_path = tmp_path / "manifests" / "deepread_manifest.json"

    _write_json(
        run_dir / "quality_gate.json",
        {
            "paper_id": "paper-manifest",
            "run_id": "run-manifest",
            "overall_status": "pass",
            "current_promotion_candidate": True,
            "review_ready": True,
            "reason_codes": [],
            "hard_fail_codes": [],
            "checks": [{"name": "section_navigation_signal", "status": "pass", "detail": "ok"}],
            "step_stability_summary": {"status": "pass", "reason_codes": [], "detail": "ok"},
            "failure_recovery_summary": {"status": "pass", "reason_codes": [], "detail": "ok"},
        },
    )
    _write_json(
        run_dir / "context_manifest.json",
        {
            "paper_id": "paper-manifest",
            "run_id": "run-manifest",
            "goal_drift_summary": {"status": "pass", "reason_codes": [], "detail": "ok"},
        },
    )
    _write_json(
        manifest_path,
        {
            "schema_version": "deepread_handoff_manifest.v1",
            "manifest_batch_id": "deepread_manifest_test",
            "runs": [
                {
                    "run_id": "run-manifest",
                    "paper_id": "paper-manifest",
                    "run_dir": str(run_dir),
                    "notes": "Repo-grounded saved handoff run.",
                }
            ],
        },
    )

    loaded_run_dirs = load_manifest_run_dirs(manifest_path)
    assert loaded_run_dirs == [run_dir.resolve()]

    run_root = run_audit(
        run_dirs=loaded_run_dirs,
        out_dir=tmp_path / "out",
        run_id="audit_manifest_inputs",
        manifest_paths=[manifest_path],
    )

    summary = json.loads((run_root / "summary.json").read_text(encoding="utf-8"))
    assert summary["inputs"]["manifest_count"] == 1
    assert summary["inputs"]["manifests"] == [str(manifest_path.resolve())]
    assert summary["inputs"]["run_dir_count"] == 1


def test_load_manifest_run_dirs_remaps_repo_root_for_absolute_paths(tmp_path: Path) -> None:
    current_repo_root = tmp_path / "checkout" / "paperpipe"
    manifest_path = current_repo_root / "goldset" / "manifests" / "deepread_manifest.json"
    run_dir = current_repo_root / "storage" / "artifacts" / "paper-a" / "run_001"

    run_dir.mkdir(parents=True, exist_ok=True)
    _write_json(
        manifest_path,
        {
            "schema_version": "deepread_handoff_manifest.v1",
            "manifest_batch_id": "deepread_manifest_remap_test",
            "runs": [
                {
                    "run_id": "run-001",
                    "paper_id": "paper-a",
                    "run_dir": "/Users/jangseongjin/paperpipe/storage/artifacts/paper-a/run_001",
                    "notes": "Absolute path should remap onto the current checkout root.",
                }
            ],
        },
    )

    loaded_run_dirs = load_manifest_run_dirs(manifest_path, repo_root=current_repo_root)

    assert loaded_run_dirs == [run_dir.resolve()]
