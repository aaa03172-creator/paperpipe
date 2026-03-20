from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.meeting_packs.service import generate_meeting_pack
from src.schemas.meeting_pack import MeetingPackGenerateRequest, MeetingPackSourceSelector


DEFAULT_VAULT = Path("frontend/.e2e-backend-runtime/obsidian")
DEFAULT_SLUG = "zoteroduboisAlzheimerDiseaseClinicalBiological2024"
DEFAULT_ROOT = Path("tmp/meeting_pack_real_smoke")
DEFAULT_MODES = (
    "journal_club",
    "literature_update",
    "project_progress_update",
    "experiment_proposal",
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a real-input Meeting Pack smoke check.")
    parser.add_argument("--vault-path", type=Path, default=DEFAULT_VAULT)
    parser.add_argument("--slug", default=DEFAULT_SLUG)
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--max-slides", type=int, default=5)
    parser.add_argument(
        "--modes",
        nargs="+",
        default=list(DEFAULT_MODES),
        choices=list(DEFAULT_MODES),
    )
    args = parser.parse_args()

    vault_path = args.vault_path.expanduser().resolve()
    if not vault_path.exists():
        raise SystemExit(f"Vault path not found: {vault_path}")
    state_path = vault_path / ".pp" / args.slug / "state.json"
    if not state_path.exists():
        raise SystemExit(f"Structured state not found: {state_path}")

    args.root.mkdir(parents=True, exist_ok=True)

    results: list[dict[str, object]] = []
    for mode in args.modes:
        response = generate_meeting_pack(
            request=MeetingPackGenerateRequest(
                mode=mode,
                source_items=[MeetingPackSourceSelector(type="paper_slug", ref=args.slug)],
                max_slides=args.max_slides,
            ),
            vault_path=vault_path,
            root=args.root,
        )

        pack = response.pack
        if not (5 <= len(pack.slides) <= 8):
            raise SystemExit(f"{mode}: expected 5-8 slides, got {len(pack.slides)}")
        if pack.readiness != "evidence_backed":
            raise SystemExit(f"{mode}: expected evidence_backed readiness, got {pack.readiness}")
        if not pack.evidence_refs:
            raise SystemExit(f"{mode}: expected evidence refs")
        if response.markdown_sync is None or response.markdown_sync.status != "in_sync":
            raise SystemExit(f"{mode}: expected in_sync markdown status")

        results.append(
            {
                "mode": mode,
                "pack_id": pack.id,
                "slides": len(pack.slides),
                "evidence_refs": len(pack.evidence_refs),
                "readiness": pack.readiness,
                "markdown_sync": response.markdown_sync.status,
            }
        )

    print(json.dumps({"slug": args.slug, "vault_path": str(vault_path), "results": results}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
