#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from collections import Counter
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.db_utils import get_db_path
from src.services.event_log import list_request_audits


COMPATIBILITY_ROUTE_SOURCE = "compatibility_route"
COMPATIBILITY_ROUTE_OUTCOME = "deprecated_bundle_read"
KNOWN_LOCAL_OR_TEST_HOSTS = {"testserver", "localhost", "127.0.0.1", "::1"}
KNOWN_TEST_NOISE_SYNTHESIS_IDS = {"papersynth_missing"}


def _normalized_db_path(path: Path | None) -> Path:
    if path is not None:
        resolved = path.expanduser().resolve()
        os.environ["PAPERPIPE_DB_PATH"] = str(resolved)
        return resolved
    return get_db_path()


def _request_audits_table_present(db_path: Path) -> bool:
    if not db_path.exists():
        return False
    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='request_audits'"
        ).fetchone()
        return row is not None
    finally:
        conn.close()


def _load_totals(db_path: Path) -> dict[str, Any]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        summary = conn.execute(
            """
            SELECT COUNT(*) AS total_hit_count, MAX(ts) AS latest_hit_ts
            FROM request_audits
            WHERE source = ? AND outcome = ?
            """,
            (COMPATIBILITY_ROUTE_SOURCE, COMPATIBILITY_ROUTE_OUTCOME),
        ).fetchone()
        return {
            "total_hit_count": int(summary["total_hit_count"] or 0),
            "latest_hit_ts": summary["latest_hit_ts"],
        }
    finally:
        conn.close()


def _normalize_host(host: Any) -> str:
    raw = str(host or "").strip().lower()
    if not raw:
        return ""
    if raw.startswith("[") and "]" in raw:
        return raw[1 : raw.index("]")]
    if raw.count(":") == 1:
        return raw.split(":", 1)[0]
    return raw


def _classify_host_signal(host: Any) -> str:
    normalized = _normalize_host(host)
    if not normalized:
        return "unknown"
    if normalized in KNOWN_LOCAL_OR_TEST_HOSTS:
        return "known_local_or_test"
    if normalized.endswith(".local"):
        return "internal_network_like"
    return "possibly_external"


def _likely_test_noise_reason(*, synthesis_id: Any, host_signal: str, path: Any) -> str | None:
    normalized_synthesis_id = str(synthesis_id or "").strip()
    normalized_path = str(path or "").strip()
    if host_signal != "known_local_or_test":
        return None
    if normalized_synthesis_id in KNOWN_TEST_NOISE_SYNTHESIS_IDS:
        return "known_missing_placeholder_on_local_test_host"
    if any(normalized_path.endswith(f"/{item}") for item in KNOWN_TEST_NOISE_SYNTHESIS_IDS):
        return "known_missing_placeholder_on_local_test_host"
    return None


def _normalize_recent_hit(row: dict[str, Any]) -> dict[str, Any]:
    payload = row.get("payload")
    payload_dict = payload if isinstance(payload, dict) else {}
    host = row.get("host")
    synthesis_id = payload_dict.get("synthesis_id")
    path = row.get("path")
    host_signal = _classify_host_signal(host)
    likely_test_noise_reason = _likely_test_noise_reason(
        synthesis_id=synthesis_id,
        host_signal=host_signal,
        path=path,
    )
    return {
        "audit_id": row.get("audit_id"),
        "ts": row.get("ts"),
        "host": host,
        "normalized_host": _normalize_host(host) or None,
        "host_signal": host_signal,
        "method": row.get("method"),
        "path": path,
        "status_code": row.get("status_code"),
        "synthesis_id": synthesis_id,
        "likely_test_noise": likely_test_noise_reason is not None,
        "likely_test_noise_reason": likely_test_noise_reason,
        "preferred_manifest_route": payload_dict.get("preferred_manifest_route"),
        "preferred_markdown_route": payload_dict.get("preferred_markdown_route"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Summarize recent request-audit hits for the paper-synthesis compatibility bundle surface."
        )
    )
    parser.add_argument(
        "--db",
        type=Path,
        help="Optional runtime DB path. Defaults to the current PaperPipe state DB.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Number of recent compatibility-route hits to include in the summary. Default: 20.",
    )
    args = parser.parse_args()

    db_path = _normalized_db_path(args.db)
    limit = max(1, int(args.limit))

    db_exists = db_path.exists()
    table_present = _request_audits_table_present(db_path)

    if not db_exists or not table_present:
        summary = {
            "db_path": str(db_path),
            "db_exists": db_exists,
            "request_audits_table_present": table_present,
            "route_usage_observed": False,
            "total_hit_count": 0,
            "latest_hit_ts": None,
            "recent_hits_limit": limit,
            "recent_hits": [],
            "recent_host_counts": [],
            "recent_host_signal_counts": {},
            "recent_possible_external_hosts": [],
            "recent_likely_test_noise_count": 0,
            "recent_non_noise_hit_count": 0,
            "recent_unique_synthesis_ids": [],
            "not_confirmed": [
                "No readable request_audits table was available at the selected runtime DB path.",
                "No host-level signal can be used to reason about external callers without readable request_audits rows.",
            ],
        }
        print(json.dumps(summary, indent=2))
        return 2

    totals = _load_totals(db_path)
    recent_rows = list_request_audits(
        source=COMPATIBILITY_ROUTE_SOURCE,
        outcome=COMPATIBILITY_ROUTE_OUTCOME,
        limit=limit,
    )
    recent_hits = [_normalize_recent_hit(item) for item in recent_rows]
    host_counts = Counter((item.get("host") or "unknown") for item in recent_hits)
    host_signal_counts = Counter(item["host_signal"] for item in recent_hits)
    recent_unique_synthesis_ids = sorted(
        {item["synthesis_id"] for item in recent_hits if item.get("synthesis_id")}
    )
    recent_possible_external_hosts = sorted(
        {
            item["normalized_host"]
            for item in recent_hits
            if item.get("host_signal") == "possibly_external" and item.get("normalized_host")
        }
    )
    recent_likely_test_noise_count = sum(1 for item in recent_hits if item.get("likely_test_noise"))
    recent_non_noise_hit_count = len(recent_hits) - recent_likely_test_noise_count

    summary = {
        "db_path": str(db_path),
        "db_exists": True,
        "request_audits_table_present": True,
        "route_usage_observed": totals["total_hit_count"] > 0,
        "total_hit_count": totals["total_hit_count"],
        "latest_hit_ts": totals["latest_hit_ts"],
        "recent_hits_limit": limit,
        "recent_hits": recent_hits,
        "recent_host_counts": [
            {"host": host, "count": count}
            for host, count in sorted(host_counts.items(), key=lambda item: (-item[1], item[0]))
        ],
        "recent_host_signal_counts": dict(sorted(host_signal_counts.items())),
        "recent_possible_external_hosts": recent_possible_external_hosts,
        "recent_likely_test_noise_count": recent_likely_test_noise_count,
        "recent_non_noise_hit_count": recent_non_noise_hit_count,
        "recent_unique_synthesis_ids": recent_unique_synthesis_ids,
        "not_confirmed": [
            "This summary only reflects request_audits present in the selected runtime DB.",
            "Known local/test hosts such as testserver, localhost, or loopback are not evidence of external callers.",
            "Known placeholder hits such as papersynth_missing on local/test hosts are likely test noise, not deployment evidence.",
            "Non-local hostnames in recent hits are suggestive only; external caller ownership is still not confirmed without deployment context.",
        ],
    }
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
