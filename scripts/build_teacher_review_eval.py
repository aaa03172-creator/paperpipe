from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.services.teacher_review_eval_sidecar import (
    build_teacher_review_eval_sidecar,
    load_teacher_review_rows,
    write_teacher_review_eval_sidecar,
)


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build teacher_review_eval sidecars from a spot-check JSONL file.")
    parser.add_argument("--review-jsonl", required=True, help="Path to the review JSONL file")
    parser.add_argument(
        "--bundle-dir",
        action="append",
        default=[],
        help="Optional bundle directory to process. Repeat to restrict the replay set.",
    )
    parser.add_argument(
        "--report-path",
        default="",
        help="Optional markdown report path for aggregate replay output.",
    )
    return parser


def _bundle_dirs_from_rows(review_rows: list[dict]) -> list[Path]:
    bundle_dirs: list[Path] = []
    seen: set[str] = set()
    for row in review_rows:
        bundle_dir = str(row.get("bundle_dir") or "").strip()
        if not bundle_dir or bundle_dir in seen:
            continue
        seen.add(bundle_dir)
        bundle_dirs.append(Path(bundle_dir).expanduser().resolve())
    return bundle_dirs


def _write_report(report_path: Path, review_jsonl_path: Path, sidecars: list[tuple[Path, object]]) -> None:
    bundle_count = len(sidecars)
    claim_count = sum(sidecar.metrics.claim_count for _, sidecar in sidecars)
    reviewed_claim_count = sum(sidecar.metrics.reviewed_claim_count for _, sidecar in sidecars)
    direct_quote_support_count = sum(sidecar.metrics.direct_quote_support_count for _, sidecar in sidecars)
    adjacent_support_count = sum(sidecar.metrics.adjacent_support_count for _, sidecar in sidecars)
    heading_level_support_count = sum(sidecar.metrics.heading_level_support_count for _, sidecar in sidecars)
    misaligned_quote_count = sum(sidecar.metrics.misaligned_quote_count for _, sidecar in sidecars)
    fragmentary_claim_count = sum(sidecar.metrics.fragmentary_claim_count for _, sidecar in sidecars)
    supported_claim_count = sum(sidecar.metrics.supported_claim_count for _, sidecar in sidecars)
    unsupported_claim_count = sum(sidecar.metrics.unsupported_claim_count for _, sidecar in sidecars)
    ambiguous_claim_count = sum(sidecar.metrics.ambiguous_claim_count for _, sidecar in sidecars)
    misleading_location_count = sum(sidecar.metrics.misleading_location_count for _, sidecar in sidecars)
    keep_teacher_claim_count = sum(sidecar.metrics.keep_teacher_claim_count for _, sidecar in sidecars)
    drop_teacher_claim_count = sum(sidecar.metrics.drop_teacher_claim_count for _, sidecar in sidecars)
    major_issue_bundle_count = sum(sidecar.bundle_outcome == "MAJOR_ISSUE" for _, sidecar in sidecars)
    precision_denominator = supported_claim_count + unsupported_claim_count
    supported_claim_precision = round(supported_claim_count / precision_denominator, 3) if precision_denominator else 0.0

    lines = [
        "# Teacher Review Eval Sidecar Replay",
        "",
        "Status: Eval sidecar replay completed",
        f"Review JSONL: `{review_jsonl_path}`",
        "",
        "## Aggregate Metrics",
        "",
        f"- Bundle count: `{bundle_count}`",
        f"- Claim count: `{claim_count}`",
        f"- Reviewed claim count: `{reviewed_claim_count}`",
        f"- Direct quote support count: `{direct_quote_support_count}`",
        f"- Adjacent support count: `{adjacent_support_count}`",
        f"- Heading-level support count: `{heading_level_support_count}`",
        f"- Misaligned quote count: `{misaligned_quote_count}`",
        f"- Fragmentary claim count: `{fragmentary_claim_count}`",
        f"- Supported claim count: `{supported_claim_count}`",
        f"- Unsupported claim count: `{unsupported_claim_count}`",
        f"- Ambiguous claim count: `{ambiguous_claim_count}`",
        f"- Misleading location count: `{misleading_location_count}`",
        f"- Keep teacher claim count: `{keep_teacher_claim_count}`",
        f"- Drop teacher claim count: `{drop_teacher_claim_count}`",
        f"- Major-issue bundle count: `{major_issue_bundle_count}`",
        f"- Supported claim precision: `{supported_claim_precision}`",
        "",
        "## Bundle Outputs",
        "",
    ]
    for sidecar_path, sidecar in sidecars:
        lines.extend(
            [
                f"### {sidecar.paper_id}",
                "",
                f"- Sidecar: `{sidecar_path}`",
                f"- Bundle outcome: `{sidecar.bundle_outcome}`",
                f"- Issue patterns: `{', '.join(sidecar.issue_patterns) if sidecar.issue_patterns else 'none'}`",
                f"- Claims: `{sidecar.metrics.claim_count}`",
                f"- Direct quote support: `{sidecar.metrics.direct_quote_support_count}`",
                f"- Adjacent support: `{sidecar.metrics.adjacent_support_count}`",
                f"- Heading-level support: `{sidecar.metrics.heading_level_support_count}`",
                f"- Misaligned quote: `{sidecar.metrics.misaligned_quote_count}`",
                f"- Fragmentary claim: `{sidecar.metrics.fragmentary_claim_count}`",
                f"- Supported: `{sidecar.metrics.supported_claim_count}`",
                f"- Ambiguous: `{sidecar.metrics.ambiguous_claim_count}`",
                f"- Unsupported: `{sidecar.metrics.unsupported_claim_count}`",
                f"- Misleading locations: `{sidecar.metrics.misleading_location_count}`",
                "",
            ]
        )
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = _build_arg_parser()
    args = parser.parse_args()

    review_jsonl_path = Path(args.review_jsonl).expanduser().resolve()
    review_rows = load_teacher_review_rows(review_jsonl_path)
    bundle_dirs = [Path(path).expanduser().resolve() for path in args.bundle_dir] or _bundle_dirs_from_rows(review_rows)

    sidecars = []
    for bundle_dir in bundle_dirs:
        sidecar = build_teacher_review_eval_sidecar(
            bundle_dir=bundle_dir,
            review_rows=review_rows,
            review_jsonl_path=review_jsonl_path,
        )
        sidecar_path = write_teacher_review_eval_sidecar(sidecar, bundle_dir)
        sidecars.append((sidecar_path, sidecar))

    if args.report_path:
        _write_report(Path(args.report_path).expanduser().resolve(), review_jsonl_path, sidecars)

    payload = {
        "review_jsonl": str(review_jsonl_path),
        "bundle_count": len(sidecars),
        "sidecar_paths": [str(path) for path, _ in sidecars],
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
