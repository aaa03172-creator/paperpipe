#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
import shutil
from pathlib import Path
from typing import Any
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.services.runtime_paths import research_dna_root as default_research_dna_root
from src.services.runtime_paths import search_eval_root as default_search_eval_root
from src.profiles.research_dna_schema import RunLogEntry
from src.profiles.research_dna_store import append_run_log, load_external_benchmark_manifest_from_path, load_research_dna


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"invalid_json_object={path}")
    return payload


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _resolve_run_dir(*, run_dir: Path | None, run_id: str | None, search_eval_root: Path) -> Path:
    if run_dir:
        return run_dir.expanduser().resolve()
    if not run_id:
        raise ValueError("Either run_dir or run_id must be provided")
    return (search_eval_root / run_id).expanduser().resolve()


def _screening_log_path(research_dna_root: Path, dna_id: str) -> Path:
    return research_dna_root / dna_id / "logs" / "screening.jsonl"


def _normalize_search_identifier(value: Any) -> str | None:
    if value is None:
        return None
    raw = str(value).strip().lower()
    if not raw:
        return None
    if raw.startswith("doi:"):
        return raw[4:]
    if raw.startswith("pmid:"):
        return raw
    if raw.isdigit():
        return f"pmid:{raw}"
    if "/" in raw and raw.startswith("10."):
        return raw
    return raw


def _row_identifier_tokens(row: dict[str, Any]) -> set[str]:
    tokens: set[str] = set()
    for value in (row.get("candidate_id"), row.get("paper_id"), row.get("doi"), row.get("id")):
        normalized = _normalize_search_identifier(value)
        if normalized:
            tokens.add(normalized)
    return tokens


def _compute_goldset_recall(research_dna_root: Path, dna_id: str, retrieved_rows: list[dict[str, Any]]) -> tuple[float | None, int, int]:
    try:
        dna = load_research_dna(dna_id, research_dna_root)
    except FileNotFoundError:
        return None, 0, 0

    goldset = list(dna.pilot.goldset or [])
    if not goldset:
        return None, 0, 0

    goldset_tokens: list[str] = []
    seen_goldset_tokens: set[str] = set()
    for token in (_normalize_search_identifier(item) for item in goldset):
        if not token or token in seen_goldset_tokens:
            continue
        seen_goldset_tokens.add(token)
        goldset_tokens.append(token)
    if not goldset_tokens:
        return None, 0, 0

    retrieved_tokens: set[str] = set()
    for row in retrieved_rows:
        retrieved_tokens.update(_row_identifier_tokens(row))

    hit_count = sum(1 for token in goldset_tokens if token in retrieved_tokens)
    total = len(goldset_tokens)
    return (hit_count / total) if total else None, hit_count, total


def _compute_manifest_recall(
    manifest_path: Path | None,
    retrieved_rows: list[dict[str, Any]],
) -> tuple[float | None, int, int, str | None]:
    if not manifest_path:
        return None, 0, 0, None

    manifest = load_external_benchmark_manifest_from_path(manifest_path)
    included_tokens: list[str] = []
    seen_tokens: set[str] = set()
    for study in manifest.studies:
        if study.decision != "include":
            continue
        token = _normalize_search_identifier(study.identifier)
        if not token or token in seen_tokens:
            continue
        seen_tokens.add(token)
        included_tokens.append(token)

    if not included_tokens:
        return None, 0, 0, str(manifest_path)

    retrieved_tokens: set[str] = set()
    for row in retrieved_rows:
        retrieved_tokens.update(_row_identifier_tokens(row))

    hit_count = sum(1 for token in included_tokens if token in retrieved_tokens)
    total = len(included_tokens)
    return ((hit_count / total) if total else None), hit_count, total, str(manifest_path)


def _metric_delta(current: float | None, baseline: float | None) -> float | None:
    if current is None or baseline is None:
        return None
    return float(current) - float(baseline)


def _share(count: int, total: int) -> float:
    return (float(count) / float(total)) if total else 0.0


