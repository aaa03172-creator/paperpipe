#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _load_json_dict(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"json_object_expected={path}")
    return payload


def _load_jsonl_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        payload = json.loads(line)
        if isinstance(payload, dict):
            rows.append(payload)
    return rows


def _artifact_history_promotion_policy_path() -> Path:
    value = os.getenv("PAPERPIPE_ARTIFACT_HISTORY_PROMOTION_POLICY_PATH")
    if value:
        return Path(value).expanduser().resolve()
    return (ROOT / "config" / "artifact_history_promotion_policy.json").resolve()


def _load_artifact_history_policy() -> dict[str, Any]:
    path = _artifact_history_promotion_policy_path()
    payload = _load_json_dict(path)

    required_families = [str(item).strip() for item in (payload.get("required_families") or [])]
    thresholds = payload.get("thresholds") or {}
    threshold_families = [str(item).strip() for item in (thresholds.get("required_families") or [])]

    if payload.get("schema_version") != "artifact_history_promotion_policy.v1":
        raise ValueError(f"unexpected_policy_schema_version={payload.get('schema_version')}")
    if payload.get("status") != "active":
        raise ValueError(f"unexpected_policy_status={payload.get('status')}")
    if payload.get("policy_mode") != "manual_review_only":
        raise ValueError(f"unexpected_policy_mode={payload.get('policy_mode')}")
    if not required_families:
        raise ValueError("policy_required_families_missing")
    if required_families != threshold_families:
        raise ValueError("policy_required_families_mismatch")
    for key in (
        "min_review_feedback_events",
        "min_generation_outcome_events",
        "min_paired_artifacts",
    ):
        value = thresholds.get(key)
        if not isinstance(value, int) or value < 0:
            raise ValueError(f"invalid_policy_threshold={key}")
    return {
        "path": path,
        "policy_mode": str(payload["policy_mode"]),
        "required_families": required_families,
        "thresholds": {
            "required_families": threshold_families,
            "min_review_feedback_events": int(thresholds["min_review_feedback_events"]),
            "min_generation_outcome_events": int(thresholds["min_generation_outcome_events"]),
            "min_paired_artifacts": int(thresholds["min_paired_artifacts"]),
        },
    }


def _paperpipe_home() -> Path:
    value = os.getenv("PAPERPIPE_HOME")
    if value:
        return Path(value).expanduser().resolve()
    return ROOT


def _storage_root() -> Path:
    value = os.getenv("PAPERPIPE_STORAGE_DIR")
    if value:
        return Path(value).expanduser().resolve()
    if os.getenv("PAPERPIPE_HOME"):
        return (_paperpipe_home() / "storage").resolve()
    return (ROOT / "storage").resolve()


def _artifact_review_feedback_log_path() -> Path:
    value = os.getenv("PAPERPIPE_ARTIFACT_REVIEW_FEEDBACK_LOG_PATH")
    if value:
        return Path(value).expanduser().resolve()
    return (_storage_root() / "artifact_review_feedback.jsonl").resolve()


def _artifact_generation_outcome_log_path() -> Path:
    value = os.getenv("PAPERPIPE_ARTIFACT_GENERATION_OUTCOME_LOG_PATH")
    if value:
        return Path(value).expanduser().resolve()
    return (_storage_root() / "artifact_generation_outcomes.jsonl").resolve()


def _review_counts(rows: list[dict[str, Any]], artifact_type: str) -> dict[str, int]:
    counts = Counter(
        str(row.get("artifact_id") or "").strip()
        for row in rows
        if str(row.get("artifact_type") or "").strip() == artifact_type and str(row.get("artifact_id") or "").strip()
    )
    return {key: int(value) for key, value in counts.items()}


