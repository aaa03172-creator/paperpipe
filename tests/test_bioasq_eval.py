from __future__ import annotations

import json
from pathlib import Path
import shutil

from scripts.eval.run_bioasq_rerank_experiment import main as run_bioasq_rerank_cli
from scripts.eval.evaluate_bioasq_research_dna_run import main as run_bioasq_cli
from src.schemas.bioasq_eval import BioASQQuestion
from src.services.bioasq_eval import (
    build_bioasq_rerank_labels,
    evaluate_bioasq_screening_queue,
    load_bioasq_questions,
    run_bioasq_rerank_experiment,
    summarize_bioasq_rerank_labels,
)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False))
            handle.write("\n")


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_load_bioasq_questions_accepts_object_with_questions(tmp_path: Path) -> None:
    gold_path = tmp_path / "bioasq.json"
    _write_json(
        gold_path,
        {
            "questions": [
                {
                    "question_id": "q1",
                    "question": "Which drug targets EGFR-mutant lung cancer?",
                    "ideal_answers": ["gefitinib"],
                    "source_candidate_ids": ["PMID:123"],
                    "source_snippets": ["EGFR-mutant lung cancer responds to gefitinib."],
                }
            ]
        },
    )

    questions = load_bioasq_questions(gold_path)

    assert len(questions) == 1
    assert questions[0].question_id == "q1"


def test_evaluate_bioasq_screening_queue_scores_candidate_snippet_and_answer_hits() -> None:
    questions = [
        {
            "question_id": "q1",
            "question": "Which drug targets EGFR-mutant lung cancer?",
            "ideal_answers": ["gefitinib"],
            "exact_answers": [],
            "source_candidate_ids": ["PMID:123"],
            "source_snippets": ["EGFR-mutant lung cancer responds to gefitinib."],
        }
    ]
    screening_rows = [
        {
            "candidate_id": "pmid:123",
            "paper_id": "PMID:123",
            "title": "EGFR-mutant lung cancer and gefitinib",
            "summary": "EGFR-mutant lung cancer responds to gefitinib in this cohort.",
        },
        {
            "candidate_id": "pmid:456",
            "paper_id": "PMID:456",
            "title": "Unrelated paper",
            "summary": "No relevant answer.",
        },
    ]

    report = evaluate_bioasq_screening_queue(
        questions=_questions_from_inline(questions),
        screening_rows=screening_rows,
    )

    assert report.question_count == 1
    assert report.candidate_macro_recall == 1.0
    assert report.candidate_mrr == 1.0
    assert report.candidate_map == 1.0
    assert report.candidate_ndcg_at_10 == 1.0
    assert report.snippet_macro_recall == 1.0
    assert report.answer_alias_hit_rate == 1.0
    assert report.top_1_hit_rate == 1.0
    assert report.questions[0].first_candidate_hit_rank == 1
    assert report.questions[0].candidate_reciprocal_rank == 1.0
    assert report.questions[0].candidate_average_precision == 1.0
    assert report.questions[0].candidate_ndcg_at_10 == 1.0


def test_evaluate_bioasq_screening_queue_scores_late_candidate_hits() -> None:
    report = evaluate_bioasq_screening_queue(
        questions=_questions_from_inline(
            [
                {
                    "question_id": "q_rank",
                    "question": "Which paper supports the target answer?",
                    "ideal_answers": ["gefitinib"],
                    "exact_answers": [],
                    "source_candidate_ids": ["PMID:123"],
                    "source_snippets": [],
                }
            ]
        ),
        screening_rows=[
            {
                "candidate_id": "pmid:999",
                "paper_id": "PMID:999",
                "title": "Distractor",
                "summary": "No matching answer here.",
            },
            {
                "candidate_id": "pmid:123",
                "paper_id": "PMID:123",
                "title": "Relevant paper",
                "summary": "This row contains the supporting study.",
            },
        ],
    )

    assert report.question_count == 1
    assert report.candidate_macro_recall == 1.0
    assert report.candidate_mrr == 0.5
    assert report.candidate_map == 0.5
    assert report.candidate_ndcg_at_10 == 0.6309
    assert report.top_1_hit_rate == 0.0
    assert report.top_5_hit_rate == 1.0
    assert report.questions[0].first_candidate_hit_rank == 2
    assert report.questions[0].candidate_reciprocal_rank == 0.5
    assert report.questions[0].candidate_average_precision == 0.5
    assert report.questions[0].candidate_ndcg_at_10 == 0.6309


