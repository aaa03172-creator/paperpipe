from __future__ import annotations

import json

from typer.testing import CliRunner

import src.cli as cli
from src.services.retraction_audit import RetractionAuditSummary, run_retraction_audit


def test_retraction_audit_dry_run_does_not_mark_db(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("PAPERPIPE_DB_PATH", str(tmp_path / "state.db"))
    marked: list[str] = []

    summary = run_retraction_audit(
        apply=False,
        sleep_seconds=0,
        email="ops@example.test",
        papers=[
            {"doi": "10.1000/retracted", "title": "Retracted candidate", "is_retracted": 0},
            {"doi": "10.1000/known", "title": "Known retracted", "is_retracted": 1},
            {"doi": "", "title": "Missing DOI", "is_retracted": 0},
        ],
        checker=lambda doi, email: {"is_retracted": doi.endswith("retracted"), "retraction_details": "test signal"},
        marker=lambda doi: marked.append(doi) or True,
    )

    assert summary.total_papers == 3
    assert summary.checked_count == 1
    assert summary.retracted_count == 1
    assert summary.marked_count == 0
    assert summary.skipped_known_retracted == 1
    assert summary.skipped_missing_identifier == 1
    assert marked == []
    assert summary.results[0].status == "retracted_found"


def test_retraction_audit_apply_marks_detected_retractions(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("PAPERPIPE_DB_PATH", str(tmp_path / "state.db"))
    marked: list[str] = []

    summary = run_retraction_audit(
        apply=True,
        sleep_seconds=0,
        email="ops@example.test",
        papers=[{"doi": "10.1000/retracted", "title": "Retracted candidate", "is_retracted": 0}],
        checker=lambda doi, email: {"is_retracted": True, "retraction_details": "test signal"},
        marker=lambda doi: marked.append(doi) or True,
    )

    assert summary.retracted_count == 1
    assert summary.marked_count == 1
    assert marked == ["10.1000/retracted"]
    assert summary.results[0].status == "marked_retracted"


def test_retraction_audit_cli_json_uses_dry_run_by_default(monkeypatch) -> None:
    def fake_run_retraction_audit(*, apply, limit, sleep_seconds):
        return RetractionAuditSummary(
            total_papers=1,
            checked_count=1,
            skipped_known_retracted=0,
            skipped_missing_identifier=0,
            retracted_count=1,
            marked_count=0,
            error_count=0,
            apply=apply,
        )

    monkeypatch.setattr("src.services.retraction_audit.run_retraction_audit", fake_run_retraction_audit)

    result = CliRunner().invoke(cli.app, ["audit-retractions", "--json", "--sleep-seconds", "0"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["apply"] is False
    assert payload["retracted_count"] == 1
    assert payload["marked_count"] == 0
