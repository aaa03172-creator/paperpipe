#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "storage" / "state.db"
ARTIFACTS_ROOT = ROOT / "storage" / "artifacts"


@dataclass
class RunMeasurement:
    run_id: str
    paper_id: str | None
    run_root: Path
    status: str | None
    started_at: str | None
    finished_at: str | None
    total_seconds: float | None
    pages: int | None
    chunk_count: int | None
    claim_count: int | None
    stats_checks: int | None
    run_verify: bool | None
    reader_timeout_budget_sec: int | None
    reader_attempt_count: int | None
    reader_return_mode: str | None
    reader_selected_attempt_label: str | None
    analysis_wall_seconds: float | None
    estimated_prompt_tokens: int | None
    estimated_response_tokens: int | None
    selected_context_mode: str | None
    selected_chunk_count: int | None
    selected_sentence_count: int | None
    selected_unique_section_count: int | None
    selected_truncated_chunk_count: int | None
    selected_generate_wall_seconds: float | None
    selected_parse_wall_seconds: float | None
    selected_attempt_wall_seconds: float | None
    selected_provider_request_wall_seconds: float | None
    selected_provider_done_reason: str | None
    selected_provider_prompt_eval_count: int | None
    selected_provider_eval_count: int | None
    selected_provider_total_duration_seconds: float | None
    attempts: list[dict[str, Any]]
    phase_seconds: dict[str, float]
    phase_messages: dict[str, list[str]]


def _parse_ts(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw)
    except Exception:
        return None


def _duration_seconds(start: str | None, end: str | None) -> float | None:
    start_dt = _parse_ts(start)
    end_dt = _parse_ts(end)
    if start_dt is None or end_dt is None:
        return None
    return round((end_dt - start_dt).total_seconds(), 3)


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def _find_run_root(run_id: str) -> Path | None:
    matches = list(ARTIFACTS_ROOT.glob(f"*/{run_id}"))
    if not matches:
        return None
    matches.sort()
    return matches[-1]


