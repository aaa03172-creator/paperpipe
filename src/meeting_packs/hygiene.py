from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil

from src.meeting_packs.service import validate_meeting_pack
from src.meeting_packs.store import list_meeting_pack_ids, load_meeting_pack
from src.schemas.meeting_pack import MeetingPack, MeetingPackValidation
from src.services.fixture_visibility import is_test_fixture_meeting_pack
from src.skills.storage import atomic_write_text


@dataclass(frozen=True)
class MeetingPackArchiveCandidate:
    pack_id: str
    reason: str
    selector_key: str
    title: str
    source_dir: Path
    destination_dir: Path


def default_archive_root(root: Path, *, now: datetime | None = None) -> Path:
    stamp = (now or datetime.now(timezone.utc)).strftime("%Y%m%dT%H%M%SZ")
    return root.parent / "_quarantine" / "meeting_packs" / stamp


def _selector_key(pack: MeetingPack) -> str:
    if pack.generation_request and pack.generation_request.source_items:
        first = pack.generation_request.source_items[0]
        source_key = f"{first.type}:{first.ref}"
    elif pack.source_items:
        first = pack.source_items[0]
        source_key = f"{first.type}:{first.ref}"
    else:
        source_key = "unknown"
    return f"{pack.mode}|{source_key}"


def _is_healthy_validation(validation: MeetingPackValidation) -> bool:
    return (
        validation.markdown_sync.status == "in_sync"
        and validation.can_regenerate
        and not validation.warnings
    )


def _validation_for(pack_id: str, *, root: Path, vault_path: Path | None) -> MeetingPackValidation:
    return validate_meeting_pack(pack_id, root=root, vault_path=vault_path).validation


def select_archive_candidates(
    root: Path,
    *,
    vault_path: Path | None = None,
    keep_latest: int = 3,
    now: datetime | None = None,
) -> list[MeetingPackArchiveCandidate]:
    resolved_root = root.expanduser().resolve()
    archive_root = default_archive_root(resolved_root, now=now)
    pack_ids = list_meeting_pack_ids(resolved_root)
    packs_by_id: dict[str, MeetingPack] = {}
    groups: dict[str, list[str]] = defaultdict(list)
    fixture_pack_ids: set[str] = set()

    for pack_id in pack_ids:
        pack = load_meeting_pack(pack_id, root=resolved_root)
        packs_by_id[pack_id] = pack
        groups[_selector_key(pack)].append(pack_id)
        if is_test_fixture_meeting_pack(pack):
            fixture_pack_ids.add(pack_id)

    candidates: dict[str, MeetingPackArchiveCandidate] = {}

    for pack_id in sorted(fixture_pack_ids):
        pack = packs_by_id[pack_id]
        candidates[pack_id] = MeetingPackArchiveCandidate(
            pack_id=pack_id,
            reason="fixture_like_pack",
            selector_key=_selector_key(pack),
            title=pack.title,
            source_dir=resolved_root / pack_id,
            destination_dir=archive_root / pack_id,
        )

    effective_keep_latest = max(1, keep_latest)
    for selector_key, group_pack_ids in groups.items():
        non_fixture_ids = sorted(pack_id for pack_id in group_pack_ids if pack_id not in fixture_pack_ids)
        if len(non_fixture_ids) <= effective_keep_latest:
            continue

        kept_ids = non_fixture_ids[-effective_keep_latest:]
        kept_validations = [
            _validation_for(pack_id, root=resolved_root, vault_path=vault_path)
            for pack_id in kept_ids
        ]
        if not kept_validations or not all(_is_healthy_validation(validation) for validation in kept_validations):
            continue

        for pack_id in non_fixture_ids[:-effective_keep_latest]:
            pack = packs_by_id[pack_id]
            candidates.setdefault(
                pack_id,
                MeetingPackArchiveCandidate(
                    pack_id=pack_id,
                    reason="superseded_by_recent_healthy_pack",
                    selector_key=selector_key,
                    title=pack.title,
                    source_dir=resolved_root / pack_id,
                    destination_dir=archive_root / pack_id,
                ),
            )

    return sorted(candidates.values(), key=lambda item: item.pack_id)


def apply_archive(
    candidates: list[MeetingPackArchiveCandidate],
    *,
    archive_root: Path,
) -> int:
    if not candidates:
        return 0

    resolved_archive_root = archive_root.expanduser().resolve()
    resolved_archive_root.mkdir(parents=True, exist_ok=True)
    moved = 0
    manifest_rows: list[dict[str, str]] = []

    for candidate in candidates:
        if not candidate.source_dir.exists():
            continue
        candidate.destination_dir.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(candidate.source_dir), str(candidate.destination_dir))
        moved += 1
        manifest_rows.append(
            {
                "pack_id": candidate.pack_id,
                "reason": candidate.reason,
                "selector_key": candidate.selector_key,
                "title": candidate.title,
                "source_dir": str(candidate.source_dir),
                "destination_dir": str(candidate.destination_dir),
            }
        )

    manifest_path = resolved_archive_root / "manifest.json"
    atomic_write_text(
        manifest_path,
        json.dumps(
            {
                "schema_version": "meeting_pack_archive.v1",
                "archived_at": datetime.now(timezone.utc).isoformat(),
                "archived_count": moved,
                "items": manifest_rows,
            },
            ensure_ascii=False,
            indent=2,
        ),
    )
    return moved
