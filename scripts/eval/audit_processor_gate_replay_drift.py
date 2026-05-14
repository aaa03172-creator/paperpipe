from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from pathlib import Path
from statistics import mean

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.config import load_config
from src.gates import GateEngine
from src.services.processor_gate_replay_drift import (
    build_processor_gate_replay_drift,
    write_processor_gate_replay_drift,
)
from scripts.replay_processor_gate_intake_logs import (
    build_processor_gate_replay_plan,
    select_backfill_intake_override_rows,
)


def _repo_local_threshold_review_hint() -> str:
    if os.name == "nt":
        return (
            r".venv\Scripts\python.exe scripts/eval/recommend_processor_gate_threshold_review.py "
            r"--drift-summary <summary_path> --run-id <review_run_id>"
        )
    return (
        ".venv/bin/python scripts/eval/recommend_processor_gate_threshold_review.py "
        "--drift-summary <summary_path> --run-id <review_run_id>"
    )


def _build_repo_local_threshold_review_command(*, summary_path: Path, run_id: str) -> str:
    review_run_id = f"{run_id}__threshold_review"
    if os.name == "nt":
        interpreter = ROOT / ".venv" / "Scripts" / "python.exe"
        if interpreter.exists():
            return (
                f'"{interpreter}" "{ROOT / "scripts" / "eval" / "recommend_processor_gate_threshold_review.py"}" '
                f'--drift-summary "{summary_path}" --run-id "{review_run_id}"'
            )
        return (
            f'python "{ROOT / "scripts" / "eval" / "recommend_processor_gate_threshold_review.py"}" '
            f'--drift-summary "{summary_path}" --run-id "{review_run_id}"'
        )
    interpreter = ROOT / ".venv" / "bin" / "python"
    if interpreter.exists():
        return (
            f"{interpreter} {ROOT / 'scripts' / 'eval' / 'recommend_processor_gate_threshold_review.py'} "
            f"--drift-summary {summary_path} --run-id {review_run_id}"
        )
    return (
        f"python3 {ROOT / 'scripts' / 'eval' / 'recommend_processor_gate_threshold_review.py'} "
        f"--drift-summary {summary_path} --run-id {review_run_id}"
    )


def _load_rows(db_path: Path) -> list[dict]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        return [dict(row) for row in conn.execute("SELECT * FROM papers ORDER BY paper_id").fetchall()]
    finally:
        conn.close()


