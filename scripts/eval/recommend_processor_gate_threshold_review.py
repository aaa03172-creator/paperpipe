#!/usr/bin/env python3
from __future__ import annotations

import argparse
from collections import Counter
import csv
import json
from datetime import datetime, timezone
from io import StringIO
import os
from pathlib import Path
import shlex
from typing import Any
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.services.processor_gate_replay_drift import (
    build_processor_gate_threshold_review_viewer_command,
    render_processor_gate_threshold_review_markdown,
)


DEFAULT_DRIFT_ROOT = ROOT / "snapshots" / "processor_gate_replay_drift"
DEFAULT_OUT_DIR = ROOT / "snapshots" / "processor_gate_threshold_review"
DEFAULT_MIN_CANDIDATE_ROWS = 20
DEFAULT_DRIFT_WARN_THRESHOLD = 0.25
THRESHOLD_CHANGE_PLACEHOLDER = "REVIEWED_HIGH_THRESHOLD"

_TUNING_ACTIONS_BY_TARGET: dict[str, dict[str, str]] = {
    "mid_confidence_escalation": {
        "action": "review_mid_confidence_escalation_policy",
        "summary": "Review whether historical mid-confidence approvals should now escalate to pending review before changing the high threshold.",
    },
    "high_threshold": {
        "action": "review_high_threshold_boundary",
        "summary": "Inspect the high-threshold boundary only after policy-only drift rows are separated from threshold-relevant rows.",
    },
    "high_confidence_pending_policy": {
        "action": "audit_high_confidence_pending_contract",
        "summary": "Audit whether high-confidence pending rows reflect policy debt rather than a raw threshold miss.",
    },
    "manual_override_boundary": {
        "action": "exclude_manual_override_rows_from_threshold_tuning",
        "summary": "Keep manual or human override rows out of threshold changes and review them as explicit policy exceptions.",
    },
    "indexed_pending_policy": {
        "action": "exclude_indexed_pending_rows_from_threshold_tuning",
        "summary": "Keep indexed-pending rows out of raw threshold changes and review their status policy separately.",
    },
}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _repo_local_viewer_hint() -> str:
    if os.name == "nt":
        return r".venv\Scripts\paperpipe.exe show-processor-gate-threshold-review <run_dir>"
    return ".venv/bin/paperpipe show-processor-gate-threshold-review <run_dir>"


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _compact_processor_gate_threshold_review_text(summary: dict[str, Any]) -> str:
    decision = summary.get("decision") if isinstance(summary.get("decision"), dict) else {}
    signal_summary = summary.get("signal_summary") if isinstance(summary.get("signal_summary"), dict) else {}

    parts = [f"review_ready={bool(decision.get('review_ready'))}"]

    recommended_action = str(decision.get("recommended_action") or "").strip()
    if recommended_action:
        parts.append(f"action={recommended_action}")

    latest_run_status = str(decision.get("latest_run_status") or "").strip()
    if latest_run_status:
        parts.append(f"latest_run_status={latest_run_status}")

    threshold_change_status = str(decision.get("threshold_change_status") or "").strip()
    if threshold_change_status:
        parts.append(f"threshold_change={threshold_change_status}")

    candidate_count = signal_summary.get("candidate_count")
    if candidate_count is not None:
        parts.append(f"candidate_count={int(candidate_count)}")

    drift_rate = signal_summary.get("drift_rate")
    if drift_rate is not None:
        parts.append(f"drift_rate={float(drift_rate):.4f}")

    latest_run_id = str(decision.get("latest_run_id") or "").strip()
    if latest_run_id:
        parts.append(f"latest_run={latest_run_id}")

    return " ".join(parts)


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("processor gate drift summary must be a JSON object")
    return payload


def _latest_drift_summary_path(root: Path) -> Path | None:
    if not root.exists() or not root.is_dir():
        return None
    candidates = [path for path in root.glob("*/summary.json") if path.is_file()]
    if not candidates:
        return None
    return max(candidates, key=lambda path: (path.stat().st_mtime, path.parent.name))


def _drift_details_path(drift_summary_path: Path | None) -> Path | None:
    if drift_summary_path is None:
        return None
    candidate = drift_summary_path.with_name("details.json")
    return candidate if candidate.exists() else None


def _compact_row_identifiers(rows: list[dict[str, Any]]) -> list[str]:
    ordered: list[str] = []
    for row in rows:
        paper_id = str(row.get("paper_id") or "").strip()
        if not paper_id or paper_id in ordered:
            continue
        ordered.append(paper_id)
    return ordered


def _partition_manual_review_rows(drift_details: dict[str, Any] | None) -> dict[str, Any]:
    documents = drift_details.get("documents") if isinstance(drift_details, dict) else None
    if not isinstance(documents, list):
        return {
            "threshold_relevant": [],
            "policy_edge_cases": [],
            "excluded": {
                "manual_override": [],
                "indexed_pending": [],
                "fixture_or_test": [],
                "other": [],
            },
        }

    drift_docs = [doc for doc in documents if isinstance(doc, dict) and doc.get("eligible_for_apply") is False]
    threshold_relevant_rows: list[dict[str, Any]] = []
    policy_edge_case_rows: list[dict[str, Any]] = []
    excluded_manual_override_rows: list[dict[str, Any]] = []
    excluded_indexed_pending_rows: list[dict[str, Any]] = []
    excluded_fixture_or_test_rows: list[dict[str, Any]] = []
    excluded_other_rows: list[dict[str, Any]] = []

    for doc in sorted(drift_docs, key=lambda item: str(item.get("paper_id") or "")):
        probable_cause = str(doc.get("probable_drift_cause") or "").strip()
        local_provenance_hint = str(doc.get("local_provenance_hint") or "").strip()
        fixture_classification_reason = str(doc.get("fixture_classification_reason") or "").strip()
        is_fixture_or_test = bool(
            local_provenance_hint == "test_fixture_row" or fixture_classification_reason
        )

        if is_fixture_or_test:
            excluded_fixture_or_test_rows.append(doc)
            continue
        if probable_cause == "manual_or_human_override_mid_confidence":
            excluded_manual_override_rows.append(doc)
            continue
        if probable_cause == "legacy_indexed_pending_review":
            excluded_indexed_pending_rows.append(doc)
            continue
        if probable_cause == "legacy_mid_confidence_approval":
            threshold_relevant_rows.append(doc)
            continue
        if probable_cause == "legacy_high_confidence_pending":
            policy_edge_case_rows.append(doc)
            continue
        excluded_other_rows.append(doc)

    return {
        "threshold_relevant": threshold_relevant_rows,
        "policy_edge_cases": policy_edge_case_rows,
        "excluded": {
            "manual_override": excluded_manual_override_rows,
            "indexed_pending": excluded_indexed_pending_rows,
            "fixture_or_test": excluded_fixture_or_test_rows,
            "other": excluded_other_rows,
        },
    }


def _manual_review_scope(drift_details: dict[str, Any] | None) -> dict[str, Any]:
    partition = _partition_manual_review_rows(drift_details)
    threshold_relevant_rows = partition["threshold_relevant"]
    policy_edge_case_rows = partition["policy_edge_cases"]
    excluded = partition["excluded"]
    excluded_manual_override_rows = excluded["manual_override"]
    excluded_indexed_pending_rows = excluded["indexed_pending"]
    excluded_fixture_or_test_rows = excluded["fixture_or_test"]
    excluded_other_rows = excluded["other"]

    def _bucket(rows: list[dict[str, Any]]) -> dict[str, Any]:
        transition_counts = Counter(
            f"{str(row.get('current_gate_decision') or '-').strip()}->{str(row.get('replay_gate_decision') or '-').strip()}"
            for row in rows
        )
        probable_counts = Counter(str(row.get("probable_drift_cause") or "unknown").strip() or "unknown" for row in rows)
        confidence_counts = Counter(str(row.get("confidence_band") or "unknown").strip() or "unknown" for row in rows)
        return {
            "count": len(rows),
            "paper_ids": _compact_row_identifiers(rows),
            "decision_transition_counts": dict(sorted(transition_counts.items())),
            "probable_drift_cause_counts": dict(sorted(probable_counts.items())),
            "confidence_band_counts": dict(sorted(confidence_counts.items())),
        }

    threshold_relevant_count = len(threshold_relevant_rows)
    policy_edge_case_count = len(policy_edge_case_rows)
    excluded_count = (
        len(excluded_manual_override_rows)
        + len(excluded_indexed_pending_rows)
        + len(excluded_fixture_or_test_rows)
        + len(excluded_other_rows)
    )
    focus_recommendation = (
        "Use threshold_relevant rows as the primary tuning basis and keep excluded rows out of threshold changes "
        "unless their policy contracts are reviewed separately."
    )
    if threshold_relevant_count > 0:
        focus_recommendation = (
            f"Focus threshold tuning on {threshold_relevant_count} threshold-relevant row(s) first; "
            f"exclude {excluded_count} manual-override, indexed-pending, or fixture/test row(s) from raw threshold changes."
        )

    return {
        "threshold_relevant": _bucket(threshold_relevant_rows),
        "policy_edge_cases": _bucket(policy_edge_case_rows),
        "excluded": {
            "manual_override": _bucket(excluded_manual_override_rows),
            "indexed_pending": _bucket(excluded_indexed_pending_rows),
            "fixture_or_test": _bucket(excluded_fixture_or_test_rows),
            "other": _bucket(excluded_other_rows),
        },
        "focus_recommendation": focus_recommendation,
    }


def _manual_review_row_entry(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "paper_id": str(row.get("paper_id") or "").strip() or None,
        "title": str(row.get("title") or "").strip() or None,
        "current_status": str(row.get("current_status") or "").strip() or None,
        "replay_status": str(row.get("replay_status") or "").strip() or None,
        "confidence": row.get("confidence"),
        "confidence_band": str(row.get("confidence_band") or "").strip() or None,
        "current_gate_decision": str(row.get("current_gate_decision") or "").strip() or None,
        "replay_gate_decision": str(row.get("replay_gate_decision") or "").strip() or None,
        "precanonical_gate_reason": str(row.get("precanonical_gate_reason") or "").strip() or None,
        "current_gate_reason": str(row.get("current_gate_reason") or "").strip() or None,
        "probable_drift_cause": str(row.get("probable_drift_cause") or "").strip() or None,
        "current_gate_reason_category": str(row.get("current_gate_reason_category") or "").strip() or None,
        "evidence_source": str(row.get("evidence_source") or "").strip() or None,
        "has_evidence_text": bool(row.get("has_evidence_text")),
        "feedback_log_import_hint": str(row.get("feedback_log_import_hint") or "").strip() or None,
        "historical_path_hint": str(row.get("historical_path_hint") or "").strip() or None,
        "historical_rewrite_hint": str(row.get("historical_rewrite_hint") or "").strip() or None,
        "local_provenance_hint": str(row.get("local_provenance_hint") or "").strip() or None,
        "fixture_classification_reason": str(row.get("fixture_classification_reason") or "").strip() or None,
    }


