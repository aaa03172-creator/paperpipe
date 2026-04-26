#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timezone
import os
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.services.processor_gate_replay_drift import (
    build_processor_gate_threshold_review_viewer_command,
    load_processor_gate_threshold_review_summary,
    render_processor_gate_threshold_review_markdown,
    resolve_processor_gate_threshold_review_drift_artifacts,
)

DEFAULT_WORKSHEET_FILENAMES = (
    "manual_review_checklist.csv",
    "manual_review_frontier.csv",
    "manual_review_seed.csv",
)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _resolve_review_summary_path(path_or_dir: Path) -> Path:
    candidate = path_or_dir.expanduser().resolve(strict=False)
    return candidate / "summary.json" if candidate.is_dir() else candidate


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _normalize_text(value: object) -> str:
    return str(value or "").strip()


def _normalize_yes_no(value: object) -> str:
    text = _normalize_text(value).lower()
    if text in {"yes", "y", "true", "1"}:
        return "yes"
    if text in {"no", "n", "false", "0"}:
        return "no"
    return ""


def _load_review_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _resolve_default_worksheet(run_root: Path) -> Path:
    for filename in DEFAULT_WORKSHEET_FILENAMES:
        candidate = run_root / filename
        if candidate.exists():
            return candidate
    raise FileNotFoundError(
        "no processor gate manual review worksheet found; expected one of: "
        + ", ".join(DEFAULT_WORKSHEET_FILENAMES)
    )


def _row_completed(row: dict[str, str]) -> bool:
    return bool(
        _normalize_text(row.get("reviewer_disposition"))
        and _normalize_yes_no(row.get("supports_mid_confidence_policy_review"))
        and _normalize_yes_no(row.get("supports_high_threshold_change"))
    )


def _row_has_any_review_input(row: dict[str, str]) -> bool:
    return any(
        _normalize_text(row.get(field))
        for field in (
            "reviewer_disposition",
            "supports_mid_confidence_policy_review",
            "supports_high_threshold_change",
            "reviewer_notes",
        )
    )


def _row_default_agreement(row: dict[str, str]) -> bool:
    return (
        _normalize_text(row.get("reviewer_disposition"))
        == _normalize_text(row.get("default_reviewer_disposition"))
        and _normalize_yes_no(row.get("supports_mid_confidence_policy_review"))
        == _normalize_yes_no(row.get("default_supports_mid_confidence_policy_review"))
        and _normalize_yes_no(row.get("supports_high_threshold_change"))
        == _normalize_yes_no(row.get("default_supports_high_threshold_change"))
    )


def _outcome_status(
    *,
    total_rows: int,
    completed_rows: int,
    supports_mid_count: int,
    supports_high_count: int,
) -> tuple[str, str, str]:
    if total_rows <= 0:
        return (
            "empty_worksheet",
            "No manual review rows were available in the worksheet.",
            "Populate the worksheet with threshold-relevant rows before using it for calibration.",
        )
    if completed_rows <= 0:
        return (
            "not_reviewed",
            "No completed reviewer decisions are present yet.",
            "Fill reviewer disposition/support columns before treating this worksheet as calibration evidence.",
        )
    if completed_rows < total_rows:
        return (
            "partially_reviewed",
            f"{completed_rows}/{total_rows} row(s) are complete; finish the remaining rows before using this review as threshold evidence.",
            "Complete the remaining worksheet rows before making any gate-threshold conclusion.",
        )
    if supports_high_count > 0:
        return (
            "boundary_candidate_found",
            f"{supports_high_count}/{total_rows} reviewed row(s) support high-threshold boundary inspection.",
            "Keep policy-only rows separate and open a direct high-threshold boundary review with the supporting rows.",
        )
    if supports_mid_count == total_rows:
        return (
            "policy_only_confirmed",
            f"All {total_rows} reviewed row(s) support policy-only treatment and none support a high-threshold change.",
            "Keep the current high threshold unchanged and continue the mid-confidence escalation policy review lane.",
        )
    return (
        "mixed_review_result",
        f"Reviewed rows are mixed: {supports_mid_count}/{total_rows} support policy review and {supports_high_count}/{total_rows} support high-threshold change.",
        "Synthesize the divergent reviewed rows before changing threshold policy or closing the manual review.",
    )


def build_processor_gate_manual_review_outcome(
    *,
    review_summary: dict[str, Any],
    worksheet_path: Path,
    worksheet_rows: list[dict[str, str]],
) -> dict[str, Any]:
    total_rows = len(worksheet_rows)
    rows_with_input = [row for row in worksheet_rows if _row_has_any_review_input(row)]
    completed_rows = [row for row in worksheet_rows if _row_completed(row)]
    incomplete_rows = [row for row in worksheet_rows if _row_has_any_review_input(row) and not _row_completed(row)]
    untouched_rows = [row for row in worksheet_rows if not _row_has_any_review_input(row)]

    disposition_counts: dict[str, int] = {}
    supports_mid_count = 0
    supports_high_count = 0
    default_agreement_count = 0
    default_divergence_count = 0
    default_divergence_ids: list[str] = []
    high_threshold_candidate_ids: list[str] = []
    policy_only_confirmed_ids: list[str] = []

    for row in completed_rows:
        disposition = _normalize_text(row.get("reviewer_disposition")) or "unknown"
        disposition_counts[disposition] = int(disposition_counts.get(disposition) or 0) + 1
        supports_mid = _normalize_yes_no(row.get("supports_mid_confidence_policy_review")) == "yes"
        supports_high = _normalize_yes_no(row.get("supports_high_threshold_change")) == "yes"
        if supports_mid:
            supports_mid_count += 1
        if supports_high:
            supports_high_count += 1

        paper_id = _normalize_text(row.get("paper_id"))
        if supports_high and paper_id:
            high_threshold_candidate_ids.append(paper_id)
        if disposition == "policy_only_review" and supports_mid and not supports_high and paper_id:
            policy_only_confirmed_ids.append(paper_id)

        if _row_default_agreement(row):
            default_agreement_count += 1
        else:
            default_divergence_count += 1
            if paper_id:
                default_divergence_ids.append(paper_id)

    status, summary_text, next_step = _outcome_status(
        total_rows=total_rows,
        completed_rows=len(completed_rows),
        supports_mid_count=supports_mid_count,
        supports_high_count=supports_high_count,
    )

    reviewed_ids = [
        paper_id
        for paper_id in (_normalize_text(row.get("paper_id")) for row in completed_rows)
        if paper_id
    ]
    incomplete_ids = [
        paper_id
        for paper_id in (_normalize_text(row.get("paper_id")) for row in incomplete_rows)
        if paper_id
    ]
    untouched_ids = [
        paper_id
        for paper_id in (_normalize_text(row.get("paper_id")) for row in untouched_rows)
        if paper_id
    ]

    return {
        "schema_version": "processor_gate_manual_review_outcome.v1",
        "generated_at": _utc_now_iso(),
        "run_id": str(review_summary.get("run_id") or worksheet_path.parent.name).strip() or worksheet_path.parent.name,
        "worksheet_path": str(worksheet_path),
        "worksheet_name": worksheet_path.name,
        "total_row_count": total_rows,
        "rows_with_any_review_input_count": len(rows_with_input),
        "completed_row_count": len(completed_rows),
        "incomplete_row_count": len(incomplete_rows),
        "untouched_row_count": len(untouched_rows),
        "review_ready": len(completed_rows) == total_rows and total_rows > 0,
        "status": status,
        "summary": summary_text,
        "next_step": next_step,
        "reviewer_disposition_counts": dict(sorted(disposition_counts.items())),
        "supports_mid_confidence_policy_review_count": supports_mid_count,
        "supports_high_threshold_change_count": supports_high_count,
        "default_agreement_count": default_agreement_count,
        "default_divergence_count": default_divergence_count,
        "reviewed_ids": reviewed_ids,
        "incomplete_ids": incomplete_ids,
        "untouched_ids": untouched_ids,
        "default_divergence_ids": default_divergence_ids,
        "high_threshold_candidate_ids": high_threshold_candidate_ids,
        "policy_only_confirmed_ids": policy_only_confirmed_ids,
    }