def _build_refinement_report(
    *,
    screening_rows: list[dict[str, Any]],
    include_count: int,
    exclude_count: int,
    unclear_count: int,
    labeled_count: int,
    top_reason_codes: list[str],
) -> dict[str, Any]:
    reason_counter = Counter(str(row.get("reason_code") or "") for row in screening_rows if row.get("reason_code"))
    reason_code_counts = [
        {
            "reason_code": reason_code,
            "count": count,
            "share": _share(count, labeled_count),
        }
        for reason_code, count in reason_counter.most_common(5)
    ]
    return {
        "decision_counts": {
            "include": include_count,
            "exclude": exclude_count,
            "unclear": unclear_count,
        },
        "decision_shares": {
            "include": _share(include_count, labeled_count),
            "exclude": _share(exclude_count, labeled_count),
            "unclear": _share(unclear_count, labeled_count),
        },
        "reason_code_counts": reason_code_counts,
        "refinement_focus_reason_codes": list(top_reason_codes),
    }


def _baseline_target_paths(promote_dir: Path, dna_id: str, run_id: str) -> tuple[Path, Path]:
    base_dir = promote_dir / dna_id
    history_dir = base_dir / "history"
    history_dir.mkdir(parents=True, exist_ok=True)
    history_path = history_dir / f"{run_id}.metrics.json"
    if history_path.exists():
        while True:
            timestamp = _now_utc().strftime("%Y%m%dT%H%M%S%fZ")
            candidate = history_dir / f"{run_id}__{timestamp}.metrics.json"
            if not candidate.exists():
                history_path = candidate
                break
    current_path = base_dir / "current.metrics.json"
    return history_path, current_path


def _resolved_current_baseline_path(promote_dir: Path, dna_id: str) -> Path:
    return promote_dir / dna_id / "current.metrics.json"


def _manifest_actor_type(manifest: dict[str, Any]) -> str:
    actor_type = str(manifest.get("actor_type") or "")
    return actor_type if actor_type in {"human_cli", "human_api", "system", "agent"} else "system"


def _manifest_actor_id(manifest: dict[str, Any]) -> str:
    actor_id = str(manifest.get("actor_id") or "").strip()
    return actor_id or "evaluate_search"


def _manifest_run_status(manifest: dict[str, Any]) -> str:
    status = str(manifest.get("status") or "").strip()
    return status if status in {"started", "completed", "partial", "failed"} else "completed"


def _manifest_pilot_n(manifest: dict[str, Any]) -> int:
    try:
        pilot_n = int(manifest.get("pilot_n") or 30)
    except (TypeError, ValueError):
        pilot_n = 30
    return pilot_n if pilot_n >= 20 else 30


