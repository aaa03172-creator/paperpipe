#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.schemas.evidence_grounding_scorecard import (  # noqa: E402
    EvidenceGroundingScorecardInputBackfillItemRequest,
)
from src.services.evidence_grounding_scorecard_input_backfill import (  # noqa: E402
    build_evidence_grounding_scorecard_input_backfill_report,
    load_scorecard_input_backfill_items_from_benchmark_artifacts,
)
from src.services.path_masking import mask_local_paths_in_text  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Derive scorecard input sidecars from existing deepread artifacts into a copied output run root."
        )
    )
    parser.add_argument(
        "--item",
        action="append",
        default=[],
        help=(
            "JSON object with paper_id, source_run_dir, and optional run_id/output_name. "
            "May be supplied more than once."
        ),
    )
    parser.add_argument("--items-json", help="JSON file containing a list of item objects.")
    parser.add_argument(
        "--benchmark-manifest",
        action="append",
        default=[],
        help=(
            "evidence_grounding_benchmark_manifest.v1 path. Manifest items are converted into "
            "scorecard backfill item requests. May be supplied more than once."
        ),
    )
    parser.add_argument(
        "--benchmark-manifest-package",
        action="append",
        default=[],
        help=(
            "evidence_grounding_benchmark_manifest_package.v1 path. Embedded or linked manifests are "
            "converted into scorecard backfill item requests. May be supplied more than once."
        ),
    )
    parser.add_argument("--out-run-root", required=True)
    parser.add_argument("--out", help="Optional output path for the backfill report JSON.")
    parser.add_argument(
        "--run-dir-map-out",
        help=(
            "Optional output path for a paper_id-to-output_run_dir JSON map consumable by "
            "build_evidence_grounding_benchmark_manifests_from_release_package.py --run-dir-map."
        ),
    )
    parser.add_argument(
        "--reviewed-fixtures-dir",
        default="",
        help=(
            "Optional directory of approved claim/evidence reviewed fixtures. Matching fixtures are "
            "packaged into copied output run dirs before scorecards are built."
        ),
    )
    parser.add_argument(
        "--require-reviewed-fixtures",
        action="store_true",
        help="Fail an item when --reviewed-fixtures-dir has no matching fixture for that paper/run.",
    )
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--no-scorecards", action="store_true", help="Only derive input sidecars, not scorecards.")
    args = parser.parse_args()

    items = _load_items(args)
    out = Path(args.out).expanduser().resolve() if args.out else None
    run_dir_map_out = Path(args.run_dir_map_out).expanduser().resolve() if args.run_dir_map_out else None
    report = build_evidence_grounding_scorecard_input_backfill_report(
        items=items,
        out_run_root=Path(args.out_run_root),
        reviewed_fixtures_dir=Path(args.reviewed_fixtures_dir) if args.reviewed_fixtures_dir else None,
        require_reviewed_fixtures=args.require_reviewed_fixtures,
        overwrite=args.overwrite,
        write_scorecards=not args.no_scorecards,
        out=out,
        run_dir_map_out=run_dir_map_out,
    )
    print("[evidence_grounding_scorecard_input_backfill] " f"item_count={report.item_count}")
    print("[evidence_grounding_scorecard_input_backfill] " f"pass_count={report.pass_count}")
    print("[evidence_grounding_scorecard_input_backfill] " f"fail_count={report.fail_count}")
    print(
        "[evidence_grounding_scorecard_input_backfill] "
        f"scorecard_readiness=pass={report.scorecard_pass_count} "
        f"warn={report.scorecard_warn_count} fail={report.scorecard_fail_count}"
    )
    failed_scorecards = [
        _scorecard_failure_stdout_detail(item)
        for item in report.items
        if item.scorecard_readiness_status == "fail"
    ]
    if failed_scorecards:
        shown = failed_scorecards[:10]
        suffix = f";...{len(failed_scorecards) - len(shown)}_more" if len(failed_scorecards) > len(shown) else ""
        print(
            "[evidence_grounding_scorecard_input_backfill] "
            f"scorecard_failures={';'.join(shown)}{suffix}"
        )
    print(
        "[evidence_grounding_scorecard_input_backfill] "
        f"out_run_root={mask_local_paths_in_text(report.out_run_root)}"
    )
    if out is not None:
        print("[evidence_grounding_scorecard_input_backfill] " f"out={mask_local_paths_in_text(str(out))}")
    if run_dir_map_out is not None:
        print(
            "[evidence_grounding_scorecard_input_backfill] "
            f"run_dir_map_out={mask_local_paths_in_text(str(run_dir_map_out))}"
        )
    if report.reviewed_fixtures_dir:
        print(
            "[evidence_grounding_scorecard_input_backfill] "
            f"reviewed_fixtures_dir={mask_local_paths_in_text(report.reviewed_fixtures_dir)}"
        )
    return 0 if report.fail_count == 0 and report.scorecard_fail_count == 0 else 1


