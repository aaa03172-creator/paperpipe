from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from src.schemas.meeting_pack import (
    MeetingPack,
    MeetingPackMarkdownSync,
    MeetingPackRequestSnapshot,
    MeetingPackSourceItem,
    MeetingPackSourceSelector,
    MeetingPackValidation,
)
from src.meeting_packs.hygiene import (
    MeetingPackArchiveCandidate,
    apply_archive,
    select_archive_candidates,
)


def _make_pack(
    pack_id: str,
    *,
    mode: str,
    ref: str,
    title: str,
) -> MeetingPack:
    return MeetingPack(
        id=pack_id,
        mode=mode,
        title=title,
        created_at=datetime(2026, 4, 10, 0, 0, tzinfo=timezone.utc),
        generation_request=MeetingPackRequestSnapshot(
            mode=mode,
            title=title,
            source_items=[MeetingPackSourceSelector(type="paper_slug", ref=ref)],
            max_slides=6,
        ),
        source_items=[
            MeetingPackSourceItem(
                id="src_01",
                type="paper_slug",
                ref=ref,
                title=title,
                priority=1,
                included=True,
            )
        ],
    )


def _make_validation(*, healthy: bool, can_regenerate: bool = True) -> SimpleNamespace:
    return SimpleNamespace(
        validation=MeetingPackValidation(
            pack_id="unused",
            readiness="evidence_backed",
            markdown_sync=MeetingPackMarkdownSync(
                status="in_sync" if healthy else "drifted",
                stored_markdown_sha1="a",
                rendered_markdown_sha1="a" if healthy else "b",
                note=None if healthy else "drift",
            ),
            can_regenerate=can_regenerate,
            regenerate_strategy="saved_request" if can_regenerate else "unavailable",
            warnings=[] if healthy else ["warning"],
        )
    )


