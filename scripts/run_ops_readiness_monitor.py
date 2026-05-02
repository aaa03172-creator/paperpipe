from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.check_ops_readiness import collect_ops_readiness, render_json, render_text
from src.services.downloader_ops_metrics import Thresholds


DEFAULT_DB = Path("storage/state.db")
DEFAULT_OUT = Path("storage/reports/ops_readiness_latest.json")
DEFAULT_TEXT_OUT = Path("storage/reports/ops_readiness_latest.txt")
DEFAULT_THRESHOLDS = Thresholds(
    rate_limit_warn=3,
    temp_fail_warn=5,
    bad_content_warn=3,
    policy_block_warn=1,
)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _load_json(text: str) -> dict[str, Any]:
    parsed = json.loads(text)
    return parsed if isinstance(parsed, dict) else {"payload": parsed}


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def run_monitor(
    *,
    db_path: Path = DEFAULT_DB,
    out_path: Path = DEFAULT_OUT,
    text_out_path: Path | None = DEFAULT_TEXT_OUT,
    hours: int = 24,
    thresholds: Thresholds | None = None,
    include_downloader: bool = True,
    show_ok: bool = False,
) -> tuple[int, str]:
    thresholds = thresholds or DEFAULT_THRESHOLDS
    checked_at = _utc_now_iso()
    result = collect_ops_readiness(
        db_path=db_path,
        hours=hours,
        thresholds=thresholds,
        include_downloader=include_downloader,
    )

    payload = _load_json(render_json(result))
    payload["checked_at"] = checked_at
    payload["monitor"] = {
        "db_path": str(db_path),
        "hours": hours,
        "include_downloader": include_downloader,
    }
    _write_text(out_path, json.dumps(payload, indent=2, sort_keys=True) + "\n")

    text_summary = (
        f"checked_at={checked_at}\n"
        f"exit_code={result.exit_code}\n"
        + render_text(result, show_ok=show_ok)
    )
    if text_out_path is not None:
        _write_text(text_out_path, text_summary)

    return result.exit_code, text_summary


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run PaperPipe ops readiness for local schedulers. Writes latest JSON/text reports "
            "and exits with the readiness status code."
        )
    )
    parser.add_argument("--db", type=Path, default=DEFAULT_DB, help="SQLite DB path for downloader metrics.")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help="JSON report path.")
    parser.add_argument("--text-out", type=Path, default=DEFAULT_TEXT_OUT, help="Text report path.")
    parser.add_argument("--no-text-out", action="store_true", help="Do not write a text report file.")
    parser.add_argument("--hours", type=int, default=24, help="Downloader metrics window in hours.")
    parser.add_argument("--rate-limit-warn", type=int, default=3)
    parser.add_argument("--temp-fail-warn", type=int, default=5)
    parser.add_argument("--bad-content-warn", type=int, default=3)
    parser.add_argument("--policy-block-warn", type=int, default=1)
    parser.add_argument("--skip-downloader", action="store_true", help="Skip downloader metrics and alerts.")
    parser.add_argument("--show-ok", action="store_true", help="Include ok runtime checks in text output.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    thresholds = Thresholds(
        rate_limit_warn=args.rate_limit_warn,
        temp_fail_warn=args.temp_fail_warn,
        bad_content_warn=args.bad_content_warn,
        policy_block_warn=args.policy_block_warn,
    )
    exit_code, text_summary = run_monitor(
        db_path=args.db.expanduser(),
        out_path=args.out.expanduser(),
        text_out_path=None if args.no_text_out else args.text_out.expanduser(),
        hours=max(1, args.hours),
        thresholds=thresholds,
        include_downloader=not args.skip_downloader,
        show_ok=bool(args.show_ok),
    )
    print(text_summary, end="")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