def render_processor_gate_manual_review_outcome_markdown(payload: dict[str, Any]) -> str:
    lines = [
        f"# Processor Gate Manual Review Outcome: {payload.get('run_id') or '-'}",
        "",
        f"- Generated At: {payload.get('generated_at') or '-'}",
        f"- Worksheet: {payload.get('worksheet_path') or '-'}",
        f"- Status: {payload.get('status') or '-'}",
        f"- Review Ready: {'yes' if bool(payload.get('review_ready')) else 'no'}",
        f"- Summary: {payload.get('summary') or '-'}",
        f"- Next Step: {payload.get('next_step') or '-'}",
        f"- Completed Rows: {payload.get('completed_row_count') or 0}/{payload.get('total_row_count') or 0}",
        f"- Incomplete Rows: {payload.get('incomplete_row_count') or 0}",
        f"- Untouched Rows: {payload.get('untouched_row_count') or 0}",
        f"- Default Agreement: {payload.get('default_agreement_count') or 0}",
        f"- Default Divergence: {payload.get('default_divergence_count') or 0}",
        f"- Supports Mid-Confidence Policy Review: {payload.get('supports_mid_confidence_policy_review_count') or 0}",
        f"- Supports High-Threshold Change: {payload.get('supports_high_threshold_change_count') or 0}",
        "",
    ]

    for title, key in (
        ("Reviewer Dispositions", "reviewer_disposition_counts"),
        ("Reviewed IDs", "reviewed_ids"),
        ("Incomplete IDs", "incomplete_ids"),
        ("Untouched IDs", "untouched_ids"),
        ("Default Divergence IDs", "default_divergence_ids"),
        ("High-Threshold Candidate IDs", "high_threshold_candidate_ids"),
        ("Policy-Only Confirmed IDs", "policy_only_confirmed_ids"),
    ):
        value = payload.get(key)
        if isinstance(value, dict) and value:
            lines.append(f"## {title}")
            for item_key, item_value in sorted(value.items()):
                lines.append(f"- {item_key}: {int(item_value or 0)}")
            lines.append("")
        elif isinstance(value, list) and value:
            lines.append(f"## {title}")
            lines.extend(f"- {str(item).strip()}" for item in value if str(item).strip())
            lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def build_processor_gate_threshold_change_decision(
    *,
    review_summary: dict[str, Any],
    manual_review_outcome: dict[str, Any],
    threshold_change_preflight: dict[str, Any] | None = None,
) -> dict[str, Any]:
    inputs = review_summary.get("inputs") if isinstance(review_summary.get("inputs"), dict) else {}
    decision = (
        review_summary.get("decision")
        if isinstance(review_summary.get("decision"), dict)
        else {}
    )

    outcome_status = str(manual_review_outcome.get("status") or "").strip()
    review_ready = bool(manual_review_outcome.get("review_ready"))
    supports_high_count = int(manual_review_outcome.get("supports_high_threshold_change_count") or 0)
    supports_mid_count = int(
        manual_review_outcome.get("supports_mid_confidence_policy_review_count") or 0
    )
    completed_count = int(manual_review_outcome.get("completed_row_count") or 0)
    total_count = int(manual_review_outcome.get("total_row_count") or 0)
    high_candidate_ids = [
        str(item).strip()
        for item in manual_review_outcome.get("high_threshold_candidate_ids", [])
        if str(item).strip()
    ] if isinstance(manual_review_outcome.get("high_threshold_candidate_ids"), list) else []
    preflight = threshold_change_preflight or {
        "required": False,
        "ready": False,
        "status": "not_applicable",
        "blocker": None,
    }
    preflight_ready = bool(preflight.get("ready"))
    preflight_status = str(preflight.get("status") or "").strip() or "not_applicable"
    preflight_blocker = str(preflight.get("blocker") or "").strip() or None

    if outcome_status == "policy_only_confirmed" and review_ready and supports_high_count == 0:
        final_status = "no_threshold_change_supported"
        recommended_action = "keep_current_high_threshold"
        next_step = "continue_mid_confidence_escalation_policy_review"
        decision_summary = (
            f"Manual review confirmed {completed_count}/{total_count} threshold-relevant row(s) as "
            "policy-only; none support a high-threshold change."
        )
        threshold_change_ready = False
    elif supports_high_count > 0:
        if preflight_ready:
            final_status = "high_threshold_boundary_review_needed"
            recommended_action = "review_high_threshold_boundary_candidates"
            next_step = "open_high_threshold_boundary_review"
            decision_summary = (
                f"Manual review found {supports_high_count}/{total_count} row(s) that may support "
                "high-threshold boundary inspection, and validation replay matched the proposal."
            )
            threshold_change_ready = True
        else:
            final_status = "threshold_change_validation_replay_required"
            recommended_action = "run_threshold_change_validation_replay_before_decision"
            next_step = "run_threshold_change_validation_replay"
            blocker_text = preflight_blocker or preflight_status
            decision_summary = (
                f"Manual review found {supports_high_count}/{total_count} row(s) that may support "
                "high-threshold boundary inspection, but threshold-change decision readiness is "
                f"blocked until validation replay matches the proposal ({blocker_text})."
            )
            threshold_change_ready = False
    elif not review_ready:
        final_status = "manual_review_incomplete"
        recommended_action = "complete_manual_review_before_threshold_decision"
        next_step = "complete_processor_gate_manual_review"
        decision_summary = (
            f"Manual review is incomplete: {completed_count}/{total_count} row(s) are complete."
        )
        threshold_change_ready = False
    else:
        final_status = "mixed_manual_review_result"
        recommended_action = "synthesize_manual_review_before_threshold_decision"
        next_step = "resolve_mixed_manual_review_result"
        decision_summary = (
            f"Manual review is mixed: {supports_mid_count}/{total_count} row(s) support policy review "
            f"and {supports_high_count}/{total_count} row(s) support high-threshold inspection."
        )
        threshold_change_ready = False

    return {
        "schema_version": "processor_gate_threshold_change_decision.v1",
        "generated_at": _utc_now_iso(),
        "run_id": str(review_summary.get("run_id") or manual_review_outcome.get("run_id") or "").strip()
        or None,
        "source_worksheet_path": str(manual_review_outcome.get("worksheet_path") or "").strip()
        or None,
        "outcome_status": outcome_status or None,
        "final_status": final_status,
        "recommended_action": recommended_action,
        "threshold_change_ready": threshold_change_ready,
        "threshold_change_status": final_status,
        "threshold_change_next_step": next_step,
        "threshold_change_preflight": {
            "required": bool(preflight.get("required")),
            "ready": preflight_ready,
            "status": preflight_status,
            "blocker": preflight_blocker,
            "validation_replay_status": str(
                preflight.get("validation_replay_status") or ""
            ).strip()
            or None,
            "validation_replay_matches_proposal": bool(
                preflight.get("validation_replay_matches_proposal")
            ),
        },
        "summary": decision_summary,
        "current_thresholds": {
            "high": inputs.get("high_threshold"),
            "low": inputs.get("low_threshold"),
        },
        "manual_review_counts": {
            "total": total_count,
            "completed": completed_count,
            "supports_mid_confidence_policy_review": supports_mid_count,
            "supports_high_threshold_change": supports_high_count,
            "default_divergence": int(manual_review_outcome.get("default_divergence_count") or 0),
        },
        "high_threshold_candidate_ids": high_candidate_ids,
        "policy_only_confirmed_ids": [
            str(item).strip()
            for item in manual_review_outcome.get("policy_only_confirmed_ids", [])
            if str(item).strip()
        ]
        if isinstance(manual_review_outcome.get("policy_only_confirmed_ids"), list)
        else [],
        "original_threshold_review_status": str(decision.get("threshold_change_status") or "").strip()
        or None,
        "original_threshold_review_next_step": str(
            decision.get("threshold_change_next_step") or ""
        ).strip()
        or None,
        "operator_note": (
            "This is a review artifact only. It does not modify live gate thresholds or runtime gate policy."
        ),
    }