def test_evaluate_bioasq_screening_queue_handles_missing_gold_fields() -> None:
    report = evaluate_bioasq_screening_queue(
        questions=_questions_from_inline(
            [
                {
                    "question_id": "q2",
                    "question": "What is the key biomarker?",
                    "ideal_answers": [],
                    "exact_answers": [],
                    "source_candidate_ids": [],
                    "source_snippets": [],
                }
            ]
        ),
        screening_rows=[],
    )

    assert report.question_count == 1
    assert "q2:question_missing_source_candidate_ids" in report.warnings
    assert "q2:question_missing_source_snippets" in report.warnings


def test_evaluate_bioasq_screening_queue_uses_identifier_alias_fallback_and_url_normalization() -> None:
    report = evaluate_bioasq_screening_queue(
        questions=_questions_from_inline(
            [
                {
                    "question_id": "q_alias",
                    "question": "Which study supports gefitinib for EGFR-mutant lung cancer?",
                    "ideal_answers": ["gefitinib"],
                    "exact_answers": [],
                    "source_candidate_ids": [],
                    "source_candidate_aliases": ["https://pubmed.ncbi.nlm.nih.gov/123/"],
                    "source_snippets": ["EGFR-mutant lung cancer responds to gefitinib."],
                }
            ]
        ),
        screening_rows=[
            {
                "candidate_id": "pmid:999",
                "paper_id": "PMID:999",
                "title": "Distractor",
                "summary": "No matching answer here.",
            },
            {
                "candidate_id": "pmid:123",
                "paper_id": "PMID:123",
                "title": "Relevant paper",
                "summary": "EGFR-mutant lung cancer responds to gefitinib in this cohort.",
            },
        ],
    )

    assert report.question_count == 1
    assert report.candidate_macro_recall == 1.0
    assert report.candidate_mrr == 0.5
    assert report.questions[0].candidate_gold_count == 1
    assert report.questions[0].candidate_hit_count == 1
    assert report.questions[0].first_candidate_hit_rank == 2
    assert report.questions[0].warnings == ["question_identifier_alias_fallback_used"]
    assert "q_alias:question_identifier_alias_fallback_used" in report.warnings


def test_build_bioasq_rerank_labels_exports_ranked_rows() -> None:
    questions = _questions_from_inline(
        [
            {
                "question_id": "q_labels",
                "question": "Which drug targets EGFR-mutant lung cancer?",
                "ideal_answers": ["gefitinib"],
                "exact_answers": [],
                "source_candidate_ids": ["PMID:123"],
                "source_snippets": ["EGFR-mutant lung cancer responds to gefitinib."],
            }
        ]
    )
    screening_rows = [
        {
            "candidate_id": "pmid:999",
            "paper_id": "PMID:999",
            "title": "Distractor",
            "summary": "No matching answer here.",
        },
        {
            "candidate_id": "pmid:123",
            "paper_id": "PMID:123",
            "title": "Relevant paper",
            "summary": "EGFR-mutant lung cancer responds to gefitinib in this cohort.",
        },
    ]

    labels = build_bioasq_rerank_labels(questions=questions, screening_rows=screening_rows)
    summary = summarize_bioasq_rerank_labels(labels)

    assert len(labels) == 2
    assert labels[0].candidate_rank == 1
    assert labels[0].relevance_grade == 0
    assert labels[1].candidate_rank == 2
    assert labels[1].identifier_match is True
    assert labels[1].snippet_support is True
    assert labels[1].answer_alias_support is True
    assert labels[1].relevance_grade == 2
    assert summary == {
        "row_count": 2,
        "positive_row_count": 1,
        "strong_positive_row_count": 1,
    }


def test_build_bioasq_rerank_labels_matches_row_identifier_aliases_and_doi_urls() -> None:
    questions = _questions_from_inline(
        [
            {
                "question_id": "q_alias_labels",
                "question": "Which paper discusses gefitinib for EGFR mutant lung cancer?",
                "ideal_answers": ["gefitinib"],
                "exact_answers": [],
                "source_candidate_ids": ["doi:10.1000/abc"],
                "source_snippets": ["EGFR mutant lung cancer responds to gefitinib."],
            }
        ]
    )
    screening_rows = [
        {
            "candidate_id": "paper-1",
            "paper_id": "paper-1",
            "title": "Relevant paper",
            "summary": "EGFR mutant lung cancer responds to gefitinib in this cohort.",
            "metadata": {
                "identifier_aliases": ["https://doi.org/10.1000/ABC"],
            },
        }
    ]

    labels = build_bioasq_rerank_labels(questions=questions, screening_rows=screening_rows)

    assert len(labels) == 1
    assert labels[0].identifier_match is True
    assert labels[0].snippet_support is True
    assert labels[0].answer_alias_support is True
    assert labels[0].relevance_grade == 2