def _paired_counts(
    review_rows: list[dict[str, Any]],
    outcome_rows: list[dict[str, Any]],
    artifact_type: str,
) -> dict[str, int]:
    review_ids = Counter(
        str(row.get("artifact_id") or "").strip()
        for row in review_rows
        if str(row.get("artifact_type") or "").strip() == artifact_type and str(row.get("artifact_id") or "").strip()
    )
    outcome_ids = Counter(
        str(row.get("artifact_id") or "").strip()
        for row in outcome_rows
        if str(row.get("artifact_type") or "").strip() == artifact_type and str(row.get("artifact_id") or "").strip()
    )
    paired_ids = set(review_ids) & set(outcome_ids)
    return {artifact_id: 1 for artifact_id in paired_ids}


def _meeting_packs_root() -> Path:
    value = os.getenv("PAPERPIPE_MEETING_PACKS_DIR")
    if value:
        return Path(value).expanduser().resolve()
    return (_storage_root() / "meeting_packs").resolve()


def _protocol_cards_root() -> Path:
    value = os.getenv("PAPERPIPE_PROTOCOL_CARDS_DIR")
    if value:
        return Path(value).expanduser().resolve()
    return (_storage_root() / "protocol_cards").resolve()


def _json_artifact_rows(root: Path, filename: str) -> list[dict[str, Any]]:
    if not root.exists():
        return []

    rows: list[dict[str, Any]] = []
    for artifact_dir in sorted(entry for entry in root.iterdir() if entry.is_dir()):
        path = artifact_dir / filename
        if not path.exists():
            continue
        try:
            payload = _load_json_dict(path)
        except Exception:
            continue
        rows.append(payload)
    return rows


def _is_fixture_like_meeting_pack_payload(payload: dict[str, Any]) -> bool:
    title = str(payload.get("title") or "").strip().lower()
    request_title = str((payload.get("generation_request") or {}).get("title") or "").strip().lower()

    if title.startswith("e2e ") or "fixture" in title or title.startswith("backend visual "):
        return True
    if request_title.startswith("e2e ") or "fixture" in request_title or request_title.startswith("backend visual "):
        return True

    for source in payload.get("source_items") or []:
        if not isinstance(source, dict):
            continue
        ref = str(source.get("ref") or "").strip().lower()
        source_title = str(source.get("title") or "").strip().lower()
        if "e2e" in ref or "fixture" in ref:
            return True
        if source_title.startswith("e2e ") or "fixture" in source_title:
            return True

    return False


def _prefer_non_fixture_meeting_pack_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    visible = [row for row in rows if not _is_fixture_like_meeting_pack_payload(row)]
    return visible or rows


def _protocol_card_candidate_kind(payload: dict[str, Any]) -> str:
    title = str(payload.get("title") or "").strip().lower()
    purpose = str(payload.get("purpose") or "").strip().lower()
    context = str(payload.get("context") or "").strip().lower()
    linked_paper_ids = [str(item).strip().lower() for item in (payload.get("linked_paper_ids") or [])]
    linked_note_slugs = [str(item).strip().lower() for item in (payload.get("linked_note_slugs") or [])]

    smoke_markers = ("smoke", "reviewprotocolsmoke")
    verification_markers = ("verification", "re-entry verification")
    if any(marker in title for marker in smoke_markers + verification_markers):
        return "verification_or_smoke"
    if any(marker in purpose for marker in smoke_markers + verification_markers):
        return "verification_or_smoke"
    if any(marker in context for marker in smoke_markers + verification_markers):
        return "verification_or_smoke"
    if any("paper-review-smoke" == item for item in linked_paper_ids):
        return "verification_or_smoke"
    if any(marker in item for item in linked_note_slugs for marker in smoke_markers):
        return "verification_or_smoke"
    return "review_candidate"


def _meeting_pack_items() -> list[dict[str, Any]]:
    packs = _prefer_non_fixture_meeting_pack_rows(
        _json_artifact_rows(_meeting_packs_root(), "meeting_pack.json")
    )
    return [
        {
            "artifact_type": "meeting_pack",
            "artifact_id": str(pack.get("id") or "").strip(),
            "title": str(pack.get("title") or "").strip(),
            "timestamp": str(pack.get("created_at") or "").strip(),
            "candidate_kind": "review_candidate",
        }
        for pack in sorted(
            packs,
            key=lambda item: (str(item.get("created_at") or ""), str(item.get("id") or "")),
            reverse=True,
        )
        if str(pack.get("id") or "").strip()
    ]


