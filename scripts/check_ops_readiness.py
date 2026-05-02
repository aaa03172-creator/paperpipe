from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.schemas.ops import RuntimeReadinessCheck, RuntimeReadinessResponse
from src.services.downloader_ops_metrics import Thresholds, collect_metrics, evaluate_alerts
from src.services.runtime_readiness import collect_runtime_readiness


DEFAULT_DB = Path("storage/state.db")


@dataclass(frozen=True)
class OpsReadinessResult:
    status: str
    exit_code: int
    readiness: RuntimeReadinessResponse
    downloader_metrics: dict[str, Any] | None
    downloader_alerts: list[str]
    downloader_error: str | None = None


def _model_dump(value: Any) -> dict[str, Any]:
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if hasattr(value, "dict"):
        return value.dict()
    return dict(value)


def _ops_status_and_exit_code(
    *,
    readiness_status: str,
    downloader_alerts: list[str],
    downloader_error: str | None,
) -> tuple[str, int]:
    if readiness_status == "error" or downloader_error:
        return "error", 1
    if readiness_status == "degraded" or downloader_alerts:
        return "warn", 2
    return "ok", 0


def collect_ops_readiness(
    *,
    db_path: Path,
    hours: int,
    thresholds: Thresholds,
    include_downloader: bool,
) -> OpsReadinessResult:
    readiness = collect_runtime_readiness()
    downloader_metrics: dict[str, Any] | None = None
    downloader_alerts: list[str] = []
    downloader_error: str | None = None

    if include_downloader:
        try:
            downloader_metrics = collect_metrics(db_path, hours)
            downloader_alerts = evaluate_alerts(downloader_metrics, thresholds)
        except Exception as exc:
            downloader_error = f"{type(exc).__name__}: {exc}"

    status, exit_code = _ops_status_and_exit_code(
        readiness_status=readiness.status,
        downloader_alerts=downloader_alerts,
        downloader_error=downloader_error,
    )
    return OpsReadinessResult(
        status=status,
        exit_code=exit_code,
        readiness=readiness,
        downloader_metrics=downloader_metrics,
        downloader_alerts=downloader_alerts,
        downloader_error=downloader_error,
    )


def _checks_by_status(checks: list[RuntimeReadinessCheck], statuses: set[str]) -> list[RuntimeReadinessCheck]:
    return [check for check in checks if check.status in statuses]


def render_text(result: OpsReadinessResult, *, show_ok: bool) -> str:
    lines = [
        f"ops_readiness={result.status}",
        f"runtime_readiness={result.readiness.status}",
    ]

    checks_to_show = (
        result.readiness.checks
        if show_ok
        else _checks_by_status(result.readiness.checks, {"warn", "error"})
    )
    if checks_to_show:
        lines.append("")
        lines.append("Runtime checks:")
        for check in checks_to_show:
            path_suffix = f" path={check.path}" if check.path else ""
            lines.append(f"- {check.status}: {check.name}: {check.detail}{path_suffix}")
    elif not show_ok:
        lines.append("runtime_checks=all_ok")

    if result.downloader_error:
        lines.append("")
        lines.append(f"downloader_error={result.downloader_error}")
    elif result.downloader_metrics is not None:
        metrics = result.downloader_metrics
        lines.append("")
        lines.append(
            "downloader_metrics="
            f"papers={metrics.get('paper_rows', 0)} "
            f"attempt_rows={metrics.get('attempt_rows', 0)} "
            f"missing_pdf_rows={metrics.get('missing_pdf_rows', 0)}"
        )
        if result.downloader_alerts:
            lines.append("Downloader alerts:")
            for alert in result.downloader_alerts:
                lines.append(f"- ALERT: {alert}")
        else:
            lines.append("downloader_alerts=none")

    return "\n".join(lines) + "\n"


def render_json(result: OpsReadinessResult) -> str:
    payload = {
        "status": result.status,
        "exit_code": result.exit_code,
        "runtime_readiness": _model_dump(result.readiness),
        "downloader_metrics": result.downloader_metrics,
        "downloader_alerts": result.downloader_alerts,
        "downloader_error": result.downloader_error,
    }
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Check PaperPipe operational readiness with stable exit codes."
    )
    parser.add_argument("--db", type=Path, default=DEFAULT_DB, help="SQLite DB path for downloader metrics.")
    parser.add_argument("--hours", type=int, default=24, help="Downloader metrics window in hours.")
    parser.add_argument("--rate-limit-warn", type=int, default=3)
    parser.add_argument("--temp-fail-warn", type=int, default=5)
    parser.add_argument("--bad-content-warn", type=int, default=3)
    parser.add_argument("--policy-block-warn", type=int, default=1)
    parser.add_argument(
        "--skip-downloader",
        action="store_true",
        help="Only check runtime readiness; skip downloader metrics and alerts.",
    )
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
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
    result = collect_ops_readiness(
        db_path=args.db,
        hours=args.hours,
        thresholds=thresholds,
        include_downloader=not args.skip_downloader,
    )
    output = render_json(result) if args.json else render_text(result, show_ok=args.show_ok)
    print(output, end="")
    return result.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
