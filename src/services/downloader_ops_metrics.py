from __future__ import annotations

import json
import sqlite3
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


@dataclass
class Thresholds:
    rate_limit_warn: int
    temp_fail_warn: int
    bad_content_warn: int
    policy_block_warn: int


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    cur = conn.cursor()
    cur.execute(f"PRAGMA table_info({table})")
    return {row[1] for row in cur.fetchall()}


def parse_attempts(raw: Any) -> list[dict[str, Any]]:
    if not raw:
        return []
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
        except Exception:
            return []
    elif isinstance(raw, list):
        parsed = raw
    else:
        return []
    if not isinstance(parsed, list):
        return []
    return [item for item in parsed if isinstance(item, dict)]


def collect_metrics(db_path: Path, hours: int) -> dict[str, Any]:
    if not db_path.exists():
        return {
            "db_exists": False,
            "window_hours": hours,
            "paper_rows": 0,
            "attempt_rows": 0,
            "status_counts": {},
            "provider_counts": {},
            "retry_attempts_total": 0,
            "retry_attempts_by_provider": {},
            "rate_limit_retry_signals": 0,
            "rate_limit_exhausted": 0,
            "missing_pdf_rows": 0,
            "has_download_attempts_column": False,
        }

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cols = table_columns(conn, "papers")

    has_updated = "updated_at" in cols
    has_pdf_path = "pdf_path" in cols
    has_attempts = "download_attempts" in cols

    where_clause = ""
    params: list[Any] = []
    if has_updated:
        threshold = (utc_now() - timedelta(hours=hours)).strftime("%Y-%m-%d %H:%M:%S")
        where_clause = " WHERE updated_at >= ?"
        params.append(threshold)

    cur = conn.cursor()
    cur.execute(f"SELECT * FROM papers{where_clause}", params)
    rows = cur.fetchall()

    status_counts: Counter[str] = Counter()
    provider_counts: Counter[str] = Counter()
    retry_attempts_by_provider: Counter[str] = Counter()
    attempt_rows = 0
    retry_attempts_total = 0
    rate_limit_retry_signals = 0
    rate_limit_exhausted = 0

    for row in rows:
        attempts = parse_attempts(row["download_attempts"]) if has_attempts else []
        if attempts:
            attempt_rows += 1
        for attempt in attempts:
            status = str(attempt.get("status") or "unknown")
            provider = str(attempt.get("provider") or "unknown")
            status_counts[status] += 1
            provider_counts[provider] += 1
            retry_no = int(attempt.get("retry_no") or 0)
            will_retry = bool(attempt.get("will_retry") or False)
            if retry_no > 0:
                retry_attempts_total += 1
                retry_attempts_by_provider[provider] += 1
            if status == "rate_limit":
                if will_retry:
                    rate_limit_retry_signals += 1
                else:
                    rate_limit_exhausted += 1

    missing_pdf_rows = 0
    if has_pdf_path:
        missing_pdf_rows = sum(1 for row in rows if not row["pdf_path"])

    conn.close()
    return {
        "db_exists": True,
        "window_hours": hours,
        "paper_rows": len(rows),
        "attempt_rows": attempt_rows,
        "status_counts": dict(status_counts),
        "provider_counts": dict(provider_counts),
        "retry_attempts_total": retry_attempts_total,
        "retry_attempts_by_provider": dict(retry_attempts_by_provider),
        "rate_limit_retry_signals": rate_limit_retry_signals,
        "rate_limit_exhausted": rate_limit_exhausted,
        "missing_pdf_rows": missing_pdf_rows,
        "has_download_attempts_column": has_attempts,
    }


def evaluate_alerts(metrics: dict[str, Any], thresholds: Thresholds) -> list[str]:
    alerts: list[str] = []
    status_counts = metrics.get("status_counts", {})

    checks = [
        ("rate_limit", thresholds.rate_limit_warn),
        ("temp_fail", thresholds.temp_fail_warn),
        ("bad_content", thresholds.bad_content_warn),
        ("policy_block", thresholds.policy_block_warn),
    ]
    for key, warn in checks:
        count = int(status_counts.get(key, 0))
        if count >= warn:
            alerts.append(f"{key} count {count} >= warn threshold {warn}")

    return alerts


def render_markdown(metrics: dict[str, Any], alerts: list[str]) -> str:
    now = utc_now().strftime("%Y-%m-%d %H:%M:%S UTC")
    lines = [
        "# Downloader Ops Dashboard",
        "",
        f"- Generated: {now}",
        f"- Window: last {metrics['window_hours']} hours",
        f"- DB exists: {metrics['db_exists']}",
        f"- Papers in window: {metrics['paper_rows']}",
        f"- Rows with attempts: {metrics['attempt_rows']}",
        f"- Rows missing `pdf_path`: {metrics['missing_pdf_rows']}",
        f"- Retry attempts (actual): {metrics.get('retry_attempts_total', 0)}",
        f"- Rate-limit retry signals: {metrics.get('rate_limit_retry_signals', 0)}",
        f"- Rate-limit exhausted: {metrics.get('rate_limit_exhausted', 0)}",
        "",
    ]

    if not metrics.get("has_download_attempts_column", False):
        lines.extend(
            [
                "## Note",
                "`papers.download_attempts` column not found. Provider/failure taxonomy metrics are unavailable.",
                "",
            ]
        )

    lines.extend(["## Failure Status Counts", "| status | count |", "| --- | ---: |"])
    for key, value in sorted(metrics.get("status_counts", {}).items()):
        lines.append(f"| {key} | {value} |")
    if not metrics.get("status_counts"):
        lines.append("| (none) | 0 |")

    lines.extend(["", "## Provider Attempt Counts", "| provider | count |", "| --- | ---: |"])
    for key, value in sorted(metrics.get("provider_counts", {}).items()):
        lines.append(f"| {key} | {value} |")
    if not metrics.get("provider_counts"):
        lines.append("| (none) | 0 |")

    lines.extend(["", "## Retry Attempt Counts", "| provider | retry_attempts |", "| --- | ---: |"])
    for key, value in sorted(metrics.get("retry_attempts_by_provider", {}).items()):
        lines.append(f"| {key} | {value} |")
    if not metrics.get("retry_attempts_by_provider"):
        lines.append("| (none) | 0 |")

    lines.extend(["", "## Alerts"])
    if alerts:
        for item in alerts:
            lines.append(f"- ALERT: {item}")
    else:
        lines.append("- none")

    lines.append("")
    return "\n".join(lines)