def _compare_against_baseline(
    *,
    baseline: dict[str, Any],
    metrics: dict[str, Any],
    min_labeled_count: int,
    min_precision_delta: float,
    min_goldset_recall_delta: float,
    min_external_benchmark_recall_delta: float,
    allow_missing_goldset: bool,
    allow_missing_external_benchmark: bool,
) -> dict[str, Any]:
    baseline_precision = baseline.get("precision_proxy")
    current_precision = metrics.get("precision_proxy")
    baseline_goldset = baseline.get("goldset_recall")
    current_goldset = metrics.get("goldset_recall")
    baseline_external_benchmark = baseline.get("external_benchmark_recall")
    current_external_benchmark = metrics.get("external_benchmark_recall")

    checks = [
        {
            "name": "min_labeled_count",
            "baseline": None,
            "current": metrics.get("labeled_count"),
            "required": min_labeled_count,
            "passed": int(metrics.get("labeled_count") or 0) >= int(min_labeled_count),
        },
        {
            "name": "precision_proxy_delta",
            "baseline": baseline_precision,
            "current": current_precision,
            "required": (float(baseline_precision or 0.0) + float(min_precision_delta)),
            "passed": float(current_precision or 0.0) >= (float(baseline_precision or 0.0) + float(min_precision_delta)),
        },
    ]

    if baseline_goldset is None or current_goldset is None:
        checks.append(
            {
                "name": "goldset_recall_delta",
                "baseline": baseline_goldset,
                "current": current_goldset,
                "required": None if allow_missing_goldset else float(baseline_goldset or 0.0) + float(min_goldset_recall_delta),
                "passed": bool(allow_missing_goldset),
                "note": "goldset optional",
            }
        )
    else:
        checks.append(
            {
                "name": "goldset_recall_delta",
                "baseline": baseline_goldset,
                "current": current_goldset,
                "required": float(baseline_goldset or 0.0) + float(min_goldset_recall_delta),
                "passed": float(current_goldset or 0.0) >= (float(baseline_goldset or 0.0) + float(min_goldset_recall_delta)),
            }
        )

    if baseline_external_benchmark is None or current_external_benchmark is None:
        checks.append(
            {
                "name": "external_benchmark_recall_delta",
                "baseline": baseline_external_benchmark,
                "current": current_external_benchmark,
                "required": None
                if allow_missing_external_benchmark
                else float(baseline_external_benchmark or 0.0) + float(min_external_benchmark_recall_delta),
                "passed": bool(allow_missing_external_benchmark),
                "note": "external benchmark optional",
            }
        )
    else:
        checks.append(
            {
                "name": "external_benchmark_recall_delta",
                "baseline": baseline_external_benchmark,
                "current": current_external_benchmark,
                "required": float(baseline_external_benchmark or 0.0) + float(min_external_benchmark_recall_delta),
                "passed": float(current_external_benchmark or 0.0)
                >= (float(baseline_external_benchmark or 0.0) + float(min_external_benchmark_recall_delta)),
            }
        )

    failed_checks = [check["name"] for check in checks if not check["passed"]]
    return {
        "policy": {
            "min_labeled_count": min_labeled_count,
            "min_precision_delta": min_precision_delta,
            "min_goldset_recall_delta": min_goldset_recall_delta,
            "min_external_benchmark_recall_delta": min_external_benchmark_recall_delta,
            "allow_missing_goldset": allow_missing_goldset,
            "allow_missing_external_benchmark": allow_missing_external_benchmark,
        },
        "checks": checks,
        "failed_checks": failed_checks,
        "keep_discard": "KEEP" if not failed_checks else "DISCARD",
    }


def _build_decision_summary(*, metrics: dict[str, Any], comparison: dict[str, Any]) -> dict[str, Any]:
    blocking_checks = [check for check in comparison["checks"] if not check["passed"]]
    passed_checks = [check for check in comparison["checks"] if check["passed"]]
    refinement_report = metrics.get("refinement_report") or {}
    return {
        "keep_discard": comparison["keep_discard"],
        "blocking_checks": blocking_checks,
        "passed_checks": passed_checks,
        "metrics_snapshot": {
            "labeled_count": metrics.get("labeled_count"),
            "precision_proxy": metrics.get("precision_proxy"),
            "goldset_recall": metrics.get("goldset_recall"),
            "external_benchmark_recall": metrics.get("external_benchmark_recall"),
            "top_reason_codes": metrics.get("top_reason_codes"),
        },
        "refinement_focus_reason_codes": list(refinement_report.get("refinement_focus_reason_codes") or []),
    }


