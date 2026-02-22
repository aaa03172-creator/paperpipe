import asyncio
from pathlib import Path

from backend.services import job_runner_stages as stages


def test_run_ingest_stage_returns_none_when_cancelled(tmp_path):
    called = {"ingest": False}
    events: list[tuple[str, int, str, str]] = []

    class FakeIngestAgent:
        def process_v2(self, path: str):
            called["ingest"] = True
            return object()

    async def emit(stage: str, progress: int, message: str, level: str = "INFO"):
        events.append((stage, progress, message, level))

    async def is_cancelled() -> bool:
        return True

    result = asyncio.run(
        stages.run_ingest_stage(
            pdf_path=tmp_path / "x.pdf",
            artifact_dir=tmp_path,
            bootstrap_meta={},
            emit=emit,
            is_cancelled=is_cancelled,
            write_artifact_model=lambda *_args, **_kwargs: None,
            write_bootstrap_meta=lambda *_args, **_kwargs: None,
            ingest_agent_cls=FakeIngestAgent,
        )
    )

    assert result is None
    assert called["ingest"] is False
    assert events == []


def test_run_verify_stage_sets_failed_meta_on_exception(tmp_path):
    class FailingStatsAgent:
        def run(self, **_kwargs):
            raise RuntimeError("boom")

    events: list[tuple[str, int, str, str]] = []
    writes: list[str] = []
    bootstrap_meta = {"verifier_status": "not_run"}

    async def emit(stage: str, progress: int, message: str, level: str = "INFO"):
        events.append((stage, progress, message, level))

    async def is_cancelled() -> bool:
        return False

    def write_bootstrap_meta(_artifact_dir: Path, payload: dict):
        writes.append(payload.get("verifier_status", ""))

    result = asyncio.run(
        stages.run_verify_stage(
            job_id="job1",
            doc_artifact=object(),
            claim_set=object(),
            artifact_dir=tmp_path,
            bootstrap_meta=bootstrap_meta,
            emit=emit,
            is_cancelled=is_cancelled,
            write_artifact_model=lambda *_args, **_kwargs: None,
            write_bootstrap_meta=write_bootstrap_meta,
            stats_agent_cls=FailingStatsAgent,
        )
    )

    assert result["cancelled"] is False
    assert result["stats_report"] is None
    assert bootstrap_meta["verifier_status"] == "failed"
    assert "failed" in writes
    assert any(level == "WARNING" and progress == 85 for _, progress, _, level in events)


def test_run_verify_stage_returns_cancelled_early(tmp_path):
    events: list[tuple[str, int, str, str]] = []
    bootstrap_meta = {"verifier_status": "not_run"}

    async def emit(stage: str, progress: int, message: str, level: str = "INFO"):
        events.append((stage, progress, message, level))

    async def is_cancelled() -> bool:
        return True

    result = asyncio.run(
        stages.run_verify_stage(
            job_id="job2",
            doc_artifact=object(),
            claim_set=object(),
            artifact_dir=tmp_path,
            bootstrap_meta=bootstrap_meta,
            emit=emit,
            is_cancelled=is_cancelled,
            write_artifact_model=lambda *_args, **_kwargs: None,
            write_bootstrap_meta=lambda *_args, **_kwargs: None,
            stats_agent_cls=object,
        )
    )

    assert result == {"cancelled": True, "stats_report": None}
    assert bootstrap_meta["verifier_status"] == "not_run"
    assert events == []
