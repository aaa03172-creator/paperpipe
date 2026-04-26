from __future__ import annotations

import json
import os
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import shlex
import sys
from typing import Any, Mapping

from src.schemas.processor_gate_replay_drift import (
    ProcessorGateReplayDriftDetails,
    ProcessorGateReplayDriftDocument,
    ProcessorGateReplayDriftInput,
    ProcessorGateReplayDriftMetrics,
    ProcessorGateReplayDriftSummary,
)
from src.services.fixture_visibility import classify_test_fixture_paper_record
from src.skills.storage import atomic_write_text

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PROCESSOR_GATE_THRESHOLD_REVIEW_ROOT = REPO_ROOT / "snapshots" / "processor_gate_threshold_review"
DEFAULT_PROCESSOR_GATE_REPLAY_DRIFT_ROOT = REPO_ROOT / "snapshots" / "processor_gate_replay_drift"


def default_processor_gate_threshold_review_root(*, repo_root: Path | None = None) -> Path:
    base = (repo_root or REPO_ROOT).expanduser().resolve(strict=False)
    return (base / "snapshots" / "processor_gate_threshold_review").resolve(strict=False)


def default_processor_gate_replay_drift_root(*, repo_root: Path | None = None) -> Path:
    base = (repo_root or REPO_ROOT).expanduser().resolve(strict=False)
    return (base / "snapshots" / "processor_gate_replay_drift").resolve(strict=False)


def latest_processor_gate_threshold_review_run(root: Path | None = None) -> Path | None:
    review_root = (root or DEFAULT_PROCESSOR_GATE_THRESHOLD_REVIEW_ROOT).expanduser().resolve(strict=False)
    if not review_root.exists() or not review_root.is_dir():
        return None

    candidates: list[tuple[float, str, Path]] = []
    for candidate in review_root.iterdir():
        if not candidate.is_dir():
            continue
        summary_path = candidate / "summary.json"
        if not summary_path.exists():
            continue
        try:
            mtime = summary_path.stat().st_mtime
        except OSError:
            continue
        candidates.append((mtime, candidate.name, candidate))

    if not candidates:
        return None
    return max(candidates, key=lambda item: (item[0], item[1]))[2]


