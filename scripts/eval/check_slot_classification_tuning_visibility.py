#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _resolve_summary_path(path: Path) -> Path:
    candidate = path.expanduser().resolve()
    if candidate.is_dir():
        candidate = candidate / "summary.json"
    return candidate


def _load_summary(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"internal_data_readiness_summary_dict_expected={path}")
    return payload


def _compact_visibility_text(summary: dict[str, Any]) -> str:
    inputs = summary.get("inputs") if isinstance(summary.get("inputs"), dict) else {}
    decision = summary.get("decision") if isinstance(summary.get("decision"), dict) else {}

    parts: list[str] = [f"passed={bool(decision.get('passed'))}"]

    category_status = str(inputs.get("classification_tuning_review_status") or "").strip()
    if category_status:
        parts.append(f"status={category_status}")

    recommended_action = str(inputs.get("recommended_action") or "").strip()
    if recommended_action:
        parts.append(f"action={recommended_action}")

    surface_status = str(inputs.get("surface_status") or "").strip()
    if surface_status:
        parts.append(f"surface={surface_status}")

    blockers = decision.get("blockers")
    if isinstance(blockers, list) and blockers:
        parts.append(
            "blockers=" + ",".join(str(item).strip() for item in blockers if str(item).strip())
        )

    return " ".join(parts)


def build_slot_classification_tuning_visibility_summary(
    *,
    internal_data_readiness_summary: dict[str, Any],
    internal_data_readiness_summary_path: Path | None,
    run_id: str,
    allowed_category_statuses: list[str],
) -> dict[str, Any]:
    surfaces = (
        internal_data_readiness_summary.get("surfaces")
        if isinstance(internal_data_readiness_summary.get("surfaces"), dict)
        else {}
    )
    category_status = (
        internal_data_readiness_summary.get("category_status")
        if isinstance(internal_data_readiness_summary.get("category_status"), dict)
        else {}
    )
    surface = (
        surfaces.get("slot_classification_tuning_review")
        if isinstance(surfaces.get("slot_classification_tuning_review"), dict)
        else {}
    )
    decision = surface.get("decision") if isinstance(surface.get("decision"), dict) else {}

    surface_status = str(surface.get("status") or "").strip() or None
    classification_tuning_review_status = (
        str(category_status.get("classification_tuning_review") or "").strip() or None
    )
    summary_path = str(surface.get("summary_path") or "").strip() or None
    recommended_action = str(decision.get("recommended_action") or "").strip() or None

    blockers: list[str] = []
    if surface_status != "present":
        blockers.append("slot_classification_tuning_review_surface_not_present")
    if classification_tuning_review_status not in set(allowed_category_statuses):
        blockers.append("classification_tuning_review_category_not_report_visible")
    if not isinstance(surface.get("decision"), dict):
        blockers.append("slot_classification_tuning_review_decision_missing")
    if not summary_path:
        blockers.append("slot_classification_tuning_review_summary_path_missing")
    if not recommended_action:
        blockers.append("slot_classification_tuning_review_action_missing")

    return {
        "schema_version": "slot_classification_tuning_visibility.v1",
        "generated_at": _utc_now_iso(),
        "run_id": run_id,
        "thresholds": {
            "allowed_category_statuses": [str(item) for item in allowed_category_statuses if str(item)],
        },
        "inputs": {
            "internal_data_readiness_summary_path": (
                str(internal_data_readiness_summary_path)
                if internal_data_readiness_summary_path is not None
                else None
            ),
            "internal_data_readiness_run_id": internal_data_readiness_summary.get("run_id"),
            "internal_data_readiness_generated_at": internal_data_readiness_summary.get("generated_at"),
            "surface_status": surface_status,
            "classification_tuning_review_status": classification_tuning_review_status,
            "slot_tuning_summary_path": summary_path,
            "slot_tuning_markdown_path": str(surface.get("markdown_path") or "").strip() or None,
            "recommended_action": recommended_action,
            "review_ready": bool(decision.get("review_ready")) if isinstance(decision, dict) else None,
        },
        "decision": {
            "passed": not blockers,
            "report_visible": not blockers,
            "blockers": blockers,
            "decision_reason": (
                "slot classification tuning review remains visible in broader reporting even while the lane stays advisory-only"
                if not blockers
                else "slot classification tuning review is missing or incomplete in the broader reporting lane"
            ),
        },
    }


def run_slot_classification_tuning_visibility(
    *,
    internal_data_readiness_summary_path: Path,
    out_dir: Path,
    run_id: str,
    allowed_category_statuses: list[str],
) -> Path:
    resolved_summary_path = _resolve_summary_path(internal_data_readiness_summary_path)
    summary = build_slot_classification_tuning_visibility_summary(
        internal_data_readiness_summary=_load_summary(resolved_summary_path),
        internal_data_readiness_summary_path=resolved_summary_path,
        run_id=run_id,
        allowed_category_statuses=allowed_category_statuses,
    )
    run_root = out_dir / run_id
    _write_json(run_root / "summary.json", summary)
    return run_root


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Visibility check that keeps slot-classification tuning review present in the broader internal-data reporting lane."
    )
    parser.add_argument(
        "--internal-data-summary",
        required=True,
        help="Path to an internal_data_readiness summary.json file or its run directory.",
    )
    parser.add_argument(
        "--out-dir",
        default=str(ROOT / "snapshots" / "slot_classification_tuning_visibility"),
        help="Directory to write the visibility summary into.",
    )
    parser.add_argument("--run-id", required=True, help="Output run identifier.")
    parser.add_argument(
        "--allowed-category-status",
        action="append",
        dest="allowed_category_statuses",
        default=None,
        help="Allowed classification_tuning_review category status. May be passed multiple times.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_arg_parser()
    args = parser.parse_args(argv)
    run_root = run_slot_classification_tuning_visibility(
        internal_data_readiness_summary_path=Path(args.internal_data_summary),
        out_dir=Path(args.out_dir).expanduser().resolve(),
        run_id=str(args.run_id),
        allowed_category_statuses=args.allowed_category_statuses or ["advisory_hold", "review_ready"],
    )
    payload = _load_summary(run_root / "summary.json")
    print(f"[check_slot_classification_tuning_visibility] out={run_root}")
    print(f"[check_slot_classification_tuning_visibility] summary={run_root / 'summary.json'}")
    print(
        "[check_slot_classification_tuning_visibility] "
        + _compact_visibility_text(payload)
    )
    return 0 if bool(((payload.get("decision") or {}).get("passed"))) else 1


if __name__ == "__main__":
    raise SystemExit(main())