def test_run_bioasq_rerank_experiment_improves_heuristic_ordering() -> None:
    labels = build_bioasq_rerank_labels(
        questions=_questions_from_inline(
            [
                {
                    "question_id": "q_rerank",
                    "question": "Which paper discusses gefitinib for EGFR mutant lung cancer?",
                    "ideal_answers": ["gefitinib"],
                    "exact_answers": [],
                    "source_candidate_ids": ["PMID:123"],
                    "source_snippets": ["EGFR mutant lung cancer responds to gefitinib."],
                }
            ]
        ),
        screening_rows=[
            {
                "candidate_id": "pmid:999",
                "paper_id": "PMID:999",
                "title": "Liver disease review",
                "summary": "A general review with no relevant cancer treatment details.",
            },
            {
                "candidate_id": "pmid:123",
                "paper_id": "PMID:123",
                "title": "Gefitinib for EGFR mutant lung cancer",
                "summary": "EGFR mutant lung cancer responds to gefitinib in this cohort.",
            },
        ],
    )

    report = run_bioasq_rerank_experiment(labels)

    assert report.question_count == 1
    assert report.original_top_1_hit_rate == 0.0
    assert report.reranked_top_1_hit_rate == 1.0
    assert report.original_mrr == 0.5
    assert report.reranked_mrr == 1.0
    assert report.original_map == 0.5
    assert report.reranked_map == 1.0
    assert report.original_ndcg_at_10 < report.reranked_ndcg_at_10


def test_bioasq_rerank_experiment_cli_writes_report_and_updates_metrics(tmp_path: Path) -> None:
    labels_path = tmp_path / "bioasq_rerank_labels.jsonl"
    out_path = tmp_path / "bioasq_rerank_experiment.json"
    metrics_path = tmp_path / "metrics.json"

    _write_jsonl(
        labels_path,
        [
            {
                "question_id": "q_rerank",
                "question": "Which paper discusses gefitinib for EGFR mutant lung cancer?",
                "candidate_rank": 1,
                "candidate_id": "pmid:999",
                "paper_id": "PMID:999",
                "doi": "",
                "title": "Liver disease review",
                "summary": "A general review with no relevant cancer treatment details.",
                "identifier_match": False,
                "snippet_support": False,
                "answer_alias_support": False,
                "relevance_grade": 0,
                "metadata": {},
            },
            {
                "question_id": "q_rerank",
                "question": "Which paper discusses gefitinib for EGFR mutant lung cancer?",
                "candidate_rank": 2,
                "candidate_id": "pmid:123",
                "paper_id": "PMID:123",
                "doi": "",
                "title": "Gefitinib for EGFR mutant lung cancer",
                "summary": "EGFR mutant lung cancer responds to gefitinib in this cohort.",
                "identifier_match": True,
                "snippet_support": True,
                "answer_alias_support": True,
                "relevance_grade": 2,
                "metadata": {},
            },
        ],
    )
    _write_json(metrics_path, {"run_id": "pilot_001"})

    exit_code = run_bioasq_rerank_cli(
        [
            "--labels",
            str(labels_path),
            "--out",
            str(out_path),
            "--metrics-path",
            str(metrics_path),
        ]
    )

    assert exit_code == 0
    report = json.loads(out_path.read_text(encoding="utf-8"))
    assert report["original_top_1_hit_rate"] == 0.0
    assert report["reranked_top_1_hit_rate"] == 1.0
    assert report["original_mrr"] == 0.5
    assert report["reranked_mrr"] == 1.0

    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    assert metrics["bioasq_rerank_experiment"]["question_count"] == 1
    assert metrics["bioasq_rerank_experiment"]["row_count"] == 2
    assert metrics["bioasq_rerank_experiment"]["original_top_1_hit_rate"] == 0.0
    assert metrics["bioasq_rerank_experiment"]["reranked_top_1_hit_rate"] == 1.0