def _protocol_card_items() -> list[dict[str, Any]]:
    items = _json_artifact_rows(_protocol_cards_root(), "protocol_card.json")
    return [
        {
            "artifact_type": "protocol_card",
            "artifact_id": str(item.get("protocol_id") or "").strip(),
            "title": str(item.get("title") or "").strip(),
            "timestamp": str(item.get("updated_at") or item.get("created_at") or "").strip(),
            "candidate_kind": _protocol_card_candidate_kind(item),
        }
        for item in sorted(
            items,
            key=lambda entry: (
                str(entry.get("updated_at") or entry.get("created_at") or ""),
                str(entry.get("protocol_id") or ""),
            ),
            reverse=True,
        )
        if str(item.get("protocol_id") or "").strip()
    ]


def _candidate_commands(artifact_type: str, artifact_id: str) -> dict[str, str]:
    if artifact_type == "meeting_pack":
        return {
            "review": f"paperpipe artifact-history meeting-pack-review {artifact_id} --run-id <run_id> --decision <decision> --reason-code <reason_code> --actor-id <actor_id> --note '<note>'",
            "outcome": f"paperpipe artifact-history meeting-pack-outcome {artifact_id} --run-id <run_id> --review-feedback-id <feedback_id> --decision <decision> --downstream-use <downstream_use> --actor-id <actor_id> --note '<note>'",
        }
    return {
        "review": f"paperpipe artifact-history protocol-card-review {artifact_id} --paper-id <paper_id> --decision <decision> --reason-code <reason_code> --actor-id <actor_id> --note '<note>'",
        "outcome": f"paperpipe artifact-history protocol-card-outcome {artifact_id} --paper-id <paper_id> --review-feedback-id <feedback_id> --decision <decision> --downstream-use <downstream_use> --actor-id <actor_id> --note '<note>'",
    }


def _build_family_summary(
    *,
    artifact_type: str,
    items: list[dict[str, Any]],
    review_rows: list[dict[str, Any]],
    outcome_rows: list[dict[str, Any]],
    thresholds: dict[str, Any],
    max_candidates: int,
) -> dict[str, Any]:
    review_counts = _review_counts(review_rows, artifact_type)
    outcome_counts = _review_counts(outcome_rows, artifact_type)
    paired_counts = _paired_counts(review_rows, outcome_rows, artifact_type)

    candidate_items: list[dict[str, Any]] = []
    sufficient_history_count = 0
    partial_history_count = 0
    verification_or_smoke_candidate_count = 0

    for item in items:
        artifact_id = item["artifact_id"]
        review_count = review_counts.get(artifact_id, 0)
        outcome_count = outcome_counts.get(artifact_id, 0)
        paired_count = paired_counts.get(artifact_id, 0)
        sufficient = (
            review_count >= thresholds["min_review_feedback_events"]
            and outcome_count >= thresholds["min_generation_outcome_events"]
            and paired_count >= thresholds["min_paired_artifacts"]
        )
        has_any_history = review_count > 0 or outcome_count > 0
        if sufficient:
            sufficient_history_count += 1
        elif has_any_history:
            partial_history_count += 1

        history_status = "sufficient" if sufficient else "partial" if has_any_history else "missing"
        candidate = {
            **item,
            "review_feedback_count": review_count,
            "generation_outcome_count": outcome_count,
            "paired_artifact_count": paired_count,
            "history_status": history_status,
            "commands": _candidate_commands(artifact_type, artifact_id),
        }
        if not sufficient:
            if candidate.get("candidate_kind") == "verification_or_smoke":
                verification_or_smoke_candidate_count += 1
            candidate_items.append(candidate)

    return {
        "artifact_type": artifact_type,
        "artifact_count": len(items),
        "artifacts_with_sufficient_history": sufficient_history_count,
        "artifacts_with_partial_history": partial_history_count,
        "candidate_count": len(candidate_items),
        "verification_or_smoke_candidate_count": verification_or_smoke_candidate_count,
        "candidates": candidate_items[:max_candidates],
    }


