from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path

from src.schemas.paper_notes import PaperNoteOpsSummary
from src.services.runtime_paths import preferred_artifact_paper_dir


@dataclass(frozen=True)
class ArtifactOperationalSnapshot:
    paper_id: str
    run_id: str | None
    updated_at: str
    mtime: float
    has_claimset: bool
    has_stats_report: bool
    stats_check_count: int


ArtifactSnapshotCache = dict[str, ArtifactOperationalSnapshot | None]


def load_stats_check_count(stats_path: Path) -> int:
    if not stats_path.exists():
        return 0
    try:
        payload = json.loads(stats_path.read_text(encoding="utf-8"))
    except Exception:
        return 0
    checks = payload.get("checks")
    return len(checks) if isinstance(checks, list) else 0


def artifact_snapshot_from_run_dir(
    paper_id: str,
    run_dir: Path,
) -> ArtifactOperationalSnapshot | None:
    if not run_dir.exists() or not run_dir.is_dir():
        return None

    claimset_path = run_dir / "claimset.resolved.json"
    if not claimset_path.exists():
        claimset_path = run_dir / "claimset.json"
    stats_path = run_dir / "stats_report.json"
    mtime = run_dir.stat().st_mtime
    return ArtifactOperationalSnapshot(
        paper_id=paper_id,
        run_id=run_dir.name,
        updated_at=datetime.fromtimestamp(mtime, tz=timezone.utc).isoformat(),
        mtime=mtime,
        has_claimset=claimset_path.exists(),
        has_stats_report=stats_path.exists(),
        stats_check_count=load_stats_check_count(stats_path),
    )


def artifact_snapshot_for_paper_id(
    artifacts_path: Path,
    paper_id: str,
    cache: ArtifactSnapshotCache,
) -> ArtifactOperationalSnapshot | None:
    if paper_id in cache:
        return cache[paper_id]

    paper_dir = preferred_artifact_paper_dir(paper_id, root=artifacts_path)
    if paper_dir is None:
        cache[paper_id] = None
        return None
    if not paper_dir.exists() or not paper_dir.is_dir():
        cache[paper_id] = None
        return None

    run_dirs = [path for path in paper_dir.iterdir() if path.is_dir()]
    if not run_dirs:
        cache[paper_id] = None
        return None

    run_dirs.sort(key=lambda path: path.stat().st_mtime, reverse=True)
    run_dir = run_dirs[0]
    snapshot = artifact_snapshot_from_run_dir(paper_id, run_dir)
    cache[paper_id] = snapshot
    return snapshot


def build_ops_summary_from_snapshot(snapshot: ArtifactOperationalSnapshot | None) -> PaperNoteOpsSummary | None:
    if snapshot is None:
        return None

    if snapshot.has_claimset and snapshot.has_stats_report and snapshot.stats_check_count > 0:
        return PaperNoteOpsSummary(
            state="healthy",
            label="Healthy",
            reason=f"Saved claims and note checks are available. {snapshot.stats_check_count} checks are ready.",
            recommended_action="none",
            latest_run_id=snapshot.run_id,
            has_claimset=True,
            has_stats_report=True,
            stats_check_count=snapshot.stats_check_count,
        )

    if snapshot.has_claimset and (not snapshot.has_stats_report or snapshot.stats_check_count == 0):
        return PaperNoteOpsSummary(
            state="action_needed",
            label="Action needed",
            reason="Saved note checks are missing or empty.",
            recommended_action="repair_stats",
            latest_run_id=snapshot.run_id,
            has_claimset=True,
            has_stats_report=snapshot.has_stats_report,
            stats_check_count=snapshot.stats_check_count,
        )

    if snapshot.has_stats_report and not snapshot.has_claimset:
        return PaperNoteOpsSummary(
            state="action_needed",
            label="Action needed",
            reason="Saved note checks exist, but saved claims are missing.",
            recommended_action="open_workbench",
            latest_run_id=snapshot.run_id,
            has_claimset=False,
            has_stats_report=True,
            stats_check_count=snapshot.stats_check_count,
        )

    return None


def build_ops_summary_for_paper_id(
    artifacts_path: Path,
    paper_id: str,
    cache: ArtifactSnapshotCache,
) -> PaperNoteOpsSummary | None:
    snapshot = artifact_snapshot_for_paper_id(artifacts_path, paper_id, cache)
    return build_ops_summary_from_snapshot(snapshot)


def build_ops_summary_for_candidate_ids(
    artifacts_path: Path,
    candidate_ids: list[str],
    cache: ArtifactSnapshotCache,
) -> PaperNoteOpsSummary | None:
    snapshots = [
        snapshot
        for paper_id in candidate_ids
        if (snapshot := artifact_snapshot_for_paper_id(artifacts_path, paper_id, cache)) is not None
    ]
    if not snapshots:
        return None
    selected = max(snapshots, key=lambda item: item.mtime)
    return build_ops_summary_from_snapshot(selected)
