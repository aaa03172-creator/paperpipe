import json
from pathlib import Path

from scripts import run_ops_readiness_monitor as monitor
from scripts.check_ops_readiness import OpsReadinessResult
from src.schemas.ops import RuntimeReadinessCheck, RuntimeReadinessResponse


def _result(status: str = "ok", exit_code: int = 0) -> OpsReadinessResult:
    readiness_status = "ok" if status == "ok" else "degraded"
    return OpsReadinessResult(
        status=status,
        exit_code=exit_code,
        readiness=RuntimeReadinessResponse(
            status=readiness_status,
            checks=[
                RuntimeReadinessCheck(name="config_file", status="ok", detail="loaded"),
                RuntimeReadinessCheck(name="queue_health", status="warn", detail="queued=2"),
            ],
        ),
        downloader_metrics={"paper_rows": 1, "attempt_rows": 2, "missing_pdf_rows": 0},
        downloader_alerts=[],
    )


def test_run_monitor_writes_json_and_text_reports(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(monitor, "_utc_now_iso", lambda: "2026-04-26T00:00:00Z")
    monkeypatch.setattr(monitor, "collect_ops_readiness", lambda **kwargs: _result("warn", 2))

    out_path = tmp_path / "latest.json"
    text_path = tmp_path / "latest.txt"
    exit_code, summary = monitor.run_monitor(
        db_path=tmp_path / "state.db",
        out_path=out_path,
        text_out_path=text_path,
        thresholds=monitor.DEFAULT_THRESHOLDS,
    )

    payload = json.loads(out_path.read_text(encoding="utf-8"))
    text = text_path.read_text(encoding="utf-8")

    assert exit_code == 2
    assert payload["checked_at"] == "2026-04-26T00:00:00Z"
    assert payload["status"] == "warn"
    assert payload["exit_code"] == 2
    assert payload["monitor"]["db_path"].endswith("state.db")
    assert "checked_at=2026-04-26T00:00:00Z" in summary
    assert "ops_readiness=warn" in text
    assert "queue_health" in text


def test_run_monitor_can_skip_text_report(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(monitor, "_utc_now_iso", lambda: "2026-04-26T00:00:00Z")
    monkeypatch.setattr(monitor, "collect_ops_readiness", lambda **kwargs: _result("ok", 0))

    out_path = tmp_path / "latest.json"
    exit_code, summary = monitor.run_monitor(
        db_path=tmp_path / "state.db",
        out_path=out_path,
        text_out_path=None,
        thresholds=monitor.DEFAULT_THRESHOLDS,
    )

    assert exit_code == 0
    assert out_path.exists()
    assert "ops_readiness=ok" in summary
    assert not (tmp_path / "ops_readiness_latest.txt").exists()