def build_processor_gate_threshold_manual_review_rows(
    *,
    drift_details: dict[str, Any] | None,
    drift_details_path: Path | None,
    summary: dict[str, Any],
) -> dict[str, Any]:
    partition = _partition_manual_review_rows(drift_details)

    def _bucket(rows: list[dict[str, Any]]) -> dict[str, Any]:
        return {
            "count": len(rows),
            "rows": [_manual_review_row_entry(row) for row in rows],
        }

    return {
        "schema_version": "processor_gate_threshold_manual_review_rows.v1",
        "generated_at": str(summary.get("generated_at") or _utc_now_iso()),
        "run_id": str(summary.get("run_id") or "").strip() or None,
        "source_details_path": str(drift_details_path) if drift_details_path is not None else None,
        "threshold_relevant": _bucket(partition["threshold_relevant"]),
        "policy_edge_cases": _bucket(partition["policy_edge_cases"]),
        "excluded": {
            "manual_override": _bucket(partition["excluded"]["manual_override"]),
            "indexed_pending": _bucket(partition["excluded"]["indexed_pending"]),
            "fixture_or_test": _bucket(partition["excluded"]["fixture_or_test"]),
            "other": _bucket(partition["excluded"]["other"]),
        },
    }


def render_processor_gate_threshold_manual_review_markdown(payload: dict[str, Any]) -> str:
    lines = [
        f"# Processor Gate Threshold Manual Review: {payload.get('run_id') or '-'}",
        "",
        f"- Generated At: {payload.get('generated_at') or '-'}",
        f"- Source Details: {payload.get('source_details_path') or '-'}",
        "",
    ]

    def _render_bucket(title: str, bucket: object) -> None:
        if not isinstance(bucket, dict):
            return
        rows = bucket.get("rows")
        count = int(bucket.get("count") or 0)
        lines.append(f"## {title} ({count})")
        if not isinstance(rows, list) or not rows:
            lines.append("- none")
            lines.append("")
            return
        for row in rows:
            if not isinstance(row, dict):
                continue
            paper_id = str(row.get("paper_id") or "-")
            title_text = str(row.get("title") or "-")
            transition = (
                f"{str(row.get('current_gate_decision') or '-')}->"
                f"{str(row.get('replay_gate_decision') or '-')}"
            )
            confidence_text = str(row.get("confidence") if row.get("confidence") is not None else "-")
            confidence_band = str(row.get("confidence_band") or "-")
            cause = str(row.get("probable_drift_cause") or "-")
            evidence_source = str(row.get("evidence_source") or "-")
            lines.append(
                f"- {paper_id} | {title_text} | transition={transition} | "
                f"confidence={confidence_text} ({confidence_band}) | cause={cause} | evidence={evidence_source}"
            )
        lines.append("")

    _render_bucket("Threshold Relevant", payload.get("threshold_relevant"))
    _render_bucket("Policy Edge Cases", payload.get("policy_edge_cases"))
    excluded = payload.get("excluded") if isinstance(payload.get("excluded"), dict) else {}
    _render_bucket("Excluded: Manual Override", excluded.get("manual_override"))
    _render_bucket("Excluded: Indexed Pending", excluded.get("indexed_pending"))
    _render_bucket("Excluded: Fixture Or Test", excluded.get("fixture_or_test"))
    _render_bucket("Excluded: Other", excluded.get("other"))
    return "\n".join(lines).rstrip() + "\n"


def _default_manual_review_recommendation(row: dict[str, Any]) -> dict[str, str]:
    confidence_band = str(row.get("confidence_band") or "").strip()
    probable_drift_cause = str(row.get("probable_drift_cause") or "").strip()
    current_gate_decision = str(row.get("current_gate_decision") or "").strip()
    replay_gate_decision = str(row.get("replay_gate_decision") or "").strip()

    if (
        confidence_band == "mid"
        and probable_drift_cause == "legacy_mid_confidence_approval"
        and current_gate_decision == "APPROVED"
        and replay_gate_decision == "PENDING_REVIEW"
    ):
        return {
            "default_reviewer_disposition": "policy_only_review",
            "default_supports_mid_confidence_policy_review": "yes",
            "default_supports_high_threshold_change": "no",
            "default_reviewer_note": (
                "Legacy mid-confidence approval replayed to pending review; treat as policy-only unless manual review finds a true threshold miss."
            ),
        }

    if confidence_band == "high" or probable_drift_cause == "legacy_high_confidence_pending":
        return {
            "default_reviewer_disposition": "boundary_review",
            "default_supports_mid_confidence_policy_review": "no",
            "default_supports_high_threshold_change": "yes",
            "default_reviewer_note": (
                "High-confidence or high-threshold-like replay drift may justify direct boundary review before changing policy."
            ),
        }

    return {
        "default_reviewer_disposition": "manual_triage",
        "default_supports_mid_confidence_policy_review": "no",
        "default_supports_high_threshold_change": "no",
        "default_reviewer_note": (
            "Mixed replay-drift signals; inspect manually before treating this row as policy-only or threshold-boundary evidence."
        ),
    }


def _manual_review_checklist_fieldnames() -> list[str]:
    return [
        "review_bucket",
        "paper_id",
        "title",
        "current_gate_decision",
        "replay_gate_decision",
        "confidence",
        "confidence_band",
        "probable_drift_cause",
        "evidence_source",
        "historical_rewrite_hint",
        "review_target",
        "default_reviewer_disposition",
        "default_supports_mid_confidence_policy_review",
        "default_supports_high_threshold_change",
        "default_review_priority",
        "default_review_priority_reason",
        "default_reviewer_note",
        "reviewer_disposition",
        "supports_mid_confidence_policy_review",
        "supports_high_threshold_change",
        "reviewer_notes",
    ]


def _sorted_threshold_relevant_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    threshold_relevant = (
        payload.get("threshold_relevant") if isinstance(payload.get("threshold_relevant"), dict) else {}
    )
    rows = threshold_relevant.get("rows") if isinstance(threshold_relevant.get("rows"), list) else []
    return sorted(
        (row for row in rows if isinstance(row, dict)),
        key=lambda row: (
            int(_default_manual_review_priority(row)["sort_order"]),
            str(row.get("title") or ""),
            str(row.get("paper_id") or ""),
        ),
    )


def _default_manual_review_priority(row: dict[str, Any]) -> dict[str, object]:
    default_recommendation = _default_manual_review_recommendation(row)
    disposition = str(default_recommendation.get("default_reviewer_disposition") or "").strip()
    historical_rewrite_hint = str(row.get("historical_rewrite_hint") or "").strip()

    if disposition == "boundary_review":
        return {
            "sort_order": 1,
            "priority": "review_now",
            "reason": "High-threshold-like replay drift may justify direct boundary review before policy-only rows.",
        }
    if disposition == "manual_triage":
        return {
            "sort_order": 2,
            "priority": "review_now",
            "reason": "Mixed replay-drift signals need manual triage before using this row as policy-only evidence.",
        }
    if not historical_rewrite_hint:
        return {
            "sort_order": 3,
            "priority": "review_first",
            "reason": "Policy-only default holds, but the historical rewrite hint is missing, so review this row before stronger policy-only rows.",
        }
    return {
        "sort_order": 4,
        "priority": "review_later",
        "reason": "Policy-only default is reinforced by the historical rewrite hint; review after more ambiguous rows.",
    }


def _manual_review_checklist_row(
    row: dict[str, Any],
    *,
    prefill_reviewer_fields: bool,
) -> dict[str, Any]:
    default_recommendation = _default_manual_review_recommendation(row)
    default_priority = _default_manual_review_priority(row)
    return {
        "review_bucket": "threshold_relevant",
        "paper_id": str(row.get("paper_id") or ""),
        "title": str(row.get("title") or ""),
        "current_gate_decision": str(row.get("current_gate_decision") or ""),
        "replay_gate_decision": str(row.get("replay_gate_decision") or ""),
        "confidence": row.get("confidence") if row.get("confidence") is not None else "",
        "confidence_band": str(row.get("confidence_band") or ""),
        "probable_drift_cause": str(row.get("probable_drift_cause") or ""),
        "evidence_source": str(row.get("evidence_source") or ""),
        "historical_rewrite_hint": str(row.get("historical_rewrite_hint") or ""),
        "review_target": "mid_confidence_escalation_policy",
        "default_reviewer_disposition": default_recommendation["default_reviewer_disposition"],
        "default_supports_mid_confidence_policy_review": default_recommendation[
            "default_supports_mid_confidence_policy_review"
        ],
        "default_supports_high_threshold_change": default_recommendation[
            "default_supports_high_threshold_change"
        ],
        "default_review_priority": default_priority["priority"],
        "default_review_priority_reason": default_priority["reason"],
        "default_reviewer_note": default_recommendation["default_reviewer_note"],
        "reviewer_disposition": (
            default_recommendation["default_reviewer_disposition"]
            if prefill_reviewer_fields
            else ""
        ),
        "supports_mid_confidence_policy_review": (
            default_recommendation["default_supports_mid_confidence_policy_review"]
            if prefill_reviewer_fields
            else ""
        ),
        "supports_high_threshold_change": (
            default_recommendation["default_supports_high_threshold_change"]
            if prefill_reviewer_fields
            else ""
        ),
        "reviewer_notes": (
            default_recommendation["default_reviewer_note"]
            if prefill_reviewer_fields
            else ""
        ),
    }


def render_processor_gate_threshold_manual_review_checklist_csv(payload: dict[str, Any]) -> str:
    sorted_rows = _sorted_threshold_relevant_rows(payload)
    fieldnames = _manual_review_checklist_fieldnames()
    output = StringIO()
    writer = csv.DictWriter(output, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    for row in sorted_rows:
        writer.writerow(_manual_review_checklist_row(row, prefill_reviewer_fields=False))
    return output.getvalue()


def render_processor_gate_threshold_manual_review_seed_csv(payload: dict[str, Any]) -> str:
    sorted_rows = _sorted_threshold_relevant_rows(payload)
    output = StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=_manual_review_checklist_fieldnames(),
        lineterminator="\n",
    )
    writer.writeheader()
    for row in sorted_rows:
        writer.writerow(_manual_review_checklist_row(row, prefill_reviewer_fields=True))
    return output.getvalue()


def render_processor_gate_threshold_manual_review_frontier_csv(payload: dict[str, Any]) -> str:
    sorted_rows = _frontier_manual_review_rows(payload)
    output = StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=_manual_review_checklist_fieldnames(),
        lineterminator="\n",
    )
    writer.writeheader()
    for row in sorted_rows:
        writer.writerow(_manual_review_checklist_row(row, prefill_reviewer_fields=True))
    return output.getvalue()