def _load_progress_events(conn: sqlite3.Connection, run_id: str) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT ts, event_type, message, payload_json
        FROM job_events
        WHERE run_id = ?
        ORDER BY ts ASC, rowid ASC
        """,
        (run_id,),
    ).fetchall()
    events: list[dict[str, Any]] = []
    for row in rows:
        payload: dict[str, Any] = {}
        raw_payload = row["payload_json"]
        if raw_payload:
            try:
                candidate = json.loads(raw_payload)
                if isinstance(candidate, dict):
                    payload = candidate
            except Exception:
                payload = {}
        stage = payload.get("stage")
        events.append(
            {
                "ts": row["ts"],
                "event_type": row["event_type"],
                "message": row["message"],
                "stage": stage if isinstance(stage, str) else None,
            }
        )
    return events


def _collect_phase_windows(events: list[dict[str, Any]]) -> tuple[dict[str, float], dict[str, list[str]]]:
    progress = [e for e in events if e.get("event_type") == "progress" and e.get("stage")]
    if not progress:
        return {}, {}

    stages: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for event in progress:
        stage = str(event["stage"])
        if current is None or current["stage"] != stage:
            current = {"stage": stage, "first_ts": event["ts"], "messages": [str(event.get("message") or "")]}
            stages.append(current)
        else:
            current["messages"].append(str(event.get("message") or ""))

    phase_seconds: dict[str, float] = {}
    phase_messages: dict[str, list[str]] = {}
    for idx, stage in enumerate(stages):
        name = str(stage["stage"])
        next_stage = stages[idx + 1] if idx + 1 < len(stages) else None
        end_ts = next_stage["first_ts"] if next_stage is not None else progress[-1]["ts"]
        duration = _duration_seconds(stage["first_ts"], end_ts)
        if duration is not None:
            phase_seconds[name] = round(phase_seconds.get(name, 0.0) + duration, 3)
        phase_messages.setdefault(name, []).extend(list(stage["messages"]))
    return phase_seconds, phase_messages


def measure_run(run_id: str) -> RunMeasurement:
    run_root = _find_run_root(run_id)
    if run_root is None:
        raise FileNotFoundError(f"run root not found for {run_id}")

    run_meta = _load_json(run_root / "run_meta.json")
    document_artifact = _load_json(run_root / "document_artifact.json")
    index_artifact = _load_json(run_root / "index_artifact.json")
    claimset = _load_json(run_root / "claimset.resolved.json") or _load_json(run_root / "claimset.json")
    stats_report = _load_json(run_root / "stats_report.json")

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        events = _load_progress_events(conn, run_id)
        params_row = conn.execute(
            "SELECT params_json FROM execution_runs WHERE run_id = ? LIMIT 1",
            (run_id,),
        ).fetchone()
    finally:
        conn.close()

    params: dict[str, Any] = {}
    if params_row and params_row["params_json"]:
        try:
            candidate = json.loads(params_row["params_json"])
            if isinstance(candidate, dict):
                params = candidate
        except Exception:
            params = {}

    phase_seconds, phase_messages = _collect_phase_windows(events)
    paper_id = str(run_meta.get("paper_id") or run_root.parent.name or "")
    reader_analysis = run_meta.get("reader_analysis") if isinstance(run_meta.get("reader_analysis"), dict) else {}
    attempts = reader_analysis.get("attempts") if isinstance(reader_analysis.get("attempts"), list) else []
    selected_attempt = None
    selected_label = str(reader_analysis.get("selected_attempt_label") or "")
    if selected_label:
        for attempt in attempts:
            if isinstance(attempt, dict) and str(attempt.get("label") or "") == selected_label:
                selected_attempt = attempt
                break

    estimated_prompt_tokens = 0
    estimated_response_tokens = 0
    if attempts:
        for attempt in attempts:
            if not isinstance(attempt, dict):
                continue
            estimated_prompt_tokens += int(attempt.get("estimated_prompt_tokens") or 0)
            estimated_response_tokens += int(attempt.get("estimated_response_tokens") or 0)

    normalized_attempts: list[dict[str, Any]] = []
    for attempt in attempts:
        if not isinstance(attempt, dict):
            continue
        prompt_tokens = int(attempt.get("estimated_prompt_tokens") or 0)
        parsed_claim_count = int(attempt.get("parsed_claim_count") or 0)
        included_chunk_count = int(attempt.get("included_chunk_count") or 0)
        prompt_tokens_per_claim = round(prompt_tokens / parsed_claim_count, 3) if parsed_claim_count > 0 and prompt_tokens > 0 else None
        claims_per_1k_prompt_tokens = round((parsed_claim_count / prompt_tokens) * 1000.0, 3) if prompt_tokens > 0 else None
        normalized_attempts.append(
            {
                "attempt_idx": int(attempt.get("attempt_idx") or 0),
                "label": str(attempt.get("label") or ""),
                "status": str(attempt.get("status") or ""),
                "context_mode": str(attempt.get("context_mode") or "") or None,
                "context_chars": int(attempt.get("context_chars") or 0),
                "prompt_chars": int(attempt.get("prompt_chars") or 0),
                "estimated_prompt_tokens": prompt_tokens or None,
                "estimated_response_tokens": int(attempt.get("estimated_response_tokens") or 0) or None,
                "parsed_claim_count": parsed_claim_count,
                "included_chunk_count": included_chunk_count or None,
                "sentence_focus_count": int(attempt.get("sentence_focus_count") or 0) or None,
                "unique_section_count": int(attempt.get("unique_section_count") or 0) or None,
                "truncated_chunk_count": int(attempt.get("truncated_chunk_count") or 0) or None,
                "generate_wall_seconds": float(attempt.get("generate_wall_seconds")) if attempt.get("generate_wall_seconds") is not None else None,
                "parse_wall_seconds": float(attempt.get("parse_wall_seconds")) if attempt.get("parse_wall_seconds") is not None else None,
                "attempt_wall_seconds": float(attempt.get("attempt_wall_seconds")) if attempt.get("attempt_wall_seconds") is not None else None,
                "provider_status": str(attempt.get("provider_status") or "") or None,
                "provider_request_wall_seconds": float(attempt.get("provider_request_wall_seconds")) if attempt.get("provider_request_wall_seconds") is not None else None,
                "provider_done_reason": str(attempt.get("provider_done_reason") or "") or None,
                "provider_prompt_eval_count": int(attempt.get("provider_prompt_eval_count")) if attempt.get("provider_prompt_eval_count") is not None else None,
                "provider_eval_count": int(attempt.get("provider_eval_count")) if attempt.get("provider_eval_count") is not None else None,
                "provider_total_duration_seconds": float(attempt.get("provider_total_duration_seconds")) if attempt.get("provider_total_duration_seconds") is not None else None,
                "provider_error_type": str(attempt.get("provider_error_type") or "") or None,
                "prompt_tokens_per_claim": prompt_tokens_per_claim,
                "claims_per_1k_prompt_tokens": claims_per_1k_prompt_tokens,
            }
        )

    return RunMeasurement(
        run_id=run_id,
        paper_id=paper_id or None,
        run_root=run_root,
        status=str(run_meta.get("status") or "") or None,
        started_at=str(run_meta.get("started_at") or "") or None,
        finished_at=str(run_meta.get("finished_at") or "") or None,
        total_seconds=_duration_seconds(run_meta.get("started_at"), run_meta.get("finished_at")),
        pages=len(document_artifact.get("pages") or []) if isinstance(document_artifact.get("pages"), list) else None,
        chunk_count=int(index_artifact.get("chunk_count")) if index_artifact.get("chunk_count") is not None else None,
        claim_count=len(claimset.get("claims") or []) if isinstance(claimset.get("claims"), list) else None,
        stats_checks=len(stats_report.get("checks") or []) if isinstance(stats_report.get("checks"), list) else None,
        run_verify=bool(params.get("run_verify")) if "run_verify" in params else None,
        reader_timeout_budget_sec=int(run_meta.get("reader_timeout_budget_sec")) if run_meta.get("reader_timeout_budget_sec") is not None else None,
        reader_attempt_count=int(reader_analysis.get("attempt_count")) if reader_analysis.get("attempt_count") is not None else None,
        reader_return_mode=str(reader_analysis.get("return_mode") or "") or None,
        reader_selected_attempt_label=str(reader_analysis.get("selected_attempt_label") or "") or None,
        analysis_wall_seconds=float(reader_analysis.get("analysis_wall_seconds")) if reader_analysis.get("analysis_wall_seconds") is not None else None,
        estimated_prompt_tokens=estimated_prompt_tokens or None,
        estimated_response_tokens=estimated_response_tokens or None,
        selected_context_mode=str(selected_attempt.get("context_mode") or "") or None if isinstance(selected_attempt, dict) else None,
        selected_chunk_count=int(selected_attempt.get("included_chunk_count")) if isinstance(selected_attempt, dict) and selected_attempt.get("included_chunk_count") is not None else None,
        selected_sentence_count=int(selected_attempt.get("sentence_focus_count")) if isinstance(selected_attempt, dict) and selected_attempt.get("sentence_focus_count") is not None else None,
        selected_unique_section_count=int(selected_attempt.get("unique_section_count")) if isinstance(selected_attempt, dict) and selected_attempt.get("unique_section_count") is not None else None,
        selected_truncated_chunk_count=int(selected_attempt.get("truncated_chunk_count")) if isinstance(selected_attempt, dict) and selected_attempt.get("truncated_chunk_count") is not None else None,
        selected_generate_wall_seconds=float(selected_attempt.get("generate_wall_seconds")) if isinstance(selected_attempt, dict) and selected_attempt.get("generate_wall_seconds") is not None else None,
        selected_parse_wall_seconds=float(selected_attempt.get("parse_wall_seconds")) if isinstance(selected_attempt, dict) and selected_attempt.get("parse_wall_seconds") is not None else None,
        selected_attempt_wall_seconds=float(selected_attempt.get("attempt_wall_seconds")) if isinstance(selected_attempt, dict) and selected_attempt.get("attempt_wall_seconds") is not None else None,
        selected_provider_request_wall_seconds=float(selected_attempt.get("provider_request_wall_seconds")) if isinstance(selected_attempt, dict) and selected_attempt.get("provider_request_wall_seconds") is not None else None,
        selected_provider_done_reason=(str(selected_attempt.get("provider_done_reason") or "") or None) if isinstance(selected_attempt, dict) else None,
        selected_provider_prompt_eval_count=int(selected_attempt.get("provider_prompt_eval_count")) if isinstance(selected_attempt, dict) and selected_attempt.get("provider_prompt_eval_count") is not None else None,
        selected_provider_eval_count=int(selected_attempt.get("provider_eval_count")) if isinstance(selected_attempt, dict) and selected_attempt.get("provider_eval_count") is not None else None,
        selected_provider_total_duration_seconds=float(selected_attempt.get("provider_total_duration_seconds")) if isinstance(selected_attempt, dict) and selected_attempt.get("provider_total_duration_seconds") is not None else None,
        attempts=normalized_attempts,
        phase_seconds=phase_seconds,
        phase_messages=phase_messages,
    )


def _format_markdown(measurements: list[RunMeasurement]) -> str:
    lines: list[str] = []
    lines.append("# Local Deep Read Runtime Measurement")
    lines.append("")
    for item in measurements:
        lines.append(f"## {item.run_id}")
        lines.append("")
        lines.append(f"- paper_id: `{item.paper_id}`")
        lines.append(f"- status: `{item.status}`")
        lines.append(f"- run_root: `{item.run_root}`")
        lines.append(f"- total_seconds: `{item.total_seconds}`")
        lines.append(f"- pages: `{item.pages}`")
        lines.append(f"- chunk_count: `{item.chunk_count}`")
        lines.append(f"- claim_count: `{item.claim_count}`")
        lines.append(f"- stats_checks: `{item.stats_checks}`")
        lines.append(f"- run_verify: `{item.run_verify}`")
        lines.append(f"- reader_timeout_budget_sec: `{item.reader_timeout_budget_sec}`")
        lines.append(f"- reader_attempt_count: `{item.reader_attempt_count}`")
        lines.append(f"- reader_return_mode: `{item.reader_return_mode}`")
        lines.append(f"- reader_selected_attempt_label: `{item.reader_selected_attempt_label}`")
        lines.append(f"- analysis_wall_seconds: `{item.analysis_wall_seconds}`")
        lines.append(f"- estimated_prompt_tokens: `{item.estimated_prompt_tokens}`")
        lines.append(f"- estimated_response_tokens: `{item.estimated_response_tokens}`")
        lines.append(f"- selected_context_mode: `{item.selected_context_mode}`")
        lines.append(f"- selected_chunk_count: `{item.selected_chunk_count}`")
        lines.append(f"- selected_sentence_count: `{item.selected_sentence_count}`")
        lines.append(f"- selected_unique_section_count: `{item.selected_unique_section_count}`")
        lines.append(f"- selected_truncated_chunk_count: `{item.selected_truncated_chunk_count}`")
        lines.append(f"- selected_generate_wall_seconds: `{item.selected_generate_wall_seconds}`")
        lines.append(f"- selected_parse_wall_seconds: `{item.selected_parse_wall_seconds}`")
        lines.append(f"- selected_attempt_wall_seconds: `{item.selected_attempt_wall_seconds}`")
        lines.append(f"- selected_provider_request_wall_seconds: `{item.selected_provider_request_wall_seconds}`")
        lines.append(f"- selected_provider_done_reason: `{item.selected_provider_done_reason}`")
        lines.append(f"- selected_provider_prompt_eval_count: `{item.selected_provider_prompt_eval_count}`")
        lines.append(f"- selected_provider_eval_count: `{item.selected_provider_eval_count}`")
        lines.append(f"- selected_provider_total_duration_seconds: `{item.selected_provider_total_duration_seconds}`")
        lines.append("")
        lines.append("| Phase | Seconds |")
        lines.append("| --- | ---: |")
        for phase, seconds in item.phase_seconds.items():
            lines.append(f"| `{phase}` | `{seconds}` |")
        lines.append("")
        if item.attempts:
            lines.append("| Attempt | Status | Mode | Chunks | Sections | Claims | Prompt tokens | Generate sec | Parse sec | Attempt sec | Provider sec | Done | Prompt eval | Eval | Tokens/claim | Claims/1k tokens |")
            lines.append("| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | ---: | ---: | ---: | ---: |")
            for attempt in item.attempts:
                lines.append(
                    f"| `{attempt['label']}` | `{attempt['status']}` | `{attempt['context_mode']}` | "
                    f"`{attempt['included_chunk_count']}` | `{attempt['unique_section_count']}` | "
                    f"`{attempt['parsed_claim_count']}` | `{attempt['estimated_prompt_tokens']}` | "
                    f"`{attempt['generate_wall_seconds']}` | `{attempt['parse_wall_seconds']}` | "
                    f"`{attempt['attempt_wall_seconds']}` | `{attempt['provider_request_wall_seconds']}` | "
                    f"`{attempt['provider_done_reason']}` | `{attempt['provider_prompt_eval_count']}` | "
                    f"`{attempt['provider_eval_count']}` | `{attempt['prompt_tokens_per_claim']}` | "
                    f"`{attempt['claims_per_1k_prompt_tokens']}` |"
                )
            lines.append("")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Summarize deep-read runtime timings from saved run artifacts and job events.")
    parser.add_argument("--run-id", action="append", dest="run_ids", default=[], help="Run id to summarize. Repeatable.")
    parser.add_argument("--out", type=Path, help="Optional output path for markdown summary.")
    args = parser.parse_args()

    run_ids = [str(item).strip() for item in args.run_ids if str(item).strip()]
    if not run_ids:
        parser.error("at least one --run-id is required")

    measurements = [measure_run(run_id) for run_id in run_ids]
    output = _format_markdown(measurements)
    if args.out:
        args.out.write_text(output, encoding="utf-8")
    print(output, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
