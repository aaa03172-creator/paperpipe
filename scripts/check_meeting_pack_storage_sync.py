from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.meeting_packs.service import validate_meeting_pack
from src.meeting_packs.store import list_meeting_pack_ids


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate stored Meeting Pack bundles for markdown sync and optional regenerate availability."
    )
    parser.add_argument("--root", type=Path, default=Path("storage/meeting_packs"))
    parser.add_argument("--vault-path", type=Path, default=None)
    parser.add_argument("--require-regenerable", action="store_true")
    args = parser.parse_args()

    root = args.root.expanduser().resolve()
    if not root.exists():
        raise SystemExit(f"Meeting Pack root not found: {root}")

    vault_path = args.vault_path.expanduser().resolve() if args.vault_path is not None else None
    pack_ids = list_meeting_pack_ids(root)
    if not pack_ids:
        raise SystemExit(f"No Meeting Pack directories found under {root}")

    drifted_pack_ids: list[str] = []
    unavailable_regenerate_pack_ids: list[str] = []
    results: list[dict[str, object]] = []

    for pack_id in pack_ids:
        validation = validate_meeting_pack(pack_id, root=root, vault_path=vault_path).validation
        results.append(
            {
                "pack_id": pack_id,
                "markdown_sync": validation.markdown_sync.status,
                "can_regenerate": validation.can_regenerate,
                "regenerate_strategy": validation.regenerate_strategy,
                "warnings": validation.warnings,
            }
        )
        if validation.markdown_sync.status != "in_sync":
            drifted_pack_ids.append(pack_id)
        if args.require_regenerable and not validation.can_regenerate:
            unavailable_regenerate_pack_ids.append(pack_id)

    summary = {
        "root": str(root),
        "vault_path": str(vault_path) if vault_path is not None else None,
        "pack_count": len(results),
        "drifted_pack_ids": drifted_pack_ids,
        "unavailable_regenerate_pack_ids": unavailable_regenerate_pack_ids,
        "results": results,
    }
    print(json.dumps(summary, indent=2))

    if drifted_pack_ids:
        raise SystemExit(1)
    if args.require_regenerable and unavailable_regenerate_pack_ids:
        raise SystemExit(1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
