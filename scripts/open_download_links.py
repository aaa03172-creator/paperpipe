from __future__ import annotations

import argparse
import json
import subprocess
from typing import Any

from src.db_utils import get_db_connection
from src.institutional_access import extract_institutional_proxy_link


def _parse_feedback(raw: Any) -> Any:
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except Exception:
            return {}
    return raw or {}


def collect_institutional_links(limit: int = 20, status: str = "manual_required") -> list[dict[str, str]]:
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT paper_id, title, feedback_json
        FROM papers
        WHERE pdf_status = ?
        ORDER BY updated_at DESC
        LIMIT ?
        """,
        (status, limit),
    )
    rows = cur.fetchall()
    conn.close()

    results: list[dict[str, str]] = []
    for row in rows:
        item = dict(row)
        url = extract_institutional_proxy_link(_parse_feedback(item.get("feedback_json")))
        if not url:
            continue
        results.append(
            {
                "paper_id": str(item.get("paper_id") or ""),
                "title": str(item.get("title") or ""),
                "url": url,
            }
        )
    return results


def open_links(items: list[dict[str, str]]) -> None:
    for item in items:
        print(f"{item['paper_id']}\t{item['title']}\t{item['url']}")
        subprocess.run(["open", item["url"]], check=False)


def main() -> int:
    parser = argparse.ArgumentParser(description="Open institutional download links from manual_required queue.")
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--status", default="manual_required")
    args = parser.parse_args()

    items = collect_institutional_links(limit=max(1, args.limit), status=args.status)
    if not items:
        print("No institutional links found.")
        return 0

    open_links(items)
    print(f"Opened {len(items)} links.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