def render_processor_gate_threshold_change_decision_markdown(payload: dict[str, Any]) -> str:
    current_thresholds = (
        payload.get("current_thresholds")
        if isinstance(payload.get("current_thresholds"), dict)
        else {}
    )
    manual_review_counts = (
        payload.get("manual_review_counts")
        if isinstance(payload.get("manual_review_counts"), dict)
        else {}
    )
    preflight = (
        payload.get("threshold_change_preflight")
        if isinstance(payload.get("threshold_change_preflight"), dict)
        else {}
    )
    preflight_text = (
        f"required={'yes' if bool(preflight.get('required')) else 'no'}, "
        f"ready={'yes' if bool(preflight.get('ready')) else 'no'}, "
        f"status={preflight.get('status') or '-'}"
    )
    if preflight.get("blocker"):
        preflight_text = f"{preflight_text}, blocker={preflight.get('blocker')}"

    lines = [
        f"# Processor Gate Threshold Change Decision: {payload.get('run_id') or '-'}",
        "",
        f"- Generated At: {payload.get('generated_at') or '-'}",
        f"- Final Status: {payload.get('final_status') or '-'}",
        f"- Recommended Action: {payload.get('recommended_action') or '-'}",
        f"- Threshold Change Ready: {'yes' if bool(payload.get('threshold_change_ready')) else 'no'}",
        f"- Threshold Change Next Step: {payload.get('threshold_change_next_step') or '-'}",
        f"- Threshold Change Preflight: {preflight_text}",
        f"- Summary: {payload.get('summary') or '-'}",
        f"- Current High Threshold: {current_thresholds.get('high') if current_thresholds.get('high') is not None else '-'}",
        f"- Current Low Threshold: {current_thresholds.get('low') if current_thresholds.get('low') is not None else '-'}",
        f"- Reviewed Rows: {manual_review_counts.get('completed') or 0}/{manual_review_counts.get('total') or 0}",
        f"- Supports Mid-Confidence Policy Review: {manual_review_counts.get('supports_mid_confidence_policy_review') or 0}",
        f"- Supports High-Threshold Change: {manual_review_counts.get('supports_high_threshold_change') or 0}",
        f"- Default Divergence: {manual_review_counts.get('default_divergence') or 0}",
        f"- Operator Note: {payload.get('operator_note') or '-'}",
        "",
    ]

    high_threshold_candidate_ids = (
        [str(item).strip() for item in payload.get("high_threshold_candidate_ids", []) if str(item).strip()]
        if isinstance(payload.get("high_threshold_candidate_ids"), list)
        else []
    )
    if high_threshold_candidate_ids:
        lines.append("## High-Threshold Candidate IDs")
        lines.extend(f"- {item}" for item in high_threshold_candidate_ids)
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def build_processor_gate_mid_confidence_policy_decision(
    *,
    review_summary: dict[str, Any],
    manual_review_outcome: dict[str, Any],
    threshold_change_decision: dict[str, Any],
) -> dict[str, Any]:
    inputs = review_summary.get("inputs") if isinstance(review_summary.get("inputs"), dict) else {}

    total_count = int(manual_review_outcome.get("total_row_count") or 0)
    completed_count = int(manual_review_outcome.get("completed_row_count") or 0)
    supports_mid_count = int(
        manual_review_outcome.get("supports_mid_confidence_policy_review_count") or 0
    )
    supports_high_count = int(manual_review_outcome.get("supports_high_threshold_change_count") or 0)
    outcome_status = str(manual_review_outcome.get("status") or "").strip()
    threshold_final_status = str(threshold_change_decision.get("final_status") or "").strip()

    if (
        outcome_status == "policy_only_confirmed"
        and bool(manual_review_outcome.get("review_ready"))
        and total_count > 0
        and completed_count == total_count
        and supports_mid_count == total_count
        and supports_high_count == 0
        and threshold_final_status == "no_threshold_change_supported"
    ):
        final_status = "mid_confidence_escalation_policy_confirmed"
        recommended_action = "keep_mid_confidence_pending_review_policy"
        next_step = "treat_legacy_mid_confidence_approvals_as_policy_debt"
        summary_text = (
            f"Manual review confirmed {completed_count}/{total_count} reviewed row(s) as "
            "mid-confidence policy debt; keep the current pending-review behavior for "
            "mid-confidence rows."
        )
        policy_decision_ready = True
    elif not bool(manual_review_outcome.get("review_ready")):
        final_status = "manual_review_incomplete"
        recommended_action = "complete_manual_review_before_policy_decision"
        next_step = "complete_processor_gate_manual_review"
        summary_text = (
            f"Manual review is incomplete: {completed_count}/{total_count} row(s) are complete."
        )
        policy_decision_ready = False
    else:
        final_status = "mid_confidence_policy_review_unresolved"
        recommended_action = "resolve_manual_review_before_policy_decision"
        next_step = "resolve_mid_confidence_policy_review"
        summary_text = (
            f"Manual review is not a clean policy-only result: {supports_mid_count}/{total_count} "
            f"support mid-confidence policy review and {supports_high_count}/{total_count} support "
            "high-threshold inspection."
        )
        policy_decision_ready = False

    return {
        "schema_version": "processor_gate_mid_confidence_policy_decision.v1",
        "generated_at": _utc_now_iso(),
        "run_id": str(review_summary.get("run_id") or manual_review_outcome.get("run_id") or "").strip()
        or None,
        "source_worksheet_path": str(manual_review_outcome.get("worksheet_path") or "").strip()
        or None,
        "outcome_status": outcome_status or None,
        "threshold_change_final_status": threshold_final_status or None,
        "final_status": final_status,
        "recommended_action": recommended_action,
        "policy_decision_ready": policy_decision_ready,
        "runtime_change_ready": False,
        "next_step": next_step,
        "summary": summary_text,
        "current_thresholds": {
            "high": inputs.get("high_threshold"),
            "low": inputs.get("low_threshold"),
        },
        "manual_review_counts": {
            "total": total_count,
            "completed": completed_count,
            "supports_mid_confidence_policy_review": supports_mid_count,
            "supports_high_threshold_change": supports_high_count,
            "default_divergence": int(manual_review_outcome.get("default_divergence_count") or 0),
        },
        "policy_only_confirmed_ids": [
            str(item).strip()
            for item in manual_review_outcome.get("policy_only_confirmed_ids", [])
            if str(item).strip()
        ]
        if isinstance(manual_review_outcome.get("policy_only_confirmed_ids"), list)
        else [],
        "operator_note": (
            "This records the policy interpretation of reviewed drift rows. It does not mutate "
            "historical rows, live thresholds, or gate runtime behavior."
        ),
    }


