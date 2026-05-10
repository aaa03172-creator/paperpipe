#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.services.bioasq_eval import (  # noqa: E402
    load_bioasq_rerank_labels,
    run_bioasq_rerank_experiment,
    write_bioasq_rerank_experiment_report,
)


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"invalid_json_object={path}")
    return payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run a bounded rerank experiment from BioASQ-style rerank labels.",
    )
    parser.add_argument("--labels", required=True, help="Path to BioASQ rerank labels JSONL.")
    parser.add_argument("--out", required=True, help="Path where the rerank experiment report should be written.")
    parser.add_argument(
        "--metrics-path",
        default="",
        help="Optional metrics.json path to backfill with rerank experiment summary.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    labels_path = Path(args.labels).expanduser().resolve()
    report_path = Path(args.out).expanduser().resolve()

    labels = load_bioasq_rerank_labels(labels_path)
    report = run_bioasq_rerank_experiment(labels)
    write_bioasq_rerank_experiment_report(report, report_path)

    if args.metrics_path:
        metrics_path = Path(args.metrics_path).expanduser().resolve()
        if metrics_path.exists():
            metrics = _load_json(metrics_path)
            metrics["bioasq_rerank_experiment"] = {
                "question_count": report.question_count,
                "row_count": report.row_count,
                "original_top_1_hit_rate": report.original_top_1_hit_rate,
                "reranked_top_1_hit_rate": report.reranked_top_1_hit_rate,
                "original_mrr": report.original_mrr,
                "reranked_mrr": report.reranked_mrr,
                "original_map": report.original_map,
                "reranked_map": report.reranked_map,
                "original_ndcg_at_10": report.original_ndcg_at_10,
                "reranked_ndcg_at_10": report.reranked_ndcg_at_10,
            }
            metrics_path.write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")

    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
