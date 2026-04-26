from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from scripts.eval.check_slot_classification_tuning_visibility import (
    build_slot_classification_tuning_visibility_summary,
    run_slot_classification_tuning_visibility,
)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _internal_data_summary(
    *,
    run_id: str,
    surface_status: str,
    category_status: str,
    include_decision: bool = True,
    include_summary_path: bool = True,
    recommended_action: str | None = "hold_current_prompt_policy",
) -> dict:
    surface: dict[str, object] = {
        "status": surface_status,
        "summary_path": "/tmp/slot_tuning_review/summary.json" if include_summary_path else None,
        "markdown_path": "/tmp/slot_tuning_review/audit.md",
    }
    if include_decision:
        surface["decision"] = {
            "recommended_action": recommended_action,
            "review_ready": category_status == "review_ready",
        }
    return {
        "schema_version": "internal_data_readiness.v1",
        "generated_at": "2026-04-22T02:50:00Z",
        "run_id": run_id,
        "surfaces": {
            "slot_classification_tuning_review": surface,
        },
        "category_status": {
            "classification_tuning_review": category_status,
        },
    }


def test_build_slot_classification_tuning_visibility_summary_passes_for_advisory_hold() -> None:
    payload = build_slot_classification_tuning_visibility_summary(
        internal_data_readiness_summary=_internal_data_summary(
            run_id="internal_data_visible",
            surface_status="present",
            category_status="advisory_hold",
        ),
        internal_data_readiness_summary_path=Path("/tmp/internal_data/summary.json"),
        run_id="slot_tuning_visibility_pass",
        allowed_category_statuses=["advisory_hold", "review_ready"],
    )

    assert payload["decision"]["passed"] is True
    assert payload["decision"]["report_visible"] is True
    assert payload["decision"]["blockers"] == []
    assert payload["inputs"]["classification_tuning_review_status"] == "advisory_hold"


def test_build_slot_classification_tuning_visibility_summary_fails_when_surface_is_missing() -> None:
    payload = build_slot_classification_tuning_visibility_summary(
        internal_data_readiness_summary=_internal_data_summary(
            run_id="internal_data_missing",
            surface_status="missing",
            category_status="missing",
            include_decision=False,
            include_summary_path=False,
            recommended_action=None,
        ),
        internal_data_readiness_summary_path=Path("/tmp/internal_data/summary.json"),
        run_id="slot_tuning_visibility_fail",
        allowed_category_statuses=["advisory_hold", "review_ready"],
    )

    assert payload["decision"]["passed"] is False
    assert payload["decision"]["blockers"] == [
        "slot_classification_tuning_review_surface_not_present",
        "classification_tuning_review_category_not_report_visible",
        "slot_classification_tuning_review_decision_missing",
        "slot_classification_tuning_review_summary_path_missing",
        "slot_classification_tuning_review_action_missing",
    ]


def test_run_slot_classification_tuning_visibility_writes_summary_and_cli_returns_nonzero_on_failure(
    tmp_path: Path,
) -> None:
    summary_run_root = tmp_path / "internal_data_readiness"
    _write_json(
        summary_run_root / "summary.json",
        _internal_data_summary(
            run_id="internal_data_cli",
            surface_status="present",
            category_status="review_ready",
            recommended_action="manual_slot_tuning_review",
        ),
    )

    run_root = run_slot_classification_tuning_visibility(
        internal_data_readiness_summary_path=summary_run_root,
        out_dir=tmp_path / "out",
        run_id="slot_tuning_visibility_python",
        allowed_category_statuses=["advisory_hold", "review_ready"],
    )
    payload = json.loads((run_root / "summary.json").read_text(encoding="utf-8"))
    assert payload["decision"]["passed"] is True
    assert payload["inputs"]["internal_data_readiness_run_id"] == "internal_data_cli"

    failing_summary = tmp_path / "internal_data_readiness_fail"
    _write_json(
        failing_summary / "summary.json",
        _internal_data_summary(
            run_id="internal_data_fail",
            surface_status="invalid",
            category_status="invalid",
            include_decision=False,
            include_summary_path=False,
            recommended_action=None,
        ),
    )

    script = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "eval"
        / "check_slot_classification_tuning_visibility.py"
    )
    cli_out_dir = tmp_path / "cli_out"
    completed = subprocess.run(
        [
            sys.executable,
            str(script),
            "--internal-data-summary",
            str(failing_summary),
            "--out-dir",
            str(cli_out_dir),
            "--run-id",
            "slot_tuning_visibility_cli",
        ],
        cwd=Path(__file__).resolve().parents[1],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 1, completed.stderr
    cli_payload = json.loads(
        (cli_out_dir / "slot_tuning_visibility_cli" / "summary.json").read_text(encoding="utf-8")
    )
    assert "[check_slot_classification_tuning_visibility] out=" in completed.stdout
    assert "[check_slot_classification_tuning_visibility] summary=" in completed.stdout
    assert (
        "[check_slot_classification_tuning_visibility] "
        "passed=False status=invalid surface=invalid blockers="
        "slot_classification_tuning_review_surface_not_present,"
        "classification_tuning_review_category_not_report_visible,"
        "slot_classification_tuning_review_decision_missing,"
        "slot_classification_tuning_review_summary_path_missing,"
        "slot_classification_tuning_review_action_missing"
    ) in completed.stdout
    assert cli_payload["decision"]["passed"] is False
    assert "slot_classification_tuning_review_surface_not_present" in cli_payload["decision"]["blockers"]