def render_processor_gate_mid_confidence_policy_decision_markdown(payload: dict[str, Any]) -> str:
    current_thresholds = (
        payload.get("current_thresholds")
        if isinstance(payload.get("current_thresholds"), dict)
        else {}
    )
    manual_review_counts = (
        payload.get("manual_review_counts")
        if isinstance(payload.get("manual_review_counts"), dict)
        else {}
    )

    return (
        "\n".join(
            [
                f"# Processor Gate Mid-Confidence Policy Decision: {payload.get('run_id') or '-'}",
                "",
                f"- Generated At: {payload.get('generated_at') or '-'}",
                f"- Final Status: {payload.get('final_status') or '-'}",
                f"- Recommended Action: {payload.get('recommended_action') or '-'}",
                f"- Policy Decision Ready: {'yes' if bool(payload.get('policy_decision_ready')) else 'no'}",
                f"- Runtime Change Ready: {'yes' if bool(payload.get('runtime_change_ready')) else 'no'}",
                f"- Next Step: {payload.get('next_step') or '-'}",
                f"- Summary: {payload.get('summary') or '-'}",
                f"- Current High Threshold: {current_thresholds.get('high') if current_thresholds.get('high') is not None else '-'}",
                f"- Current Low Threshold: {current_thresholds.get('low') if current_thresholds.get('low') is not None else '-'}",
                f"- Reviewed Rows: {manual_review_counts.get('completed') or 0}/{manual_review_counts.get('total') or 0}",
                f"- Supports Mid-Confidence Policy Review: {manual_review_counts.get('supports_mid_confidence_policy_review') or 0}",
                f"- Supports High-Threshold Change: {manual_review_counts.get('supports_high_threshold_change') or 0}",
                f"- Operator Note: {payload.get('operator_note') or '-'}",
                "",
            ]
        ).rstrip()
        + "\n"
    )


def build_processor_gate_mid_confidence_policy_debt_reconciliation(
    *,
    review_summary: dict[str, Any],
    manual_review_outcome: dict[str, Any],
    threshold_change_decision: dict[str, Any],
    mid_confidence_policy_decision: dict[str, Any],
) -> dict[str, Any]:
    total_count = int(manual_review_outcome.get("total_row_count") or 0)
    completed_count = int(manual_review_outcome.get("completed_row_count") or 0)
    supports_mid_count = int(
        manual_review_outcome.get("supports_mid_confidence_policy_review_count") or 0
    )
    supports_high_count = int(manual_review_outcome.get("supports_high_threshold_change_count") or 0)
    policy_final_status = str(mid_confidence_policy_decision.get("final_status") or "").strip()
    threshold_final_status = str(threshold_change_decision.get("final_status") or "").strip()
    review_ready = bool(manual_review_outcome.get("review_ready"))

    if (
        review_ready
        and total_count > 0
        and completed_count == total_count
        and supports_mid_count == total_count
        and supports_high_count == 0
        and policy_final_status == "mid_confidence_escalation_policy_confirmed"
        and threshold_final_status == "no_threshold_change_supported"
    ):
        final_status = "legacy_policy_debt_confirmed"
        recommended_action = "keep_historical_approvals_as_legacy_policy_debt"
        next_step = "monitor_future_mid_confidence_pending_review"
        summary_text = (
            f"Manual review confirmed {completed_count}/{total_count} historical mid-confidence "
            "approval row(s) as policy debt. Keep the current pending-review behavior for future "
            "mid-confidence rows and do not mass-rewrite historical approvals from this artifact."
        )
        reconciliation_ready = True
    elif not review_ready:
        final_status = "manual_review_incomplete"
        recommended_action = "complete_manual_review_before_policy_debt_reconciliation"
        next_step = "complete_processor_gate_manual_review"
        summary_text = (
            f"Manual review is incomplete: {completed_count}/{total_count} row(s) are complete."
        )
        reconciliation_ready = False
    else:
        final_status = "policy_debt_reconciliation_unresolved"
        recommended_action = "resolve_manual_review_before_policy_debt_reconciliation"
        next_step = "resolve_mid_confidence_policy_review"
        summary_text = (
            f"Manual review is not a clean policy-debt result: {supports_mid_count}/{total_count} "
            f"support mid-confidence policy review and {supports_high_count}/{total_count} support "
            "high-threshold inspection."
        )
        reconciliation_ready = False

    policy_debt_ids = (
        [
            str(item).strip()
            for item in manual_review_outcome.get("policy_only_confirmed_ids", [])
            if str(item).strip()
        ]
        if isinstance(manual_review_outcome.get("policy_only_confirmed_ids"), list)
        else []
    )

    return {
        "schema_version": "processor_gate_mid_confidence_policy_debt_reconciliation.v1",
        "generated_at": _utc_now_iso(),
        "run_id": str(review_summary.get("run_id") or manual_review_outcome.get("run_id") or "").strip()
        or None,
        "source_worksheet_path": str(manual_review_outcome.get("worksheet_path") or "").strip()
        or None,
        "policy_decision_final_status": policy_final_status or None,
        "threshold_change_final_status": threshold_final_status or None,
        "final_status": final_status,
        "recommended_action": recommended_action,
        "reconciliation_ready": reconciliation_ready,
        "runtime_change_ready": False,
        "historical_mutation_ready": False,
        "reconciliation_scope": "historical_mid_confidence_approved_rows",
        "future_policy": "mid_confidence_rows_remain_pending_review",
        "historical_row_policy": "do_not_mass_rewrite_historical_approved_rows",
        "next_step": next_step,
        "summary": summary_text,
        "manual_review_counts": {
            "total": total_count,
            "completed": completed_count,
            "supports_mid_confidence_policy_review": supports_mid_count,
            "supports_high_threshold_change": supports_high_count,
            "default_divergence": int(manual_review_outcome.get("default_divergence_count") or 0),
        },
        "policy_debt_ids": policy_debt_ids,
        "operator_note": (
            "This is a reconciliation artifact only. It records how to interpret reviewed legacy "
            "APPROVED rows; it does not mutate historical rows, live thresholds, or runtime gate policy."
        ),
    }