def load_processor_gate_threshold_review_summary(path_or_dir: Path) -> dict[str, Any]:
    candidate = path_or_dir.expanduser().resolve(strict=False)
    summary_path = candidate / "summary.json" if candidate.is_dir() else candidate
    payload = json.loads(summary_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("processor gate threshold review summary must be a JSON object")
    return payload


def _optional_resolved_path(value: object) -> Path | None:
    text = str(value or "").strip()
    if not text:
        return None
    return Path(text).expanduser().resolve(strict=False)


def _load_threshold_replay_context(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _threshold_replay_compact_text(payload: Mapping[str, Any]) -> str | None:
    mode = str(payload.get("threshold_replay_mode") or "").strip()
    if not mode:
        return None

    parts = [f"mode={mode}"]
    high_threshold = _coerce_optional_float(payload.get("high_threshold"))
    low_threshold = _coerce_optional_float(payload.get("low_threshold"))
    reviewed_high_threshold = _coerce_optional_float(payload.get("reviewed_high_threshold"))
    proposal_run_id = str(payload.get("proposal_run_id") or "").strip()
    if high_threshold is not None:
        parts.append(f"high={high_threshold:.2f}")
    if low_threshold is not None:
        parts.append(f"low={low_threshold:.2f}")
    if reviewed_high_threshold is not None:
        parts.append(f"reviewed_high={reviewed_high_threshold:.2f}")
    if proposal_run_id:
        parts.append(f"proposal={proposal_run_id}")
    return ", ".join(parts)


def _load_json_mapping(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _dedupe_paths(paths: list[Path]) -> list[Path]:
    out: list[Path] = []
    seen: set[str] = set()
    for path in paths:
        resolved = path.expanduser().resolve(strict=False)
        key = str(resolved)
        if key in seen:
            continue
        seen.add(key)
        out.append(resolved)
    return out


def _candidate_validation_replay_dirs(
    *,
    summary: Mapping[str, Any],
    validation_run_id: str,
    threshold_replay_path: Path | None,
    replay_root: Path | None,
) -> list[Path]:
    preferred: list[Path] = []
    fallback: list[Path] = []
    if threshold_replay_path is not None:
        parent = threshold_replay_path.parent
        if parent.name == validation_run_id:
            preferred.append(parent)
        else:
            fallback.append(parent)

    inputs = summary.get("inputs") if isinstance(summary.get("inputs"), Mapping) else {}
    for key in ("drift_summary_path", "drift_details_path"):
        candidate = _optional_resolved_path(inputs.get(key))
        if candidate is None:
            continue
        if candidate.parent.name == validation_run_id:
            preferred.append(candidate.parent)
        if candidate.parent.parent != candidate.parent:
            preferred.append(candidate.parent.parent / validation_run_id)

    preferred.append((replay_root or DEFAULT_PROCESSOR_GATE_REPLAY_DRIFT_ROOT) / validation_run_id)
    return _dedupe_paths(preferred + fallback)


def _resolve_threshold_change_validation_replay_state(
    *,
    summary: Mapping[str, Any],
    proposal_path: Path | None,
    threshold_replay_path: Path | None,
    threshold_replay_context: Mapping[str, Any],
    replay_root: Path | None,
) -> dict[str, object]:
    state: dict[str, object] = {
        "threshold_change_validation_replay_run_id": None,
        "threshold_change_validation_replay_available": False,
        "threshold_change_validation_replay_matches_proposal": False,
        "threshold_change_validation_replay_needs_rerun": False,
        "threshold_change_validation_replay_status": "not_applicable",
    }
    if proposal_path is None or not proposal_path.exists():
        return state

    try:
        proposal = _load_json_mapping(proposal_path)
    except Exception:
        state.update(
            {
                "threshold_change_validation_replay_needs_rerun": True,
                "threshold_change_validation_replay_status": "proposal_unreadable",
            }
        )
        return state

    validation_run_id = str(proposal.get("validation_replay_run_id") or "").strip()
    proposal_run_id = str(proposal.get("run_id") or "").strip()
    state["threshold_change_validation_replay_run_id"] = validation_run_id or None
    if not validation_run_id:
        state.update(
            {
                "threshold_change_validation_replay_needs_rerun": True,
                "threshold_change_validation_replay_status": "missing_validation_run_id",
            }
        )
        return state

    selected_run_dir: Path | None = None
    selected_replay_path: Path | None = None
    selected_context: Mapping[str, Any] = {}
    for run_dir in _candidate_validation_replay_dirs(
        summary=summary,
        validation_run_id=validation_run_id,
        threshold_replay_path=threshold_replay_path,
        replay_root=replay_root,
    ):
        candidate_replay_path = run_dir / "threshold_replay.json"
        if not candidate_replay_path.exists():
            continue
        selected_run_dir = run_dir
        selected_replay_path = candidate_replay_path
        selected_context = (
            threshold_replay_context
            if threshold_replay_path is not None
            and candidate_replay_path.resolve(strict=False) == threshold_replay_path.resolve(strict=False)
            else _load_threshold_replay_context(candidate_replay_path)
        )
        break

    if selected_replay_path is None:
        state.update(
            {
                "threshold_change_validation_replay_needs_rerun": True,
                "threshold_change_validation_replay_status": "missing_validation_replay",
            }
        )
        return state

    state["threshold_change_validation_replay_available"] = True
    if not selected_context:
        state.update(
            {
                "threshold_change_validation_replay_needs_rerun": True,
                "threshold_change_validation_replay_status": "missing_threshold_replay_context",
            }
        )
        return state

    replay_mode = str(selected_context.get("threshold_replay_mode") or "").strip()
    replay_proposal_run_id = str(selected_context.get("proposal_run_id") or "").strip()
    run_id_matches = selected_run_dir is not None and selected_run_dir.name == validation_run_id
    proposal_matches = bool(proposal_run_id and replay_proposal_run_id == proposal_run_id)
    mode_matches = replay_mode == "threshold_change_proposal_replay"
    matches = bool(run_id_matches and proposal_matches and mode_matches)
    status = "matched"
    if not run_id_matches:
        status = "mismatched_validation_run_id"
    elif not mode_matches:
        status = "mismatched_replay_mode"
    elif not proposal_matches:
        status = "mismatched_proposal"

    state.update(
        {
            "threshold_change_validation_replay_matches_proposal": matches,
            "threshold_change_validation_replay_needs_rerun": not matches,
            "threshold_change_validation_replay_status": status,
        }
    )
    return state


def _derive_threshold_change_manual_decision_state(
    validation_replay_state: Mapping[str, object],
) -> dict[str, object]:
    validation_status = str(
        validation_replay_state.get("threshold_change_validation_replay_status") or ""
    ).strip()
    if not validation_status or validation_status == "not_applicable":
        return {
            "threshold_change_manual_decision_ready": False,
            "threshold_change_manual_decision_status": "not_applicable",
            "threshold_change_manual_decision_blocker": None,
        }

    if bool(validation_replay_state.get("threshold_change_validation_replay_matches_proposal")):
        return {
            "threshold_change_manual_decision_ready": True,
            "threshold_change_manual_decision_status": "ready",
            "threshold_change_manual_decision_blocker": None,
        }

    return {
        "threshold_change_manual_decision_ready": False,
        "threshold_change_manual_decision_status": "blocked_validation_replay",
        "threshold_change_manual_decision_blocker": validation_status,
    }


def resolve_processor_gate_threshold_review_drift_artifacts(
    summary: Mapping[str, Any],
    *,
    threshold_change_proposal_path: Path | None = None,
    replay_root: Path | None = None,
) -> dict[str, object]:
    inputs = summary.get("inputs") if isinstance(summary.get("inputs"), Mapping) else {}
    drift_summary_path = _optional_resolved_path(inputs.get("drift_summary_path"))
    drift_details_path = _optional_resolved_path(inputs.get("drift_details_path"))

    drift_markdown_path: Path | None = None
    threshold_replay_path: Path | None = None
    threshold_replay_markdown_path: Path | None = None
    for candidate in (drift_summary_path, drift_details_path):
        if candidate is None:
            continue
        sibling_markdown = candidate.with_name("audit.md")
        if sibling_markdown.exists():
            drift_markdown_path = sibling_markdown
            break
    for candidate in (drift_summary_path, drift_details_path):
        if candidate is None:
            continue
        sibling_threshold_replay = candidate.with_name("threshold_replay.json")
        sibling_threshold_replay_markdown = candidate.with_name("threshold_replay.md")
        if sibling_threshold_replay.exists() or sibling_threshold_replay_markdown.exists():
            threshold_replay_path = sibling_threshold_replay
            threshold_replay_markdown_path = sibling_threshold_replay_markdown
            break
    threshold_replay_context = _load_threshold_replay_context(threshold_replay_path)
    threshold_replay_text = _threshold_replay_compact_text(threshold_replay_context)
    threshold_replay_review_command = (
        str(threshold_replay_context.get("threshold_review_command") or "").strip()
        or None
    )
    validation_replay_state = _resolve_threshold_change_validation_replay_state(
        summary=summary,
        proposal_path=threshold_change_proposal_path,
        threshold_replay_path=threshold_replay_path,
        threshold_replay_context=threshold_replay_context,
        replay_root=replay_root,
    )
    manual_decision_state = _derive_threshold_change_manual_decision_state(
        validation_replay_state
    )

    return {
        "drift_summary_path": str(drift_summary_path) if drift_summary_path is not None else None,
        "drift_details_path": str(drift_details_path) if drift_details_path is not None else None,
        "drift_markdown_path": str(drift_markdown_path) if drift_markdown_path is not None else None,
        "threshold_replay_path": str(threshold_replay_path) if threshold_replay_path is not None else None,
        "threshold_replay_markdown_path": (
            str(threshold_replay_markdown_path)
            if threshold_replay_markdown_path is not None
            else None
        ),
        "threshold_replay_text": threshold_replay_text,
        "threshold_replay_review_command": threshold_replay_review_command,
        "threshold_replay_mode": (
            str(threshold_replay_context.get("threshold_replay_mode") or "").strip()
            or None
        ),
        "threshold_replay_high_threshold": _coerce_optional_float(
            threshold_replay_context.get("high_threshold")
        ),
        "threshold_replay_low_threshold": _coerce_optional_float(
            threshold_replay_context.get("low_threshold")
        ),
        "threshold_replay_reviewed_high_threshold": _coerce_optional_float(
            threshold_replay_context.get("reviewed_high_threshold")
        ),
        "threshold_replay_proposal_run_id": (
            str(threshold_replay_context.get("proposal_run_id") or "").strip()
            or None
        ),
        "drift_summary_available": bool(drift_summary_path is not None and drift_summary_path.exists()),
        "drift_details_available": bool(drift_details_path is not None and drift_details_path.exists()),
        "drift_markdown_available": bool(drift_markdown_path is not None and drift_markdown_path.exists()),
        "threshold_replay_available": bool(
            threshold_replay_path is not None and threshold_replay_path.exists()
        ),
        "threshold_replay_markdown_available": bool(
            threshold_replay_markdown_path is not None
            and threshold_replay_markdown_path.exists()
        ),
        **validation_replay_state,
        **manual_decision_state,
    }


def build_processor_gate_threshold_review_viewer_command(
    run_root: Path,
    *,
    repo_root: Path | None = None,
    python_executable: Path | None = None,
) -> str:
    resolved_repo_root = (repo_root or REPO_ROOT).resolve()
    if os.name == "nt":
        venv_cli = resolved_repo_root / ".venv" / "Scripts" / "paperpipe.exe"
        venv_python = resolved_repo_root / ".venv" / "Scripts" / "python.exe"
    else:
        venv_cli = resolved_repo_root / ".venv" / "bin" / "paperpipe"
        venv_python = resolved_repo_root / ".venv" / "bin" / "python"

    if venv_cli.exists():
        return (
            f"{shlex.quote(str(venv_cli))} "
            f"show-processor-gate-threshold-review {shlex.quote(str(run_root))}"
        )

    interpreter = venv_python if venv_python.exists() else Path(python_executable or sys.executable)
    return (
        f"PYTHONPATH={shlex.quote(str(resolved_repo_root))} "
        f"{shlex.quote(str(interpreter))} "
        f"-m src.cli show-processor-gate-threshold-review {shlex.quote(str(run_root))}"
    )


def render_processor_gate_threshold_review_markdown(
    summary: Mapping[str, Any],
    *,
    run_root: Path | None = None,
) -> str:
    inputs = summary.get("inputs") if isinstance(summary.get("inputs"), Mapping) else {}
    decision = summary.get("decision") if isinstance(summary.get("decision"), Mapping) else {}
    signal_summary = (
        summary.get("signal_summary") if isinstance(summary.get("signal_summary"), Mapping) else {}
    )
    manual_review_scope = (
        summary.get("manual_review_scope") if isinstance(summary.get("manual_review_scope"), Mapping) else {}
    )
    manual_review_basis = (
        summary.get("manual_review_basis") if isinstance(summary.get("manual_review_basis"), Mapping) else {}
    )
    recommendations = (
        [str(item).strip() for item in summary.get("recommendations", []) if str(item).strip()]
        if isinstance(summary.get("recommendations"), list)
        else []
    )
    threshold_change_proposal_path = (
        run_root / "threshold_change_proposal.json" if run_root is not None else None
    )
    drift_artifacts = resolve_processor_gate_threshold_review_drift_artifacts(
        summary,
        threshold_change_proposal_path=threshold_change_proposal_path,
    )

    run_id = str(summary.get("run_id") or "-").strip() or "-"
    lines = [f"# Processor Gate Threshold Review: {run_id}", ""]
    generated_at = str(summary.get("generated_at") or "").strip()
    if generated_at:
        lines.append(f"- Generated At: {generated_at}")
    high_threshold = inputs.get("high_threshold")
    low_threshold = inputs.get("low_threshold")
    if high_threshold not in (None, ""):
        lines.append(f"- High Threshold: {high_threshold}")
    if low_threshold not in (None, ""):
        lines.append(f"- Low Threshold: {low_threshold}")
    min_candidate_rows = inputs.get("min_candidate_rows")
    if min_candidate_rows not in (None, ""):
        lines.append(f"- Minimum Candidate Rows: {int(min_candidate_rows)}")
    drift_warn_threshold = inputs.get("drift_warn_threshold")
    if drift_warn_threshold not in (None, ""):
        lines.append(f"- Drift Warn Threshold: {float(drift_warn_threshold):.1%}")
    if run_root is not None:
        lines.append(
            "- Viewer Command: "
            + build_processor_gate_threshold_review_viewer_command(run_root)
        )
        manual_review_rows_path = run_root / "manual_review_rows.json"
        manual_review_markdown_path = run_root / "manual_review.md"
        manual_review_checklist_path = run_root / "manual_review_checklist.csv"
        manual_review_seed_path = run_root / "manual_review_seed.csv"
        manual_review_frontier_path = run_root / "manual_review_frontier.csv"
        manual_review_frontier_notes_path = run_root / "manual_review_frontier_notes.md"
        manual_review_frontier_crosscheck_packet_path = run_root / "manual_review_frontier_crosscheck_packet.md"
        manual_review_frontier_claude_crosscheck_path = run_root / "manual_review_frontier_claude_crosscheck.md"
        manual_review_frontier_claude_crosscheck_json_path = run_root / "manual_review_frontier_claude_crosscheck.json"
        manual_review_basis_markdown_path = run_root / "manual_review_basis.md"
        manual_review_decision_markdown_path = run_root / "manual_review_decision.md"
        manual_review_outcome_path = run_root / "manual_review_outcome.json"
        manual_review_outcome_markdown_path = run_root / "manual_review_outcome.md"
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
        manual_override_policy_decision_markdown_path = run_root / "manual_override_policy_decision.md"
        indexed_pending_policy_decision_path = run_root / "indexed_pending_policy_decision.json"
        indexed_pending_policy_decision_markdown_path = run_root / "indexed_pending_policy_decision.md"
        fixture_or_test_policy_decision_path = run_root / "fixture_or_test_policy_decision.json"
        fixture_or_test_policy_decision_markdown_path = run_root / "fixture_or_test_policy_decision.md"
        threshold_change_proposal_path = run_root / "threshold_change_proposal.json"
        threshold_change_proposal_markdown_path = run_root / "threshold_change_proposal.md"
        if manual_review_rows_path.exists():
            lines.append(f"- Manual Review Rows: {manual_review_rows_path}")
        if manual_review_markdown_path.exists():
            lines.append(f"- Manual Review Markdown: {manual_review_markdown_path}")
        if manual_review_checklist_path.exists():
            lines.append(f"- Manual Review Checklist: {manual_review_checklist_path}")
        if manual_review_seed_path.exists():
            lines.append(f"- Manual Review Seed: {manual_review_seed_path}")
        if manual_review_frontier_path.exists():
            lines.append(f"- Manual Review Frontier: {manual_review_frontier_path}")
        if manual_review_frontier_notes_path.exists():
            lines.append(f"- Manual Review Frontier Notes: {manual_review_frontier_notes_path}")
        if manual_review_frontier_crosscheck_packet_path.exists():
            lines.append(f"- Manual Review Frontier Crosscheck Packet: {manual_review_frontier_crosscheck_packet_path}")
        if manual_review_frontier_claude_crosscheck_path.exists():
            lines.append(f"- Manual Review Frontier Claude Crosscheck: {manual_review_frontier_claude_crosscheck_path}")
        if manual_review_frontier_claude_crosscheck_json_path.exists():
            lines.append(f"- Manual Review Frontier Claude Crosscheck JSON: {manual_review_frontier_claude_crosscheck_json_path}")
        if manual_review_basis_markdown_path.exists():
            lines.append(f"- Manual Review Basis: {manual_review_basis_markdown_path}")
        if manual_review_decision_markdown_path.exists():
            lines.append(f"- Manual Review Decision: {manual_review_decision_markdown_path}")
        if manual_review_outcome_path.exists():
            lines.append(f"- Manual Review Outcome: {manual_review_outcome_path}")
        if manual_review_outcome_markdown_path.exists():
            lines.append(f"- Manual Review Outcome Markdown: {manual_review_outcome_markdown_path}")
        if threshold_change_decision_path.exists():
            lines.append(f"- Threshold Change Decision: {threshold_change_decision_path}")
        if threshold_change_decision_markdown_path.exists():
            lines.append(f"- Threshold Change Decision Markdown: {threshold_change_decision_markdown_path}")
        if mid_confidence_policy_decision_path.exists():
            lines.append(f"- Mid-Confidence Policy Decision: {mid_confidence_policy_decision_path}")
        if mid_confidence_policy_decision_markdown_path.exists():
            lines.append(
                f"- Mid-Confidence Policy Decision Markdown: {mid_confidence_policy_decision_markdown_path}"
            )
        if mid_confidence_policy_debt_reconciliation_path.exists():
            lines.append(
                f"- Mid-Confidence Policy Debt Reconciliation: {mid_confidence_policy_debt_reconciliation_path}"
            )
        if mid_confidence_policy_debt_reconciliation_markdown_path.exists():
            lines.append(
                "- Mid-Confidence Policy Debt Reconciliation Markdown: "
                f"{mid_confidence_policy_debt_reconciliation_markdown_path}"
            )
        if manual_override_policy_decision_path.exists():
            lines.append(
                f"- Manual Override Policy Decision: {manual_override_policy_decision_path}"
            )
        if manual_override_policy_decision_markdown_path.exists():
            lines.append(
                f"- Manual Override Policy Decision Markdown: {manual_override_policy_decision_markdown_path}"
            )
        if indexed_pending_policy_decision_path.exists():
            lines.append(
                f"- Indexed Pending Policy Decision: {indexed_pending_policy_decision_path}"
            )
        if indexed_pending_policy_decision_markdown_path.exists():
            lines.append(
                f"- Indexed Pending Policy Decision Markdown: {indexed_pending_policy_decision_markdown_path}"
            )
        if fixture_or_test_policy_decision_path.exists():
            lines.append(
                f"- Fixture/Test Policy Decision: {fixture_or_test_policy_decision_path}"
            )
        if fixture_or_test_policy_decision_markdown_path.exists():
            lines.append(
                f"- Fixture/Test Policy Decision Markdown: {fixture_or_test_policy_decision_markdown_path}"
            )
        if threshold_change_proposal_path.exists():
            lines.append(f"- Threshold Change Proposal: {threshold_change_proposal_path}")
        if threshold_change_proposal_markdown_path.exists():
            lines.append(
                f"- Threshold Change Proposal Markdown: {threshold_change_proposal_markdown_path}"
            )
    if drift_artifacts["drift_summary_path"]:
        lines.append(f"- Replay Drift Summary: {drift_artifacts['drift_summary_path']}")
    if drift_artifacts["drift_details_path"]:
        lines.append(f"- Replay Drift Details: {drift_artifacts['drift_details_path']}")
    if drift_artifacts["drift_markdown_path"]:
        lines.append(f"- Replay Drift Markdown: {drift_artifacts['drift_markdown_path']}")
    if drift_artifacts["threshold_replay_path"]:
        lines.append(f"- Threshold Replay Context: {drift_artifacts['threshold_replay_path']}")
    if drift_artifacts["threshold_replay_markdown_path"]:
        lines.append(
            f"- Threshold Replay Context Markdown: {drift_artifacts['threshold_replay_markdown_path']}"
        )
    if drift_artifacts["threshold_replay_text"]:
        lines.append(f"- Threshold Replay: {drift_artifacts['threshold_replay_text']}")
    if drift_artifacts["threshold_replay_review_command"]:
        lines.append(
            "- Threshold Replay Review Command: "
            f"{drift_artifacts['threshold_replay_review_command']}"
        )
    if drift_artifacts["threshold_change_validation_replay_status"] != "not_applicable":
        lines.append(
            "- Threshold Change Validation Replay: "
            f"status={drift_artifacts['threshold_change_validation_replay_status']}, "
            f"available={'yes' if drift_artifacts['threshold_change_validation_replay_available'] else 'no'}, "
            f"matches={'yes' if drift_artifacts['threshold_change_validation_replay_matches_proposal'] else 'no'}, "
            f"needs_rerun={'yes' if drift_artifacts['threshold_change_validation_replay_needs_rerun'] else 'no'}"
        )
    if drift_artifacts["threshold_change_manual_decision_status"] != "not_applicable":
        manual_decision_blocker = str(
            drift_artifacts.get("threshold_change_manual_decision_blocker") or ""
        ).strip()
        manual_decision_text = (
            "- Threshold Change Manual Decision: "
            f"ready={'yes' if drift_artifacts['threshold_change_manual_decision_ready'] else 'no'}, "
            f"status={drift_artifacts['threshold_change_manual_decision_status']}"
        )
        if manual_decision_blocker:
            manual_decision_text = f"{manual_decision_text}, blocker={manual_decision_blocker}"
        lines.append(manual_decision_text)
    lines.append("")

    lines.append("## Decision")
    lines.append(f"- Recommended Action: {str(decision.get('recommended_action') or '-').strip() or '-'}")
    lines.append(f"- Review Ready: {'yes' if bool(decision.get('review_ready')) else 'no'}")
    next_step = str(decision.get("next_step") or "").strip()
    if next_step:
        lines.append(f"- Next Step: {next_step}")
    latest_run_id = str(decision.get("latest_run_id") or "").strip()
    latest_run_status = str(decision.get("latest_run_status") or "").strip()
    if latest_run_id:
        latest_run_text = latest_run_id
        if latest_run_status:
            latest_run_text = f"{latest_run_text} ({latest_run_status})"
        lines.append(f"- Latest Drift Run: {latest_run_text}")
    focus_areas = (
        [str(item).strip() for item in decision.get("focus_areas", []) if str(item).strip()]
        if isinstance(decision.get("focus_areas"), list)
        else []
    )
    if focus_areas:
        lines.append(f"- Focus Areas: {', '.join(focus_areas)}")
    tuning_targets = (
        [str(item).strip() for item in decision.get("tuning_targets", []) if str(item).strip()]
        if isinstance(decision.get("tuning_targets"), list)
        else []
    )
    if tuning_targets:
        lines.append(f"- Tuning Targets: {', '.join(tuning_targets)}")
    tuning_actions = (
        [
            f"{str(item.get('target') or '').strip()}:{str(item.get('action') or '').strip()}"
            for item in decision.get("tuning_actions", [])
            if isinstance(item, Mapping)
            and str(item.get("target") or "").strip()
            and str(item.get("action") or "").strip()
        ]
        if isinstance(decision.get("tuning_actions"), list)
        else []
    )
    if tuning_actions:
        lines.append(f"- Tuning Actions: {' | '.join(tuning_actions)}")
    if "threshold_change_ready" in decision:
        lines.append(f"- Threshold Change Ready: {'yes' if bool(decision.get('threshold_change_ready')) else 'no'}")
    threshold_change_status = str(decision.get("threshold_change_status") or "").strip()
    if threshold_change_status:
        lines.append(f"- Threshold Change Status: {threshold_change_status}")
    threshold_change_next_step = str(decision.get("threshold_change_next_step") or "").strip()
    if threshold_change_next_step:
        lines.append(f"- Threshold Change Next Step: {threshold_change_next_step}")
    threshold_change_blocker = str(decision.get("threshold_change_blocker") or "").strip()
    if threshold_change_blocker:
        lines.append(f"- Threshold Change Blocker: {threshold_change_blocker}")
    decision_reason = str(decision.get("decision_reason") or "").strip()
    if decision_reason:
        lines.append(f"- Reason: {decision_reason}")
    lines.append("")

    action_plan = (
        [item for item in decision.get("action_plan", []) if isinstance(item, Mapping)]
        if isinstance(decision.get("action_plan"), list)
        else []
    )
    if action_plan:
        lines.append("## Action Plan")
        for item in action_plan:
            order = int(item.get("order") or 0)
            action = str(item.get("action") or "").strip()
            if order <= 0 or not action:
                continue
            target = str(item.get("target") or "").strip()
            summary_text = str(item.get("summary") or "").strip()
            label = f"{order}. {action}"
            if target:
                label = f"{label} -> {target}"
            if bool(item.get("blocking")):
                label = f"{label} [blocking]"
            lines.append(f"- {label}")
            if summary_text:
                lines.append(f"  - {summary_text}")
        lines.append("")

    lines.append("## Coverage")
    candidate_count = signal_summary.get("candidate_count")
    promotable_count = signal_summary.get("promotable_count")
    drift_count = signal_summary.get("drift_count")
    drift_rate = signal_summary.get("drift_rate")
    if candidate_count not in (None, ""):
        lines.append(f"- Candidate Rows: {int(candidate_count)}")
    if promotable_count not in (None, ""):
        lines.append(f"- Promotable Rows: {int(promotable_count)}")
    if drift_count not in (None, ""):
        lines.append(f"- Drift Rows: {int(drift_count)}")
    if drift_rate not in (None, ""):
        lines.append(f"- Drift Rate: {float(drift_rate):.1%}")
    lines.append("")

    lines.append("## Manual Review Scope")
    threshold_relevant = (
        manual_review_scope.get("threshold_relevant")
        if isinstance(manual_review_scope.get("threshold_relevant"), Mapping)
        else {}
    )
    policy_edge_cases = (
        manual_review_scope.get("policy_edge_cases")
        if isinstance(manual_review_scope.get("policy_edge_cases"), Mapping)
        else {}
    )
    excluded = (
        manual_review_scope.get("excluded")
        if isinstance(manual_review_scope.get("excluded"), Mapping)
        else {}
    )
    worksheet_summary = (
        manual_review_scope.get("worksheet_summary")
        if isinstance(manual_review_scope.get("worksheet_summary"), Mapping)
        else {}
    )
    prefill_summary = (
        manual_review_scope.get("prefill_summary")
        if isinstance(manual_review_scope.get("prefill_summary"), Mapping)
        else {}
    )
    def _sample_ids_preview(bucket: Mapping[str, Any] | dict[str, Any]) -> str:
        paper_ids = (
            [str(item).strip() for item in bucket.get("paper_ids", []) if str(item).strip()]
            if isinstance(bucket.get("paper_ids"), list)
            else []
        )
        if not paper_ids:
            return ""
        preview = ", ".join(paper_ids[:3])
        if len(paper_ids) > 3:
            preview += f" (+{len(paper_ids) - 3} more)"
        return preview

    lines.append(f"- Threshold Relevant: {int(threshold_relevant.get('count') or 0)}")
    threshold_relevant_preview = _sample_ids_preview(threshold_relevant)
    if threshold_relevant_preview:
        lines.append(f"  - Sample IDs: {threshold_relevant_preview}")
    lines.append(f"- Policy Edge Cases: {int(policy_edge_cases.get('count') or 0)}")
    policy_edge_preview = _sample_ids_preview(policy_edge_cases)
    if policy_edge_preview:
        lines.append(f"  - Sample IDs: {policy_edge_preview}")
    for label in ("manual_override", "indexed_pending", "fixture_or_test", "other"):
        bucket = excluded.get(label) if isinstance(excluded.get(label), Mapping) else {}
        lines.append(f"- Excluded {label}: {int(bucket.get('count') or 0)}")
        bucket_preview = _sample_ids_preview(bucket)
        if bucket_preview:
            lines.append(f"  - Sample IDs: {bucket_preview}")
    focus_recommendation = str(manual_review_scope.get("focus_recommendation") or "").strip()
    if focus_recommendation:
        lines.append(f"- Review Basis: {focus_recommendation}")
    worksheet_target = str(worksheet_summary.get("primary_review_target") or "").strip()
    worksheet_text = str(worksheet_summary.get("summary") or "").strip()
    if worksheet_target:
        lines.append(f"- Worksheet Target: {worksheet_target}")
    if worksheet_text:
        lines.append(f"- Worksheet: {worksheet_text}")
    prefill_text = str(prefill_summary.get("summary") or "").strip()
    if prefill_text:
        lines.append(f"- Prefill Summary: {prefill_text}")
    basis_call = str(manual_review_basis.get("preliminary_call") or "").strip()
    basis_summary = str(manual_review_basis.get("summary") or "").strip()
    if basis_call:
        lines.append(f"- Basis Call: {basis_call}")
    if basis_summary:
        lines.append(f"- Basis Summary: {basis_summary}")
    lines.append("")

    tuning_recommendations = (
        [str(item).strip() for item in decision.get("tuning_recommendations", []) if str(item).strip()]
        if isinstance(decision.get("tuning_recommendations"), list)
        else []
    )
    if tuning_recommendations:
        lines.append("## Tuning Recommendations")
        lines.extend(f"- {item}" for item in tuning_recommendations)
        lines.append("")

    if recommendations:
        lines.append("## Recommendations")
        lines.extend(f"- {item}" for item in recommendations)
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def build_processor_gate_replay_drift(
    *,
    rows: list[dict],
    plans: list,
    run_id: str,
    db_path: Path | None,
    paper_id_migration_plan_path: Path | None = None,
    precanonical_db_path: Path | None = None,
    feedback_log_path: Path | None = None,
    canonical_to_legacy_paper_id: dict[str, str] | None = None,
    precanonical_rows_by_paper_id: dict[str, dict] | None = None,
    feedback_log_summary_by_paper_id: dict[str, dict] | None = None,
    high_threshold: float,
    low_threshold: float,
) -> tuple[ProcessorGateReplayDriftSummary, ProcessorGateReplayDriftDetails]:
    rows_by_paper_id = {str(row.get("paper_id") or "").strip(): row for row in rows}
    documents = [
        _build_drift_document(
            plan=plan,
            row=rows_by_paper_id.get(plan.paper_id, {}),
            precanonical_paper_id=(canonical_to_legacy_paper_id or {}).get(plan.paper_id),
            precanonical_rows_by_paper_id=precanonical_rows_by_paper_id or {},
            feedback_log_summary_by_paper_id=feedback_log_summary_by_paper_id or {},
        )
        for plan in plans
    ]
    metrics = _build_metrics(documents)
    generated_at = datetime.now(timezone.utc)
    summary = ProcessorGateReplayDriftSummary(
        generated_at=generated_at,
        run_id=run_id,
        inputs=ProcessorGateReplayDriftInput(
            db_path=str(db_path) if db_path is not None else None,
            paper_id_migration_plan_path=(
                str(paper_id_migration_plan_path) if paper_id_migration_plan_path is not None else None
            ),
            precanonical_db_path=str(precanonical_db_path) if precanonical_db_path is not None else None,
            feedback_log_path=str(feedback_log_path) if feedback_log_path is not None else None,
            row_count=len(rows),
            high_threshold=high_threshold,
            low_threshold=low_threshold,
        ),
        metrics=metrics,
        documents_with_drift=[doc.paper_id for doc in documents if doc.eligible_for_apply is False],
    )
    details = ProcessorGateReplayDriftDetails(
        generated_at=generated_at,
        run_id=run_id,
        documents=documents,
    )
    return summary, details


def write_processor_gate_replay_drift(
    *,
    summary: ProcessorGateReplayDriftSummary,
    details: ProcessorGateReplayDriftDetails,
    out_dir: Path,
) -> Path:
    run_root = out_dir / summary.run_id
    atomic_write_text(run_root / "summary.json", summary.model_dump_json(indent=2))
    atomic_write_text(run_root / "details.json", details.model_dump_json(indent=2))
    atomic_write_text(
        run_root / "audit.md",
        render_processor_gate_replay_drift_markdown(summary=summary, details=details),
    )
    return run_root


def render_processor_gate_replay_drift_markdown(
    *,
    summary: ProcessorGateReplayDriftSummary,
    details: ProcessorGateReplayDriftDetails,
) -> str:
    metrics = summary.metrics
    lines = [
        f"# Processor Gate Replay Drift: {summary.run_id}",
        "",
        f"- Generated At: {summary.generated_at.isoformat()}",
        f"- Candidate Rows: {metrics.candidate_count}",
        f"- Promotable Rows: {metrics.promotable_count}",
        f"- Drift Rows: {metrics.drift_count}",
        f"- Drift Rate: {metrics.drift_rate:.4f}",
        "",
        "## Drift Counts",
        f"- Skip Reasons: {dict(metrics.skip_reason_counts)}",
        f"- Decision Transitions: {dict(metrics.decision_transition_counts)}",
        f"- Gate Reason Categories: {dict(metrics.gate_reason_category_counts)}",
        f"- Timestamp Relations: {dict(metrics.timestamp_relation_counts)}",
        f"- Probable Causes: {dict(metrics.probable_drift_cause_counts)}",
        f"- Historical Path Hints: {dict(metrics.historical_path_hint_counts)}",
        f"- Identity Migration Hints: {dict(metrics.identity_migration_hint_counts)}",
        f"- Feedback Import Hints: {dict(metrics.feedback_log_import_hint_counts)}",
        f"- Feedback Timestamp Relations: {dict(metrics.feedback_log_timestamp_relation_counts)}",
        f"- Feedback To Precanonical Update Relations: {dict(metrics.feedback_log_to_precanonical_update_relation_counts)}",
        f"- Local Provenance Hints: {dict(metrics.local_provenance_hint_counts)}",
        f"- Historical Rewrite Hints: {dict(metrics.historical_rewrite_hint_counts)}",
        f"- Exact Confidence Values: {dict(metrics.confidence_value_counts)}",
        f"- Confidence Bands: {dict(metrics.confidence_band_counts)}",
        f"- Evidence Sources: {dict(metrics.evidence_source_counts)}",
        "",
        "## Examples",
    ]
    for doc in [item for item in details.documents if item.eligible_for_apply is False][:10]:
        lines.append(
            f"- {doc.paper_id}: {doc.current_gate_decision or '-'} -> {doc.replay_gate_decision or '-'} "
            f"({doc.skip_reason or 'drift'}, cause={doc.probable_drift_cause or '-'}, "
            f"band={doc.confidence_band or '-'}, evidence={doc.evidence_source}, "
            f"legacy={doc.precanonical_paper_id or '-'}, migration={doc.identity_migration_hint or '-'}, "
            f"feedback={doc.feedback_log_import_hint or '-'}, local={doc.local_provenance_hint or '-'}, "
            f"rewrite={doc.historical_rewrite_hint or '-'})"
        )
    return "\n".join(lines) + "\n"


def _build_drift_document(
    *,
    plan,
    row: dict,
    precanonical_paper_id: str | None,
    precanonical_rows_by_paper_id: dict[str, dict],
    feedback_log_summary_by_paper_id: dict[str, dict],
) -> ProcessorGateReplayDriftDocument:
    payload = _parse_feedback_json(plan.original_feedback_json)
    confidence = _coerce_optional_float(payload.get("confidence", row.get("confidence")))
    evidence_source = _evidence_source(payload)
    soft_tags = payload.get("soft_tags")
    hard_tags = payload.get("hard_tags")
    current_gate_reason = str(row.get("gate_reason") or "").strip() or None
    created_at = _clean_optional_text(row.get("created_at"))
    updated_at = _clean_optional_text(row.get("updated_at"))
    precanonical_lookup_paper_id = _precanonical_lookup_paper_id(plan.paper_id, precanonical_paper_id)
    precanonical_row = precanonical_rows_by_paper_id.get(precanonical_lookup_paper_id or "", {})
    precanonical_created_at = _clean_optional_text(precanonical_row.get("created_at"))
    precanonical_updated_at = _clean_optional_text(precanonical_row.get("updated_at"))
    precanonical_status = _clean_optional_text(precanonical_row.get("status"))
    precanonical_gate_decision = _clean_optional_text(precanonical_row.get("gate_decision"))
    precanonical_gate_reason = _clean_optional_text(precanonical_row.get("gate_reason"))
    precanonical_gate_reason_category = _gate_reason_category(precanonical_gate_reason)
    precanonical_confidence = _coerce_optional_float(precanonical_row.get("confidence"))
    confidence_band = _confidence_band(confidence)
    current_gate_reason_category = _gate_reason_category(current_gate_reason)
    fixture_record = {
        "paper_id": row.get("paper_id", plan.paper_id),
        "title": row.get("title", plan.title),
        "pdf_path": row.get("pdf_path"),
    }
    is_test_fixture, fixture_classification_reason = classify_test_fixture_paper_record(fixture_record)
    feedback_log_paper_id = _feedback_log_lookup_paper_id(plan.paper_id, precanonical_paper_id)
    feedback_log_summary = feedback_log_summary_by_paper_id.get(feedback_log_paper_id or "", {})
    feedback_log_avg_confidence = _coerce_optional_float(feedback_log_summary.get("avg_confidence"))
    feedback_log_gate_decision_hint = _clean_optional_text(feedback_log_summary.get("gate_decision_hint"))
    feedback_log_timestamp = _clean_optional_text(feedback_log_summary.get("timestamp"))
    feedback_log_to_precanonical_update_relation = _feedback_log_timestamp_relation(
        feedback_log_timestamp=feedback_log_timestamp,
        created_at=precanonical_updated_at,
    )
    feedback_log_import_hint = _feedback_log_import_hint(
        feedback_log_paper_id=feedback_log_paper_id,
        feedback_log_avg_confidence=feedback_log_avg_confidence,
        feedback_log_gate_decision_hint=feedback_log_gate_decision_hint,
        current_gate_decision=plan.current_gate_decision or None,
        current_confidence=confidence,
    )
    return ProcessorGateReplayDriftDocument(
        paper_id=plan.paper_id,
        title=plan.title,
        precanonical_paper_id=precanonical_paper_id,
        precanonical_created_at=precanonical_created_at,
        precanonical_updated_at=precanonical_updated_at,
        precanonical_status=precanonical_status,
        precanonical_gate_decision=precanonical_gate_decision,
        precanonical_gate_reason=precanonical_gate_reason,
        precanonical_gate_reason_category=precanonical_gate_reason_category,
        precanonical_confidence=precanonical_confidence,
        identity_migration_hint=_identity_migration_hint(
            precanonical_paper_id=precanonical_paper_id,
            current_status=plan.current_status or None,
            current_gate_decision=plan.current_gate_decision or None,
            current_confidence=confidence,
            precanonical_status=precanonical_status,
            precanonical_gate_decision=precanonical_gate_decision,
            precanonical_confidence=precanonical_confidence,
        ),
        feedback_log_paper_id=feedback_log_paper_id,
        feedback_log_avg_confidence=feedback_log_avg_confidence,
        feedback_log_gate_decision_hint=feedback_log_gate_decision_hint,
        feedback_log_timestamp=feedback_log_timestamp,
        feedback_log_timestamp_relation=_feedback_log_timestamp_relation(
            feedback_log_timestamp=feedback_log_timestamp,
            created_at=created_at,
        ),
        feedback_log_to_precanonical_update_relation=feedback_log_to_precanonical_update_relation,
        feedback_log_import_hint=feedback_log_import_hint,
        fixture_classification_reason=fixture_classification_reason,
        local_provenance_hint=_local_provenance_hint(
            is_test_fixture=is_test_fixture,
            feedback_log_import_hint=feedback_log_import_hint,
            current_gate_reason=current_gate_reason,
            current_gate_reason_category=current_gate_reason_category,
            precanonical_gate_reason=precanonical_gate_reason,
            precanonical_gate_reason_category=precanonical_gate_reason_category,
        ),
        historical_rewrite_hint=_historical_rewrite_hint(
            is_test_fixture=is_test_fixture,
            feedback_log_import_hint=feedback_log_import_hint,
            feedback_log_to_precanonical_update_relation=feedback_log_to_precanonical_update_relation,
            precanonical_gate_reason_category=precanonical_gate_reason_category,
        ),
        current_status=plan.current_status or None,
        current_gate_decision=plan.current_gate_decision or None,
        current_gate_reason=current_gate_reason,
        current_gate_reason_category=current_gate_reason_category,
        current_producer=plan.current_producer or None,
        created_at=created_at,
        updated_at=updated_at,
        timestamp_relation=_timestamp_relation(created_at, updated_at),
        replay_status=plan.replay_status or None,
        replay_gate_decision=plan.replay_gate_decision or None,
        eligible_for_apply=bool(plan.eligible_for_apply),
        skip_reason=plan.skip_reason,
        probable_drift_cause=_probable_drift_cause(
            current_status=plan.current_status or None,
            current_gate_decision=plan.current_gate_decision or None,
            replay_gate_decision=plan.replay_gate_decision or None,
            gate_reason=current_gate_reason,
            confidence_band=confidence_band,
        ),
        historical_path_hint=_historical_path_hint(
            current_status=plan.current_status or None,
            current_gate_decision=plan.current_gate_decision or None,
            replay_gate_decision=plan.replay_gate_decision or None,
            gate_reason_category=current_gate_reason_category,
            confidence=confidence,
            confidence_band=confidence_band,
        ),
        confidence=confidence,
        confidence_band=confidence_band,
        has_evidence_text=evidence_source != "none",
        evidence_source=evidence_source,
        soft_tags_count=len(soft_tags) if isinstance(soft_tags, list) else 0,
        hard_tags_present=bool(isinstance(hard_tags, dict) and hard_tags),
    )


def _build_metrics(documents: list[ProcessorGateReplayDriftDocument]) -> ProcessorGateReplayDriftMetrics:
    candidate_count = len(documents)
    promotable_count = sum(1 for doc in documents if doc.eligible_for_apply)
    drift_docs = [doc for doc in documents if doc.eligible_for_apply is False]
    drift_count = len(drift_docs)
    skip_reason_counts = Counter(doc.skip_reason for doc in drift_docs if doc.skip_reason)
    current_gate_decision_counts = Counter(doc.current_gate_decision for doc in documents if doc.current_gate_decision)
    replay_gate_decision_counts = Counter(doc.replay_gate_decision for doc in documents if doc.replay_gate_decision)
    decision_transition_counts = Counter(
        f"{doc.current_gate_decision or 'UNKNOWN'}->{doc.replay_gate_decision or 'UNKNOWN'}"
        for doc in drift_docs
    )
    gate_reason_category_counts = Counter(doc.current_gate_reason_category for doc in drift_docs if doc.current_gate_reason_category)
    timestamp_relation_counts = Counter(doc.timestamp_relation for doc in drift_docs if doc.timestamp_relation)
    probable_drift_cause_counts = Counter(doc.probable_drift_cause for doc in drift_docs if doc.probable_drift_cause)
    historical_path_hint_counts = Counter(doc.historical_path_hint for doc in drift_docs if doc.historical_path_hint)
    identity_migration_hint_counts = Counter(doc.identity_migration_hint for doc in drift_docs if doc.identity_migration_hint)
    feedback_log_import_hint_counts = Counter(doc.feedback_log_import_hint for doc in drift_docs if doc.feedback_log_import_hint)
    feedback_log_timestamp_relation_counts = Counter(
        doc.feedback_log_timestamp_relation for doc in drift_docs if doc.feedback_log_timestamp_relation
    )
    feedback_log_to_precanonical_update_relation_counts = Counter(
        doc.feedback_log_to_precanonical_update_relation
        for doc in drift_docs
        if doc.feedback_log_to_precanonical_update_relation
    )
    local_provenance_hint_counts = Counter(doc.local_provenance_hint for doc in drift_docs if doc.local_provenance_hint)
    historical_rewrite_hint_counts = Counter(doc.historical_rewrite_hint for doc in drift_docs if doc.historical_rewrite_hint)
    confidence_value_counts = Counter(_format_confidence_value(doc.confidence) for doc in drift_docs if doc.confidence is not None)
    confidence_band_counts = Counter(doc.confidence_band for doc in drift_docs if doc.confidence_band)
    evidence_source_counts = Counter(doc.evidence_source for doc in drift_docs)
    return ProcessorGateReplayDriftMetrics(
        candidate_count=candidate_count,
        promotable_count=promotable_count,
        drift_count=drift_count,
        drift_rate=(float(drift_count) / float(candidate_count)) if candidate_count else 0.0,
        skip_reason_counts=dict(sorted(skip_reason_counts.items())),
        current_gate_decision_counts=dict(sorted(current_gate_decision_counts.items())),
        replay_gate_decision_counts=dict(sorted(replay_gate_decision_counts.items())),
        decision_transition_counts=dict(sorted(decision_transition_counts.items())),
        gate_reason_category_counts=dict(sorted(gate_reason_category_counts.items())),
        timestamp_relation_counts=dict(sorted(timestamp_relation_counts.items())),
        probable_drift_cause_counts=dict(sorted(probable_drift_cause_counts.items())),
        historical_path_hint_counts=dict(sorted(historical_path_hint_counts.items())),
        identity_migration_hint_counts=dict(sorted(identity_migration_hint_counts.items())),
        feedback_log_import_hint_counts=dict(sorted(feedback_log_import_hint_counts.items())),
        feedback_log_timestamp_relation_counts=dict(sorted(feedback_log_timestamp_relation_counts.items())),
        feedback_log_to_precanonical_update_relation_counts=dict(
            sorted(feedback_log_to_precanonical_update_relation_counts.items())
        ),
        local_provenance_hint_counts=dict(sorted(local_provenance_hint_counts.items())),
        historical_rewrite_hint_counts=dict(sorted(historical_rewrite_hint_counts.items())),
        confidence_value_counts=dict(sorted(confidence_value_counts.items())),
        confidence_band_counts=dict(sorted(confidence_band_counts.items())),
        evidence_source_counts=dict(sorted(evidence_source_counts.items())),
    )


def _parse_feedback_json(feedback_json: str | None) -> dict:
    if not feedback_json:
        return {}
    try:
        parsed = json.loads(feedback_json)
    except Exception:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _evidence_source(payload: dict) -> str:
    evidence_snippets = payload.get("evidence_snippets")
    if isinstance(evidence_snippets, list) and evidence_snippets:
        return "evidence_snippets"
    evidence_span = payload.get("evidence_span")
    if isinstance(evidence_span, str) and evidence_span.strip():
        return "evidence_span"
    return "none"


def _coerce_optional_float(value) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _clean_optional_text(value) -> str | None:
    text = str(value or "").strip()
    return text or None


def _confidence_band(confidence: float | None) -> str | None:
    if confidence is None:
        return None
    if confidence >= 0.9:
        return "high"
    if confidence < 0.7:
        return "low"
    return "mid"


def _format_confidence_value(confidence: float) -> str:
    return f"{confidence:.2f}".rstrip("0").rstrip(".")


def _gate_reason_category(gate_reason: str | None) -> str:
    reason_text = str(gate_reason or "").strip().lower()
    if not reason_text:
        return "none"
    if any(token in reason_text for token in ("manual", "human review", "gatekeeper")):
        return "manual_or_human"
    if reason_text.startswith("confidence"):
        return "confidence_threshold"
    if reason_text == "reconciled from feedback_json decision":
        return "reconciled_feedback"
    return "other_named_reason"


def _timestamp_relation(created_at: str | None, updated_at: str | None) -> str:
    if created_at and updated_at:
        if created_at == updated_at:
            return "created_updated_same"
        return "created_updated_differ"
    return "missing_created_or_updated"


def _probable_drift_cause(
    *,
    current_status: str | None,
    current_gate_decision: str | None,
    replay_gate_decision: str | None,
    gate_reason: str | None,
    confidence_band: str | None,
) -> str | None:
    normalized_status = str(current_status or "").strip().upper()
    normalized_current = str(current_gate_decision or "").strip().upper()
    normalized_replay = str(replay_gate_decision or "").strip().upper()
    reason_text = str(gate_reason or "").strip().lower()

    if (
        normalized_status == "INDEXED"
        and normalized_current == "PENDING_REVIEW"
        and normalized_replay == "PENDING_REVIEW"
    ):
        return "legacy_indexed_pending_review"
    if normalized_current == "PENDING_REVIEW" and normalized_replay == "APPROVED" and confidence_band == "high":
        return "legacy_high_confidence_pending"
    if normalized_current == "APPROVED" and normalized_replay == "PENDING_REVIEW":
        if any(token in reason_text for token in ("manual", "human review", "gatekeeper")):
            return "manual_or_human_override_mid_confidence"
        if confidence_band == "mid":
            return "legacy_mid_confidence_approval"
    return "unclassified_drift"


def _historical_path_hint(
    *,
    current_status: str | None,
    current_gate_decision: str | None,
    replay_gate_decision: str | None,
    gate_reason_category: str,
    confidence: float | None,
    confidence_band: str | None,
) -> str:
    normalized_status = str(current_status or "").strip().upper()
    normalized_current = str(current_gate_decision or "").strip().upper()
    normalized_replay = str(replay_gate_decision or "").strip().upper()

    if gate_reason_category == "manual_or_human":
        return "manual_or_human_gate_reason_present"
    if gate_reason_category == "confidence_threshold":
        return "explicit_confidence_gate_reason_present"
    if (
        normalized_status == "INDEXED"
        and normalized_current == "PENDING_REVIEW"
        and normalized_replay == "PENDING_REVIEW"
    ):
        return "legacy_pending_indexed_shape"
    if (
        normalized_status == "INDEXED"
        and normalized_current == "APPROVED"
        and normalized_replay == "PENDING_REVIEW"
        and gate_reason_category == "none"
        and confidence is not None
        and confidence > 0.8
        and confidence_band == "mid"
    ):
        return "matches_migrate_legacy_import_shape"
    return "no_direct_history_hint"


def _identity_migration_hint(
    *,
    precanonical_paper_id: str | None,
    current_status: str | None,
    current_gate_decision: str | None,
    current_confidence: float | None,
    precanonical_status: str | None,
    precanonical_gate_decision: str | None,
    precanonical_confidence: float | None,
) -> str | None:
    if not precanonical_paper_id:
        return None
    if not precanonical_status and not precanonical_gate_decision and precanonical_confidence is None:
        return "planned_canonical_migration_target"

    same_status = _normalized_text(precanonical_status) == _normalized_text(current_status)
    same_gate_decision = _normalized_text(precanonical_gate_decision) == _normalized_text(current_gate_decision)
    same_confidence = _float_matches(precanonical_confidence, current_confidence)
    if same_status and same_gate_decision and same_confidence:
        return "precanonical_row_matches_current_decision"
    return "precanonical_row_differs_from_current"


def _precanonical_lookup_paper_id(current_paper_id: str | None, precanonical_paper_id: str | None) -> str | None:
    legacy = _clean_optional_text(precanonical_paper_id)
    if legacy:
        return legacy
    current = _clean_optional_text(current_paper_id)
    if not current:
        return None
    if current.lower().startswith("zotero:"):
        return None
    return current


def _feedback_log_lookup_paper_id(current_paper_id: str | None, precanonical_paper_id: str | None) -> str | None:
    legacy = _clean_optional_text(precanonical_paper_id)
    if legacy:
        return legacy
    current = _clean_optional_text(current_paper_id)
    if not current:
        return None
    if current.lower().startswith("zotero:"):
        return current.split(":", 1)[1].strip() or None
    return current


def _feedback_log_import_hint(
    *,
    feedback_log_paper_id: str | None,
    feedback_log_avg_confidence: float | None,
    feedback_log_gate_decision_hint: str | None,
    current_gate_decision: str | None,
    current_confidence: float | None,
) -> str | None:
    if not feedback_log_paper_id:
        return None
    if feedback_log_avg_confidence is None or not feedback_log_gate_decision_hint:
        return "no_feedback_log_match"
    same_gate = _normalized_text(feedback_log_gate_decision_hint) == _normalized_text(current_gate_decision)
    same_confidence = _float_matches(feedback_log_avg_confidence, current_confidence)
    if same_gate and not same_confidence:
        return "feedback_import_gate_preserved_confidence_overwritten"
    if same_gate and same_confidence:
        return "feedback_import_gate_and_confidence_match"
    return "feedback_import_gate_mismatch"


def _feedback_log_timestamp_relation(
    *,
    feedback_log_timestamp: str | None,
    created_at: str | None,
) -> str | None:
    feedback_dt = _parse_optional_datetime(feedback_log_timestamp)
    created_dt = _parse_optional_datetime(created_at)
    if feedback_dt is None or created_dt is None:
        return None
    if feedback_dt <= created_dt:
        return "feedback_before_or_equal_created"
    return "feedback_after_created"


def _local_provenance_hint(
    *,
    is_test_fixture: bool,
    feedback_log_import_hint: str | None,
    current_gate_reason: str | None,
    current_gate_reason_category: str | None,
    precanonical_gate_reason: str | None,
    precanonical_gate_reason_category: str | None,
) -> str | None:
    if is_test_fixture:
        return "test_fixture_row"
    if feedback_log_import_hint != "no_feedback_log_match":
        return None
    if (
        precanonical_gate_reason_category in {"manual_or_human", "confidence_threshold"}
        and _normalized_text(precanonical_gate_reason) == _normalized_text(current_gate_reason)
    ):
        return "precanonical_explicit_gate_reason_preserved"
    if current_gate_reason_category in {"manual_or_human", "confidence_threshold"}:
        return "current_explicit_gate_reason_without_feedback_log"
    return None


def _historical_rewrite_hint(
    *,
    is_test_fixture: bool,
    feedback_log_import_hint: str | None,
    feedback_log_to_precanonical_update_relation: str | None,
    precanonical_gate_reason_category: str | None,
) -> str | None:
    if is_test_fixture:
        return None
    if feedback_log_import_hint != "feedback_import_gate_preserved_confidence_overwritten":
        return None
    if feedback_log_to_precanonical_update_relation != "feedback_before_or_equal_created":
        return None
    if precanonical_gate_reason_category != "none":
        return None
    return "post_feedback_precanonical_confidence_overwrite_candidate"


def _normalized_text(value: str | None) -> str:
    return str(value or "").strip().upper()


def _float_matches(left: float | None, right: float | None) -> bool:
    if left is None and right is None:
        return True
    if left is None or right is None:
        return False
    return abs(left - right) < 1e-9


def _parse_optional_datetime(value: str | None) -> datetime | None:
    text = _clean_optional_text(value)
    if not text:
        return None
    normalized = text.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        try:
            parsed = datetime.fromisoformat(normalized.replace(" ", "T", 1))
        except ValueError:
            return None
    if parsed.tzinfo is not None:
        return parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed
