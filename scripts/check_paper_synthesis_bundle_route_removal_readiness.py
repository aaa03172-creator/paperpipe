#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
AUDIT_SCRIPT = REPO_ROOT / "scripts" / "check_paper_synthesis_bundle_route_usage.py"
RUNTIME_HIT_SUMMARY_SCRIPT = REPO_ROOT / "scripts" / "summarize_paper_synthesis_bundle_route_hits.py"
BUNDLE_ROUTE_PATTERN = re.compile(r"/paper-syntheses/\$\{[^}]+\}(?!/)")


def _run_json(command: list[str]) -> tuple[int, dict]:
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    try:
        payload = json.loads(result.stdout) if result.stdout.strip() else {}
    except json.JSONDecodeError as exc:
        payload = {"stdout_parse_error": str(exc), "raw_stdout": result.stdout}
    if result.stderr.strip():
        payload["stderr"] = result.stderr.strip()
    return result.returncode, payload


def _read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="ignore")


def _frontend_manifest_contract(root: Path) -> dict[str, object]:
    api_path = root / "frontend" / "src" / "app" / "lib" / "api.ts"
    types_path = root / "frontend" / "src" / "app" / "lib" / "types.ts"
    api_text = _read_text(api_path)
    types_text = _read_text(types_path)

    checks = {
        "api_file_present": api_path.exists(),
        "manifest_helper_present": "export async function getPaperSynthesisManifest(" in api_text,
        "manifest_route_present": "`/paper-syntheses/${encodeURIComponent(normalizedId)}/manifest`" in api_text,
        "legacy_detail_helper_absent": "getPaperSynthesisDetail" not in api_text,
        "bare_bundle_route_absent": not BUNDLE_ROUTE_PATTERN.search(api_text),
        "types_file_present": types_path.exists(),
        "manifest_type_present": "export interface PaperSynthesisManifest" in types_text,
        "legacy_detail_type_absent": "export interface PaperSynthesisDetail" not in types_text,
    }
    return {"ready": all(checks.values()), **checks}


def _cli_manifest_contract(root: Path) -> dict[str, object]:
    cli_path = root / "src" / "cli.py"
    cli_text = _read_text(cli_path)

    manifest_flag_count = cli_text.count('"--manifest"')
    checks = {
        "cli_file_present": cli_path.exists(),
        "generate_command_present": '@app.command(name="paper-synthesis-generate")' in cli_text,
        "show_command_present": '@app.command(name="paper-synthesis-show")' in cli_text,
        "manifest_flag_count": manifest_flag_count,
        "manifest_flag_present_for_both_commands": manifest_flag_count >= 2,
        "conflict_guard_present": "Choose only one of --manifest or --markdown" in cli_text,
    }
    ready = (
        bool(checks["cli_file_present"])
        and bool(checks["generate_command_present"])
        and bool(checks["show_command_present"])
        and bool(checks["manifest_flag_present_for_both_commands"])
        and bool(checks["conflict_guard_present"])
    )
    return {"ready": ready, **checks}