def render_processor_gate_mid_confidence_policy_debt_reconciliation_markdown(
    payload: dict[str, Any],
) -> str:
    manual_review_counts = (
        payload.get("manual_review_counts")
        if isinstance(payload.get("manual_review_counts"), dict)
        else {}
    )

    lines = [
        f"# Processor Gate Mid-Confidence Policy Debt Reconciliation: {payload.get('run_id') or '-'}",
        "",
        f"- Generated At: {payload.get('generated_at') or '-'}",
        f"- Final Status: {payload.get('final_status') or '-'}",
        f"- Recommended Action: {payload.get('recommended_action') or '-'}",
        f"- Reconciliation Ready: {'yes' if bool(payload.get('reconciliation_ready')) else 'no'}",
        f"- Runtime Change Ready: {'yes' if bool(payload.get('runtime_change_ready')) else 'no'}",
        f"- Historical Mutation Ready: {'yes' if bool(payload.get('historical_mutation_ready')) else 'no'}",
        f"- Reconciliation Scope: {payload.get('reconciliation_scope') or '-'}",
        f"- Future Policy: {payload.get('future_policy') or '-'}",
        f"- Historical Row Policy: {payload.get('historical_row_policy') or '-'}",
        f"- Next Step: {payload.get('next_step') or '-'}",
        f"- Summary: {payload.get('summary') or '-'}",
        f"- Reviewed Rows: {manual_review_counts.get('completed') or 0}/{manual_review_counts.get('total') or 0}",
        f"- Supports Mid-Confidence Policy Review: {manual_review_counts.get('supports_mid_confidence_policy_review') or 0}",
        f"- Supports High-Threshold Change: {manual_review_counts.get('supports_high_threshold_change') or 0}",
        f"- Operator Note: {payload.get('operator_note') or '-'}",
        "",
    ]

    policy_debt_ids = (
        [str(item).strip() for item in payload.get("policy_debt_ids", []) if str(item).strip()]
        if isinstance(payload.get("policy_debt_ids"), list)
        else []
    )
    if policy_debt_ids:
        lines.append("## Policy Debt IDs")
        lines.extend(f"- {item}" for item in policy_debt_ids)
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def build_processor_gate_manual_override_policy_decision(
    *,
    review_summary: dict[str, Any],
) -> dict[str, Any]:
    manual_review_scope = (
        review_summary.get("manual_review_scope")
        if isinstance(review_summary.get("manual_review_scope"), dict)
        else {}
    )
    excluded = (
        manual_review_scope.get("excluded")
        if isinstance(manual_review_scope.get("excluded"), dict)
        else {}
    )
    manual_override = (
        excluded.get("manual_override")
        if isinstance(excluded.get("manual_override"), dict)
        else {}
    )
    indexed_pending = (
        excluded.get("indexed_pending")
        if isinstance(excluded.get("indexed_pending"), dict)
        else {}
    )

    manual_override_count = int(manual_override.get("count") or 0)
    indexed_pending_count = int(indexed_pending.get("count") or 0)
    manual_override_ids = (
        [
            str(item).strip()
            for item in manual_override.get("paper_ids", [])
            if str(item).strip()
        ]
        if isinstance(manual_override.get("paper_ids"), list)
        else []
    )

    if manual_override_count > 0:
        final_status = "manual_override_exception_policy_confirmed"
        recommended_action = "exclude_manual_override_rows_from_threshold_tuning"
        summary_text = (
            f"{manual_override_count} manual or human override row(s) remain explicit policy "
            "exceptions and should stay outside raw threshold tuning."
        )
        next_step = (
            "review_indexed_pending_status_contract"
            if indexed_pending_count > 0
            else "monitor_processor_gate_excluded_policy_buckets"
        )
        policy_decision_ready = True
    else:
        final_status = "no_manual_override_rows"
        recommended_action = "no_manual_override_policy_action"
        summary_text = "No manual or human override row(s) are present in the excluded bucket."
        next_step = (
            "review_indexed_pending_status_contract"
            if indexed_pending_count > 0
            else "monitor_processor_gate_excluded_policy_buckets"
        )
        policy_decision_ready = False

    return {
        "schema_version": "processor_gate_manual_override_policy_decision.v1",
        "generated_at": _utc_now_iso(),
        "run_id": str(review_summary.get("run_id") or "").strip() or None,
        "final_status": final_status,
        "recommended_action": recommended_action,
        "policy_decision_ready": policy_decision_ready,
        "threshold_change_ready": False,
        "runtime_change_ready": False,
        "historical_mutation_ready": False,
        "manual_override_count": manual_override_count,
        "indexed_pending_count": indexed_pending_count,
        "manual_override_ids": manual_override_ids,
        "manual_override_policy": "keep_as_explicit_policy_exception",
        "next_step": next_step,
        "summary": summary_text,
        "operator_note": (
            "This is a policy review artifact only. It excludes manual/human override rows "
            "from raw threshold tuning and does not mutate historical rows or runtime gate behavior."
        ),
    }


