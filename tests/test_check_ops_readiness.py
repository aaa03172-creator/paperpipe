from pathlib import Path

from scripts import check_ops_readiness
from src.schemas.ops import RuntimeReadinessCheck, RuntimeReadinessResponse
from src.services.downloader_ops_metrics import Thresholds


def test_ops_status_exit_code_prioritizes_runtime_error():
    status, exit_code = check_ops_readiness._ops_status_and_exit_code(
        readiness_status="error",
        downloader_alerts=["rate_limit count 3 >= warn threshold 3"],
        downloader_error=None,
    )
    assert status == "error"
    assert exit_code == 1


def test_ops_status_exit_code_warns_for_degraded_or_downloader_alerts():
    assert check_ops_readiness._ops_status_and_exit_code(
        readiness_status="degraded",
        downloader_alerts=[],
        downloader_error=None,
    ) == ("warn", 2)
    assert check_ops_readiness._ops_status_and_exit_code(
        readiness_status="ok",
        downloader_alerts=["policy_block count 1 >= warn threshold 1"],
        downloader_error=None,
    ) == ("warn", 2)


def test_render_text_hides_ok_checks_by_default():
    result = check_ops_readiness.OpsReadinessResult(
        status="warn",
        exit_code=2,
        readiness=RuntimeReadinessResponse(
            status="degraded",
            checks=[
                RuntimeReadinessCheck(name="config_file", status="ok", detail="loaded"),
                RuntimeReadinessCheck(name="queue_health", status="warn", detail="queued=2"),
            ],
        ),
        downloader_metrics={"paper_rows": 1, "attempt_rows": 1, "missing_pdf_rows": 0},
        downloader_alerts=[],
    )

    rendered = check_ops_readiness.render_text(result, show_ok=False)

    assert "queue_health" in rendered
    assert "config_file" not in rendered
    assert "downloader_alerts=none" in rendered


def test_collect_ops_readiness_maps_downloader_alert(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(
        check_ops_readiness,
        "collect_runtime_readiness",
        lambda: RuntimeReadinessResponse(status="ok", checks=[]),
    )
    monkeypatch.setattr(
        check_ops_readiness,
        "collect_metrics",
        lambda db_path, hours: {
            "paper_rows": 1,
            "attempt_rows": 1,
            "missing_pdf_rows": 0,
            "status_counts": {"rate_limit": 3},
        },
    )

    result = check_ops_readiness.collect_ops_readiness(
        db_path=tmp_path / "state.db",
        hours=24,
        thresholds=Thresholds(
            rate_limit_warn=3,
            temp_fail_warn=5,
            bad_content_warn=3,
            policy_block_warn=1,
        ),
        include_downloader=True,
    )

    assert result.status == "warn"
    assert result.exit_code == 2
    assert result.downloader_alerts == ["rate_limit count 3 >= warn threshold 3"]