def _frontier_manual_review_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        row
        for row in _sorted_threshold_relevant_rows(payload)
        if str(_default_manual_review_priority(row).get("priority") or "").strip()
        in {"review_now", "review_first"}
    ]


def _frontier_local_precheck(row: dict[str, Any]) -> dict[str, str]:
    default_recommendation = _default_manual_review_recommendation(row)
    disposition = str(default_recommendation.get("default_reviewer_disposition") or "").strip()
    confidence_band = str(row.get("confidence_band") or "").strip()
    probable_drift_cause = str(row.get("probable_drift_cause") or "").strip()
    current_gate_decision = str(row.get("current_gate_decision") or "").strip()
    replay_gate_decision = str(row.get("replay_gate_decision") or "").strip()
    current_gate_reason_category = str(row.get("current_gate_reason_category") or "").strip()
    local_provenance_hint = str(row.get("local_provenance_hint") or "").strip()
    feedback_log_import_hint = str(row.get("feedback_log_import_hint") or "").strip()
    historical_rewrite_hint = str(row.get("historical_rewrite_hint") or "").strip()

    if disposition == "boundary_review":
        return {
            "call": "boundary_signal_present",
            "reason": (
                "Local evidence already includes high-threshold-like replay drift, so this frontier row still needs direct boundary review."
            ),
        }
    if disposition == "manual_triage":
        return {
            "call": "manual_triage_needed",
            "reason": (
                "Local evidence remains mixed, so this frontier row should stay in manual triage before being treated as policy-only or threshold-boundary support."
            ),
        }

    reasons: list[str] = []
    if current_gate_reason_category == "confidence_threshold":
        reasons.append("current gate reason remains confidence-threshold based")
    if local_provenance_hint == "precanonical_explicit_gate_reason_preserved":
        reasons.append("precanonical explicit gate reason is still preserved")
    if feedback_log_import_hint == "no_feedback_log_match":
        reasons.append("no feedback-log rewrite is recorded locally")
    if not historical_rewrite_hint:
        reasons.append("historical rewrite hint is missing, which is why the row stays at the frontier")
    if (
        confidence_band == "mid"
        and probable_drift_cause == "legacy_mid_confidence_approval"
        and current_gate_decision == "APPROVED"
        and replay_gate_decision == "PENDING_REVIEW"
    ):
        if not reasons:
            reasons.append("row still fits the legacy mid-confidence approval replay pattern")
        return {
            "call": "policy_only_supported",
            "reason": "; ".join(reasons) + ".",
        }

    return {
        "call": "manual_triage_needed",
        "reason": "Frontier row does not cleanly match the current policy-only pattern and should stay in manual triage.",
    }