def render_processor_gate_manual_override_policy_decision_markdown(
    payload: dict[str, Any],
) -> str:
    lines = [
        f"# Processor Gate Manual Override Policy Decision: {payload.get('run_id') or '-'}",
        "",
        f"- Generated At: {payload.get('generated_at') or '-'}",
        f"- Final Status: {payload.get('final_status') or '-'}",
        f"- Recommended Action: {payload.get('recommended_action') or '-'}",
        f"- Policy Decision Ready: {'yes' if bool(payload.get('policy_decision_ready')) else 'no'}",
        f"- Threshold Change Ready: {'yes' if bool(payload.get('threshold_change_ready')) else 'no'}",
        f"- Runtime Change Ready: {'yes' if bool(payload.get('runtime_change_ready')) else 'no'}",
        f"- Historical Mutation Ready: {'yes' if bool(payload.get('historical_mutation_ready')) else 'no'}",
        f"- Manual Override Count: {payload.get('manual_override_count') or 0}",
        f"- Indexed Pending Count: {payload.get('indexed_pending_count') or 0}",
        f"- Manual Override Policy: {payload.get('manual_override_policy') or '-'}",
        f"- Next Step: {payload.get('next_step') or '-'}",
        f"- Summary: {payload.get('summary') or '-'}",
        f"- Operator Note: {payload.get('operator_note') or '-'}",
        "",
    ]

    manual_override_ids = (
        [str(item).strip() for item in payload.get("manual_override_ids", []) if str(item).strip()]
        if isinstance(payload.get("manual_override_ids"), list)
        else []
    )
    if manual_override_ids:
        lines.append("## Manual Override IDs")
        lines.extend(f"- {item}" for item in manual_override_ids)
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def build_processor_gate_indexed_pending_policy_decision(
    *,
    review_summary: dict[str, Any],
) -> dict[str, Any]:
    manual_review_scope = (
        review_summary.get("manual_review_scope")
        if isinstance(review_summary.get("manual_review_scope"), dict)
        else {}
    )
    excluded = (
        manual_review_scope.get("excluded")
        if isinstance(manual_review_scope.get("excluded"), dict)
        else {}
    )
    indexed_pending = (
        excluded.get("indexed_pending")
        if isinstance(excluded.get("indexed_pending"), dict)
        else {}
    )
    manual_override = (
        excluded.get("manual_override")
        if isinstance(excluded.get("manual_override"), dict)
        else {}
    )

    indexed_pending_count = int(indexed_pending.get("count") or 0)
    manual_override_count = int(manual_override.get("count") or 0)
    indexed_pending_ids = (
        [
            str(item).strip()
            for item in indexed_pending.get("paper_ids", [])
            if str(item).strip()
        ]
        if isinstance(indexed_pending.get("paper_ids"), list)
        else []
    )

    if indexed_pending_count > 0:
        final_status = "indexed_pending_status_contract_confirmed"
        recommended_action = "keep_indexed_pending_rows_out_of_threshold_tuning"
        summary_text = (
            f"{indexed_pending_count} indexed-pending row(s) remain status-contract "
            "cases and should stay outside raw threshold tuning."
        )
        policy_decision_ready = True
    else:
        final_status = "no_indexed_pending_rows"
        recommended_action = "no_indexed_pending_policy_action"
        summary_text = "No indexed-pending row(s) are present in the excluded bucket."
        policy_decision_ready = False

    return {
        "schema_version": "processor_gate_indexed_pending_policy_decision.v1",
        "generated_at": _utc_now_iso(),
        "run_id": str(review_summary.get("run_id") or "").strip() or None,
        "final_status": final_status,
        "recommended_action": recommended_action,
        "policy_decision_ready": policy_decision_ready,
        "threshold_change_ready": False,
        "runtime_change_ready": False,
        "historical_mutation_ready": False,
        "indexed_pending_count": indexed_pending_count,
        "manual_override_count": manual_override_count,
        "indexed_pending_ids": indexed_pending_ids,
        "indexed_pending_policy": "keep_pending_indexed_rows_out_of_threshold_tuning",
        "next_step": "monitor_processor_gate_excluded_policy_buckets",
        "summary": summary_text,
        "operator_note": (
            "This is a policy review artifact only. It excludes indexed-pending status-contract "
            "rows from raw threshold tuning and does not mutate historical rows or runtime gate behavior."
        ),
    }


def render_processor_gate_indexed_pending_policy_decision_markdown(
    payload: dict[str, Any],
) -> str:
    lines = [
        f"# Processor Gate Indexed Pending Policy Decision: {payload.get('run_id') or '-'}",
        "",
        f"- Generated At: {payload.get('generated_at') or '-'}",
        f"- Final Status: {payload.get('final_status') or '-'}",
        f"- Recommended Action: {payload.get('recommended_action') or '-'}",
        f"- Policy Decision Ready: {'yes' if bool(payload.get('policy_decision_ready')) else 'no'}",
        f"- Threshold Change Ready: {'yes' if bool(payload.get('threshold_change_ready')) else 'no'}",
        f"- Runtime Change Ready: {'yes' if bool(payload.get('runtime_change_ready')) else 'no'}",
        f"- Historical Mutation Ready: {'yes' if bool(payload.get('historical_mutation_ready')) else 'no'}",
        f"- Indexed Pending Count: {payload.get('indexed_pending_count') or 0}",
        f"- Manual Override Count: {payload.get('manual_override_count') or 0}",
        f"- Indexed Pending Policy: {payload.get('indexed_pending_policy') or '-'}",
        f"- Next Step: {payload.get('next_step') or '-'}",
        f"- Summary: {payload.get('summary') or '-'}",
        f"- Operator Note: {payload.get('operator_note') or '-'}",
        "",
    ]

    indexed_pending_ids = (
        [str(item).strip() for item in payload.get("indexed_pending_ids", []) if str(item).strip()]
        if isinstance(payload.get("indexed_pending_ids"), list)
        else []
    )
    if indexed_pending_ids:
        lines.append("## Indexed Pending IDs")
        lines.extend(f"- {item}" for item in indexed_pending_ids)
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def build_processor_gate_fixture_or_test_policy_decision(
    *,
    review_summary: dict[str, Any],
) -> dict[str, Any]:
    manual_review_scope = (
        review_summary.get("manual_review_scope")
        if isinstance(review_summary.get("manual_review_scope"), dict)
        else {}
    )
    excluded = (
        manual_review_scope.get("excluded")
        if isinstance(manual_review_scope.get("excluded"), dict)
        else {}
    )
    fixture_or_test = (
        excluded.get("fixture_or_test")
        if isinstance(excluded.get("fixture_or_test"), dict)
        else {}
    )
    manual_override = (
        excluded.get("manual_override")
        if isinstance(excluded.get("manual_override"), dict)
        else {}
    )
    indexed_pending = (
        excluded.get("indexed_pending")
        if isinstance(excluded.get("indexed_pending"), dict)
        else {}
    )

    fixture_or_test_count = int(fixture_or_test.get("count") or 0)
    manual_override_count = int(manual_override.get("count") or 0)
    indexed_pending_count = int(indexed_pending.get("count") or 0)
    fixture_or_test_ids = (
        [
            str(item).strip()
            for item in fixture_or_test.get("paper_ids", [])
            if str(item).strip()
        ]
        if isinstance(fixture_or_test.get("paper_ids"), list)
        else []
    )

    if fixture_or_test_count > 0:
        final_status = "fixture_or_test_hygiene_exclusion_confirmed"
        recommended_action = "keep_fixture_or_test_rows_out_of_threshold_tuning"
        summary_text = (
            f"{fixture_or_test_count} fixture/test row(s) remain hygiene-scope "
            "cases and should stay outside raw threshold tuning."
        )
        policy_decision_ready = True
    else:
        final_status = "no_fixture_or_test_rows"
        recommended_action = "no_fixture_or_test_policy_action"
        summary_text = "No fixture/test row(s) are present in the excluded bucket."
        policy_decision_ready = False

    return {
        "schema_version": "processor_gate_fixture_or_test_policy_decision.v1",
        "generated_at": _utc_now_iso(),
        "run_id": str(review_summary.get("run_id") or "").strip() or None,
        "final_status": final_status,
        "recommended_action": recommended_action,
        "policy_decision_ready": policy_decision_ready,
        "threshold_change_ready": False,
        "runtime_change_ready": False,
        "historical_mutation_ready": False,
        "archive_action_ready": False,
        "fixture_or_test_count": fixture_or_test_count,
        "manual_override_count": manual_override_count,
        "indexed_pending_count": indexed_pending_count,
        "fixture_or_test_ids": fixture_or_test_ids,
        "fixture_or_test_policy": "keep_fixture_and_test_rows_out_of_threshold_tuning",
        "next_step": "monitor_processor_gate_excluded_policy_buckets",
        "summary": summary_text,
        "operator_note": (
            "This is a policy review artifact only. It excludes fixture/test hygiene rows "
            "from raw threshold tuning and does not archive rows, mutate historical rows, or "
            "change runtime gate behavior."
        ),
    }


