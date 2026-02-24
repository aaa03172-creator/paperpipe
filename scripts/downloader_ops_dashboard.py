from __future__ import annotations

import argparse
from pathlib import Path
from src.services.downloader_ops_metrics import (
    Thresholds,
    collect_metrics,
    evaluate_alerts,
    render_markdown,
)


DEFAULT_DB = Path("storage/state.db")
DEFAULT_OUT = Path("storage/reports/downloader_ops_dashboard.md")


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate downloader ops dashboard and threshold alerts.")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--hours", type=int, default=24)
    parser.add_argument("--rate-limit-warn", type=int, default=3)
    parser.add_argument("--temp-fail-warn", type=int, default=5)
    parser.add_argument("--bad-content-warn", type=int, default=3)
    parser.add_argument("--policy-block-warn", type=int, default=1)
    args = parser.parse_args()

    thresholds = Thresholds(
        rate_limit_warn=args.rate_limit_warn,
        temp_fail_warn=args.temp_fail_warn,
        bad_content_warn=args.bad_content_warn,
        policy_block_warn=args.policy_block_warn,
    )

    metrics = collect_metrics(args.db, args.hours)
    alerts = evaluate_alerts(metrics, thresholds)
    report = render_markdown(metrics, alerts)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(report, encoding="utf-8")
    print(f"dashboard written: {args.out}")

    if alerts:
        for item in alerts:
            print(f"ALERT: {item}")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