def test_bioasq_eval_cli_writes_report_and_updates_metrics(tmp_path: Path) -> None:
    gold_path = tmp_path / "bioasq.json"
    run_dir = tmp_path / "search_eval" / "pilot_001"
    out_path = tmp_path / "bioasq_eval.json"
    labels_out_path = tmp_path / "bioasq_rerank_labels.jsonl"

    _write_json(
        gold_path,
        {
            "questions": [
                {
                    "question_id": "q1",
                    "question": "Which drug targets EGFR-mutant lung cancer?",
                    "ideal_answers": ["gefitinib"],
                    "source_candidate_ids": ["PMID:123"],
                    "source_snippets": ["EGFR-mutant lung cancer responds to gefitinib."],
                }
            ]
        },
    )
    _write_jsonl(
        run_dir / "screening_queue.jsonl",
        [
            {
                "candidate_id": "pmid:123",
                "paper_id": "PMID:123",
                "title": "EGFR-mutant lung cancer and gefitinib",
                "summary": "EGFR-mutant lung cancer responds to gefitinib in this cohort.",
            }
        ],
    )
    _write_json(run_dir / "metrics.json", {"run_id": "pilot_001"})

    exit_code = run_bioasq_cli(
        [
            "--gold",
            str(gold_path),
            "--run-dir",
            str(run_dir),
            "--out",
            str(out_path),
            "--labels-out",
            str(labels_out_path),
        ]
    )

    assert exit_code == 0
    report = json.loads(out_path.read_text(encoding="utf-8"))
    assert report["candidate_macro_recall"] == 1.0
    assert report["candidate_mrr"] == 1.0
    assert report["candidate_map"] == 1.0
    assert report["candidate_ndcg_at_10"] == 1.0
    assert report["snippet_macro_recall"] == 1.0
    assert report["top_1_hit_rate"] == 1.0
    labels = _read_jsonl(labels_out_path)
    assert len(labels) == 1
    assert labels[0]["question_id"] == "q1"
    assert labels[0]["relevance_grade"] == 2

    metrics = json.loads((run_dir / "metrics.json").read_text(encoding="utf-8"))
    assert metrics["bioasq_eval"]["candidate_macro_recall"] == 1.0
    assert metrics["bioasq_eval"]["candidate_mrr"] == 1.0
    assert metrics["bioasq_eval"]["candidate_map"] == 1.0
    assert metrics["bioasq_eval"]["candidate_ndcg_at_10"] == 1.0
    assert metrics["bioasq_eval"]["top_10_hit_rate"] == 1.0
    assert metrics["bioasq_eval"]["rerank_labels"] == {
        "row_count": 1,
        "positive_row_count": 1,
        "strong_positive_row_count": 1,
    }


def test_bioasq_eval_cli_replays_repo_grounded_fixture(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    gold_path = (
        repo_root
        / "goldset"
        / "bioasq_eval"
        / "repo_grounded_pilot_20260410"
        / "questions"
        / "repo_grounded_questions.json"
    )
    fixture_run_dir = (
        repo_root
        / "goldset"
        / "bioasq_eval"
        / "repo_grounded_pilot_20260410"
        / "run_dir"
    )
    run_dir = tmp_path / "run_dir"
    shutil.copytree(fixture_run_dir, run_dir)

    out_path = tmp_path / "bioasq_eval.json"
    labels_out_path = tmp_path / "bioasq_rerank_labels.jsonl"

    exit_code = run_bioasq_cli(
        [
            "--gold",
            str(gold_path),
            "--run-dir",
            str(run_dir),
            "--out",
            str(out_path),
            "--labels-out",
            str(labels_out_path),
        ]
    )

    assert exit_code == 0
    report = json.loads(out_path.read_text(encoding="utf-8"))
    assert report["question_count"] == 2
    assert report["candidate_macro_recall"] == 1.0
    assert report["candidate_mrr"] == 0.4166
    assert report["candidate_map"] == 0.4166
    assert report["candidate_ndcg_at_10"] == 0.5655
    assert report["snippet_macro_recall"] == 1.0
    assert report["answer_alias_hit_rate"] == 1.0
    assert report["top_1_hit_rate"] == 0.0
    assert report["top_5_hit_rate"] == 1.0
    assert "q_repo_pubmed_alias:question_identifier_alias_fallback_used" in report["warnings"]

    labels = _read_jsonl(labels_out_path)
    assert len(labels) == 6
    strong_positive_labels = [row for row in labels if row["relevance_grade"] == 2]
    assert {row["question_id"] for row in strong_positive_labels} == {
        "q_repo_pubmed_alias",
        "q_repo_row_alias",
    }
    assert {row["candidate_id"] for row in strong_positive_labels} == {
        "pmid:123",
        "paper-local-acetate",
    }

    metrics = json.loads((run_dir / "metrics.json").read_text(encoding="utf-8"))
    assert metrics["bioasq_eval"]["question_count"] == 2
    assert metrics["bioasq_eval"]["candidate_mrr"] == 0.4166
    assert metrics["bioasq_eval"]["candidate_map"] == 0.4166
    assert metrics["bioasq_eval"]["candidate_ndcg_at_10"] == 0.5655
    assert metrics["bioasq_eval"]["rerank_labels"] == {
        "row_count": 6,
        "positive_row_count": 2,
        "strong_positive_row_count": 2,
    }


def _questions_from_inline(rows: list[dict]) -> list[BioASQQuestion]:
    return [BioASQQuestion.model_validate(row) for row in rows]