def test_select_archive_candidates_archives_fixtures_and_only_superseded_groups(monkeypatch, tmp_path: Path):
    root = tmp_path / "meeting_packs"
    root.mkdir()
    pack_ids = [
        "meetingpack_20260401T000000000000Z_journal_club_alpha",
        "meetingpack_20260402T000000000000Z_journal_club_alpha",
        "meetingpack_20260403T000000000000Z_journal_club_alpha",
        "meetingpack_20260404T000000000000Z_journal_club_alpha",
        "meetingpack_20260401T000000000000Z_project_progress_update_fixture",
        "meetingpack_20260402T000000000000Z_project_progress_update_fixture",
        "meetingpack_20260401T000000000000Z_journal_club_beta",
        "meetingpack_20260402T000000000000Z_journal_club_beta",
        "meetingpack_20260403T000000000000Z_journal_club_beta",
        "meetingpack_20260404T000000000000Z_journal_club_beta",
    ]
    for pack_id in pack_ids:
        (root / pack_id).mkdir(parents=True)

    packs = {
        "meetingpack_20260401T000000000000Z_journal_club_alpha": _make_pack(
            "meetingpack_20260401T000000000000Z_journal_club_alpha",
            mode="journal_club",
            ref="alpha",
            title="Alpha title",
        ),
        "meetingpack_20260402T000000000000Z_journal_club_alpha": _make_pack(
            "meetingpack_20260402T000000000000Z_journal_club_alpha",
            mode="journal_club",
            ref="alpha",
            title="Alpha title",
        ),
        "meetingpack_20260403T000000000000Z_journal_club_alpha": _make_pack(
            "meetingpack_20260403T000000000000Z_journal_club_alpha",
            mode="journal_club",
            ref="alpha",
            title="Alpha title",
        ),
        "meetingpack_20260404T000000000000Z_journal_club_alpha": _make_pack(
            "meetingpack_20260404T000000000000Z_journal_club_alpha",
            mode="journal_club",
            ref="alpha",
            title="Alpha title",
        ),
        "meetingpack_20260401T000000000000Z_project_progress_update_fixture": _make_pack(
            "meetingpack_20260401T000000000000Z_project_progress_update_fixture",
            mode="project_progress_update",
            ref="zoteroe2eFixtureAlpha",
            title="Fixture title",
        ),
        "meetingpack_20260402T000000000000Z_project_progress_update_fixture": _make_pack(
            "meetingpack_20260402T000000000000Z_project_progress_update_fixture",
            mode="project_progress_update",
            ref="zoteroe2eFixtureAlpha",
            title="Fixture title",
        ),
        "meetingpack_20260401T000000000000Z_journal_club_beta": _make_pack(
            "meetingpack_20260401T000000000000Z_journal_club_beta",
            mode="journal_club",
            ref="beta",
            title="Beta title",
        ),
        "meetingpack_20260402T000000000000Z_journal_club_beta": _make_pack(
            "meetingpack_20260402T000000000000Z_journal_club_beta",
            mode="journal_club",
            ref="beta",
            title="Beta title",
        ),
        "meetingpack_20260403T000000000000Z_journal_club_beta": _make_pack(
            "meetingpack_20260403T000000000000Z_journal_club_beta",
            mode="journal_club",
            ref="beta",
            title="Beta title",
        ),
        "meetingpack_20260404T000000000000Z_journal_club_beta": _make_pack(
            "meetingpack_20260404T000000000000Z_journal_club_beta",
            mode="journal_club",
            ref="beta",
            title="Beta title",
        ),
    }
    validations = {
        "meetingpack_20260403T000000000000Z_journal_club_alpha": _make_validation(healthy=True),
        "meetingpack_20260404T000000000000Z_journal_club_alpha": _make_validation(healthy=True),
        "meetingpack_20260403T000000000000Z_journal_club_beta": _make_validation(healthy=False),
        "meetingpack_20260404T000000000000Z_journal_club_beta": _make_validation(healthy=False),
    }

    monkeypatch.setattr(
        "src.meeting_packs.hygiene.list_meeting_pack_ids",
        lambda root: sorted(pack_ids),
    )
    monkeypatch.setattr(
        "src.meeting_packs.hygiene.load_meeting_pack",
        lambda pack_id, root=None: packs[pack_id],
    )
    monkeypatch.setattr(
        "src.meeting_packs.hygiene.validate_meeting_pack",
        lambda pack_id, root=None, vault_path=None: validations[pack_id],
    )

    candidates = select_archive_candidates(root, keep_latest=2)
    candidate_ids = {candidate.pack_id for candidate in candidates}
    reasons = {candidate.pack_id: candidate.reason for candidate in candidates}

    assert candidate_ids == {
        "meetingpack_20260401T000000000000Z_journal_club_alpha",
        "meetingpack_20260402T000000000000Z_journal_club_alpha",
        "meetingpack_20260401T000000000000Z_project_progress_update_fixture",
        "meetingpack_20260402T000000000000Z_project_progress_update_fixture",
    }
    assert reasons["meetingpack_20260401T000000000000Z_journal_club_alpha"] == "superseded_by_recent_healthy_pack"
    assert reasons["meetingpack_20260401T000000000000Z_project_progress_update_fixture"] == "fixture_like_pack"


def test_apply_archive_moves_pack_directories_and_writes_manifest(tmp_path: Path):
    root = tmp_path / "meeting_packs"
    archive_root = tmp_path / "_quarantine" / "meeting_packs" / "20260410T034500Z"
    source_a = root / "meetingpack_20260401T000000000000Z_journal_club_alpha"
    source_b = root / "meetingpack_20260402T000000000000Z_journal_club_alpha"
    source_a.mkdir(parents=True)
    source_b.mkdir(parents=True)
    (source_a / "meeting_pack.json").write_text("{}", encoding="utf-8")
    (source_b / "meeting_pack.json").write_text("{}", encoding="utf-8")

    candidates = [
        MeetingPackArchiveCandidate(
            pack_id=source_a.name,
            reason="superseded_by_recent_healthy_pack",
            selector_key="journal_club|paper_slug:alpha",
            title="Alpha title",
            source_dir=source_a,
            destination_dir=archive_root / source_a.name,
        ),
        MeetingPackArchiveCandidate(
            pack_id=source_b.name,
            reason="superseded_by_recent_healthy_pack",
            selector_key="journal_club|paper_slug:alpha",
            title="Alpha title",
            source_dir=source_b,
            destination_dir=archive_root / source_b.name,
        ),
    ]

    moved = apply_archive(candidates, archive_root=archive_root)

    assert moved == 2
    assert not source_a.exists()
    assert not source_b.exists()
    assert (archive_root / source_a.name / "meeting_pack.json").exists()
    assert (archive_root / source_b.name / "meeting_pack.json").exists()
    assert (archive_root / "manifest.json").exists()
