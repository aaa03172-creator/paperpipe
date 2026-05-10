from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.services.runtime_paths import goldset_root as default_goldset_root

PROMOTE_RESOLUTIONS = {
    "APPROVE_NO_EDIT",
    "APPROVED_WITH_EDIT",
    "MANUAL_FIX",
    "OVERRIDE",
    "REWRITE",
}

MANUAL_CORRECTED_RESOLUTIONS = {
    "APPROVED_WITH_EDIT",
    "MANUAL_FIX",
    "OVERRIDE",
    "REWRITE",
}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_name(value: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9._-]", "_", value)
    normalized = re.sub(r"_+", "_", normalized).strip("_")
    return normalized or "paper"


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"invalid_json_object={path}")
    return payload


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")


def _quarantine_dir(goldset_root: Path) -> Path:
    return goldset_root / "quarantine"


def _accepted_dir(goldset_root: Path) -> Path:
    return goldset_root / "accepted"


def _reviews_dir(goldset_root: Path) -> Path:
    return goldset_root / "reviews"


def _manual_decisions_path(goldset_root: Path) -> Path:
    return goldset_root / "manual_decisions" / "human_decisions.jsonl"


def _review_status_by_paper(reviews_dir: Path) -> dict[str, dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    if not reviews_dir.exists():
        return latest

    for path in sorted(reviews_dir.glob("*.json")):
        payload = _load_json(path)
        paper_id = str(payload.get("paper_id") or "").strip()
        reviewed_at = str(payload.get("reviewed_at") or "")
        if not paper_id:
            continue
        current = latest.get(paper_id)
        if current is None or reviewed_at >= str(current.get("reviewed_at") or ""):
            latest[paper_id] = payload
    return latest


def _quarantine_path_for(goldset_root: Path, paper_id: str) -> Path:
    return _quarantine_dir(goldset_root) / f"{_safe_name(paper_id)}.json"


def _accepted_path_for(goldset_root: Path, paper_id: str) -> Path:
    return _accepted_dir(goldset_root) / f"{_safe_name(paper_id)}.json"


def list_quarantine_records(*, goldset_root: Path, include_resolved: bool = False) -> list[dict[str, Any]]:
    q_dir = _quarantine_dir(goldset_root)
    review_index = _review_status_by_paper(_reviews_dir(goldset_root))
    rows: list[dict[str, Any]] = []
    if not q_dir.exists():
        return rows

    for path in sorted(q_dir.glob("*.json")):
        payload = _load_json(path)
        paper_id = str(payload.get("paper_id") or "").strip()
        if not paper_id:
            continue
        review = review_index.get(paper_id)
        if review and not include_resolved:
            continue
        rows.append(
            {
                "paper_id": paper_id,
                "reason_codes": payload.get("reason_codes", []),
                "quarantine_path": str(path),
                "reviewed": review is not None,
                "review_resolution": review.get("resolution") if review else None,
                "reviewed_at": review.get("reviewed_at") if review else None,
                "accepted_after_review": bool(review.get("accepted_after_review")) if review else False,
            }
        )
    return rows


def resolve_quarantine_record(
    *,
    goldset_root: Path,
    paper_id: str,
    resolution: str,
    reviewer: str,
    notes: str = "",
) -> dict[str, Any]:
    normalized_resolution = resolution.strip().upper()
    if not normalized_resolution:
        raise RuntimeError("resolution is required")

    quarantine_path = _quarantine_path_for(goldset_root, paper_id)
    if not quarantine_path.exists():
        raise FileNotFoundError(f"quarantine_missing={quarantine_path}")

    quarantine_record = _load_json(quarantine_path)
    reviewed_at = _utc_now_iso()
    accepted_after_review = normalized_resolution in PROMOTE_RESOLUTIONS
    manual_corrected = normalized_resolution in MANUAL_CORRECTED_RESOLUTIONS
    review_payload = {
        "schema_version": "teacher_quarantine_review.v1",
        "paper_id": paper_id,
        "reviewed_at": reviewed_at,
        "reviewer": reviewer.strip() or "unknown",
        "resolution": normalized_resolution,
        "accepted_after_review": accepted_after_review,
        "manual_corrected": manual_corrected,
        "notes": notes.strip(),
        "reason_codes": quarantine_record.get("reason_codes", []),
        "quarantine_path": str(quarantine_path),
    }

    reviews_dir = _reviews_dir(goldset_root)
    reviews_dir.mkdir(parents=True, exist_ok=True)
    review_path = reviews_dir / f"{_safe_name(paper_id)}_{reviewed_at.replace(':', '').replace('-', '')}.json"
    review_path.write_text(json.dumps(review_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    manual_decision = {
        "paper_id": paper_id,
        "resolution": normalized_resolution,
        "manual_corrected": manual_corrected,
        "accepted_after_review": accepted_after_review,
        "reviewed_at": reviewed_at,
        "reviewer": review_payload["reviewer"],
        "notes": review_payload["notes"],
    }
    _append_jsonl(_manual_decisions_path(goldset_root), manual_decision)

    accepted_path = _accepted_path_for(goldset_root, paper_id)
    if accepted_after_review:
        accepted_path.parent.mkdir(parents=True, exist_ok=True)
        accepted_payload = dict(quarantine_record)
        accepted_payload["accepted"] = True
        accepted_payload["review"] = review_payload
        accepted_path.write_text(json.dumps(accepted_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    elif accepted_path.exists():
        accepted_path.unlink()

    return {
        "paper_id": paper_id,
        "resolution": normalized_resolution,
        "accepted_after_review": accepted_after_review,
        "manual_corrected": manual_corrected,
        "review_path": str(review_path),
        "manual_decisions_path": str(_manual_decisions_path(goldset_root)),
        "accepted_path": str(accepted_path) if accepted_after_review else None,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="List or resolve teacher-output quarantine records.")
    parser.add_argument(
        "--goldset-root",
        default=str(default_goldset_root()),
        help="Goldset root directory",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    list_parser = subparsers.add_parser("list", help="List quarantine records pending or completed review.")
    list_parser.add_argument("--all", action="store_true", help="Include already reviewed quarantine records.")

    resolve_parser = subparsers.add_parser("resolve", help="Resolve one quarantine record with a human decision.")
    resolve_parser.add_argument("--paper-id", required=True, help="Paper id to resolve")
    resolve_parser.add_argument(
        "--resolution",
        required=True,
        choices=sorted(PROMOTE_RESOLUTIONS | {"KEEP_QUARANTINE"}),
        help="Human review resolution",
    )
    resolve_parser.add_argument("--reviewer", default="human", help="Reviewer label for audit trail")
    resolve_parser.add_argument("--notes", default="", help="Optional short review note")

    args = parser.parse_args()
    goldset_root = Path(args.goldset_root).expanduser().resolve()

    if args.command == "list":
        rows = list_quarantine_records(goldset_root=goldset_root, include_resolved=bool(args.all))
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return 0

    result = resolve_quarantine_record(
        goldset_root=goldset_root,
        paper_id=args.paper_id,
        resolution=args.resolution,
        reviewer=args.reviewer,
        notes=args.notes,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
