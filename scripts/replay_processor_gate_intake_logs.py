from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.config import load_config
from src.gates import GateEngine
from src.processor import STATE_APPROVED, STATE_INDEXED, build_gate_persistence_outcome


@dataclass(frozen=True)
class ProcessorGateReplayPlan:
    paper_id: str
    title: str
    current_status: str
    current_gate_decision: str
    current_producer: str
    replay_status: str
    replay_gate_decision: str
    original_feedback_json: str
    replay_feedback_json: str
    eligible_for_apply: bool
    skip_reason: str | None = None


def _load_paper_rows(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    conn.row_factory = sqlite3.Row
    return [dict(row) for row in conn.execute("SELECT * FROM papers ORDER BY paper_id").fetchall()]


def _extract_current_producer(row: dict[str, Any]) -> str | None:
    feedback_json = row.get("feedback_json")
    if feedback_json in (None, ""):
        return None
    try:
        payload = json.loads(str(feedback_json))
    except Exception:
        return None
    if not isinstance(payload, dict):
        return None
    intake_override_log = payload.get("intake_override_log")
    if not isinstance(intake_override_log, dict):
        return None
    producer = intake_override_log.get("producer")
    text = str(producer or "").strip()
    return text or None


def select_backfill_intake_override_rows(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = _load_paper_rows(conn)
    return [row for row in rows if _extract_current_producer(row) == "backfill_analysis"]


def _replay_status_matches(*, current_status: str, replay_status: str) -> bool:
    normalized_current = current_status.strip().upper()
    normalized_replay = replay_status.strip().upper()
    if normalized_current == STATE_INDEXED:
        return normalized_replay == STATE_APPROVED
    return normalized_current == normalized_replay


def build_processor_gate_replay_plan(
    rows: list[dict[str, Any]],
    *,
    gate_engine: GateEngine,
) -> list[ProcessorGateReplayPlan]:
    plans: list[ProcessorGateReplayPlan] = []
    for row in rows:
        outcome = build_gate_persistence_outcome(
            row,
            gate_engine=gate_engine,
            llm_provider=None,
            producer="processor_gate",
            allow_escalation=False,
        )
        current_status = str(row.get("status") or "").strip()
        current_gate_decision = str(row.get("gate_decision") or "").strip().upper()
        replay_status = str(outcome.status or "").strip().upper()
        replay_gate_decision = str(outcome.updates.get("gate_decision") or "").strip().upper()

        skip_reason: str | None = None
        if current_gate_decision and current_gate_decision != replay_gate_decision:
            skip_reason = "gate_decision_mismatch"
        elif not _replay_status_matches(current_status=current_status, replay_status=replay_status):
            skip_reason = "status_mismatch"

        plans.append(
            ProcessorGateReplayPlan(
                paper_id=str(row.get("paper_id") or "").strip(),
                title=str(row.get("title") or "").strip(),
                current_status=current_status,
                current_gate_decision=current_gate_decision,
                current_producer="backfill_analysis",
                replay_status=replay_status,
                replay_gate_decision=replay_gate_decision,
                original_feedback_json=str(row.get("feedback_json") or ""),
                replay_feedback_json=str(outcome.updates["feedback_json"]),
                eligible_for_apply=skip_reason is None,
                skip_reason=skip_reason,
            )
        )
    return plans


def apply_processor_gate_replay(conn: sqlite3.Connection, plans: list[ProcessorGateReplayPlan]) -> int:
    eligible_plans = [plan for plan in plans if plan.eligible_for_apply]
    if not eligible_plans:
        return 0

    conn.execute("BEGIN IMMEDIATE")
    try:
        updated = 0
        for plan in eligible_plans:
            cursor = conn.execute(
                """
                UPDATE papers
                SET feedback_json = ?, updated_at = ?
                WHERE paper_id = ?
                  AND feedback_json = ?
                """,
                (
                    plan.replay_feedback_json,
                    datetime.now().isoformat(timespec="seconds"),
                    plan.paper_id,
                    plan.original_feedback_json,
                ),
            )
            updated += int(cursor.rowcount or 0)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return updated


def backup_db(db_path: Path, backup_path: Path) -> None:
    backup_path.parent.mkdir(parents=True, exist_ok=True)
    src = sqlite3.connect(db_path)
    dst = sqlite3.connect(backup_path)
    try:
        src.backup(dst)
    finally:
        src.close()
        dst.close()


def default_backup_path(db_path: Path) -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return db_path.parent / "backups" / f"{db_path.stem}_before_processor_gate_replay_{stamp}{db_path.suffix}"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Replay stable backfill intake logs through processor gate ownership. Dry-run by default."
    )
    parser.add_argument("--db", default="storage/state.db", help="SQLite DB path (default: storage/state.db)")
    parser.add_argument("--apply", action="store_true", help="Apply stable processor-gate replay. Default is dry-run.")
    parser.add_argument("--sample", type=int, default=20, help="Number of rows to print.")
    parser.add_argument("--max-count", type=int, default=0, help="Limit candidate rows (0 = all).")
    parser.add_argument("--backup-path", default="", help="Optional backup file path. Auto-generated if omitted.")
    args = parser.parse_args()

    db_path = Path(args.db).expanduser()
    if not db_path.exists():
        print(f"[REPLAY] db_not_found={db_path}")
        return 1

    config = load_config()
    gate_engine = GateEngine(
        high_threshold=config.confidence_thresholds.high,
        low_threshold=config.confidence_thresholds.low,
    )

    conn = sqlite3.connect(db_path)
    try:
        rows = select_backfill_intake_override_rows(conn)
        if args.max_count and args.max_count > 0:
            rows = rows[: args.max_count]

        plans = build_processor_gate_replay_plan(rows, gate_engine=gate_engine)
        promotable = [plan for plan in plans if plan.eligible_for_apply]
        skipped = [plan for plan in plans if not plan.eligible_for_apply]

        skip_reason_counts: dict[str, int] = {}
        for plan in skipped:
            reason = str(plan.skip_reason or "unknown")
            skip_reason_counts[reason] = skip_reason_counts.get(reason, 0) + 1

        print(f"[REPLAY] backfill_candidates={len(plans)}")
        print(f"[REPLAY] promotable_candidates={len(promotable)}")
        print(f"[REPLAY] skipped_candidates={len(skipped)}")
        if skip_reason_counts:
            print(f"[REPLAY] skipped_by_reason={skip_reason_counts}")

        for plan in promotable[: max(0, args.sample)]:
            print(
                f"  + {plan.paper_id} | {plan.current_status or '-'} -> {plan.replay_status or '-'} | "
                f"{plan.current_gate_decision or '-'} -> {plan.replay_gate_decision or '-'} | {plan.title or '-'}"
            )
        for plan in skipped[: max(0, args.sample)]:
            print(
                f"  - {plan.paper_id} | {plan.skip_reason or 'skipped'} | "
                f"{plan.current_status or '-'} -> {plan.replay_status or '-'} | "
                f"{plan.current_gate_decision or '-'} -> {plan.replay_gate_decision or '-'}"
            )

        if not args.apply:
            print("[REPLAY] dry-run only (no changes applied)")
            return 0

        backup_path = Path(args.backup_path).expanduser() if args.backup_path else default_backup_path(db_path)
        backup_db(db_path, backup_path)
        updated = apply_processor_gate_replay(conn, plans)
        print(f"[REPLAY] backup={backup_path}")
        print(f"[REPLAY] updated={updated}")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
