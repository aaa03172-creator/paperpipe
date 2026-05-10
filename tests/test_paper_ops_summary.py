from src.services.paper_ops_summary import ArtifactOperationalSnapshot, build_ops_summary_from_snapshot


def _snapshot(
    *,
    has_claimset: bool,
    has_stats_report: bool,
    stats_check_count: int,
    run_id: str = "run_ops_001",
) -> ArtifactOperationalSnapshot:
    return ArtifactOperationalSnapshot(
        paper_id="paper_ops_contract",
        run_id=run_id,
        updated_at="2026-05-10T00:00:00+00:00",
        mtime=1_776_000_000.0,
        has_claimset=has_claimset,
        has_stats_report=has_stats_report,
        stats_check_count=stats_check_count,
    )


def test_build_ops_summary_returns_none_without_snapshot() -> None:
    assert build_ops_summary_from_snapshot(None) is None


def test_build_ops_summary_marks_claimset_and_nonempty_stats_as_healthy() -> None:
    summary = build_ops_summary_from_snapshot(
        _snapshot(has_claimset=True, has_stats_report=True, stats_check_count=2)
    )

    assert summary is not None
    assert summary.model_dump() == {
        "state": "healthy",
        "label": "Healthy",
        "reason": "Saved claims and note checks are available. 2 checks are ready.",
        "recommended_action": "none",
        "latest_run_id": "run_ops_001",
        "has_claimset": True,
        "has_stats_report": True,
        "stats_check_count": 2,
    }


def test_build_ops_summary_requests_stats_repair_when_checks_are_missing_or_empty() -> None:
    missing_stats = build_ops_summary_from_snapshot(
        _snapshot(has_claimset=True, has_stats_report=False, stats_check_count=0)
    )
    empty_stats = build_ops_summary_from_snapshot(
        _snapshot(has_claimset=True, has_stats_report=True, stats_check_count=0)
    )

    for summary in (missing_stats, empty_stats):
        assert summary is not None
        assert summary.state == "action_needed"
        assert summary.label == "Action needed"
        assert summary.reason == "Saved note checks are missing or empty."
        assert summary.recommended_action == "repair_stats"
        assert summary.latest_run_id == "run_ops_001"
        assert summary.has_claimset is True
        assert summary.stats_check_count == 0
    assert missing_stats is not None
    assert missing_stats.has_stats_report is False
    assert empty_stats is not None
    assert empty_stats.has_stats_report is True


def test_build_ops_summary_requests_workbench_when_stats_exist_without_claimset() -> None:
    summary = build_ops_summary_from_snapshot(
        _snapshot(has_claimset=False, has_stats_report=True, stats_check_count=3)
    )

    assert summary is not None
    assert summary.model_dump() == {
        "state": "action_needed",
        "label": "Action needed",
        "reason": "Saved note checks exist, but saved claims are missing.",
        "recommended_action": "open_workbench",
        "latest_run_id": "run_ops_001",
        "has_claimset": False,
        "has_stats_report": True,
        "stats_check_count": 3,
    }


def test_build_ops_summary_returns_none_when_no_claimset_or_stats_exist() -> None:
    summary = build_ops_summary_from_snapshot(
        _snapshot(has_claimset=False, has_stats_report=False, stats_check_count=0)
    )

    assert summary is None