def _load_canonical_to_legacy_paper_id(plan_path: Path | None) -> dict[str, str]:
    if plan_path is None or not plan_path.exists():
        return {}
    try:
        payload = json.loads(plan_path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    out: dict[str, str] = {}
    if not isinstance(payload, list):
        return out
    for item in payload:
        if not isinstance(item, dict):
            continue
        legacy = str(item.get("paper_id_current") or "").strip()
        canonical = str(item.get("paper_id_proposed") or "").strip()
        if legacy and canonical:
            out[canonical] = legacy
    return out


def _load_rows_by_paper_id(db_path: Path | None) -> dict[str, dict]:
    if db_path is None or not db_path.exists():
        return {}
    return {str(row.get("paper_id") or "").strip(): row for row in _load_rows(db_path)}


def _load_threshold_change_proposal(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("threshold change proposal must be a JSON object")
    if not bool(payload.get("proposal_ready")):
        raise ValueError("threshold change proposal is not marked proposal_ready=true")
    target_field = str(payload.get("target_field") or "").strip()
    if target_field != "confidence_thresholds.high":
        raise ValueError(
            "unsupported threshold change proposal target_field: "
            f"{target_field!r} (expected confidence_thresholds.high)"
        )
    return payload


def _coerce_threshold(value: object, *, label: str) -> float:
    try:
        threshold = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} must be a number between 0 and 1") from exc
    if threshold < 0.0 or threshold > 1.0:
        raise ValueError(f"{label} must be between 0 and 1")
    return threshold


def _resolve_thresholds_for_replay(
    *,
    config_high_threshold: float,
    config_low_threshold: float,
    high_threshold: float | None,
    low_threshold: float | None,
    threshold_change_proposal_path: Path | None,
    reviewed_high_threshold: float | None,
) -> tuple[float, float, dict[str, object]]:
    if threshold_change_proposal_path is not None:
        if high_threshold is not None:
            raise ValueError(
                "use --reviewed-high-threshold with --threshold-change-proposal; "
                "do not also pass --high-threshold"
            )
        if reviewed_high_threshold is None:
            raise ValueError("--reviewed-high-threshold is required with --threshold-change-proposal")

        proposal = _load_threshold_change_proposal(threshold_change_proposal_path)
        current_thresholds = (
            proposal.get("current_thresholds")
            if isinstance(proposal.get("current_thresholds"), dict)
            else {}
        )
        resolved_high = _coerce_threshold(reviewed_high_threshold, label="reviewed high threshold")
        resolved_low = _coerce_threshold(
            low_threshold
            if low_threshold is not None
            else current_thresholds.get("low", config_low_threshold),
            label="low threshold",
        )
        metadata = {
            "threshold_replay_mode": "threshold_change_proposal_replay",
            "threshold_change_proposal_path": str(threshold_change_proposal_path),
            "reviewed_high_threshold": resolved_high,
            "proposal_run_id": str(proposal.get("run_id") or "") or None,
        }
    else:
        if reviewed_high_threshold is not None:
            raise ValueError("--reviewed-high-threshold requires --threshold-change-proposal")
        resolved_high = _coerce_threshold(
            high_threshold if high_threshold is not None else config_high_threshold,
            label="high threshold",
        )
        resolved_low = _coerce_threshold(
            low_threshold if low_threshold is not None else config_low_threshold,
            label="low threshold",
        )
        metadata = {
            "threshold_replay_mode": (
                "threshold_override_replay"
                if high_threshold is not None or low_threshold is not None
                else "config_default_replay"
            ),
            "threshold_change_proposal_path": None,
            "reviewed_high_threshold": None,
            "proposal_run_id": None,
        }

    if resolved_high < resolved_low:
        raise ValueError("high threshold must be greater than or equal to low threshold")
    metadata.update(
        {
            "high_threshold": resolved_high,
            "low_threshold": resolved_low,
        }
    )
    return resolved_high, resolved_low, metadata


def _threshold_replay_artifacts_enabled(threshold_replay: dict[str, object]) -> bool:
    return str(threshold_replay.get("threshold_replay_mode") or "").strip() != "config_default_replay"


def _render_threshold_replay_markdown(
    threshold_replay: dict[str, object],
    *,
    threshold_review_command: str | None = None,
) -> str:
    proposal_path = str(threshold_replay.get("threshold_change_proposal_path") or "").strip()
    proposal_run_id = str(threshold_replay.get("proposal_run_id") or "").strip()
    reviewed_high = threshold_replay.get("reviewed_high_threshold")
    high_threshold = threshold_replay.get("high_threshold")
    low_threshold = threshold_replay.get("low_threshold")
    lines = [
        "# Processor Gate Threshold Replay Context",
        "",
        f"- Mode: {threshold_replay.get('threshold_replay_mode') or '-'}",
        f"- Effective High Threshold: {high_threshold if high_threshold is not None else '-'}",
        f"- Effective Low Threshold: {low_threshold if low_threshold is not None else '-'}",
    ]
    if reviewed_high is not None:
        lines.append(f"- Reviewed High Threshold: {reviewed_high}")
    if proposal_path:
        lines.append(f"- Threshold Change Proposal: {proposal_path}")
    if proposal_run_id:
        lines.append(f"- Proposal Run ID: {proposal_run_id}")
    lines.append(
        "- Operator Note: replay-only context; this artifact does not apply threshold changes."
    )
    if threshold_review_command:
        lines.extend(
            [
                "",
                "## Next Threshold Review Command",
                "",
                "```bash",
                threshold_review_command,
                "```",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def _write_threshold_replay_artifacts(
    *,
    run_root: Path,
    threshold_replay: dict[str, object],
    threshold_review_command: str | None = None,
) -> tuple[Path | None, Path | None]:
    if not _threshold_replay_artifacts_enabled(threshold_replay):
        return None, None

    json_path = run_root / "threshold_replay.json"
    markdown_path = run_root / "threshold_replay.md"
    artifact_payload = dict(threshold_replay)
    if threshold_review_command:
        artifact_payload.update(
            {
                "threshold_review_command": threshold_review_command,
                "threshold_review_next_step": (
                    "Run this command to review the validation replay summary before changing config."
                ),
            }
        )
    json_path.write_text(
        json.dumps(artifact_payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    replay_markdown = _render_threshold_replay_markdown(
        threshold_replay,
        threshold_review_command=threshold_review_command,
    )
    markdown_path.write_text(replay_markdown, encoding="utf-8")

    audit_path = run_root / "audit.md"
    if audit_path.exists():
        existing = audit_path.read_text(encoding="utf-8").rstrip()
        audit_path.write_text(f"{existing}\n\n{replay_markdown}", encoding="utf-8")

    return json_path, markdown_path


def _load_feedback_log_summary_by_paper_id(feedback_log_path: Path | None) -> dict[str, dict]:
    if feedback_log_path is None or not feedback_log_path.exists():
        return {}
    out: dict[str, dict] = {}
    for raw_line in feedback_log_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except Exception:
            continue
        paper_id = str(rec.get("paper_id") or "").strip()
        if not paper_id:
            continue
        user_correction = str(rec.get("user_correction") or "")
        cleaned = user_correction.split("\n", 1)[1] if "\n" in user_correction else user_correction
        avg_confidence = None
        try:
            payload = json.loads(cleaned)
            claims = payload.get("claims", [])
            if isinstance(claims, list) and claims:
                confidence_values = [float(item.get("confidence", 0.0) or 0.0) for item in claims if isinstance(item, dict)]
                if confidence_values:
                    avg_confidence = round(mean(confidence_values), 2)
        except Exception:
            avg_confidence = None
        if avg_confidence is None:
            avg_confidence = 0.8
        out[paper_id] = {
            "avg_confidence": avg_confidence,
            "gate_decision_hint": "APPROVED" if avg_confidence > 0.8 else "PENDING_REVIEW",
            "timestamp": str(rec.get("timestamp") or "").strip() or None,
        }
    return out


def run_audit(
    *,
    db_path: Path,
    out_dir: Path,
    run_id: str,
    paper_id_migration_plan_path: Path | None = None,
    precanonical_db_path: Path | None = None,
    feedback_log_path: Path | None = None,
    high_threshold: float | None = None,
    low_threshold: float | None = None,
) -> Path:
    rows = _load_rows(db_path)
    canonical_to_legacy_paper_id = _load_canonical_to_legacy_paper_id(paper_id_migration_plan_path)
    precanonical_rows_by_paper_id = _load_rows_by_paper_id(precanonical_db_path)
    feedback_log_summary_by_paper_id = _load_feedback_log_summary_by_paper_id(feedback_log_path)
    conn = sqlite3.connect(db_path)
    try:
        config = load_config()
        gate_engine = GateEngine(
            high_threshold=(
                high_threshold
                if high_threshold is not None
                else config.confidence_thresholds.high
            ),
            low_threshold=(
                low_threshold
                if low_threshold is not None
                else config.confidence_thresholds.low
            ),
        )
        candidate_rows = select_backfill_intake_override_rows(conn)
        plans = build_processor_gate_replay_plan(candidate_rows, gate_engine=gate_engine)
    finally:
        conn.close()

    summary, details = build_processor_gate_replay_drift(
        rows=candidate_rows,
        plans=plans,
        run_id=run_id,
        db_path=db_path,
        paper_id_migration_plan_path=paper_id_migration_plan_path,
        precanonical_db_path=precanonical_db_path,
        feedback_log_path=feedback_log_path,
        canonical_to_legacy_paper_id=canonical_to_legacy_paper_id,
        precanonical_rows_by_paper_id=precanonical_rows_by_paper_id,
        feedback_log_summary_by_paper_id=feedback_log_summary_by_paper_id,
        high_threshold=gate_engine.high_threshold,
        low_threshold=gate_engine.low_threshold,
    )
    return write_processor_gate_replay_drift(summary=summary, details=details, out_dir=out_dir)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Audit residual drift between historical backfill-owned rows and the current processor gate helper.",
        epilog=(
            "Writes summary.json, details.json, and audit.md into the run directory. "
            "For the next bounded review step, run: "
            f"{_repo_local_threshold_review_hint()}"
        ),
    )
    parser.add_argument("--db-path", default="storage/state.db", help="SQLite DB path (default: storage/state.db)")
    parser.add_argument(
        "--out-dir",
        default=str(ROOT / "snapshots" / "processor_gate_replay_drift"),
        help="Output directory for audit artifacts.",
    )
    parser.add_argument(
        "--paper-id-migration-plan",
        default="storage/paper_id_migration_plan.json",
        help="Optional JSON plan mapping legacy paper_ids to canonical paper_ids.",
    )
    parser.add_argument(
        "--precanonical-db-path",
        default="storage/state.db.bak.zotero_policy.20260223_125245",
        help="Optional SQLite DB captured before canonical zotero-key migration.",
    )
    parser.add_argument(
        "--feedback-log-path",
        default="storage/feedback.jsonl",
        help="Optional legacy feedback log used to infer pre-backfill gate decisions.",
    )
    parser.add_argument("--run-id", required=True, help="Audit run identifier.")
    parser.add_argument(
        "--high-threshold",
        type=float,
        default=None,
        help="Optional high-threshold override for a replay-only audit. Does not edit config.",
    )
    parser.add_argument(
        "--low-threshold",
        type=float,
        default=None,
        help="Optional low-threshold override for a replay-only audit. Does not edit config.",
    )
    parser.add_argument(
        "--threshold-change-proposal",
        type=Path,
        default=None,
        help="Optional threshold_change_proposal.json to validate before replaying a reviewed high threshold.",
    )
    parser.add_argument(
        "--reviewed-high-threshold",
        type=float,
        default=None,
        help="Reviewed high threshold to replay when --threshold-change-proposal is provided.",
    )
    args = parser.parse_args()

    config = load_config()
    proposal_path = (
        args.threshold_change_proposal.expanduser().resolve(strict=False)
        if args.threshold_change_proposal is not None
        else None
    )
    high_threshold, low_threshold, threshold_replay = _resolve_thresholds_for_replay(
        config_high_threshold=config.confidence_thresholds.high,
        config_low_threshold=config.confidence_thresholds.low,
        high_threshold=args.high_threshold,
        low_threshold=args.low_threshold,
        threshold_change_proposal_path=proposal_path,
        reviewed_high_threshold=args.reviewed_high_threshold,
    )
    run_root = run_audit(
        db_path=Path(args.db_path).expanduser(),
        out_dir=Path(args.out_dir).expanduser(),
        run_id=args.run_id,
        paper_id_migration_plan_path=Path(args.paper_id_migration_plan).expanduser(),
        precanonical_db_path=Path(args.precanonical_db_path).expanduser(),
        feedback_log_path=Path(args.feedback_log_path).expanduser(),
        high_threshold=high_threshold,
        low_threshold=low_threshold,
    )
    summary_path = run_root / "summary.json"
    threshold_review_command = _build_repo_local_threshold_review_command(
        summary_path=summary_path,
        run_id=args.run_id,
    )
    threshold_replay_path, threshold_replay_markdown_path = _write_threshold_replay_artifacts(
        run_root=run_root,
        threshold_replay=threshold_replay,
        threshold_review_command=threshold_review_command,
    )
    payload = {
        "run_root": str(run_root),
        "summary_path": str(summary_path),
        "details_path": str(run_root / "details.json"),
        "markdown_path": str(run_root / "audit.md"),
        "threshold_replay": threshold_replay,
        "threshold_replay_path": (
            str(threshold_replay_path) if threshold_replay_path is not None else None
        ),
        "threshold_replay_markdown_path": (
            str(threshold_replay_markdown_path)
            if threshold_replay_markdown_path is not None
            else None
        ),
        "threshold_review_command": threshold_review_command,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