def evaluate_search_run(
    *,
    run_dir: Path | None = None,
    run_id: str | None = None,
    search_eval_root: Path | None = None,
    research_dna_root: Path | None = None,
    baseline_metrics_path: Path | None = None,
    external_benchmark_manifest_path: Path | None = None,
    out_diff_path: Path | None = None,
    promote_dir: Path | None = None,
    seed_baseline_if_missing: bool = False,
    min_labeled_count: int = 1,
    min_precision_delta: float = 0.0,
    min_goldset_recall_delta: float = 0.0,
    min_external_benchmark_recall_delta: float = 0.0,
    allow_missing_goldset: bool = True,
    allow_missing_external_benchmark: bool = True,
) -> dict[str, Any]:
    resolved_search_eval_root = (search_eval_root or default_search_eval_root()).expanduser().resolve()
    resolved_research_dna_root = (research_dna_root or default_research_dna_root()).expanduser().resolve()
    resolved_run_dir = _resolve_run_dir(run_dir=run_dir, run_id=run_id, search_eval_root=resolved_search_eval_root)

    manifest_path = resolved_run_dir / "manifest.json"
    queries_path = resolved_run_dir / "queries.json"
    retrieved_path = resolved_run_dir / "retrieved.jsonl"
    screening_queue_path = resolved_run_dir / "screening_queue.jsonl"
    metrics_path = resolved_run_dir / "metrics.json"

    manifest = _load_json(manifest_path)
    _load_json(queries_path)
    retrieved_rows = _load_jsonl(retrieved_path)
    screening_queue_rows = _load_jsonl(screening_queue_path)
    existing_metrics = _load_json(metrics_path) if metrics_path.exists() else {}

    dna_id = str(manifest.get("dna_id") or "")
    resolved_run_id = str(manifest.get("run_id") or resolved_run_dir.name)
    if not dna_id:
        raise RuntimeError(f"manifest_missing_dna_id={manifest_path}")

    screening_rows = [
        row
        for row in _load_jsonl(_screening_log_path(resolved_research_dna_root, dna_id))
        if str(row.get("run_id") or "") == resolved_run_id and str(row.get("dna_id") or "") == dna_id
    ]

    labeled_count = len(screening_rows)
    include_count = sum(1 for row in screening_rows if row.get("decision") == "include")
    exclude_count = sum(1 for row in screening_rows if row.get("decision") == "exclude")
    unclear_count = sum(1 for row in screening_rows if row.get("decision") == "unclear")
    precision_proxy = (include_count / labeled_count) if labeled_count else 0.0
    top_reason_codes = [
        code
        for code, _count in Counter(str(row.get("reason_code") or "") for row in screening_rows if row.get("reason_code")).most_common(5)
    ]

    retrieved_count = len(retrieved_rows)
    deduped_count = len(screening_queue_rows)
    dedupe_rate = max(0.0, 1.0 - (deduped_count / retrieved_count)) if retrieved_count else 0.0

    goldset_recall, goldset_hit_count, goldset_total = _compute_goldset_recall(
        resolved_research_dna_root,
        dna_id,
        retrieved_rows,
    )
    external_benchmark_recall, external_benchmark_hit_count, external_benchmark_total, resolved_external_benchmark_manifest = (
        _compute_manifest_recall(
            external_benchmark_manifest_path.expanduser().resolve() if external_benchmark_manifest_path else None,
            retrieved_rows,
        )
    )

    metrics = {
        "schema_version": "search_eval.v1",
        "run_id": resolved_run_id,
        "dna_id": dna_id,
        "retrieved_count": retrieved_count,
        "deduped_count": deduped_count,
        "dedupe_rate": dedupe_rate,
        "labeled_count": labeled_count,
        "include_count": include_count,
        "exclude_count": exclude_count,
        "unclear_count": unclear_count,
        "precision_proxy": precision_proxy,
        "goldset_recall": goldset_recall,
        "goldset_hit_count": goldset_hit_count,
        "goldset_total": goldset_total,
        "external_benchmark_recall": external_benchmark_recall,
        "external_benchmark_hit_count": external_benchmark_hit_count,
        "external_benchmark_total": external_benchmark_total,
        "top_reason_codes": top_reason_codes,
        "refinement_report": _build_refinement_report(
            screening_rows=screening_rows,
            include_count=include_count,
            exclude_count=exclude_count,
            unclear_count=unclear_count,
            labeled_count=labeled_count,
            top_reason_codes=top_reason_codes,
        ),
        "inputs": {
            "manifest": str(manifest_path),
            "queries": str(queries_path),
            "retrieved": str(retrieved_path),
            "screening_queue": str(screening_queue_path),
            "screening_log": str(_screening_log_path(resolved_research_dna_root, dna_id)),
            "external_benchmark_manifest": resolved_external_benchmark_manifest,
        },
    }
    _write_json(metrics_path, metrics)
    append_run_log(
        dna_id,
        RunLogEntry(
            ts=_now_utc(),
            run_id=resolved_run_id,
            dna_id=dna_id,
            query_version=str(manifest.get("query_version") or "v1"),
            status=_manifest_run_status(manifest),
            actor_type=_manifest_actor_type(manifest),
            actor_id=_manifest_actor_id(manifest),
            sources=list(manifest.get("active_sources") or []),
            retrieved_count=retrieved_count,
            deduped_count=deduped_count,
            dedupe_rate=dedupe_rate,
            pilot_n=_manifest_pilot_n(manifest),
            labeled_count=labeled_count,
            include_count=include_count,
            exclude_count=exclude_count,
            unclear_count=unclear_count,
            precision_proxy=precision_proxy,
            goldset_recall=metrics.get("goldset_recall"),
            goldset_hit_count=metrics.get("goldset_hit_count"),
            goldset_total=metrics.get("goldset_total"),
            external_benchmark_recall=metrics.get("external_benchmark_recall"),
            external_benchmark_hit_count=metrics.get("external_benchmark_hit_count"),
            external_benchmark_total=metrics.get("external_benchmark_total"),
            top_reason_codes=top_reason_codes,
        ),
        resolved_research_dna_root,
    )

    resolved_promote_dir = promote_dir.expanduser().resolve() if promote_dir else None
    resolved_baseline_metrics_path = baseline_metrics_path.expanduser().resolve() if baseline_metrics_path else None
    if not resolved_baseline_metrics_path and resolved_promote_dir:
        candidate_baseline = _resolved_current_baseline_path(resolved_promote_dir, dna_id)
        if candidate_baseline.exists():
            resolved_baseline_metrics_path = candidate_baseline

    diff_report: dict[str, Any] | None = None
    seed_report: dict[str, Any] | None = None
    if resolved_baseline_metrics_path:
        baseline = _load_json(resolved_baseline_metrics_path)
        baseline_snapshot_path = resolved_run_dir / "baseline_snapshot.json"
        _write_json(baseline_snapshot_path, baseline)
        comparison = _compare_against_baseline(
            baseline=baseline,
            metrics=metrics,
            min_labeled_count=min_labeled_count,
            min_precision_delta=min_precision_delta,
            min_goldset_recall_delta=min_goldset_recall_delta,
            min_external_benchmark_recall_delta=min_external_benchmark_recall_delta,
            allow_missing_goldset=allow_missing_goldset,
            allow_missing_external_benchmark=allow_missing_external_benchmark,
        )
        diff_report = {
            "schema_version": "search_eval_diff.v1",
            "baseline_metrics_path": str(resolved_baseline_metrics_path),
            "baseline_snapshot_path": str(baseline_snapshot_path),
            "run_metrics_path": str(metrics_path),
            "decision": {
                "precision_proxy": {
                    "baseline": baseline.get("precision_proxy"),
                    "current": metrics.get("precision_proxy"),
                    "delta": _metric_delta(metrics.get("precision_proxy"), baseline.get("precision_proxy")),
                },
                "goldset_recall": {
                    "baseline": baseline.get("goldset_recall"),
                    "current": metrics.get("goldset_recall"),
                    "delta": _metric_delta(metrics.get("goldset_recall"), baseline.get("goldset_recall")),
                },
                "external_benchmark_recall": {
                    "baseline": baseline.get("external_benchmark_recall"),
                    "current": metrics.get("external_benchmark_recall"),
                    "delta": _metric_delta(
                        metrics.get("external_benchmark_recall"), baseline.get("external_benchmark_recall")
                    ),
                },
                "retrieved_count": {
                    "baseline": baseline.get("retrieved_count"),
                    "current": metrics.get("retrieved_count"),
                    "delta": _metric_delta(metrics.get("retrieved_count"), baseline.get("retrieved_count")),
                },
                "deduped_count": {
                    "baseline": baseline.get("deduped_count"),
                    "current": metrics.get("deduped_count"),
                    "delta": _metric_delta(metrics.get("deduped_count"), baseline.get("deduped_count")),
                },
            },
            "policy": comparison["policy"],
            "checks": comparison["checks"],
            "failed_checks": comparison["failed_checks"],
            "keep_discard": comparison["keep_discard"],
            "decision_summary": _build_decision_summary(metrics=metrics, comparison=comparison),
        }
        if resolved_promote_dir and diff_report["keep_discard"] == "KEEP":
            promote_root = resolved_promote_dir
            history_path, current_path = _baseline_target_paths(promote_root, dna_id, resolved_run_id)
            history_path.parent.mkdir(parents=True, exist_ok=True)
            current_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(metrics_path, history_path)
            shutil.copy2(metrics_path, current_path)
            diff_report["promotion"] = {
                "promoted": True,
                "history_path": str(history_path),
                "current_path": str(current_path),
            }
        else:
            diff_report["promotion"] = {
                "promoted": False,
                "history_path": None,
                "current_path": None,
            }
        target_diff_path = out_diff_path or (resolved_run_dir / "diff.json")
        _write_json(target_diff_path, diff_report)
    elif resolved_promote_dir and seed_baseline_if_missing:
        history_path, current_path = _baseline_target_paths(resolved_promote_dir, dna_id, resolved_run_id)
        history_path.parent.mkdir(parents=True, exist_ok=True)
        current_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(metrics_path, history_path)
        shutil.copy2(metrics_path, current_path)
        seed_report = {
            "seeded": True,
            "history_path": str(history_path),
            "current_path": str(current_path),
        }

    return {
        "metrics_path": str(metrics_path),
        "diff_path": str((out_diff_path or (resolved_run_dir / "diff.json")).resolve()) if diff_report else None,
        "metrics": metrics,
        "diff": diff_report,
        "seed": seed_report,
    }


