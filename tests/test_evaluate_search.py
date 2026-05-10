from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from scripts.evaluate_search import evaluate_search_run
from src.profiles.research_dna_schema import (
    ExternalBenchmarkManifest,
    ExternalBenchmarkStudyDecision,
    PilotConfig,
    QueryVersion,
    ResearchDNA,
)
from src.profiles.research_dna_store import save_external_benchmark_manifest, save_research_dna


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False))
            handle.write("\n")


def _sample_dna(*, goldset: list[str] | None = None) -> ResearchDNA:
    return ResearchDNA(
        id="dna_test",
        title="Mild cognitive impairment and medium-chain triglycerides",
        intent="systematic_review",
        pilot=PilotConfig(n=30, goldset=list(goldset or [])),
        query_versions=[
            QueryVersion(
                version="v1",
                mode="recall",
                per_db={"pubmed": "(\"mild cognitive impairment\") AND (\"medium-chain triglycerides\")"},
                change_summary="initial draft",
                created_at=datetime(2026, 3, 11, tzinfo=timezone.utc),
                created_by="human_cli:tester",
            )
        ],
    )


def test_evaluate_search_run_recomputes_metrics_from_screening_log(tmp_path):
    search_eval_root = tmp_path / "search_eval"
    research_dna_root = tmp_path / "research_dna"
    run_dir = search_eval_root / "pilot_001"
    _write_json(
        run_dir / "manifest.json",
        {
            "run_id": "pilot_001",
            "dna_id": "dna_test",
        },
    )
    _write_json(run_dir / "queries.json", {"queries": {"pubmed": "test"}})
    _write_jsonl(
        run_dir / "retrieved.jsonl",
        [
            {"candidate_id": "pmid:1"},
            {"candidate_id": "pmid:2"},
            {"candidate_id": "doi:10.1000/abc"},
        ],
    )
    _write_jsonl(
        run_dir / "screening_queue.jsonl",
        [
            {"candidate_id": "pmid:1"},
            {"candidate_id": "pmid:2"},
        ],
    )
    _write_json(run_dir / "metrics.json", {"goldset_recall": None})
    _write_jsonl(
        research_dna_root / "dna_test" / "logs" / "screening.jsonl",
        [
            {"dna_id": "dna_test", "run_id": "pilot_001", "decision": "include", "reason_code": "wrong_population"},
            {"dna_id": "dna_test", "run_id": "pilot_001", "decision": "exclude", "reason_code": "wrong_population"},
            {"dna_id": "dna_test", "run_id": "pilot_001", "decision": "unclear", "reason_code": "insufficient_metadata"},
            {"dna_id": "dna_test", "run_id": "other", "decision": "include", "reason_code": "duplicate"},
        ],
    )

    result = evaluate_search_run(run_dir=run_dir, research_dna_root=research_dna_root)

    assert result["metrics"]["retrieved_count"] == 3
    assert result["metrics"]["deduped_count"] == 2
    assert result["metrics"]["labeled_count"] == 3
    assert result["metrics"]["include_count"] == 1
    assert result["metrics"]["precision_proxy"] == 1 / 3
    assert result["metrics"]["top_reason_codes"] == ["wrong_population", "insufficient_metadata"]
    assert result["metrics"]["refinement_report"]["decision_counts"] == {
        "include": 1,
        "exclude": 1,
        "unclear": 1,
    }
    assert result["metrics"]["refinement_report"]["decision_shares"] == {
        "include": 1 / 3,
        "exclude": 1 / 3,
        "unclear": 1 / 3,
    }
    assert result["metrics"]["refinement_report"]["reason_code_counts"] == [
        {"reason_code": "wrong_population", "count": 2, "share": 2 / 3},
        {"reason_code": "insufficient_metadata", "count": 1, "share": 1 / 3},
    ]
    assert result["metrics"]["refinement_report"]["refinement_focus_reason_codes"] == [
        "wrong_population",
        "insufficient_metadata",
    ]

    run_log_path = research_dna_root / "dna_test" / "logs" / "runs.jsonl"
    run_rows = [json.loads(line) for line in run_log_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert run_rows[-1]["run_id"] == "pilot_001"
    assert run_rows[-1]["status"] == "completed"
    assert run_rows[-1]["labeled_count"] == 3
    assert run_rows[-1]["precision_proxy"] == 1 / 3


def test_evaluate_search_run_computes_goldset_recall_from_research_dna_profile(tmp_path):
    search_eval_root = tmp_path / "search_eval"
    research_dna_root = tmp_path / "research_dna"
    run_dir = search_eval_root / "pilot_goldset"
    save_research_dna(
        _sample_dna(goldset=["PMID:1", "10.1000/abc", "doi:10.1000/miss", "PMID:1"]),
        research_dna_root,
    )
    _write_json(
        run_dir / "manifest.json",
        {
            "run_id": "pilot_goldset",
            "dna_id": "dna_test",
        },
    )
    _write_json(run_dir / "queries.json", {"queries": {"pubmed": "test"}})
    _write_jsonl(
        run_dir / "retrieved.jsonl",
        [
            {"candidate_id": "pmid:1"},
            {"paper_id": "PMID:2"},
            {"doi": "10.1000/abc"},
        ],
    )
    _write_jsonl(run_dir / "screening_queue.jsonl", [{"candidate_id": "pmid:1"}])
    _write_json(run_dir / "metrics.json", {"goldset_recall": None})
    _write_jsonl(
        research_dna_root / "dna_test" / "logs" / "screening.jsonl",
        [
            {"dna_id": "dna_test", "run_id": "pilot_goldset", "decision": "include", "reason_code": "wrong_population"},
        ],
    )

    result = evaluate_search_run(run_dir=run_dir, research_dna_root=research_dna_root)

    assert result["metrics"]["goldset_total"] == 3
    assert result["metrics"]["goldset_hit_count"] == 2
    assert result["metrics"]["goldset_recall"] == 2 / 3


def test_evaluate_search_run_writes_diff_when_baseline_is_provided(tmp_path):
    search_eval_root = tmp_path / "search_eval"
    research_dna_root = tmp_path / "research_dna"
    run_dir = search_eval_root / "pilot_002"
    _write_json(run_dir / "manifest.json", {"run_id": "pilot_002", "dna_id": "dna_test"})
    _write_json(run_dir / "queries.json", {"queries": {"pubmed": "test"}})
    _write_jsonl(run_dir / "retrieved.jsonl", [{"candidate_id": "pmid:1"}])
    _write_jsonl(run_dir / "screening_queue.jsonl", [{"candidate_id": "pmid:1"}])
    _write_json(run_dir / "metrics.json", {"goldset_recall": 0.5})
    _write_jsonl(
        research_dna_root / "dna_test" / "logs" / "screening.jsonl",
        [{"dna_id": "dna_test", "run_id": "pilot_002", "decision": "include", "reason_code": "wrong_population"}],
    )
    baseline_path = tmp_path / "baseline_metrics.json"
    _write_json(
        baseline_path,
        {
            "precision_proxy": 0.5,
            "goldset_recall": 0.25,
            "retrieved_count": 2,
            "deduped_count": 2,
        },
    )

    result = evaluate_search_run(
        run_dir=run_dir,
        research_dna_root=research_dna_root,
        baseline_metrics_path=baseline_path,
    )

    diff_path = run_dir / "diff.json"
    assert diff_path.exists()
    diff = json.loads(diff_path.read_text(encoding="utf-8"))
    assert diff["keep_discard"] == "KEEP"
    assert diff["decision"]["precision_proxy"]["delta"] == 0.5
    assert diff["policy"]["min_labeled_count"] == 1
    assert diff["failed_checks"] == []
    assert diff["decision_summary"]["keep_discard"] == "KEEP"
    assert diff["decision_summary"]["blocking_checks"] == []
    assert [check["name"] for check in diff["decision_summary"]["passed_checks"]] == [
        "min_labeled_count",
        "precision_proxy_delta",
        "goldset_recall_delta",
        "external_benchmark_recall_delta",
    ]
    assert diff["decision_summary"]["metrics_snapshot"]["labeled_count"] == 1
    assert diff["decision_summary"]["metrics_snapshot"]["precision_proxy"] == 1.0
    assert diff["decision_summary"]["refinement_focus_reason_codes"] == ["wrong_population"]
    assert result["diff"]["keep_discard"] == "KEEP"


def test_evaluate_search_run_promotes_metrics_when_keep_and_promote_dir_provided(tmp_path):
    search_eval_root = tmp_path / "search_eval"
    research_dna_root = tmp_path / "research_dna"
    promote_dir = tmp_path / "baselines" / "search_eval"
    run_dir = search_eval_root / "pilot_003"
    _write_json(run_dir / "manifest.json", {"run_id": "pilot_003", "dna_id": "dna_test"})
    _write_json(run_dir / "queries.json", {"queries": {"pubmed": "test"}})
    _write_jsonl(run_dir / "retrieved.jsonl", [{"candidate_id": "pmid:1"}])
    _write_jsonl(run_dir / "screening_queue.jsonl", [{"candidate_id": "pmid:1"}])
    _write_json(run_dir / "metrics.json", {"goldset_recall": 0.5})
    _write_jsonl(
        research_dna_root / "dna_test" / "logs" / "screening.jsonl",
        [{"dna_id": "dna_test", "run_id": "pilot_003", "decision": "include", "reason_code": "wrong_population"}],
    )
    baseline_path = tmp_path / "baseline_metrics.json"
    _write_json(
        baseline_path,
        {
            "precision_proxy": 0.5,
            "goldset_recall": 0.25,
            "retrieved_count": 2,
            "deduped_count": 2,
        },
    )

    result = evaluate_search_run(
        run_dir=run_dir,
        research_dna_root=research_dna_root,
        baseline_metrics_path=baseline_path,
        promote_dir=promote_dir,
    )

    promoted_history_path = promote_dir / "dna_test" / "history" / "pilot_003.metrics.json"
    promoted_current_path = promote_dir / "dna_test" / "current.metrics.json"
    baseline_snapshot_path = run_dir / "baseline_snapshot.json"
    assert promoted_history_path.exists()
    assert promoted_current_path.exists()
    assert baseline_snapshot_path.exists()
    baseline_snapshot = json.loads(baseline_snapshot_path.read_text(encoding="utf-8"))
    assert baseline_snapshot["precision_proxy"] == 0.5
    assert baseline_snapshot["goldset_recall"] == 0.25
    assert result["diff"]["promotion"]["promoted"] is True
    assert result["diff"]["promotion"]["history_path"] == str(promoted_history_path)
    assert result["diff"]["promotion"]["current_path"] == str(promoted_current_path)
    assert result["diff"]["baseline_snapshot_path"] == str(baseline_snapshot_path)


def test_evaluate_search_run_keeps_history_append_only_for_repeated_promotion(tmp_path):
    search_eval_root = tmp_path / "search_eval"
    research_dna_root = tmp_path / "research_dna"
    promote_dir = tmp_path / "baselines" / "search_eval"
    run_dir = search_eval_root / "pilot_003_repeat"
    _write_json(run_dir / "manifest.json", {"run_id": "pilot_003_repeat", "dna_id": "dna_test"})
    _write_json(run_dir / "queries.json", {"queries": {"pubmed": "test"}})
    _write_jsonl(run_dir / "retrieved.jsonl", [{"candidate_id": "pmid:1"}])
    _write_jsonl(run_dir / "screening_queue.jsonl", [{"candidate_id": "pmid:1"}])
    _write_json(run_dir / "metrics.json", {"goldset_recall": 0.5})
    _write_jsonl(
        research_dna_root / "dna_test" / "logs" / "screening.jsonl",
        [{"dna_id": "dna_test", "run_id": "pilot_003_repeat", "decision": "include", "reason_code": "wrong_population"}],
    )
    baseline_path = tmp_path / "baseline_metrics.json"
    _write_json(
        baseline_path,
        {
            "precision_proxy": 0.5,
            "goldset_recall": 0.25,
            "retrieved_count": 2,
            "deduped_count": 2,
        },
    )

    first = evaluate_search_run(
        run_dir=run_dir,
        research_dna_root=research_dna_root,
        baseline_metrics_path=baseline_path,
        promote_dir=promote_dir,
    )
    second = evaluate_search_run(
        run_dir=run_dir,
        research_dna_root=research_dna_root,
        baseline_metrics_path=baseline_path,
        promote_dir=promote_dir,
    )

    history_dir = promote_dir / "dna_test" / "history"
    history_files = sorted(path.name for path in history_dir.glob("pilot_003_repeat*.json"))
    assert history_files[0] == "pilot_003_repeat.metrics.json"
    assert len(history_files) == 2
    assert history_files[1].startswith("pilot_003_repeat__")
    assert first["diff"]["promotion"]["history_path"] != second["diff"]["promotion"]["history_path"]


def test_evaluate_search_run_seeds_baseline_when_missing_and_requested(tmp_path):
    search_eval_root = tmp_path / "search_eval"
    research_dna_root = tmp_path / "research_dna"
    promote_dir = tmp_path / "baselines" / "search_eval"
    run_dir = search_eval_root / "pilot_003_seed"
    _write_json(run_dir / "manifest.json", {"run_id": "pilot_003_seed", "dna_id": "dna_test", "pilot_n": 20})
    _write_json(run_dir / "queries.json", {"queries": {"pubmed": "test"}})
    _write_jsonl(run_dir / "retrieved.jsonl", [{"candidate_id": "pmid:1"}])
    _write_jsonl(run_dir / "screening_queue.jsonl", [{"candidate_id": "pmid:1"}])
    _write_json(run_dir / "metrics.json", {"goldset_recall": None})
    _write_jsonl(
        research_dna_root / "dna_test" / "logs" / "screening.jsonl",
        [{"dna_id": "dna_test", "run_id": "pilot_003_seed", "decision": "include", "reason_code": "wrong_population"}],
    )

    result = evaluate_search_run(
        run_dir=run_dir,
        research_dna_root=research_dna_root,
        promote_dir=promote_dir,
        seed_baseline_if_missing=True,
    )

    promoted_history_path = promote_dir / "dna_test" / "history" / "pilot_003_seed.metrics.json"
    promoted_current_path = promote_dir / "dna_test" / "current.metrics.json"
    assert promoted_history_path.exists()
    assert promoted_current_path.exists()
    assert result["seed"]["seeded"] is True
    assert result["seed"]["history_path"] == str(promoted_history_path)
    assert result["seed"]["current_path"] == str(promoted_current_path)
    assert result["diff"] is None


def test_evaluate_search_run_auto_resolves_current_baseline_from_promote_dir(tmp_path):
    search_eval_root = tmp_path / "search_eval"
    research_dna_root = tmp_path / "research_dna"
    promote_dir = tmp_path / "baselines" / "search_eval"
    run_dir = search_eval_root / "pilot_003_auto"
    _write_json(run_dir / "manifest.json", {"run_id": "pilot_003_auto", "dna_id": "dna_test", "pilot_n": 20})
    _write_json(run_dir / "queries.json", {"queries": {"pubmed": "test"}})
    _write_jsonl(run_dir / "retrieved.jsonl", [{"candidate_id": "pmid:1"}])
    _write_jsonl(run_dir / "screening_queue.jsonl", [{"candidate_id": "pmid:1"}])
    _write_json(run_dir / "metrics.json", {"goldset_recall": 0.5})
    _write_jsonl(
        research_dna_root / "dna_test" / "logs" / "screening.jsonl",
        [{"dna_id": "dna_test", "run_id": "pilot_003_auto", "decision": "include", "reason_code": "wrong_population"}],
    )
    baseline_path = promote_dir / "dna_test" / "current.metrics.json"
    _write_json(
        baseline_path,
        {
            "precision_proxy": 0.5,
            "goldset_recall": 0.25,
            "retrieved_count": 2,
            "deduped_count": 2,
        },
    )

    result = evaluate_search_run(
        run_dir=run_dir,
        research_dna_root=research_dna_root,
        promote_dir=promote_dir,
    )

    assert result["diff"]["keep_discard"] == "KEEP"
    assert result["diff"]["baseline_metrics_path"] == str(baseline_path)


def test_evaluate_search_run_discards_when_threshold_policy_fails(tmp_path):
    search_eval_root = tmp_path / "search_eval"
    research_dna_root = tmp_path / "research_dna"
    run_dir = search_eval_root / "pilot_004"
    _write_json(run_dir / "manifest.json", {"run_id": "pilot_004", "dna_id": "dna_test"})
    _write_json(run_dir / "queries.json", {"queries": {"pubmed": "test"}})
    _write_jsonl(run_dir / "retrieved.jsonl", [{"candidate_id": "pmid:1"}])
    _write_jsonl(run_dir / "screening_queue.jsonl", [{"candidate_id": "pmid:1"}])
    _write_json(run_dir / "metrics.json", {"goldset_recall": None})
    _write_jsonl(
        research_dna_root / "dna_test" / "logs" / "screening.jsonl",
        [{"dna_id": "dna_test", "run_id": "pilot_004", "decision": "include", "reason_code": "wrong_population"}],
    )
    baseline_path = tmp_path / "baseline_metrics.json"
    _write_json(
        baseline_path,
        {
            "precision_proxy": 0.9,
            "goldset_recall": None,
            "retrieved_count": 2,
            "deduped_count": 2,
        },
    )

    result = evaluate_search_run(
        run_dir=run_dir,
        research_dna_root=research_dna_root,
        baseline_metrics_path=baseline_path,
        min_precision_delta=0.0,
        min_labeled_count=2,
    )

    assert result["diff"]["keep_discard"] == "DISCARD"
    assert "min_labeled_count" in result["diff"]["failed_checks"]


def test_evaluate_search_run_computes_external_benchmark_recall_from_manifest(tmp_path):
    search_eval_root = tmp_path / "search_eval"
    research_dna_root = tmp_path / "research_dna"
    run_dir = search_eval_root / "pilot_external_benchmark"
    save_research_dna(_sample_dna(), research_dna_root)
    save_external_benchmark_manifest(
        ExternalBenchmarkManifest(
            manifest_id="pmc11074881_subset",
            dna_id="dna_test",
            source_label="PMC11074881 adjudicated MCI subset",
            source_url="https://pmc.ncbi.nlm.nih.gov/articles/PMC11074881/",
            created_at=datetime(2026, 3, 13, tzinfo=timezone.utc),
            created_by="human_cli:tester",
            scope_note="Adjudicated subset for external benchmark sanity check",
            studies=[
                ExternalBenchmarkStudyDecision(
                    source_reference="B48",
                    title="A ketogenic drink improves cognition in mild cognitive impairment: results of a 6-month RCT.",
                    identifier="doi:10.1002/alz.12206",
                    decision="include",
                    reason="Clean MCI-only match",
                ),
                ExternalBenchmarkStudyDecision(
                    source_reference="B39",
                    title="Effects of beta-hydroxybutyrate on cognition in memory-impaired adults.",
                    identifier="doi:10.1016/S0197-4580(03)00087-3",
                    decision="exclude",
                    reason="Mixed AD/MCI population",
                ),
                ExternalBenchmarkStudyDecision(
                    source_reference="B60",
                    title="Pilot feasibility and safety study examining the effect of medium chain triglyceride supplementation in subjects with mild cognitive impairment.",
                    identifier="doi:10.1016/j.bbacli.2015.01.001",
                    decision="include",
                    reason="Clean MCI-only match",
                ),
            ],
        ),
        research_dna_root,
    )
    _write_json(
        run_dir / "manifest.json",
        {
            "run_id": "pilot_external_benchmark",
            "dna_id": "dna_test",
        },
    )
    _write_json(run_dir / "queries.json", {"queries": {"pubmed": "test"}})
    _write_jsonl(
        run_dir / "retrieved.jsonl",
        [
            {"doi": "10.1002/alz.12206"},
            {"candidate_id": "doi:10.1000/not-in-benchmark"},
        ],
    )
    _write_jsonl(run_dir / "screening_queue.jsonl", [{"candidate_id": "doi:10.1002/alz.12206"}])
    _write_json(run_dir / "metrics.json", {"external_benchmark_recall": None})
    _write_jsonl(
        research_dna_root / "dna_test" / "logs" / "screening.jsonl",
        [
            {"dna_id": "dna_test", "run_id": "pilot_external_benchmark", "decision": "include", "reason_code": "other_noise"},
        ],
    )

    manifest_path = research_dna_root / "dna_test" / "benchmarks" / "pmc11074881_subset.yaml"
    result = evaluate_search_run(
        run_dir=run_dir,
        research_dna_root=research_dna_root,
        external_benchmark_manifest_path=manifest_path,
    )

    assert result["metrics"]["external_benchmark_total"] == 2
    assert result["metrics"]["external_benchmark_hit_count"] == 1
    assert result["metrics"]["external_benchmark_recall"] == 0.5
    assert result["metrics"]["inputs"]["external_benchmark_manifest"] == str(manifest_path)
    assert result["metrics"]["refinement_report"]["refinement_focus_reason_codes"] == ["other_noise"]
    run_log_path = research_dna_root / "dna_test" / "logs" / "runs.jsonl"
    run_rows = [json.loads(line) for line in run_log_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert run_rows[-1]["external_benchmark_recall"] == 0.5
    assert run_rows[-1]["external_benchmark_hit_count"] == 1
    assert run_rows[-1]["external_benchmark_total"] == 2


def test_evaluate_search_run_discards_when_external_benchmark_policy_fails(tmp_path):
    search_eval_root = tmp_path / "search_eval"
    research_dna_root = tmp_path / "research_dna"
    run_dir = search_eval_root / "pilot_external_policy"
    save_research_dna(_sample_dna(), research_dna_root)
    save_external_benchmark_manifest(
        ExternalBenchmarkManifest(
            manifest_id="pmc11074881_subset",
            dna_id="dna_test",
            source_label="PMC11074881 adjudicated MCI subset",
            source_url="https://pmc.ncbi.nlm.nih.gov/articles/PMC11074881/",
            created_at=datetime(2026, 3, 13, tzinfo=timezone.utc),
            created_by="human_cli:tester",
            scope_note="Adjudicated subset for external benchmark sanity check",
            studies=[
                ExternalBenchmarkStudyDecision(
                    source_reference="B48",
                    title="A ketogenic drink improves cognition in mild cognitive impairment: results of a 6-month RCT.",
                    identifier="doi:10.1002/alz.12206",
                    decision="include",
                    reason="Clean MCI-only match",
                ),
                ExternalBenchmarkStudyDecision(
                    source_reference="B60",
                    title="Pilot feasibility and safety study examining the effect of medium chain triglyceride supplementation in subjects with mild cognitive impairment.",
                    identifier="doi:10.1016/j.bbacli.2015.01.001",
                    decision="include",
                    reason="Clean MCI-only match",
                ),
            ],
        ),
        research_dna_root,
    )
    _write_json(run_dir / "manifest.json", {"run_id": "pilot_external_policy", "dna_id": "dna_test"})
    _write_json(run_dir / "queries.json", {"queries": {"pubmed": "test"}})
    _write_jsonl(run_dir / "retrieved.jsonl", [{"doi": "10.1002/alz.12206"}])
    _write_jsonl(run_dir / "screening_queue.jsonl", [{"candidate_id": "doi:10.1002/alz.12206"}])
    _write_json(run_dir / "metrics.json", {"external_benchmark_recall": None})
    _write_jsonl(
        research_dna_root / "dna_test" / "logs" / "screening.jsonl",
        [{"dna_id": "dna_test", "run_id": "pilot_external_policy", "decision": "include", "reason_code": "other_noise"}],
    )
    baseline_path = tmp_path / "baseline_metrics.json"
    _write_json(
        baseline_path,
        {
            "precision_proxy": 0.5,
            "goldset_recall": None,
            "external_benchmark_recall": 0.75,
            "retrieved_count": 2,
            "deduped_count": 2,
        },
    )

    manifest_path = research_dna_root / "dna_test" / "benchmarks" / "pmc11074881_subset.yaml"
    result = evaluate_search_run(
        run_dir=run_dir,
        research_dna_root=research_dna_root,
        baseline_metrics_path=baseline_path,
        external_benchmark_manifest_path=manifest_path,
        min_external_benchmark_recall_delta=0.0,
    )

    assert result["metrics"]["external_benchmark_recall"] == 0.5
    assert result["diff"]["keep_discard"] == "DISCARD"
    assert "external_benchmark_recall_delta" in result["diff"]["failed_checks"]
    assert [check["name"] for check in result["diff"]["decision_summary"]["blocking_checks"]] == [
        "external_benchmark_recall_delta"
    ]