def render_processor_gate_threshold_manual_review_frontier_notes_markdown(
    payload: dict[str, Any],
    *,
    review: dict[str, Any],
) -> str:
    frontier_rows = _frontier_manual_review_rows(payload)
    decision = review.get("decision") if isinstance(review.get("decision"), dict) else {}
    manual_review_scope = (
        review.get("manual_review_scope") if isinstance(review.get("manual_review_scope"), dict) else {}
    )
    prefill_summary = (
        manual_review_scope.get("prefill_summary")
        if isinstance(manual_review_scope.get("prefill_summary"), dict)
        else {}
    )
    manual_review_basis = (
        review.get("manual_review_basis") if isinstance(review.get("manual_review_basis"), dict) else {}
    )

    review_now_count = sum(
        1
        for row in frontier_rows
        if str(_default_manual_review_priority(row).get("priority") or "").strip() == "review_now"
    )
    review_first_count = sum(
        1
        for row in frontier_rows
        if str(_default_manual_review_priority(row).get("priority") or "").strip() == "review_first"
    )
    policy_only_count = sum(
        1
        for row in frontier_rows
        if str(_default_manual_review_recommendation(row).get("default_reviewer_disposition") or "").strip()
        == "policy_only_review"
    )
    boundary_count = sum(
        1
        for row in frontier_rows
        if str(_default_manual_review_recommendation(row).get("default_reviewer_disposition") or "").strip()
        == "boundary_review"
    )
    triage_count = sum(
        1
        for row in frontier_rows
        if str(_default_manual_review_recommendation(row).get("default_reviewer_disposition") or "").strip()
        == "manual_triage"
    )

    run_id = str(payload.get("run_id") or review.get("run_id") or "-").strip() or "-"
    threshold_change_status = str(decision.get("threshold_change_status") or "-").strip() or "-"
    threshold_change_next_step = str(decision.get("threshold_change_next_step") or "-").strip() or "-"
    basis_call = str(manual_review_basis.get("preliminary_call") or "-").strip() or "-"
    basis_summary = str(manual_review_basis.get("summary") or "-").strip() or "-"
    prefill_text = str(prefill_summary.get("summary") or "-").strip() or "-"

    frontier_precheck_calls = Counter(
        str(_frontier_local_precheck(row).get("call") or "").strip() or "manual_triage_needed"
        for row in frontier_rows
    )
    if frontier_rows and policy_only_count == len(frontier_rows) and boundary_count == 0 and triage_count == 0:
        frontier_summary = (
            "Current frontier rows are front-loaded because corroborating historical rewrite hints are missing, "
            "not because they already support a high-threshold change."
        )
    elif frontier_rows:
        frontier_summary = (
            "Current frontier rows include direct boundary-review or mixed-triage evidence and should be inspected "
            "before lower-risk policy-only backlog rows."
        )
    else:
        frontier_summary = "No review_now or review_first rows are currently queued in the frontier subset."

    lines = [
        f"# Processor Gate Threshold Manual Review Frontier: {run_id}",
        "",
        f"- Frontier Rows: {len(frontier_rows)}",
        f"- review_now: {review_now_count}",
        f"- review_first: {review_first_count}",
        f"- Default Dispositions: policy_only={policy_only_count}, boundary={boundary_count}, triage={triage_count}",
        "- Local Precheck: "
        + ", ".join(
            f"{label}={int(frontier_precheck_calls.get(label) or 0)}"
            for label in ("policy_only_supported", "boundary_signal_present", "manual_triage_needed")
        ),
        f"- Threshold Change Status: {threshold_change_status}",
        f"- Threshold Change Next Step: {threshold_change_next_step}",
        f"- Basis Call: {basis_call}",
        f"- Basis Summary: {basis_summary}",
        f"- Prefill Summary: {prefill_text}",
        "",
        "## Frontier Interpretation",
        f"- {frontier_summary}",
        "",
    ]

    if not frontier_rows:
        lines.append("## Frontier Rows")
        lines.append("- none")
        lines.append("")
        return "\n".join(lines).rstrip() + "\n"

    lines.append("## Frontier Rows")
    for row in frontier_rows:
        if not isinstance(row, dict):
            continue
        paper_id = str(row.get("paper_id") or "-").strip() or "-"
        title_text = str(row.get("title") or "-").strip() or "-"
        confidence_text = str(row.get("confidence") if row.get("confidence") is not None else "-")
        confidence_band = str(row.get("confidence_band") or "-").strip() or "-"
        current_gate_decision = str(row.get("current_gate_decision") or "-").strip() or "-"
        replay_gate_decision = str(row.get("replay_gate_decision") or "-").strip() or "-"
        probable_drift_cause = str(row.get("probable_drift_cause") or "-").strip() or "-"
        gate_reason_category = str(row.get("current_gate_reason_category") or "-").strip() or "-"
        evidence_source = str(row.get("evidence_source") or "-").strip() or "-"
        local_provenance_hint = str(row.get("local_provenance_hint") or "-").strip() or "-"
        historical_rewrite_hint = str(row.get("historical_rewrite_hint") or "").strip() or "none"
        default_recommendation = _default_manual_review_recommendation(row)
        default_priority = _default_manual_review_priority(row)
        local_precheck = _frontier_local_precheck(row)
        current_status = str(row.get("current_status") or "-").strip() or "-"
        replay_status = str(row.get("replay_status") or "-").strip() or "-"
        precanonical_gate_reason = str(row.get("precanonical_gate_reason") or "-").strip() or "-"
        current_gate_reason = str(row.get("current_gate_reason") or "-").strip() or "-"
        feedback_log_import_hint = str(row.get("feedback_log_import_hint") or "-").strip() or "-"
        historical_path_hint = str(row.get("historical_path_hint") or "-").strip() or "-"
        has_evidence_text = "yes" if bool(row.get("has_evidence_text")) else "no"

        lines.extend(
            [
                f"### {paper_id}",
                f"- Title: {title_text}",
                f"- Status: current={current_status}, replay={replay_status}",
                f"- Transition: {current_gate_decision}->{replay_gate_decision}",
                f"- Confidence: {confidence_text} ({confidence_band})",
                f"- Cause: {probable_drift_cause}",
                f"- Precanonical Gate Reason: {precanonical_gate_reason}",
                f"- Current Gate Reason: {current_gate_reason}",
                f"- Gate Reason Category: {gate_reason_category}",
                f"- Evidence Source: {evidence_source}",
                f"- Evidence Present: {has_evidence_text}",
                f"- Feedback Log Import Hint: {feedback_log_import_hint}",
                f"- Local Provenance Hint: {local_provenance_hint}",
                f"- Historical Path Hint: {historical_path_hint}",
                f"- Historical Rewrite Hint: {historical_rewrite_hint}",
                f"- Default Disposition: {default_recommendation['default_reviewer_disposition']}",
                f"- Default Priority: {default_priority['priority']}",
                f"- Priority Reason: {default_priority['reason']}",
                f"- Default Note: {default_recommendation['default_reviewer_note']}",
                f"- Local Precheck: {str(local_precheck.get('call') or '-').strip() or '-'}",
                f"- Local Precheck Reason: {str(local_precheck.get('reason') or '-').strip() or '-'}",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def render_processor_gate_threshold_manual_review_crosscheck_packet_markdown(
    payload: dict[str, Any],
    *,
    review: dict[str, Any],
) -> str:
    frontier_rows = _frontier_manual_review_rows(payload)
    decision = review.get("decision") if isinstance(review.get("decision"), dict) else {}
    manual_review_basis = (
        review.get("manual_review_basis") if isinstance(review.get("manual_review_basis"), dict) else {}
    )

    run_id = str(payload.get("run_id") or review.get("run_id") or "-").strip() or "-"
    threshold_change_status = str(decision.get("threshold_change_status") or "-").strip() or "-"
    threshold_change_next_step = str(decision.get("threshold_change_next_step") or "-").strip() or "-"
    basis_summary = str(manual_review_basis.get("summary") or "-").strip() or "-"

    lines = [
        f"# Processor Gate Frontier Cross-Check Packet: {run_id}",
        "",
        "## Goal",
        "- Perform an independent review of the current frontier rows without assuming the existing Codex default is correct.",
        "- Decide whether each row still looks like `policy_only_review` or whether any row shows concrete support for `high-threshold boundary review`.",
        "",
        "## Current Local System Call",
        f"- Threshold Change Status: {threshold_change_status}",
        f"- Threshold Change Next Step: {threshold_change_next_step}",
        f"- Basis Summary: {basis_summary}",
        "",
        "## Instructions For Independent Reviewer",
        "- Use only the evidence listed below.",
        "- Do not assume missing history implies a threshold miss.",
        "- Treat explicit signs of `mid-confidence approval replaying to pending review` as policy debt unless there is concrete contradictory evidence.",
        "- If you think a row should move toward boundary review, point to the exact contradictory evidence.",
        "",
        "## Questions",
        "1. For each row, is the best current call `policy_only_review`, `boundary_review`, or `manual_triage`?",
        "2. What specific evidence supports that call?",
        "3. What, if anything, contradicts the current Codex default?",
        "4. Do these frontier rows justify changing the high threshold now?",
        "",
        "## Frontier Evidence",
    ]

    if not frontier_rows:
        lines.append("- none")
    for row in frontier_rows:
        if not isinstance(row, dict):
            continue
        local_precheck = _frontier_local_precheck(row)
        default_recommendation = _default_manual_review_recommendation(row)
        lines.extend(
            [
                f"### {str(row.get('paper_id') or '-').strip() or '-'}",
                f"- Title: {str(row.get('title') or '-').strip() or '-'}",
                f"- Status: current={str(row.get('current_status') or '-').strip() or '-'}, replay={str(row.get('replay_status') or '-').strip() or '-'}",
                f"- Transition: {str(row.get('current_gate_decision') or '-').strip() or '-'}->{str(row.get('replay_gate_decision') or '-').strip() or '-'}",
                f"- Confidence: {str(row.get('confidence') if row.get('confidence') is not None else '-')} ({str(row.get('confidence_band') or '-').strip() or '-'})",
                f"- Cause: {str(row.get('probable_drift_cause') or '-').strip() or '-'}",
                f"- Precanonical Gate Reason: {str(row.get('precanonical_gate_reason') or '-').strip() or '-'}",
                f"- Current Gate Reason: {str(row.get('current_gate_reason') or '-').strip() or '-'}",
                f"- Gate Reason Category: {str(row.get('current_gate_reason_category') or '-').strip() or '-'}",
                f"- Evidence Source: {str(row.get('evidence_source') or '-').strip() or '-'}",
                f"- Evidence Present: {'yes' if bool(row.get('has_evidence_text')) else 'no'}",
                f"- Feedback Log Import Hint: {str(row.get('feedback_log_import_hint') or '-').strip() or '-'}",
                f"- Local Provenance Hint: {str(row.get('local_provenance_hint') or '-').strip() or '-'}",
                f"- Historical Path Hint: {str(row.get('historical_path_hint') or '-').strip() or '-'}",
                f"- Historical Rewrite Hint: {str(row.get('historical_rewrite_hint') or '').strip() or 'none'}",
                f"- Current Codex Default: {default_recommendation['default_reviewer_disposition']}",
                f"- Current Codex Default Note: {default_recommendation['default_reviewer_note']}",
                f"- Local Precheck: {str(local_precheck.get('call') or '-').strip() or '-'}",
                f"- Local Precheck Reason: {str(local_precheck.get('reason') or '-').strip() or '-'}",
                "",
            ]
        )

    lines.extend(
        [
            "## Suggested Response Template",
            "- Row 1 verdict:",
            "- Row 1 supporting evidence:",
            "- Row 1 contradictory evidence:",
            "- Row 2 verdict:",
            "- Row 2 supporting evidence:",
            "- Row 2 contradictory evidence:",
            "- High-threshold change justified now? yes/no",
            "- One-line overall conclusion:",
            "",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def render_processor_gate_threshold_manual_review_basis_markdown(payload: dict[str, Any]) -> str:
    lines = [
        f"# Processor Gate Threshold Manual Review Basis: {payload.get('run_id') or '-'}",
        "",
        f"- Preliminary Call: {payload.get('preliminary_call') or '-'}",
        f"- Summary: {payload.get('summary') or '-'}",
        f"- Threshold Relevant Rows: {payload.get('threshold_relevant_count') or 0}",
        f"- Policy Edge Cases: {payload.get('policy_edge_case_count') or 0}",
        f"- Mid-Confidence Policy Support: {payload.get('mid_confidence_policy_support_count') or 0}",
        f"- High-Threshold Support: {payload.get('high_threshold_support_count') or 0}",
        "",
    ]

    def _render_counts(title: str, counts: object) -> None:
        if not isinstance(counts, dict) or not counts:
            return
        lines.append(f"## {title}")
        for key, value in sorted(counts.items(), key=lambda item: (-int(item[1] or 0), str(item[0]))):
            lines.append(f"- {key}: {int(value or 0)}")
        lines.append("")

    _render_counts("Decision Transitions", payload.get("decision_transition_counts"))
    _render_counts("Probable Drift Causes", payload.get("probable_drift_cause_counts"))
    _render_counts("Evidence Sources", payload.get("evidence_source_counts"))
    _render_counts("Historical Rewrite Hints", payload.get("historical_rewrite_hint_counts"))
    _render_counts("Exact Confidence Values", payload.get("exact_confidence_counts"))

    sample_titles = payload.get("sample_titles") if isinstance(payload.get("sample_titles"), list) else []
    if sample_titles:
        lines.append("## Sample Titles")
        lines.extend(f"- {str(title).strip()}" for title in sample_titles if str(title).strip())
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def render_processor_gate_threshold_manual_review_decision_markdown(
    *,
    review: dict[str, Any],
) -> str:
    decision = review.get("decision") if isinstance(review.get("decision"), dict) else {}
    manual_review_scope = (
        review.get("manual_review_scope") if isinstance(review.get("manual_review_scope"), dict) else {}
    )
    manual_review_basis = (
        review.get("manual_review_basis") if isinstance(review.get("manual_review_basis"), dict) else {}
    )
    worksheet_summary = (
        manual_review_scope.get("worksheet_summary")
        if isinstance(manual_review_scope.get("worksheet_summary"), dict)
        else {}
    )
    prefill_summary = (
        manual_review_scope.get("prefill_summary")
        if isinstance(manual_review_scope.get("prefill_summary"), dict)
        else {}
    )

    run_id = str(review.get("run_id") or "-").strip() or "-"
    recommended_action = str(decision.get("recommended_action") or "-").strip() or "-"
    next_step = str(decision.get("next_step") or "-").strip() or "-"
    threshold_change_ready = "yes" if bool(decision.get("threshold_change_ready")) else "no"
    threshold_change_status = str(decision.get("threshold_change_status") or "-").strip() or "-"
    threshold_change_next_step = str(decision.get("threshold_change_next_step") or "-").strip() or "-"
    threshold_change_blocker = str(decision.get("threshold_change_blocker") or "-").strip() or "-"
    worksheet_target = str(worksheet_summary.get("primary_review_target") or "-").strip() or "-"
    worksheet_text = str(worksheet_summary.get("summary") or "-").strip() or "-"
    prefill_text = str(prefill_summary.get("summary") or "-").strip() or "-"
    basis_call = str(manual_review_basis.get("preliminary_call") or "-").strip() or "-"
    basis_summary = str(manual_review_basis.get("summary") or "-").strip() or "-"
    threshold_relevant_count = int(
        ((manual_review_scope.get("threshold_relevant") or {}) if isinstance(manual_review_scope.get("threshold_relevant"), dict) else {}).get("count")
        or 0
    )
    policy_edge_case_count = int(
        ((manual_review_scope.get("policy_edge_cases") or {}) if isinstance(manual_review_scope.get("policy_edge_cases"), dict) else {}).get("count")
        or 0
    )

    default_call = "Keep the current high threshold unchanged until manual review is complete."
    if threshold_change_status == "blocked_policy_only":
        default_call = (
            "Treat the current residual bucket as mid-confidence escalation policy debt, not as evidence to lower the high threshold."
        )
    elif threshold_change_status == "candidate_boundary_review":
        default_call = (
            "Inspect the high-threshold boundary directly; current replay-drift evidence may include real boundary misses."
        )

    exit_criteria = [
        "Confirm whether the threshold-relevant rows support policy review only, or any true high-threshold boundary change.",
        "Keep excluded manual-override, indexed-pending, and fixture/test rows out of raw threshold tuning.",
    ]
    if threshold_change_status == "blocked_policy_only":
        exit_criteria.append(
            "Only revisit the high threshold if manual review finds threshold-relevant rows that support a real high-threshold boundary miss."
        )
    elif threshold_change_status == "candidate_boundary_review":
        exit_criteria.append(
            "If boundary-miss evidence is confirmed, open a separate threshold-change review rather than rewriting policy-only rows."
        )

    lines = [
        f"# Processor Gate Threshold Manual Review Decision: {run_id}",
        "",
        "## Current Call",
        f"- Recommended Action: {recommended_action}",
        f"- Next Step: {next_step}",
        f"- Threshold Change Ready: {threshold_change_ready}",
        f"- Threshold Change Status: {threshold_change_status}",
        f"- Threshold Change Next Step: {threshold_change_next_step}",
        f"- Threshold Change Blocker: {threshold_change_blocker}",
        "",
        "## Review Basis",
        f"- Worksheet Target: {worksheet_target}",
        f"- Worksheet Summary: {worksheet_text}",
        f"- Prefill Summary: {prefill_text}",
        f"- Basis Call: {basis_call}",
        f"- Basis Summary: {basis_summary}",
        f"- Threshold-Relevant Rows: {threshold_relevant_count}",
        f"- Policy Edge Cases: {policy_edge_case_count}",
        "",
        "## Default Call",
        f"- {default_call}",
        "",
        "## Review Questions",
        "- Do the threshold-relevant rows support mid-confidence escalation policy review only?",
        "- Do any threshold-relevant rows show a true high-threshold boundary miss instead of policy debt?",
        "- Can the excluded rows remain outside raw threshold tuning?",
        "",
        "## Exit Criteria",
    ]
    lines.extend(f"- {item}" for item in exit_criteria)
    lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _boundary_support_rows(manual_review_rows: dict[str, Any]) -> list[dict[str, Any]]:
    threshold_relevant = (
        manual_review_rows.get("threshold_relevant")
        if isinstance(manual_review_rows.get("threshold_relevant"), dict)
        else {}
    )
    rows = threshold_relevant.get("rows") if isinstance(threshold_relevant.get("rows"), list) else []
    support_rows: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        recommendation = _default_manual_review_recommendation(row)
        if str(recommendation.get("default_supports_high_threshold_change") or "").strip() != "yes":
            continue
        support_rows.append(
            {
                "paper_id": str(row.get("paper_id") or "").strip() or None,
                "title": str(row.get("title") or "").strip() or None,
                "confidence": row.get("confidence"),
                "confidence_band": str(row.get("confidence_band") or "").strip() or None,
                "probable_drift_cause": str(row.get("probable_drift_cause") or "").strip() or None,
                "current_gate_decision": str(row.get("current_gate_decision") or "").strip() or None,
                "replay_gate_decision": str(row.get("replay_gate_decision") or "").strip() or None,
            }
        )
    return support_rows


def _threshold_change_diff_template(*, current_high: object, current_low: object) -> str:
    high_text = (
        f"{float(current_high):.2f}"
        if current_high not in (None, "")
        else "CURRENT_HIGH_THRESHOLD"
    )
    low_text = (
        f"{float(current_low):.2f}"
        if current_low not in (None, "")
        else "CURRENT_LOW_THRESHOLD"
    )
    return "\n".join(
        [
            " confidence_thresholds:",
            f"-  high: {high_text}",
            f"+  high: <{THRESHOLD_CHANGE_PLACEHOLDER}>",
            f"   low: {low_text}",
        ]
    ) + "\n"


def _threshold_change_validation_replay_run_id(review_run_id: object) -> str:
    base = str(review_run_id or "").strip() or "processor_gate_threshold_review"
    return f"{base}__threshold_validation_replay"


def _threshold_change_validation_replay_command_template(
    *,
    proposal_path: Path,
    validation_run_id: str,
    replay_inputs: dict[str, Any],
) -> str:
    script_path = ROOT / "scripts" / "eval" / "audit_processor_gate_replay_drift.py"
    proposal_path = proposal_path.expanduser().resolve(strict=False)
    placeholder = f"<{THRESHOLD_CHANGE_PLACEHOLDER}>"
    optional_paths = [
        ("--db-path", replay_inputs.get("db_path")),
        ("--paper-id-migration-plan", replay_inputs.get("paper_id_migration_plan_path")),
        ("--precanonical-db-path", replay_inputs.get("precanonical_db_path")),
        ("--feedback-log-path", replay_inputs.get("feedback_log_path")),
    ]
    if os.name == "nt":
        interpreter = ROOT / ".venv" / "Scripts" / "python.exe"
        python_command = f'"{interpreter}"' if interpreter.exists() else "python"
        parts = [f'{python_command} "{script_path}"']
        for flag, value in optional_paths:
            value_text = str(value or "").strip()
            if value_text:
                parts.append(f'{flag} "{value_text}"')
        parts.extend(
            [
                f'--threshold-change-proposal "{proposal_path}"',
                f'--reviewed-high-threshold "{placeholder}"',
                f'--run-id "{validation_run_id}"',
            ]
        )
        return " ".join(parts)

    interpreter = ROOT / ".venv" / "bin" / "python"
    python_command = str(interpreter) if interpreter.exists() else "python3"
    parts = [shlex.quote(python_command), shlex.quote(str(script_path))]
    for flag, value in optional_paths:
        value_text = str(value or "").strip()
        if value_text:
            parts.extend([flag, shlex.quote(value_text)])
    parts.extend(
        [
            "--threshold-change-proposal",
            shlex.quote(str(proposal_path)),
            "--reviewed-high-threshold",
            shlex.quote(placeholder),
            "--run-id",
            shlex.quote(validation_run_id),
        ]
    )
    return " ".join(parts)


def build_processor_gate_threshold_change_proposal(
    *,
    review: dict[str, Any],
    manual_review_rows: dict[str, Any],
    proposal_path: Path,
) -> dict[str, Any] | None:
    decision = review.get("decision") if isinstance(review.get("decision"), dict) else {}
    if not bool(decision.get("threshold_change_ready")):
        return None

    inputs = review.get("inputs") if isinstance(review.get("inputs"), dict) else {}
    manual_review_basis = (
        review.get("manual_review_basis") if isinstance(review.get("manual_review_basis"), dict) else {}
    )
    support_rows = _boundary_support_rows(manual_review_rows)
    current_high = inputs.get("high_threshold")
    current_low = inputs.get("low_threshold")
    validation_replay_run_id = _threshold_change_validation_replay_run_id(
        review.get("run_id")
    )

    return {
        "schema_version": "processor_gate_threshold_change_proposal.v1",
        "generated_at": str(review.get("generated_at") or _utc_now_iso()),
        "run_id": str(review.get("run_id") or "").strip() or None,
        "proposal_mode": "manual_apply_candidate",
        "proposal_ready": True,
        "target_field": "confidence_thresholds.high",
        "current_thresholds": {
            "high": current_high,
            "low": current_low,
        },
        "proposed_thresholds": {
            "high": None,
            "low": current_low,
        },
        "reviewed_value_placeholder": THRESHOLD_CHANGE_PLACEHOLDER,
        "threshold_change_status": str(decision.get("threshold_change_status") or "").strip() or None,
        "threshold_change_next_step": str(decision.get("threshold_change_next_step") or "").strip() or None,
        "decision_reason": str(decision.get("decision_reason") or "").strip() or None,
        "basis_summary": str(manual_review_basis.get("summary") or "").strip() or None,
        "operator_note": (
            "Replace the placeholder only after manual review confirms a real high-threshold boundary miss; "
            "do not auto-apply this proposal directly from review artifacts."
        ),
        "validation_replay_run_id": validation_replay_run_id,
        "validation_replay_command_template": _threshold_change_validation_replay_command_template(
            proposal_path=proposal_path,
            validation_run_id=validation_replay_run_id,
            replay_inputs=inputs,
        ),
        "validation_replay_note": (
            "Replace the reviewed-threshold placeholder and run this replay before editing config."
        ),
        "support_count": len(support_rows),
        "support_sample_ids": [
            str(row.get("paper_id") or "").strip()
            for row in support_rows
            if str(row.get("paper_id") or "").strip()
        ][:5],
        "support_rows": support_rows[:5],
        "diff_template": _threshold_change_diff_template(
            current_high=current_high,
            current_low=current_low,
        ),
    }


def render_processor_gate_threshold_change_proposal_markdown(payload: dict[str, Any]) -> str:
    current_thresholds = (
        payload.get("current_thresholds") if isinstance(payload.get("current_thresholds"), dict) else {}
    )
    proposed_thresholds = (
        payload.get("proposed_thresholds") if isinstance(payload.get("proposed_thresholds"), dict) else {}
    )
    support_rows = payload.get("support_rows") if isinstance(payload.get("support_rows"), list) else []
    support_sample_ids = (
        [str(item).strip() for item in payload.get("support_sample_ids", []) if str(item).strip()]
        if isinstance(payload.get("support_sample_ids"), list)
        else []
    )
    proposed_high_threshold = (
        proposed_thresholds.get("high")
        if proposed_thresholds.get("high") is not None
        else f"<{payload.get('reviewed_value_placeholder') or THRESHOLD_CHANGE_PLACEHOLDER}>"
    )
    validation_replay_command = str(
        payload.get("validation_replay_command_template") or ""
    ).strip()

    lines = [
        f"# Processor Gate Threshold Change Proposal: {payload.get('run_id') or '-'}",
        "",
        f"- Generated At: {payload.get('generated_at') or '-'}",
        f"- Proposal Mode: {payload.get('proposal_mode') or '-'}",
        f"- Proposal Ready: {'yes' if bool(payload.get('proposal_ready')) else 'no'}",
        f"- Target Field: {payload.get('target_field') or '-'}",
        f"- Current High Threshold: {current_thresholds.get('high') if current_thresholds.get('high') is not None else '-'}",
        f"- Current Low Threshold: {current_thresholds.get('low') if current_thresholds.get('low') is not None else '-'}",
        f"- Proposed High Threshold: {proposed_high_threshold}",
        f"- Threshold Change Status: {payload.get('threshold_change_status') or '-'}",
        f"- Threshold Change Next Step: {payload.get('threshold_change_next_step') or '-'}",
        f"- Decision Reason: {payload.get('decision_reason') or '-'}",
        f"- Basis Summary: {payload.get('basis_summary') or '-'}",
        f"- Operator Note: {payload.get('operator_note') or '-'}",
        f"- Validation Replay Run ID: {payload.get('validation_replay_run_id') or '-'}",
        f"- Validation Replay Note: {payload.get('validation_replay_note') or '-'}",
        f"- Support Rows: {payload.get('support_count') or 0}",
        "",
    ]

    if validation_replay_command:
        lines.extend(
            [
                "## Validation Replay Command",
                "```bash",
                validation_replay_command,
                "```",
                "",
            ]
        )

    if support_sample_ids:
        lines.append("## Support Sample IDs")
        lines.extend(f"- {item}" for item in support_sample_ids)
        lines.append("")

    lines.extend(
        [
            "## Candidate Diff Template",
            "```diff",
            str(payload.get("diff_template") or "").rstrip(),
            "```",
            "",
        ]
    )

    if support_rows:
        lines.append("## Boundary Support Rows")
        for row in support_rows:
            if not isinstance(row, dict):
                continue
            lines.append(
                "- "
                + " | ".join(
                    [
                        str(row.get("paper_id") or "-"),
                        str(row.get("title") or "-"),
                        f"confidence={row.get('confidence') if row.get('confidence') is not None else '-'}",
                        f"band={row.get('confidence_band') or '-'}",
                        f"cause={row.get('probable_drift_cause') or '-'}",
                        f"transition={row.get('current_gate_decision') or '-'}->{row.get('replay_gate_decision') or '-'}",
                    ]
                )
            )
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def _is_mid_confidence_policy_dominant(manual_review_scope: dict[str, Any]) -> bool:
    threshold_relevant = (
        manual_review_scope.get("threshold_relevant")
        if isinstance(manual_review_scope.get("threshold_relevant"), dict)
        else {}
    )
    threshold_relevant_count = int(threshold_relevant.get("count") or 0)
    if threshold_relevant_count <= 0:
        return False
    return (
        threshold_relevant.get("probable_drift_cause_counts") == {
            "legacy_mid_confidence_approval": threshold_relevant_count
        }
        and threshold_relevant.get("confidence_band_counts") == {"mid": threshold_relevant_count}
        and threshold_relevant.get("decision_transition_counts") == {
            "APPROVED->PENDING_REVIEW": threshold_relevant_count
        }
    )


def _build_manual_review_worksheet_summary(manual_review_scope: dict[str, Any]) -> dict[str, Any]:
    threshold_relevant = (
        manual_review_scope.get("threshold_relevant")
        if isinstance(manual_review_scope.get("threshold_relevant"), dict)
        else {}
    )
    policy_edge_cases = (
        manual_review_scope.get("policy_edge_cases")
        if isinstance(manual_review_scope.get("policy_edge_cases"), dict)
        else {}
    )
    excluded = manual_review_scope.get("excluded") if isinstance(manual_review_scope.get("excluded"), dict) else {}

    threshold_relevant_count = int(threshold_relevant.get("count") or 0)
    policy_edge_case_count = int(policy_edge_cases.get("count") or 0)
    excluded_count = sum(
        int(((excluded.get(label) or {}) if isinstance(excluded.get(label), dict) else {}).get("count") or 0)
        for label in ("manual_override", "indexed_pending", "fixture_or_test", "other")
    )

    if threshold_relevant_count > 0:
        primary_review_target = (
            "mid_confidence_escalation_policy"
            if _is_mid_confidence_policy_dominant(manual_review_scope)
            else "high_threshold_boundary_review"
        )
        if primary_review_target == "mid_confidence_escalation_policy":
            summary = (
                f"{threshold_relevant_count} threshold-relevant row(s) are queued for mid-confidence "
                f"escalation policy review; exclude {excluded_count} non-threshold row(s) from raw threshold changes."
            )
        else:
            summary = (
                f"{threshold_relevant_count} threshold-relevant row(s) are queued for high-threshold "
                f"boundary review; exclude {excluded_count} non-threshold row(s) from raw threshold changes."
            )
        return {
            "pending_count": threshold_relevant_count,
            "review_bucket": "threshold_relevant",
            "primary_review_target": primary_review_target,
            "excluded_count": excluded_count,
            "summary": summary,
        }

    if policy_edge_case_count > 0:
        return {
            "pending_count": policy_edge_case_count,
            "review_bucket": "policy_edge_cases",
            "primary_review_target": "high_confidence_pending_policy",
            "excluded_count": excluded_count,
            "summary": (
                f"{policy_edge_case_count} policy edge-case row(s) are queued for "
                "high-confidence pending policy review."
            ),
        }

    summary = "No threshold-relevant rows are currently queued for manual threshold review."
    if excluded_count > 0:
        summary = (
            f"No threshold-relevant rows are currently queued for manual threshold review; "
            f"{excluded_count} excluded row(s) remain outside raw threshold changes."
        )
    return {
        "pending_count": 0,
        "review_bucket": None,
        "primary_review_target": None,
        "excluded_count": excluded_count,
        "summary": summary,
    }


def _build_manual_review_basis(
    *,
    drift_details: dict[str, Any] | None,
    manual_review_scope: dict[str, Any],
) -> dict[str, Any]:
    partition = _partition_manual_review_rows(drift_details)
    threshold_relevant_rows = partition["threshold_relevant"]
    policy_edge_case_rows = partition["policy_edge_cases"]

    evidence_source_counts = Counter(
        str(row.get("evidence_source") or "unknown").strip() or "unknown"
        for row in threshold_relevant_rows
    )
    historical_rewrite_hint_counts = Counter(
        str(row.get("historical_rewrite_hint") or "none").strip() or "none"
        for row in threshold_relevant_rows
    )
    exact_confidence_counts = Counter(
        str(row.get("confidence") if row.get("confidence") is not None else "unknown").strip() or "unknown"
        for row in threshold_relevant_rows
    )
    transition_counts = Counter(
        f"{str(row.get('current_gate_decision') or '-').strip()}->{str(row.get('replay_gate_decision') or '-').strip()}"
        for row in threshold_relevant_rows
    )
    probable_cause_counts = Counter(
        str(row.get("probable_drift_cause") or "unknown").strip() or "unknown"
        for row in threshold_relevant_rows
    )

    mid_confidence_policy_support_count = sum(
        1
        for row in threshold_relevant_rows
        if str(row.get("confidence_band") or "").strip() == "mid"
        and str(row.get("probable_drift_cause") or "").strip() == "legacy_mid_confidence_approval"
        and str(row.get("current_gate_decision") or "").strip() == "APPROVED"
        and str(row.get("replay_gate_decision") or "").strip() == "PENDING_REVIEW"
    )
    high_threshold_support_count = sum(
        1
        for row in threshold_relevant_rows
        if str(row.get("confidence_band") or "").strip() == "high"
        or str(row.get("probable_drift_cause") or "").strip() == "legacy_high_confidence_pending"
    )

    sample_titles = [
        str(row.get("title") or "").strip()
        for row in threshold_relevant_rows
        if str(row.get("title") or "").strip()
    ][:5]

    threshold_relevant_count = int(
        (
            manual_review_scope.get("threshold_relevant")
            if isinstance(manual_review_scope.get("threshold_relevant"), dict)
            else {}
        ).get("count")
        or 0
    )
    policy_edge_case_count = int(
        (
            manual_review_scope.get("policy_edge_cases")
            if isinstance(manual_review_scope.get("policy_edge_cases"), dict)
            else {}
        ).get("count")
        or 0
    )

    if threshold_relevant_count <= 0 and policy_edge_case_count > 0:
        preliminary_call = "policy_edge_case_review"
        summary = (
            f"No threshold-relevant rows are queued, but {policy_edge_case_count} policy edge-case row(s) remain for "
            "high-confidence pending policy review."
        )
    elif threshold_relevant_count <= 0:
        preliminary_call = "no_threshold_review_rows"
        summary = "No threshold-relevant rows currently support manual gate-threshold review."
    elif (
        threshold_relevant_count > 0
        and mid_confidence_policy_support_count == threshold_relevant_count
        and high_threshold_support_count == 0
    ):
        preliminary_call = "mid_confidence_policy_only"
        summary = (
            f"All {threshold_relevant_count} threshold-relevant row(s) are mid-confidence legacy approvals replaying "
            "to pending review; none support a high-threshold boundary change from this evidence alone."
        )
    else:
        preliminary_call = "mixed_manual_review"
        summary = (
            f"{threshold_relevant_count} threshold-relevant row(s) need mixed manual review; "
            f"{high_threshold_support_count} row(s) may still need high-threshold boundary inspection."
        )

    return {
        "preliminary_call": preliminary_call,
        "summary": summary,
        "threshold_relevant_count": threshold_relevant_count,
        "policy_edge_case_count": policy_edge_case_count,
        "mid_confidence_policy_support_count": mid_confidence_policy_support_count,
        "high_threshold_support_count": high_threshold_support_count,
        "evidence_source_counts": dict(sorted(evidence_source_counts.items())),
        "historical_rewrite_hint_counts": dict(sorted(historical_rewrite_hint_counts.items())),
        "exact_confidence_counts": dict(sorted(exact_confidence_counts.items())),
        "decision_transition_counts": dict(sorted(transition_counts.items())),
        "probable_drift_cause_counts": dict(sorted(probable_cause_counts.items())),
        "sample_titles": sample_titles,
    }


def _build_manual_review_prefill_summary(
    *,
    drift_details: dict[str, Any] | None,
) -> dict[str, Any]:
    partition = _partition_manual_review_rows(drift_details)
    threshold_relevant_rows = partition["threshold_relevant"]

    disposition_counts: Counter[str] = Counter()
    priority_counts: Counter[str] = Counter()
    supports_mid_confidence_policy_review_count = 0
    supports_high_threshold_change_count = 0

    for row in threshold_relevant_rows:
        recommendation = _default_manual_review_recommendation(row)
        priority = _default_manual_review_priority(row)
        disposition = str(recommendation.get("default_reviewer_disposition") or "").strip() or "manual_triage"
        disposition_counts[disposition] += 1
        priority_counts[str(priority.get("priority") or "").strip() or "review_now"] += 1
        if str(recommendation.get("default_supports_mid_confidence_policy_review") or "").strip() == "yes":
            supports_mid_confidence_policy_review_count += 1
        if str(recommendation.get("default_supports_high_threshold_change") or "").strip() == "yes":
            supports_high_threshold_change_count += 1

    policy_only_review_count = int(disposition_counts.get("policy_only_review") or 0)
    boundary_review_count = int(disposition_counts.get("boundary_review") or 0)
    manual_triage_count = int(disposition_counts.get("manual_triage") or 0)
    priority_review_now_count = int(priority_counts.get("review_now") or 0)
    priority_review_first_count = int(priority_counts.get("review_first") or 0)
    priority_review_later_count = int(priority_counts.get("review_later") or 0)
    threshold_relevant_count = len(threshold_relevant_rows)

    if threshold_relevant_count <= 0:
        summary = "No threshold-relevant rows are currently queued for default manual-review prefills."
    else:
        summary = (
            f"Default prefills: policy_only={policy_only_review_count}, "
            f"boundary={boundary_review_count}, triage={manual_triage_count}. "
            f"Priority: now={priority_review_now_count}, first={priority_review_first_count}, later={priority_review_later_count}."
        )

    return {
        "threshold_relevant_count": threshold_relevant_count,
        "policy_only_review_count": policy_only_review_count,
        "boundary_review_count": boundary_review_count,
        "manual_triage_count": manual_triage_count,
        "priority_review_now_count": priority_review_now_count,
        "priority_review_first_count": priority_review_first_count,
        "priority_review_later_count": priority_review_later_count,
        "supports_mid_confidence_policy_review_count": supports_mid_confidence_policy_review_count,
        "supports_high_threshold_change_count": supports_high_threshold_change_count,
        "summary": summary,
    }


def _build_gate_threshold_tuning_targets(manual_review_scope: dict[str, Any]) -> list[str]:
    threshold_relevant = (
        manual_review_scope.get("threshold_relevant")
        if isinstance(manual_review_scope.get("threshold_relevant"), dict)
        else {}
    )
    policy_edge_cases = (
        manual_review_scope.get("policy_edge_cases")
        if isinstance(manual_review_scope.get("policy_edge_cases"), dict)
        else {}
    )
    excluded = manual_review_scope.get("excluded") if isinstance(manual_review_scope.get("excluded"), dict) else {}

    targets: list[str] = []
    if _is_mid_confidence_policy_dominant(manual_review_scope):
        targets.append("mid_confidence_escalation")
    elif int(threshold_relevant.get("count") or 0) > 0:
        targets.append("high_threshold")

    if int(policy_edge_cases.get("count") or 0) > 0:
        targets.append("high_confidence_pending_policy")
    if int((excluded.get("manual_override") or {}).get("count") or 0) > 0:
        targets.append("manual_override_boundary")
    if int((excluded.get("indexed_pending") or {}).get("count") or 0) > 0:
        targets.append("indexed_pending_policy")
    return targets


def _build_gate_threshold_tuning_actions(tuning_targets: list[str]) -> list[dict[str, str]]:
    actions: list[dict[str, str]] = []
    for target in tuning_targets:
        action_config = _TUNING_ACTIONS_BY_TARGET.get(target)
        if not action_config:
            continue
        actions.append(
            {
                "target": target,
                "action": action_config["action"],
                "summary": action_config["summary"],
            }
        )
    return actions


def _build_gate_threshold_tuning_recommendations(
    manual_review_scope: dict[str, Any],
    tuning_targets: list[str],
) -> list[str]:
    recommendations: list[str] = []
    excluded = manual_review_scope.get("excluded") if isinstance(manual_review_scope.get("excluded"), dict) else {}
    if _is_mid_confidence_policy_dominant(manual_review_scope):
        recommendations.append(
            "Current threshold-relevant drift is entirely mid-confidence approval debt, so review the mid-confidence escalation policy before lowering the high threshold."
        )
        recommendations.append(
            "Keep the current high threshold unchanged unless manual review of the threshold-relevant bucket shows true high-threshold misses."
        )
    elif "high_threshold" in tuning_targets:
        recommendations.append(
            "Review the high-threshold boundary only after separating policy-only drift from threshold-relevant rows."
        )

    if int((excluded.get("manual_override") or {}).get("count") or 0) > 0:
        recommendations.append(
            "Manual or human override rows should stay outside raw threshold tuning and be reviewed as explicit policy exceptions."
        )
    if int((excluded.get("indexed_pending") or {}).get("count") or 0) > 0:
        recommendations.append(
            "Indexed-pending rows should stay outside raw threshold changes and be reviewed against the pending/indexed state contract."
        )
    if int((excluded.get("fixture_or_test") or {}).get("count") or 0) > 0:
        recommendations.append(
            "Fixture or test rows should not influence threshold changes."
        )
    return recommendations


def _build_gate_threshold_action_plan(
    *,
    next_step: str,
    tuning_actions: list[dict[str, str]],
    manual_review_scope: dict[str, Any],
) -> list[dict[str, object]]:
    action_plan: list[dict[str, object]] = [
        {
            "order": 1,
            "action": next_step,
            "target": None,
            "blocking": True,
            "summary": (
                "Use the threshold-relevant bucket as the primary manual-review basis before applying gate threshold changes."
                if manual_review_scope
                else "Review the current processor gate threshold evidence manually before applying threshold changes."
            ),
        }
    ]
    for index, item in enumerate(tuning_actions, start=2):
        action_plan.append(
            {
                "order": index,
                "action": item["action"],
                "target": item["target"],
                "blocking": index == 2,
                "summary": item["summary"],
            }
        )
    return action_plan


def _build_threshold_change_decision(
    *,
    review_ready: bool,
    latest_run_status: str,
    next_step: str,
    manual_review_basis: dict[str, Any],
) -> dict[str, Any]:
    preliminary_call = str(manual_review_basis.get("preliminary_call") or "").strip()
    basis_summary = str(manual_review_basis.get("summary") or "").strip()
    high_threshold_support_count = int(manual_review_basis.get("high_threshold_support_count") or 0)

    if not review_ready:
        return {
            "ready": False,
            "status": "blocked_small_sample",
            "blocker": basis_summary or "Not enough replay-drift evidence exists yet for threshold changes.",
            "next_step": next_step,
        }
    if latest_run_status == "missing":
        return {
            "ready": False,
            "status": "blocked_missing_evidence",
            "blocker": basis_summary or "No processor gate replay drift summary exists yet.",
            "next_step": next_step,
        }
    if preliminary_call == "mid_confidence_policy_only":
        return {
            "ready": False,
            "status": "blocked_policy_only",
            "blocker": basis_summary,
            "next_step": "review_mid_confidence_escalation_policy",
        }
    if preliminary_call == "policy_edge_case_review":
        return {
            "ready": False,
            "status": "blocked_policy_edge_case_review",
            "blocker": basis_summary,
            "next_step": "audit_high_confidence_pending_contract",
        }
    if preliminary_call == "no_threshold_review_rows":
        return {
            "ready": False,
            "status": "blocked_no_threshold_rows",
            "blocker": basis_summary,
            "next_step": "generate_processor_gate_replay_drift_audit",
        }
    if high_threshold_support_count > 0:
        return {
            "ready": True,
            "status": "candidate_boundary_review",
            "blocker": None,
            "next_step": "review_high_threshold_boundary",
        }
    return {
        "ready": False,
        "status": "blocked_manual_review",
        "blocker": basis_summary or "Manual review is still required before threshold changes.",
        "next_step": next_step,
    }


def _focus_areas(metrics: dict[str, Any]) -> list[str]:
    probable = metrics.get("probable_drift_cause_counts")
    probable_counts = probable if isinstance(probable, dict) else {}
    focus: list[str] = []

    if int(probable_counts.get("legacy_mid_confidence_approval") or 0) > 0:
        focus.extend(["high_threshold", "mid_confidence_escalation"])
    if int(probable_counts.get("legacy_high_confidence_pending") or 0) > 0:
        focus.append("high_confidence_pending_policy")
    if int(probable_counts.get("legacy_indexed_pending_review") or 0) > 0:
        focus.append("indexed_pending_policy")
    if int(probable_counts.get("manual_or_human_override_mid_confidence") or 0) > 0:
        focus.append("manual_override_boundary")

    deduped: list[str] = []
    for item in focus:
        if item not in deduped:
            deduped.append(item)
    return deduped


def _build_recommendations(
    *,
    metrics: dict[str, Any],
    manual_review_scope: dict[str, Any],
    manual_review_basis: dict[str, Any],
    drift_rate: float,
    drift_warn_threshold: float,
    latest_run_status: str,
) -> list[str]:
    recommendations: list[str] = []
    probable = metrics.get("probable_drift_cause_counts")
    probable_counts = probable if isinstance(probable, dict) else {}
    decision_transitions = metrics.get("decision_transition_counts")
    transition_counts = decision_transitions if isinstance(decision_transitions, dict) else {}

    mid_confidence_drift = int(probable_counts.get("legacy_mid_confidence_approval") or 0)
    if mid_confidence_drift > 0:
        recommendations.append(
            "Review the high threshold and mid-confidence escalation policy first; "
            f"{mid_confidence_drift} drift row(s) are historical mid-confidence approvals replaying to pending review."
        )

    high_pending_drift = int(probable_counts.get("legacy_high_confidence_pending") or 0)
    if high_pending_drift > 0:
        recommendations.append(
            "Check high-confidence pending rows before relaxing thresholds; some legacy rows stayed pending even above the current high threshold."
        )

    indexed_pending_drift = int(probable_counts.get("legacy_indexed_pending_review") or 0)
    if indexed_pending_drift > 0:
        recommendations.append(
            "Review the indexed-pending status contract separately from raw thresholds; some drift rows look like legacy state-shape debt."
        )

    manual_override_drift = int(probable_counts.get("manual_or_human_override_mid_confidence") or 0)
    if manual_override_drift > 0:
        recommendations.append(
            "Preserve explicit manual or human overrides during threshold review; not all mid-confidence drift is threshold debt."
        )

    approved_to_pending = int(transition_counts.get("APPROVED->PENDING_REVIEW") or 0)
    if latest_run_status == "warn" and approved_to_pending > 0:
        recommendations.append(
            f"Latest drift is above the {drift_warn_threshold:.0%} review threshold and is dominated by APPROVED->PENDING_REVIEW transitions ({approved_to_pending})."
        )
    elif latest_run_status == "ok":
        recommendations.append(
            f"Latest drift stays below the {drift_warn_threshold:.0%} warning threshold ({drift_rate:.1%}); keep current thresholds unless new evidence appears."
        )

    if manual_review_scope:
        focus_recommendation = str(manual_review_scope.get("focus_recommendation") or "").strip()
        if focus_recommendation:
            recommendations.append(focus_recommendation)
    basis_summary = str(manual_review_basis.get("summary") or "").strip()
    if basis_summary:
        recommendations.append(basis_summary)

    return recommendations


def build_processor_gate_threshold_review_summary(
    *,
    drift_summary: dict[str, Any] | None,
    drift_summary_path: Path | None,
    drift_details: dict[str, Any] | None = None,
    drift_details_path: Path | None = None,
    run_id: str,
    min_candidate_rows: int,
    drift_warn_threshold: float,
) -> dict[str, Any]:
    inputs = drift_summary.get("inputs") if isinstance(drift_summary, dict) else {}
    metrics = drift_summary.get("metrics") if isinstance(drift_summary, dict) else {}
    latest_run_id = str(drift_summary.get("run_id") or "") if isinstance(drift_summary, dict) else None

    candidate_count = int(metrics.get("candidate_count") or 0) if isinstance(metrics, dict) else 0
    drift_count = int(metrics.get("drift_count") or 0) if isinstance(metrics, dict) else 0
    promotable_count = int(metrics.get("promotable_count") or 0) if isinstance(metrics, dict) else 0
    drift_rate = float(metrics.get("drift_rate") or 0.0) if isinstance(metrics, dict) else 0.0

    review_ready = candidate_count >= min_candidate_rows
    if drift_summary is None:
        latest_run_status = "missing"
        recommended_action = "hold_current_gate_thresholds"
        decision_reason = "no processor gate replay drift summary exists yet, so threshold review should stay on hold"
        next_step = "generate_processor_gate_replay_drift_audit"
    elif not review_ready:
        latest_run_status = "small_sample"
        recommended_action = "hold_current_gate_thresholds"
        decision_reason = (
            f"latest drift run only has {candidate_count} candidate row(s), below the "
            f"{min_candidate_rows}-row review floor"
        )
        next_step = "collect_more_processor_gate_drift_evidence"
    elif drift_rate >= drift_warn_threshold and drift_count > 0:
        latest_run_status = "warn"
        recommended_action = "manual_gate_threshold_review"
        decision_reason = (
            f"latest drift run shows {drift_count}/{candidate_count} drift row(s) "
            f"({drift_rate:.1%}), above the {drift_warn_threshold:.0%} warning threshold"
        )
        next_step = "review_gate_thresholds_and_mid_confidence_policy"
    else:
        latest_run_status = "ok"
        recommended_action = "hold_current_gate_thresholds"
        decision_reason = (
            f"latest drift run shows {drift_count}/{candidate_count} drift row(s) "
            f"({drift_rate:.1%}), below the {drift_warn_threshold:.0%} warning threshold"
        )
        next_step = "keep_current_gate_thresholds"

    focus_areas = _focus_areas(metrics if isinstance(metrics, dict) else {})
    manual_review_scope = _manual_review_scope(drift_details)
    manual_review_scope["worksheet_summary"] = _build_manual_review_worksheet_summary(manual_review_scope)
    manual_review_scope["prefill_summary"] = _build_manual_review_prefill_summary(
        drift_details=drift_details
    )
    manual_review_basis = _build_manual_review_basis(
        drift_details=drift_details,
        manual_review_scope=manual_review_scope,
    )
    tuning_targets = _build_gate_threshold_tuning_targets(manual_review_scope)
    tuning_actions = _build_gate_threshold_tuning_actions(tuning_targets)
    tuning_recommendations = _build_gate_threshold_tuning_recommendations(
        manual_review_scope,
        tuning_targets,
    )
    action_plan = _build_gate_threshold_action_plan(
        next_step=next_step,
        tuning_actions=tuning_actions,
        manual_review_scope=manual_review_scope,
    )
    threshold_change = _build_threshold_change_decision(
        review_ready=review_ready,
        latest_run_status=latest_run_status,
        next_step=next_step,
        manual_review_basis=manual_review_basis,
    )
    recommendations = _build_recommendations(
        metrics=metrics if isinstance(metrics, dict) else {},
        manual_review_scope=manual_review_scope,
        manual_review_basis=manual_review_basis,
        drift_rate=drift_rate,
        drift_warn_threshold=drift_warn_threshold,
        latest_run_status=latest_run_status,
    )
    if _is_mid_confidence_policy_dominant(manual_review_scope):
        decision_reason = (
            f"{decision_reason}; threshold-relevant drift is concentrated in historical mid-confidence approvals, "
            "so review the mid-confidence escalation policy before lowering the high threshold"
        )

    return {
        "schema_version": "processor_gate_threshold_review.v1",
        "generated_at": _utc_now_iso(),
        "run_id": run_id,
        "inputs": {
            "drift_summary_path": str(drift_summary_path) if drift_summary_path is not None else None,
            "drift_details_path": str(drift_details_path) if drift_details_path is not None else None,
            "db_path": inputs.get("db_path") if isinstance(inputs, dict) else None,
            "paper_id_migration_plan_path": (
                inputs.get("paper_id_migration_plan_path") if isinstance(inputs, dict) else None
            ),
            "precanonical_db_path": (
                inputs.get("precanonical_db_path") if isinstance(inputs, dict) else None
            ),
            "feedback_log_path": (
                inputs.get("feedback_log_path") if isinstance(inputs, dict) else None
            ),
            "high_threshold": inputs.get("high_threshold") if isinstance(inputs, dict) else None,
            "low_threshold": inputs.get("low_threshold") if isinstance(inputs, dict) else None,
            "min_candidate_rows": int(max(min_candidate_rows, 0)),
            "drift_warn_threshold": float(max(drift_warn_threshold, 0.0)),
        },
        "decision": {
            "recommended_action": recommended_action,
            "review_ready": bool(review_ready),
            "decision_reason": decision_reason,
            "next_step": next_step,
            "focus_areas": focus_areas,
            "latest_run_id": latest_run_id,
            "latest_run_status": latest_run_status,
            "tuning_targets": tuning_targets,
            "tuning_actions": tuning_actions,
            "tuning_recommendations": tuning_recommendations,
            "action_plan": action_plan,
            "threshold_change_ready": bool(threshold_change["ready"]),
            "threshold_change_status": str(threshold_change["status"]),
            "threshold_change_blocker": threshold_change["blocker"],
            "threshold_change_next_step": str(threshold_change["next_step"]),
        },
        "signal_summary": {
            "candidate_count": candidate_count,
            "promotable_count": promotable_count,
            "drift_count": drift_count,
            "drift_rate": drift_rate,
            "decision_transition_counts": metrics.get("decision_transition_counts", {}) if isinstance(metrics, dict) else {},
            "probable_drift_cause_counts": metrics.get("probable_drift_cause_counts", {}) if isinstance(metrics, dict) else {},
            "gate_reason_category_counts": metrics.get("gate_reason_category_counts", {}) if isinstance(metrics, dict) else {},
            "confidence_band_counts": metrics.get("confidence_band_counts", {}) if isinstance(metrics, dict) else {},
        },
        "manual_review_scope": manual_review_scope,
        "manual_review_basis": manual_review_basis,
        "recommendations": recommendations,
    }


def run_processor_gate_threshold_review(
    *,
    drift_root: Path,
    drift_summary_path: Path | None,
    out_dir: Path,
    run_id: str,
    min_candidate_rows: int,
    drift_warn_threshold: float,
) -> Path:
    resolved_drift_summary_path = drift_summary_path or _latest_drift_summary_path(drift_root)
    summary_payload = _load_json(resolved_drift_summary_path) if resolved_drift_summary_path is not None else None
    resolved_drift_details_path = _drift_details_path(resolved_drift_summary_path)
    details_payload = _load_json(resolved_drift_details_path) if resolved_drift_details_path is not None else None
    review = build_processor_gate_threshold_review_summary(
        drift_summary=summary_payload,
        drift_summary_path=resolved_drift_summary_path,
        drift_details=details_payload,
        drift_details_path=resolved_drift_details_path,
        run_id=run_id,
        min_candidate_rows=min_candidate_rows,
        drift_warn_threshold=drift_warn_threshold,
    )
    run_root = out_dir / run_id
    _write_json(run_root / "summary.json", review)
    manual_review_rows = build_processor_gate_threshold_manual_review_rows(
        drift_details=details_payload,
        drift_details_path=resolved_drift_details_path,
        summary=review,
    )
    _write_json(run_root / "manual_review_rows.json", manual_review_rows)
    (run_root / "manual_review.md").write_text(
        render_processor_gate_threshold_manual_review_markdown(manual_review_rows),
        encoding="utf-8",
    )
    (run_root / "manual_review_checklist.csv").write_text(
        render_processor_gate_threshold_manual_review_checklist_csv(manual_review_rows),
        encoding="utf-8",
    )
    (run_root / "manual_review_seed.csv").write_text(
        render_processor_gate_threshold_manual_review_seed_csv(manual_review_rows),
        encoding="utf-8",
    )
    (run_root / "manual_review_frontier.csv").write_text(
        render_processor_gate_threshold_manual_review_frontier_csv(manual_review_rows),
        encoding="utf-8",
    )
    (run_root / "manual_review_frontier_notes.md").write_text(
        render_processor_gate_threshold_manual_review_frontier_notes_markdown(
            manual_review_rows,
            review=review,
        ),
        encoding="utf-8",
    )
    (run_root / "manual_review_frontier_crosscheck_packet.md").write_text(
        render_processor_gate_threshold_manual_review_crosscheck_packet_markdown(
            manual_review_rows,
            review=review,
        ),
        encoding="utf-8",
    )
    (run_root / "manual_review_basis.md").write_text(
        render_processor_gate_threshold_manual_review_basis_markdown(
            {
                "run_id": review.get("run_id"),
                **(
                    review.get("manual_review_basis")
                    if isinstance(review.get("manual_review_basis"), dict)
                    else {}
                ),
            }
        ),
        encoding="utf-8",
    )
    (run_root / "manual_review_decision.md").write_text(
        render_processor_gate_threshold_manual_review_decision_markdown(review=review),
        encoding="utf-8",
    )
    threshold_change_proposal = build_processor_gate_threshold_change_proposal(
        review=review,
        manual_review_rows=manual_review_rows,
        proposal_path=run_root / "threshold_change_proposal.json",
    )
    if threshold_change_proposal is not None:
        _write_json(run_root / "threshold_change_proposal.json", threshold_change_proposal)
        (run_root / "threshold_change_proposal.md").write_text(
            render_processor_gate_threshold_change_proposal_markdown(
                threshold_change_proposal
            ),
            encoding="utf-8",
        )
    (run_root / "audit.md").write_text(
        render_processor_gate_threshold_review_markdown(review, run_root=run_root),
        encoding="utf-8",
    )
    return run_root


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Recommend whether current processor gate thresholds should stay on hold or move into "
            "manual review, based on replay-drift evidence."
        ),
        epilog=(
            "Writes summary.json into the run directory and emits a repo-local viewer command. "
            "For a direct CLI view, run: "
            f"{_repo_local_viewer_hint()}"
        ),
    )
    parser.add_argument(
        "--drift-root",
        default=str(DEFAULT_DRIFT_ROOT),
        help="Directory containing processor gate replay drift runs.",
    )
    parser.add_argument(
        "--drift-summary",
        default="",
        help="Optional explicit processor gate replay drift summary.json path.",
    )
    parser.add_argument(
        "--out-dir",
        default=str(DEFAULT_OUT_DIR),
        help="Directory to write the threshold review summary into.",
    )
    parser.add_argument("--run-id", required=True, help="Output run identifier.")
    parser.add_argument(
        "--min-candidate-rows",
        type=int,
        default=DEFAULT_MIN_CANDIDATE_ROWS,
        help="Minimum candidate-row count required before gate threshold review is considered ready.",
    )
    parser.add_argument(
        "--drift-warn-threshold",
        type=float,
        default=DEFAULT_DRIFT_WARN_THRESHOLD,
        help="Drift-rate threshold that triggers manual threshold review.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_arg_parser()
    args = parser.parse_args(argv)
    run_root = run_processor_gate_threshold_review(
        drift_root=Path(args.drift_root).expanduser().resolve(),
        drift_summary_path=(Path(args.drift_summary).expanduser().resolve() if str(args.drift_summary).strip() else None),
        out_dir=Path(args.out_dir).expanduser().resolve(),
        run_id=str(args.run_id),
        min_candidate_rows=max(int(args.min_candidate_rows), 0),
        drift_warn_threshold=max(float(args.drift_warn_threshold), 0.0),
    )
    payload = {
        "run_root": str(run_root),
        "summary_path": str(run_root / "summary.json"),
        "markdown_path": str(run_root / "audit.md"),
        "manual_review_rows_path": str(run_root / "manual_review_rows.json"),
        "manual_review_markdown_path": str(run_root / "manual_review.md"),
        "manual_review_checklist_path": str(run_root / "manual_review_checklist.csv"),
        "manual_review_seed_path": str(run_root / "manual_review_seed.csv"),
        "manual_review_frontier_path": str(run_root / "manual_review_frontier.csv"),
        "manual_review_frontier_notes_path": str(run_root / "manual_review_frontier_notes.md"),
        "manual_review_frontier_crosscheck_packet_path": str(run_root / "manual_review_frontier_crosscheck_packet.md"),
        "manual_review_basis_markdown_path": str(run_root / "manual_review_basis.md"),
        "manual_review_decision_markdown_path": str(run_root / "manual_review_decision.md"),
        "threshold_change_proposal_path": (
            str(run_root / "threshold_change_proposal.json")
            if (run_root / "threshold_change_proposal.json").exists()
            else None
        ),
        "threshold_change_proposal_markdown_path": (
            str(run_root / "threshold_change_proposal.md")
            if (run_root / "threshold_change_proposal.md").exists()
            else None
        ),
        "viewer_command": build_processor_gate_threshold_review_viewer_command(
            run_root,
            repo_root=ROOT,
            python_executable=Path(sys.executable),
        ),
    }
    summary_payload = _load_json(run_root / "summary.json")
    print(
        "[recommend_processor_gate_threshold_review] "
        + _compact_processor_gate_threshold_review_text(summary_payload),
        file=sys.stderr,
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