def render_processor_gate_fixture_or_test_policy_decision_markdown(
    payload: dict[str, Any],
) -> str:
    lines = [
        f"# Processor Gate Fixture/Test Policy Decision: {payload.get('run_id') or '-'}",
        "",
        f"- Generated At: {payload.get('generated_at') or '-'}",
        f"- Final Status: {payload.get('final_status') or '-'}",
        f"- Recommended Action: {payload.get('recommended_action') or '-'}",
        f"- Policy Decision Ready: {'yes' if bool(payload.get('policy_decision_ready')) else 'no'}",
        f"- Threshold Change Ready: {'yes' if bool(payload.get('threshold_change_ready')) else 'no'}",
        f"- Runtime Change Ready: {'yes' if bool(payload.get('runtime_change_ready')) else 'no'}",
        f"- Historical Mutation Ready: {'yes' if bool(payload.get('historical_mutation_ready')) else 'no'}",
        f"- Archive Action Ready: {'yes' if bool(payload.get('archive_action_ready')) else 'no'}",
        f"- Fixture/Test Count: {payload.get('fixture_or_test_count') or 0}",
        f"- Manual Override Count: {payload.get('manual_override_count') or 0}",
        f"- Indexed Pending Count: {payload.get('indexed_pending_count') or 0}",
        f"- Fixture/Test Policy: {payload.get('fixture_or_test_policy') or '-'}",
        f"- Next Step: {payload.get('next_step') or '-'}",
        f"- Summary: {payload.get('summary') or '-'}",
        f"- Operator Note: {payload.get('operator_note') or '-'}",
        "",
    ]

    fixture_or_test_ids = (
        [str(item).strip() for item in payload.get("fixture_or_test_ids", []) if str(item).strip()]
        if isinstance(payload.get("fixture_or_test_ids"), list)
        else []
    )
    if fixture_or_test_ids:
        lines.append("## Fixture/Test IDs")
        lines.extend(f"- {item}" for item in fixture_or_test_ids)
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def build_processor_gate_threshold_change_preflight(
    *,
    review_summary: dict[str, Any],
    run_root: Path,
    supports_high_threshold_change_count: int,
) -> dict[str, Any]:
    proposal_path = run_root / "threshold_change_proposal.json"
    required = supports_high_threshold_change_count > 0
    if not required:
        return {
            "required": False,
            "ready": False,
            "status": "not_applicable",
            "blocker": None,
            "validation_replay_status": "not_applicable",
            "validation_replay_matches_proposal": False,
        }

    if not proposal_path.exists():
        return {
            "required": True,
            "ready": False,
            "status": "missing_threshold_change_proposal",
            "blocker": "missing_threshold_change_proposal",
            "validation_replay_status": "not_applicable",
            "validation_replay_matches_proposal": False,
        }

    drift_artifacts = resolve_processor_gate_threshold_review_drift_artifacts(
        review_summary,
        threshold_change_proposal_path=proposal_path,
    )
    status = str(
        drift_artifacts.get("threshold_change_manual_decision_status") or ""
    ).strip() or "not_applicable"
    blocker = str(
        drift_artifacts.get("threshold_change_manual_decision_blocker") or ""
    ).strip() or None
    validation_status = str(
        drift_artifacts.get("threshold_change_validation_replay_status") or ""
    ).strip() or "not_applicable"
    ready = bool(drift_artifacts.get("threshold_change_manual_decision_ready"))
    if not ready and status == "not_applicable":
        status = "blocked_validation_replay"
        blocker = blocker or validation_status

    return {
        "required": True,
        "ready": ready,
        "status": status,
        "blocker": blocker,
        "validation_replay_status": validation_status,
        "validation_replay_matches_proposal": bool(
            drift_artifacts.get("threshold_change_validation_replay_matches_proposal")
        ),
    }


