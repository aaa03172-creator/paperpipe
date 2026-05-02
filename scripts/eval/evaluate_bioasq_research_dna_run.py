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
    build_bioasq_rerank_labels,
    evaluate_bioasq_screening_queue,
    load_bioasq_questions,
    load_screening_queue,
    summarize_bioasq_rerank_labels,
    write_bioasq_eval_report,
    write_bioasq_rerank_labels,
)


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"invalid_json_object={path}")
    return payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Evaluate a Research DNA screening_queue.jsonl against a BioASQ-style question set.",
    )
    parser.add_argument("--gold", required=True, help="Path to a BioASQ-style gold JSON file.")
    parser.add_argument("--screening-queue", default="", help="Path to screening_queue.jsonl.")
    parser.add_argument("--run-dir", default="", help="Optional Research DNA run dir containing screening_queue.jsonl and metrics.json.")
    parser.add_argument("--out", required=True, help="Path where the BioASQ eval report should be written.")
    parser.add_argument("--labels-out", default="", help="Optional path where rerank-ready label rows should be written as JSONL.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.run_dir:
        run_dir = Path(args.run_dir).expanduser().resolve()
        screening_queue_path = run_dir / "screening_queue.jsonl"
        metrics_path = run_dir / "metrics.json"
    else:
        screening_queue_path = Path(args.screening_queue).expanduser().resolve()
        metrics_path = None

    questions = load_bioasq_questions(Path(args.gold).expanduser().resolve())
    screening_rows = load_screening_queue(screening_queue_path)
    report = evaluate_bioasq_screening_queue(questions=questions, screening_rows=screening_rows)
    write_bioasq_eval_report(report, Path(args.out).expanduser().resolve())

    rerank_labels = None
    rerank_label_summary = None
    if args.labels_out:
        rerank_labels = build_bioasq_rerank_labels(questions=questions, screening_rows=screening_rows)
        write_bioasq_rerank_labels(rerank_labels, Path(args.labels_out).expanduser().resolve())
        rerank_label_summary = summarize_bioasq_rerank_labels(rerank_labels)

    if metrics_path and metrics_path.exists():
        metrics = _load_json(metrics_path)
        metrics["bioasq_eval"] = {
            "question_count": report.question_count,
            "candidate_macro_recall": report.candidate_macro_recall,
            "candidate_mrr": report.candidate_mrr,
            "candidate_map": report.candidate_map,
            "candidate_ndcg_at_10": report.candidate_ndcg_at_10,
            "snippet_macro_recall": report.snippet_macro_recall,
            "answer_alias_hit_rate": report.answer_alias_hit_rate,
            "top_1_hit_rate": report.top_1_hit_rate,
            "top_5_hit_rate": report.top_5_hit_rate,
            "top_10_hit_rate": report.top_10_hit_rate,
        }
        if rerank_label_summary is not None:
            metrics["bioasq_eval"]["rerank_labels"] = rerank_label_summary
        metrics_path.write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")

    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
