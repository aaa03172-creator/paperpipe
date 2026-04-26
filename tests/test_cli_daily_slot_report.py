import inspect
import json
from pathlib import Path
from types import SimpleNamespace

from typer.testing import CliRunner

import src.cli as cli
import src.config as config_module
import src.processor as processor_module


class _RecordingConsole:
    def __init__(self) -> None:
        self.lines: list[str] = []

    def print(self, *args, **_kwargs) -> None:
        self.lines.append(" ".join(str(arg) for arg in args))


def test_print_results_uses_clinical_data_payload_and_icon(monkeypatch) -> None:
    recorder = _RecordingConsole()
    monkeypatch.setattr(cli, "console", recorder)

    cli._print_results(
        [
            {
                "slot": "Clinical",
                "title": "Clinical Study",
                "ai_one_liner": "Useful summary",
                "clinical_data": {
                    "population": "Adults with biomarker-positive disease",
                    "effect": "Median survival improved",
                },
            }
        ]
    )

    output = "\n".join(recorder.lines)
    assert "🏥 [Clinical] Clinical Study" in output
    assert "Clinical Data Extracted" in output
    assert "population: Adults with biomarker-positive disease" in output
    assert "effect: Median survival improved" in output


def test_print_results_shows_selection_summary_from_feedback_json(monkeypatch) -> None:
    recorder = _RecordingConsole()
    monkeypatch.setattr(cli, "console", recorder)

    cli._print_results(
        [
            {
                "slot": "Mechanism",
                "title": "Mechanism Study",
                "ai_one_liner": "Useful summary",
                "feedback_json": json.dumps(
                    {
                        "selection": {
                            "selected_rank": 2,
                            "candidate_count": 5,
                            "selected_manual_rank_score": 0.73,
                            "skipped_processed_candidates": ["pmid:top"],
                        }
                    }
                ),
            }
        ]
    )

    output = "\n".join(recorder.lines)
    assert "📝 [Mechanism] Mechanism Study" in output
    assert "🎯 Selection: r2/5, s=0.73, skip=1" in output


def test_repair_stats_help_mentions_historical_seed_set() -> None:
    paper_id_option = inspect.signature(cli.repair_stats).parameters["paper_id"].default

    assert paper_id_option.help is not None
    assert "curated historical 3-paper repair seed set" in paper_id_option.help


def test_run_bootstraps_database_before_processing(monkeypatch) -> None:
    runner = CliRunner()
    calls: list[object] = []

    def _bootstrap() -> Path:
        calls.append("bootstrap")
        return Path("/tmp/state.db")

    monkeypatch.setattr(cli, "bootstrap_database", _bootstrap)
    monkeypatch.setattr(processor_module, "process_daily_slots", lambda ignore_db=False: calls.append(("process", ignore_db)) or [])
    monkeypatch.setattr(config_module, "load_config", lambda: object())
    monkeypatch.setattr(cli, "record_run_status", lambda *args, **kwargs: None)
    monkeypatch.setattr(cli, "_print_results", lambda results: calls.append(("print", results)))

    result = runner.invoke(cli.app, ["run"])

    assert result.exit_code == 0
    assert calls[0] == "bootstrap"
    assert calls[1] == ("process", False)


def test_run_tracks_execution_run_lifecycle(monkeypatch) -> None:
    runner = CliRunner()
    ensure_calls: list[dict] = []
    update_calls: list[dict] = []
    legacy_calls: list[dict] = []
    fake_config = SimpleNamespace(search=SimpleNamespace(slots={"clinical": object(), "methods": object()}))
    fake_results = [
        {"processing_status": "APPROVED"},
        {"processing_status": "PENDING_REVIEW"},
        {"processing_status": "QUARANTINED"},
    ]

    monkeypatch.setattr(cli, "bootstrap_database", lambda: Path("/tmp/state.db"))
    monkeypatch.setattr(processor_module, "process_daily_slots", lambda ignore_db=False: fake_results)
    monkeypatch.setattr(config_module, "load_config", lambda: fake_config)
    monkeypatch.setattr(cli, "ensure_execution_run", lambda **kwargs: ensure_calls.append(kwargs))
    monkeypatch.setattr(cli, "update_execution_run", lambda **kwargs: update_calls.append(kwargs))
    monkeypatch.setattr(cli, "new_run_id", lambda: "run_20260420_120000")
    monkeypatch.setattr(
        cli,
        "record_run_status",
        lambda target_date, status, processed_count=None, last_run_at=None: legacy_calls.append(
            {
                "target_date": target_date,
                "status": status,
                "processed_count": processed_count,
                "last_run_at": last_run_at,
            }
        ),
    )
    monkeypatch.setattr(cli, "_print_results", lambda results: None)

    result = runner.invoke(cli.app, ["run"])

    assert result.exit_code == 0
    assert ensure_calls == [
        {
            "run_id": "run_20260420_120000",
            "trigger_source": "cli_run",
            "pipeline_profile": "legacy_daily_slots",
            "status": "running",
            "params": {
                "command": "paperpipe run",
                "ignore_db": False,
                "slot_names": ["clinical", "methods"],
            },
        }
    ]
    assert update_calls[0]["run_id"] == "run_20260420_120000"
    assert update_calls[0]["status"] == "running"
    assert "started_at" in update_calls[0]
    assert update_calls[1]["run_id"] == "run_20260420_120000"
    assert update_calls[1]["status"] == "completed"
    assert update_calls[1]["metrics"] == {
        "processed_count": 3,
        "approved_count": 1,
        "pending_review_count": 1,
        "quarantined_count": 1,
        "slot_count": 2,
        "report_generated": False,
        "report_path": None,
    }
    assert legacy_calls[0]["status"] == "RUNNING"
    assert legacy_calls[0]["processed_count"] == 0
    assert legacy_calls[1]["status"] == "SUCCESS"
    assert legacy_calls[1]["processed_count"] == 3


def test_run_marks_execution_run_failed_when_processing_raises(monkeypatch) -> None:
    runner = CliRunner()
    update_calls: list[dict] = []
    legacy_calls: list[dict] = []
    fake_config = SimpleNamespace(search=SimpleNamespace(slots={"clinical": object()}))

    monkeypatch.setattr(cli, "bootstrap_database", lambda: Path("/tmp/state.db"))
    monkeypatch.setattr(
        processor_module,
        "process_daily_slots",
        lambda ignore_db=False: (_ for _ in ()).throw(RuntimeError("pipeline exploded")),
    )
    monkeypatch.setattr(config_module, "load_config", lambda: fake_config)
    monkeypatch.setattr(cli, "ensure_execution_run", lambda **kwargs: None)
    monkeypatch.setattr(cli, "update_execution_run", lambda **kwargs: update_calls.append(kwargs))
    monkeypatch.setattr(cli, "new_run_id", lambda: "run_20260420_120001")
    monkeypatch.setattr(
        cli,
        "record_run_status",
        lambda target_date, status, processed_count=None, last_run_at=None: legacy_calls.append(
            {
                "target_date": target_date,
                "status": status,
                "processed_count": processed_count,
                "last_run_at": last_run_at,
            }
        ),
    )
    monkeypatch.setattr(cli, "_print_results", lambda results: None)

    result = runner.invoke(cli.app, ["run"])

    assert result.exit_code != 0
    assert update_calls[0]["status"] == "running"
    assert update_calls[1]["status"] == "failed"
    assert update_calls[1]["metrics"] == {"error": "pipeline exploded"}
    assert legacy_calls[0]["status"] == "RUNNING"
    assert legacy_calls[1]["status"] == "FAILED"