def _load_items(args: argparse.Namespace) -> list[EvidenceGroundingScorecardInputBackfillItemRequest]:
    raw_items: list[dict] = []
    if args.items_json:
        payload = json.loads(Path(args.items_json).expanduser().read_text(encoding="utf-8"))
        if not isinstance(payload, list):
            raise ValueError("--items-json must contain a list")
        raw_items.extend(payload)
    for raw in args.item:
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            raise ValueError("--item must be a JSON object")
        raw_items.append(payload)
    items = [EvidenceGroundingScorecardInputBackfillItemRequest.model_validate(item) for item in raw_items]
    items.extend(
        load_scorecard_input_backfill_items_from_benchmark_artifacts(
            benchmark_manifest_paths=[Path(path) for path in args.benchmark_manifest],
            benchmark_manifest_package_paths=[Path(path) for path in args.benchmark_manifest_package],
        )
    )
    return items


def _scorecard_failure_stdout_detail(item) -> str:
    detail_parts = [
        f"paper_id={item.paper_id}",
        f"output_name={Path(item.output_run_dir).name or '-'}",
        f"reason_codes={','.join(item.scorecard_reason_codes) or '-'}",
    ]
    metric_detail = _scorecard_readiness_metric_stdout_detail(item.scorecard_readiness_metrics)
    if metric_detail != "-":
        detail_parts.append(f"metrics={metric_detail}")
    repair_target_detail = _scorecard_repair_target_stdout_detail(item.scorecard_repair_targets)
    if repair_target_detail != "-":
        detail_parts.append(f"repair_targets={repair_target_detail}")
    return ",".join(detail_parts)


def _scorecard_repair_target_stdout_detail(targets: list) -> str:
    parts: list[str] = []
    for target in targets[:5]:
        claim_id = str(getattr(target, "claim_id", "") or "").strip()
        span_index = getattr(target, "span_index", None)
        resolution = str(getattr(target, "resolution", "") or "UNKNOWN").strip() or "UNKNOWN"
        if not claim_id or not isinstance(span_index, int):
            continue
        parts.append(f"{claim_id}#{span_index}:{resolution}")
    if len(targets) > len(parts):
        parts.append(f"...{len(targets) - len(parts)}_more")
    return ",".join(parts) if parts else "-"


def _scorecard_readiness_metric_stdout_detail(metrics: dict) -> str:
    metric_names = (
        "grounded_evidence_ratio",
        "page_coverage_ratio",
        "missing_topic_signal_count",
        "duplicate_cluster_count",
        "low_overlap_claim_rate",
        "grounded_extraction_ref_rate",
    )
    parts: list[str] = []
    for metric_name in metric_names:
        metric = metrics.get(metric_name)
        if metric is None or metric.status != "available" or not isinstance(metric.value, (int, float)):
            continue
        parts.append(f"{metric_name}:{metric.value:g}")
    return ",".join(parts) if parts else "-"


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ValueError as exc:
        print(
            f"[evidence_grounding_scorecard_input_backfill] error={mask_local_paths_in_text(str(exc))}",
            file=sys.stderr,
        )
        raise SystemExit(2) from exc