def _now_utc():
    return datetime.now(timezone.utc)


def main() -> int:
    parser = argparse.ArgumentParser(description="Recompute and compare fixed search evaluation metrics for a Research DNA pilot run.")
    parser.add_argument("--run-dir", default="", help="Search eval run directory")
    parser.add_argument("--run-id", default="", help="Search eval run ID under the search eval root")
    parser.add_argument("--search-eval-root", default=str(default_search_eval_root()), help="Search eval root directory")
    parser.add_argument("--research-dna-root", default=str(default_research_dna_root()), help="Research DNA root directory")
    parser.add_argument("--baseline-metrics", default="", help="Optional baseline metrics.json path")
    parser.add_argument("--external-benchmark-manifest", default="", help="Optional adjudicated external benchmark manifest path")
    parser.add_argument("--out-diff", default="", help="Optional explicit diff output path")
    parser.add_argument("--promote-dir", default="", help="Optional baseline promotion directory")
    parser.add_argument("--seed-baseline-if-missing", action="store_true", help="Seed current/history baseline if none exists under promote-dir")
    parser.add_argument("--min-labeled-count", type=int, default=1, help="Minimum labeled_count required for KEEP")
    parser.add_argument("--min-precision-delta", type=float, default=0.0, help="Required precision_proxy improvement over baseline")
    parser.add_argument("--min-goldset-recall-delta", type=float, default=0.0, help="Required goldset_recall improvement when goldset exists")
    parser.add_argument(
        "--min-external-benchmark-recall-delta",
        type=float,
        default=0.0,
        help="Required external_benchmark_recall improvement when an adjudicated external benchmark manifest is present",
    )
    parser.add_argument("--require-goldset", action="store_true", help="Fail comparison if goldset_recall is missing on either side")
    parser.add_argument(
        "--require-external-benchmark",
        action="store_true",
        help="Fail comparison if external_benchmark_recall is missing on either side",
    )
    args = parser.parse_args()

    result = evaluate_search_run(
        run_dir=Path(args.run_dir).expanduser().resolve() if args.run_dir else None,
        run_id=args.run_id or None,
        search_eval_root=Path(args.search_eval_root).expanduser().resolve(),
        research_dna_root=Path(args.research_dna_root).expanduser().resolve(),
        baseline_metrics_path=Path(args.baseline_metrics).expanduser().resolve() if args.baseline_metrics else None,
        external_benchmark_manifest_path=(
            Path(args.external_benchmark_manifest).expanduser().resolve() if args.external_benchmark_manifest else None
        ),
        out_diff_path=Path(args.out_diff).expanduser().resolve() if args.out_diff else None,
        promote_dir=Path(args.promote_dir).expanduser().resolve() if args.promote_dir else None,
        seed_baseline_if_missing=bool(args.seed_baseline_if_missing),
        min_labeled_count=int(args.min_labeled_count),
        min_precision_delta=float(args.min_precision_delta),
        min_goldset_recall_delta=float(args.min_goldset_recall_delta),
        min_external_benchmark_recall_delta=float(args.min_external_benchmark_recall_delta),
        allow_missing_goldset=not bool(args.require_goldset),
        allow_missing_external_benchmark=not bool(args.require_external_benchmark),
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
