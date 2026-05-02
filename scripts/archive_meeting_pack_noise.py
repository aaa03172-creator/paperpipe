from __future__ import annotations

import argparse
from collections import defaultdict
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.meeting_packs.hygiene import (
    MeetingPackArchiveCandidate,
    apply_archive,
    default_archive_root,
    select_archive_candidates,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Archive low-value Meeting Pack storage noise with dry-run default. "
            "Fixture-like packs are archived, and older duplicates are archived only when the newest kept packs are healthy."
        )
    )
    parser.add_argument("--root", type=Path, default=Path("storage/meeting_packs"))
    parser.add_argument("--vault-path", type=Path, default=None)
    parser.add_argument("--keep-latest", type=int, default=3, help="How many recent healthy packs to keep per non-fixture group.")
    parser.add_argument("--apply", action="store_true", help="Apply archive move. Default is dry-run.")
    parser.add_argument("--sample", type=int, default=20, help="How many candidate rows to print.")
    args = parser.parse_args()

    root = args.root.expanduser().resolve()
    if not root.exists():
        print(f"[MEETING-PACK-ARCHIVE] root_not_found={root}")
        return 1

    vault_path = args.vault_path.expanduser().resolve() if args.vault_path is not None else None
    archive_root = default_archive_root(root)
    candidates = select_archive_candidates(
        root,
        vault_path=vault_path,
        keep_latest=args.keep_latest,
        now=None,
    )

    by_reason: dict[str, int] = defaultdict(int)
    by_selector: dict[str, int] = defaultdict(int)
    for candidate in candidates:
        by_reason[candidate.reason] += 1
        by_selector[candidate.selector_key] += 1

    print(f"[MEETING-PACK-ARCHIVE] root={root}")
    print(f"[MEETING-PACK-ARCHIVE] archive_root={archive_root}")
    print(f"[MEETING-PACK-ARCHIVE] candidate_count={len(candidates)}")
    print(f"[MEETING-PACK-ARCHIVE] by_reason={dict(sorted(by_reason.items()))}")
    top_selectors = sorted(by_selector.items(), key=lambda item: item[1], reverse=True)[:10]
    if top_selectors:
        print(f"[MEETING-PACK-ARCHIVE] top_selector_counts={top_selectors}")
    for candidate in candidates[: max(0, args.sample)]:
        print(f"  - {candidate.pack_id} | {candidate.reason} | {candidate.selector_key}")

    if not args.apply:
        print("[MEETING-PACK-ARCHIVE] dry-run only (no changes applied)")
        return 0

    moved = apply_archive(candidates, archive_root=archive_root)
    print(f"[MEETING-PACK-ARCHIVE] archived={moved}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
