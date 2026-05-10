from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from scripts.eval.check_intake_override_coverage_gate import (
    build_intake_override_coverage_gate_summary,
    run_intake_override_coverage_gate,
)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _audit_summary(
    *,
    run_id: str,
    has_feedback_json_count: int,
    audited_document_count: int,
    missing_log_count: int,
    invalid_feedback_json_count: int = 0,
    invalid_log_count: int = 0,
) -> dict:
    return {
        "schema_version": "intake_override_audit_summary.v1",
        "generated_at": "2026-04-17T00:00:00Z",
        "run_id": run_id,
        "metrics": {
            "document_count": has_feedback_json_count + 1,
            "has_feedback_json_count": has_feedback_json_count,
            "audited_document_count": audited_document_count,
            "missing_intake_override_log_count": missing_log_count,
            "invalid_feedback_json_count": invalid_feedback_json_count,
            "invalid_intake_override_log_count": invalid_log_count,
        },
    }


def test_build_intake_override_coverage_gate_summary_passes_for_full_coverage(tmp_path: Path) -> None:
    summary_path = tmp_path / "audit" / "summary.json"
    _write_json(
        summary_path,
        _audit_summary(
            run_id="audit_pass",
            has_feedback_json_count=4,
            audited_document_count=4,
            missing_log_count=0,
        ),
    )

    payload = build_intake_override_coverage_gate_summary(
        audit_summary=json.loads(summary_path.read_text(encoding="utf-8")),
        audit_summary_path=summary_path,
        run_id="gate_pass",
        min_feedback_json_rows_for_gate=1,
        min_audited_feedback_coverage=1.0,
        max_missing_log_count=0,
        max_invalid_feedback_json_count=0,
        max_invalid_intake_override_log_count=0,
    )

    assert payload["decision"]["gate_applies"] is True
    assert payload["decision"]["passed"] is True
    assert payload["decision"]["blockers"] == []
    assert payload["decision"]["feedback_coverage_rate"] == 1.0


def test_build_intake_override_coverage_gate_summary_fails_when_logs_are_missing(tmp_path: Path) -> None:
    summary_path = tmp_path / "audit" / "summary.json"
    _write_json(
        summary_path,
        _audit_summary(
            run_id="audit_fail",
            has_feedback_json_count=4,
            audited_document_count=2,
            missing_log_count=2,
        ),
    )

    payload = build_intake_override_coverage_gate_summary(
        audit_summary=json.loads(summary_path.read_text(encoding="utf-8")),
        audit_summary_path=summary_path,
        run_id="gate_fail",
        min_feedback_json_rows_for_gate=1,
        min_audited_feedback_coverage=1.0,
        max_missing_log_count=0,
        max_invalid_feedback_json_count=0,
        max_invalid_intake_override_log_count=0,
    )

    assert payload["decision"]["gate_applies"] is True
    assert payload["decision"]["passed"] is False
    assert payload["decision"]["feedback_coverage_rate"] == 0.5
    assert payload["decision"]["blockers"] == [
        "audited_feedback_coverage_below_threshold",
        "missing_intake_override_logs_above_threshold",
    ]


def test_run_intake_override_coverage_gate_writes_summary_and_cli_accepts_run_directory(tmp_path: Path) -> None:
    audit_run_root = tmp_path / "audit_run"
    _write_json(
        audit_run_root / "summary.json",
        _audit_summary(
            run_id="audit_cli",
            has_feedback_json_count=3,
            audited_document_count=3,
            missing_log_count=0,
        ),
    )

    run_root = run_intake_override_coverage_gate(
        audit_summary_path=audit_run_root,
        out_dir=tmp_path / "out",
        run_id="gate_python",
        min_feedback_json_rows_for_gate=1,
        min_audited_feedback_coverage=1.0,
        max_missing_log_count=0,
        max_invalid_feedback_json_count=0,
        max_invalid_intake_override_log_count=0,
    )
    payload = json.loads((run_root / "summary.json").read_text(encoding="utf-8"))
    assert payload["decision"]["passed"] is True
    assert payload["inputs"]["audit_run_id"] == "audit_cli"

    script = Path(__file__).resolve().parents[1] / "scripts" / "eval" / "check_intake_override_coverage_gate.py"
    cli_out_dir = tmp_path / "cli_out"
    completed = subprocess.run(
        [
            sys.executable,
            str(script),
            "--audit-summary",
            str(audit_run_root),
            "--out-dir",
            str(cli_out_dir),
            "--run-id",
            "gate_cli",
        ],
        cwd=Path(__file__).resolve().parents[1],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    cli_payload = json.loads((cli_out_dir / "gate_cli" / "summary.json").read_text(encoding="utf-8"))
    assert cli_payload["decision"]["passed"] is True
    assert cli_payload["inputs"]["audit_summary_path"].endswith("/audit_run/summary.json")