def run_processor_gate_manual_review_outcome(
    *,
    review_run: Path,
    worksheet: Path | None = None,
) -> dict[str, Any]:
    summary_path = _resolve_review_summary_path(review_run)
    if not summary_path.exists():
        raise FileNotFoundError(f"processor gate threshold review summary not found: {summary_path}")

    run_root = summary_path.parent
    worksheet_path = (
        worksheet.expanduser().resolve(strict=False)
        if worksheet is not None
        else _resolve_default_worksheet(run_root)
    )
    if not worksheet_path.exists():
        raise FileNotFoundError(f"manual review worksheet not found: {worksheet_path}")

    review_summary = load_processor_gate_threshold_review_summary(run_root)
    worksheet_rows = _load_review_rows(worksheet_path)
    outcome = build_processor_gate_manual_review_outcome(
        review_summary=review_summary,
        worksheet_path=worksheet_path,
        worksheet_rows=worksheet_rows,
    )

    outcome_path = run_root / "manual_review_outcome.json"
    outcome_markdown_path = run_root / "manual_review_outcome.md"
    threshold_change_decision_path = run_root / "threshold_change_decision.json"
    threshold_change_decision_markdown_path = run_root / "threshold_change_decision.md"
    mid_confidence_policy_decision_path = run_root / "mid_confidence_policy_decision.json"
    mid_confidence_policy_decision_markdown_path = run_root / "mid_confidence_policy_decision.md"
    mid_confidence_policy_debt_reconciliation_path = (
        run_root / "mid_confidence_policy_debt_reconciliation.json"
    )
    mid_confidence_policy_debt_reconciliation_markdown_path = (
        run_root / "mid_confidence_policy_debt_reconciliation.md"
    )
    manual_override_policy_decision_path = run_root / "manual_override_policy_decision.json"
    manual_override_policy_decision_markdown_path = (
        run_root / "manual_override_policy_decision.md"
    )
    indexed_pending_policy_decision_path = run_root / "indexed_pending_policy_decision.json"
    indexed_pending_policy_decision_markdown_path = (
        run_root / "indexed_pending_policy_decision.md"
    )
    fixture_or_test_policy_decision_path = run_root / "fixture_or_test_policy_decision.json"
    fixture_or_test_policy_decision_markdown_path = (
        run_root / "fixture_or_test_policy_decision.md"
    )
    _write_json(outcome_path, outcome)
    outcome_markdown_path.write_text(
        render_processor_gate_manual_review_outcome_markdown(outcome),
        encoding="utf-8",
    )
    threshold_change_decision = build_processor_gate_threshold_change_decision(
        review_summary=review_summary,
        manual_review_outcome=outcome,
        threshold_change_preflight=build_processor_gate_threshold_change_preflight(
            review_summary=review_summary,
            run_root=run_root,
            supports_high_threshold_change_count=int(
                outcome.get("supports_high_threshold_change_count") or 0
            ),
        ),
    )
    _write_json(threshold_change_decision_path, threshold_change_decision)
    threshold_change_decision_markdown_path.write_text(
        render_processor_gate_threshold_change_decision_markdown(
            threshold_change_decision
        ),
        encoding="utf-8",
    )
    mid_confidence_policy_decision = build_processor_gate_mid_confidence_policy_decision(
        review_summary=review_summary,
        manual_review_outcome=outcome,
        threshold_change_decision=threshold_change_decision,
    )
    _write_json(mid_confidence_policy_decision_path, mid_confidence_policy_decision)
    mid_confidence_policy_decision_markdown_path.write_text(
        render_processor_gate_mid_confidence_policy_decision_markdown(
            mid_confidence_policy_decision
        ),
        encoding="utf-8",
    )
    mid_confidence_policy_debt_reconciliation = (
        build_processor_gate_mid_confidence_policy_debt_reconciliation(
            review_summary=review_summary,
            manual_review_outcome=outcome,
            threshold_change_decision=threshold_change_decision,
            mid_confidence_policy_decision=mid_confidence_policy_decision,
        )
    )
    _write_json(
        mid_confidence_policy_debt_reconciliation_path,
        mid_confidence_policy_debt_reconciliation,
    )
    mid_confidence_policy_debt_reconciliation_markdown_path.write_text(
        render_processor_gate_mid_confidence_policy_debt_reconciliation_markdown(
            mid_confidence_policy_debt_reconciliation
        ),
        encoding="utf-8",
    )
    manual_override_policy_decision = build_processor_gate_manual_override_policy_decision(
        review_summary=review_summary,
    )
    _write_json(manual_override_policy_decision_path, manual_override_policy_decision)
    manual_override_policy_decision_markdown_path.write_text(
        render_processor_gate_manual_override_policy_decision_markdown(
            manual_override_policy_decision
        ),
        encoding="utf-8",
    )
    indexed_pending_policy_decision = build_processor_gate_indexed_pending_policy_decision(
        review_summary=review_summary,
    )
    _write_json(indexed_pending_policy_decision_path, indexed_pending_policy_decision)
    indexed_pending_policy_decision_markdown_path.write_text(
        render_processor_gate_indexed_pending_policy_decision_markdown(
            indexed_pending_policy_decision
        ),
        encoding="utf-8",
    )
    fixture_or_test_policy_decision = build_processor_gate_fixture_or_test_policy_decision(
        review_summary=review_summary,
    )
    _write_json(fixture_or_test_policy_decision_path, fixture_or_test_policy_decision)
    fixture_or_test_policy_decision_markdown_path.write_text(
        render_processor_gate_fixture_or_test_policy_decision_markdown(
            fixture_or_test_policy_decision
        ),
        encoding="utf-8",
    )
    (run_root / "audit.md").write_text(
        render_processor_gate_threshold_review_markdown(review_summary, run_root=run_root),
        encoding="utf-8",
    )

    return {
        "run_root": str(run_root),
        "summary_path": str(summary_path),
        "worksheet_path": str(worksheet_path),
        "outcome_path": str(outcome_path),
        "outcome_markdown_path": str(outcome_markdown_path),
        "threshold_change_decision_path": str(threshold_change_decision_path),
        "threshold_change_decision_markdown_path": str(threshold_change_decision_markdown_path),
        "mid_confidence_policy_decision_path": str(mid_confidence_policy_decision_path),
        "mid_confidence_policy_decision_markdown_path": str(mid_confidence_policy_decision_markdown_path),
        "mid_confidence_policy_debt_reconciliation_path": str(mid_confidence_policy_debt_reconciliation_path),
        "mid_confidence_policy_debt_reconciliation_markdown_path": str(mid_confidence_policy_debt_reconciliation_markdown_path),
        "manual_override_policy_decision_path": str(manual_override_policy_decision_path),
        "manual_override_policy_decision_markdown_path": str(manual_override_policy_decision_markdown_path),
        "indexed_pending_policy_decision_path": str(indexed_pending_policy_decision_path),
        "indexed_pending_policy_decision_markdown_path": str(indexed_pending_policy_decision_markdown_path),
        "fixture_or_test_policy_decision_path": str(fixture_or_test_policy_decision_path),
        "fixture_or_test_policy_decision_markdown_path": str(fixture_or_test_policy_decision_markdown_path),
        "viewer_command": build_processor_gate_threshold_review_viewer_command(run_root),
        "status": outcome.get("status"),
        "review_ready": outcome.get("review_ready"),
        "summary": outcome.get("summary"),
        "next_step": outcome.get("next_step"),
    }


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Summarize a processor gate manual-review worksheet into additive outcome sidecars. "
            "This does not rewrite thresholds; it only records the current worksheet conclusion."
        ),
        epilog=(
            "Writes manual-review outcome, threshold-decision, mid-confidence policy, "
            "policy-debt reconciliation, manual-override policy, indexed-pending policy, "
            "and fixture/test policy "
            "sidecars next to the review run, "
            "then refreshes `audit.md` so the new outcome sidecars are discoverable from the existing viewer.\n\n"
            "Reopen the review run with:\n"
            f"  {_repo_local_viewer_hint()}"
        ),
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "--review-run",
        required=True,
        type=Path,
        help="Path to a processor gate threshold review run directory or summary.json file.",
    )
    parser.add_argument(
        "--worksheet",
        type=Path,
        default=None,
        help=(
            "Optional worksheet path. Defaults to the first existing file among "
            "`manual_review_checklist.csv`, `manual_review_frontier.csv`, or `manual_review_seed.csv`."
        ),
    )
    return parser


def _repo_local_viewer_hint() -> str:
    if os.name == "nt":
        return r".venv\Scripts\paperpipe.exe show-processor-gate-threshold-review <run_dir>"
    return ".venv/bin/paperpipe show-processor-gate-threshold-review <run_dir>"


def main() -> int:
    parser = _build_arg_parser()
    args = parser.parse_args()
    payload = run_processor_gate_manual_review_outcome(
        review_run=args.review_run,
        worksheet=args.worksheet,
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