def _runtime_signal_interpretation(runtime_exit_code: int, summary: dict[str, object]) -> tuple[str, list[str]]:
    if runtime_exit_code == 2 and (
        not summary.get("db_exists", True) or not summary.get("request_audits_table_present", True)
    ):
        return (
            "unavailable",
            ["Selected runtime DB did not provide readable request_audits rows for compatibility-hit inspection."],
        )
    if not summary:
        return "unavailable", ["Runtime compatibility-hit summary was not available."]

    possible_external_hosts = summary.get("recent_possible_external_hosts") or []
    route_usage_observed = bool(summary.get("route_usage_observed"))
    recent_host_signal_counts = summary.get("recent_host_signal_counts") or {}
    recent_likely_test_noise_count = int(summary.get("recent_likely_test_noise_count") or 0)
    recent_non_noise_hit_count = int(summary.get("recent_non_noise_hit_count") or 0)
    known_local_or_test_hits = int(recent_host_signal_counts.get("known_local_or_test") or 0)
    internal_network_like_hits = int(recent_host_signal_counts.get("internal_network_like") or 0)

    if possible_external_hosts:
        return (
            "possibly_external_seen",
            [
                "Selected runtime DB still shows non-local compatibility-route host signals, so API deletion would be premature."
            ],
        )
    if route_usage_observed and recent_likely_test_noise_count > 0 and recent_non_noise_hit_count == 0:
        return (
            "likely_historical_test_noise_only",
            [
                "Selected runtime DB only shows compatibility-route hits that match known local/test placeholder noise patterns; that still does not confirm external callers are gone."
            ],
        )
    if route_usage_observed and (known_local_or_test_hits > 0 or internal_network_like_hits > 0):
        return (
            "local_or_internal_only",
            [
                "Selected runtime DB only shows local/test or internal-network-like compatibility hits; that is not proof that external callers are gone."
            ],
        )
    if route_usage_observed:
        return (
            "observed_but_unclassified",
            [
                "Selected runtime DB shows compatibility-route hits, but the available host signals do not confirm external caller ownership."
            ],
        )
    return (
        "no_hits_observed",
        [
            "Selected runtime DB currently shows no observed compatibility-route hits, but external callers outside the repo remain not confirmed."
        ],
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Check whether first-party PaperPipe surfaces are clean enough to retire direct use of the "
            "paper-synthesis compatibility bundle route."
        )
    )
    parser.add_argument(
        "--root",
        default=str(REPO_ROOT),
        help="Root directory of the current repo to audit. Default: this repo.",
    )
    parser.add_argument(
        "--include-generated",
        action="store_true",
        help="Pass through to the bundle-route usage audit script.",
    )
    parser.add_argument(
        "--db",
        help=(
            "Optional runtime DB path for additive compatibility-hit observation. "
            "Defaults to the current PaperPipe state DB when omitted."
        ),
    )
    parser.add_argument(
        "--runtime-limit",
        type=int,
        default=20,
        help="Number of recent compatibility-route runtime hits to inspect. Default: 20.",
    )
    args = parser.parse_args()

    root = Path(args.root).expanduser().resolve()
    audit_command = [sys.executable, str(AUDIT_SCRIPT), "--root", str(root)]
    if args.include_generated:
        audit_command.append("--include-generated")
    audit_code, audit_payload = _run_json(audit_command)

    runtime_command = [
        sys.executable,
        str(RUNTIME_HIT_SUMMARY_SCRIPT),
        "--limit",
        str(max(1, int(args.runtime_limit))),
    ]
    if args.db:
        runtime_command.extend(["--db", str(Path(args.db).expanduser().resolve())])
    runtime_code, runtime_payload = _run_json(runtime_command)

    frontend_contract = _frontend_manifest_contract(root)
    cli_contract = _cli_manifest_contract(root)

    active_surface_ready = (
        audit_code == 0
        and int(audit_payload.get("offender_count") or 0) == 0
        and bool(frontend_contract["ready"])
        and bool(cli_contract["ready"])
    )

    not_confirmed_reason = (
        "External callers outside the current repo are not audited by this script, so API route deletion is not confirmed."
    )
    runtime_signal_interpretation, runtime_not_confirmed = _runtime_signal_interpretation(
        runtime_code, runtime_payload
    )

    summary = {
        "evaluated_at_utc": datetime.now(timezone.utc).isoformat(),
        "current_root": str(root),
        "active_surface_ready": active_surface_ready,
        "ready_to_retire_bundle_route_from_first_party": active_surface_ready,
        "ready_to_delete_api_bundle_route_now": False,
        "api_route_deletion_not_confirmed_reason": not_confirmed_reason,
        "compatibility_usage_audit": {
            "exit_code": audit_code,
            **audit_payload,
        },
        "runtime_compatibility_hit_summary": {
            "exit_code": runtime_code,
            **runtime_payload,
        },
        "runtime_signal_interpretation": runtime_signal_interpretation,
        "frontend_manifest_contract": frontend_contract,
        "cli_manifest_contract": cli_contract,
        "remaining_allowlisted_compatibility_surfaces": audit_payload.get("allowlisted_surfaces") or [],
        "not_confirmed": [not_confirmed_reason, *runtime_not_confirmed],
    }
    print(json.dumps(summary, indent=2))
    return 0 if active_surface_ready else 2


if __name__ == "__main__":
    raise SystemExit(main())
