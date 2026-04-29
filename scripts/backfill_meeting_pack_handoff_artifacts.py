from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.meeting_packs.service import backfill_meeting_pack_handoff_artifacts


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Refresh stored Meeting Pack acceptance_contract.json and quality_gate.json "
            "using the current runtime handoff rules (dry-run by default)."
        )
    )
    parser.add_argument("--root", type=Path, default=Path("storage/meeting_packs"))
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Persist refreshed handoff artifacts in place. Default is dry-run.",
    )
    args = parser.parse_args()

    root = args.root.expanduser().resolve()
    if not root.exists():
        raise SystemExit(f"Meeting Pack root not found: {root}")

    summary = backfill_meeting_pack_handoff_artifacts(root=root, apply=args.apply)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