def build_artifact_history_capture_candidate_summary(
    *,
    run_id: str,
    max_candidates_per_family: int,
) -> dict[str, Any]:
    policy = _load_artifact_history_policy()
    policy_path = policy["path"]
    review_log_path = _artifact_review_feedback_log_path()
    outcome_log_path = _artifact_generation_outcome_log_path()
    review_rows = _load_jsonl_rows(review_log_path)
    outcome_rows = _load_jsonl_rows(outcome_log_path)

    family_items = {
        "meeting_pack": _meeting_pack_items(),
        "protocol_card": _protocol_card_items(),
    }
    family_summaries = {
        artifact_type: _build_family_summary(
            artifact_type=artifact_type,
            items=family_items[artifact_type],
            review_rows=review_rows,
            outcome_rows=outcome_rows,
            thresholds=policy["thresholds"],
            max_candidates=max_candidates_per_family,
        )
        for artifact_type in policy["required_families"]
    }

    families_needing_history = [
        artifact_type
        for artifact_type, summary in family_summaries.items()
        if summary["candidate_count"] > 0
    ]
    top_candidate = None
    for artifact_type in policy["required_families"]:
        candidates = family_summaries[artifact_type]["candidates"]
        preferred_candidates = [
            candidate for candidate in candidates if candidate.get("candidate_kind") != "verification_or_smoke"
        ]
        if preferred_candidates:
            top_candidate = preferred_candidates[0]
            break
        if candidates and top_candidate is None:
            top_candidate = candidates[0]
            break

    return {
        "schema_version": "artifact_history_capture_candidates.v1",
        "generated_at": _utc_now_iso(),
        "run_id": run_id,
        "policy_path": str(policy_path),
        "policy_mode": policy["policy_mode"],
        "thresholds": policy["thresholds"],
        "inputs": {
            "review_feedback_log_path": str(review_log_path),
            "generation_outcome_log_path": str(outcome_log_path),
            "review_feedback_row_count": len(review_rows),
            "generation_outcome_row_count": len(outcome_rows),
        },
        "families": family_summaries,
        "decision": {
            "history_capture_candidates_present": bool(families_needing_history),
            "required_families_needing_more_history": families_needing_history,
            "top_capture_candidate": top_candidate,
            "next_step": (
                "record real operator review/outcome history for the top candidate using the suggested commands"
                if top_candidate is not None
                else "all required families currently meet the bounded history threshold"
            ),
        },
    }


def run_artifact_history_capture_candidate_audit(
    *,
    out_dir: Path,
    run_id: str,
    max_candidates_per_family: int,
) -> Path:
    summary = build_artifact_history_capture_candidate_summary(
        run_id=run_id,
        max_candidates_per_family=max_candidates_per_family,
    )
    run_root = out_dir / run_id
    _write_json(run_root / "summary.json", summary)
    return run_root


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Summarize active-root meeting_pack/protocol_card artifacts that still need bounded history capture."
    )
    parser.add_argument(
        "--out-dir",
        default=str(ROOT / "snapshots" / "artifact_history_capture_candidates"),
        help="Output directory for the candidate summary.",
    )
    parser.add_argument("--run-id", required=True, help="Output run identifier.")
    parser.add_argument(
        "--max-candidates-per-family",
        type=int,
        default=5,
        help="Maximum candidate artifacts to include per family.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    run_root = run_artifact_history_capture_candidate_audit(
        out_dir=Path(args.out_dir).expanduser().resolve(),
        run_id=str(args.run_id),
        max_candidates_per_family=max(int(args.max_candidates_per_family), 1),
    )
    print(run_root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
