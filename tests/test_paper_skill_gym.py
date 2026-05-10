from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from evals.paper_skill_gym.compare_reports import compare_reports
from evals.paper_skill_gym.make_answer_template import build_answer_template
from evals.paper_skill_gym.run_probe_set import build_report, evaluate_probe
from evals.paper_skill_gym.schemas import ProbeAnswer, load_answers, load_probes


def test_paper_skill_gym_loads_all_taxonomy_probes() -> None:
    root = Path(__file__).resolve().parents[1]
    probes = load_probes(root / "evals" / "paper_skill_gym" / "probes")

    assert len(probes) == 10
    assert {probe.taxonomy.value for probe in probes} == {
        "figure_grounding",
        "table_interpretation",
        "claim_evidence_separation",
        "method_reconstruction",
        "limitation_detection",
        "reproducibility",
        "citation_page_grounding",
        "unsupported_unknown_logging",
    }
    assert {probe.difficulty for probe in probes} == {"easy", "hard"}


def test_paper_skill_gym_binary_judge_scores_stub_answers() -> None:
    root = Path(__file__).resolve().parents[1]
    probes = load_probes(root / "evals" / "paper_skill_gym" / "probes")
    answers = load_answers(root / "evals" / "paper_skill_gym" / "sample_answers" / "baseline_stub.yaml")

    report = build_report(probes, answers)

    assert report.probe_count == 10
    assert report.passed_count == 10
    assert report.hard_pass_rate == 1.0
    assert report.easy_pass_rate == 1.0
    assert report.replay_balance_score == 1.0


def test_paper_skill_gym_rejects_missing_unknown_for_unsupported_probe() -> None:
    root = Path(__file__).resolve().parents[1]
    probes = load_probes(root / "evals" / "paper_skill_gym" / "probes")
    probe = next(probe for probe in probes if probe.probe_id == "unsupported_unknown_logging_mechanism")
    answer = ProbeAnswer(probe_id=probe.probe_id, answer="A mitochondrial mechanism is unsupported.")

    result = evaluate_probe(probe, answer)

    assert result.passed is False
    assert any(verdict.rubric_id == "unknown_logged" and not verdict.passed for verdict in result.verdicts)


def test_paper_skill_gym_cli_writes_report(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    out_path = tmp_path / "report.json"

    subprocess.run(
        [
            sys.executable,
            "-m",
            "evals.paper_skill_gym.run_probe_set",
            "--answers",
            "evals/paper_skill_gym/sample_answers/baseline_stub.yaml",
            "--out",
            str(out_path),
        ],
        cwd=root,
        check=True,
    )

    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "paper_skill_gym.report.v1"
    assert payload["probe_count"] == 10
    assert payload["replay_balance_score"] == 1.0


def test_paper_skill_gym_answer_template_contains_blank_answers() -> None:
    root = Path(__file__).resolve().parents[1]
    template = build_answer_template(root / "evals" / "paper_skill_gym" / "probes")

    assert len(template) == 10
    first = template[0]
    assert set(first) == {"probe_id", "taxonomy", "difficulty", "prompt", "answer", "claims", "evidence", "unknowns"}
    assert all(row["answer"] == "" for row in template)
    assert all(row["claims"] == [] for row in template)
    assert all(row["evidence"] == [] for row in template)
    assert all(row["unknowns"] == [] for row in template)


def test_paper_skill_gym_answer_template_cli_writes_yaml(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    out_path = tmp_path / "answers.todo.yaml"

    subprocess.run(
        [
            sys.executable,
            "-m",
            "evals.paper_skill_gym.make_answer_template",
            "--out",
            str(out_path),
        ],
        cwd=root,
        check=True,
    )

    assert "probe_id:" in out_path.read_text(encoding="utf-8")


def test_paper_skill_gym_compare_accepts_equal_candidate() -> None:
    root = Path(__file__).resolve().parents[1]
    probes = load_probes(root / "evals" / "paper_skill_gym" / "probes")
    answers = load_answers(root / "evals" / "paper_skill_gym" / "sample_answers" / "baseline_stub.yaml")
    baseline = build_report(probes, answers)
    candidate = build_report(probes, answers)

    comparison = compare_reports(baseline, candidate)

    assert comparison.decision == "accept"
    assert all(delta.passed for delta in comparison.deltas)
    assert comparison.regressions == []
    assert comparison.protected_rubric_regressions == []


def test_paper_skill_gym_compare_rejects_protected_rubric_regression() -> None:
    root = Path(__file__).resolve().parents[1]
    probes = load_probes(root / "evals" / "paper_skill_gym" / "probes")
    baseline_answers = load_answers(root / "evals" / "paper_skill_gym" / "sample_answers" / "baseline_stub.yaml")
    candidate_answers = dict(baseline_answers)
    candidate_answers["unsupported_unknown_logging_mechanism"] = ProbeAnswer(
        probe_id="unsupported_unknown_logging_mechanism",
        answer="A mitochondrial mechanism is unsupported.",
    )
    baseline = build_report(probes, baseline_answers)
    candidate = build_report(probes, candidate_answers)

    comparison = compare_reports(baseline, candidate)

    assert comparison.decision == "reject"
    assert any(regression.probe_id == "unsupported_unknown_logging_mechanism" for regression in comparison.regressions)
    assert any(
        regression.probe_id == "unsupported_unknown_logging_mechanism"
        and "unknown_logged" in regression.failed_rubrics
        for regression in comparison.protected_rubric_regressions
    )
    assert comparison.failure_summary["missing_unknown_logging"] == 1
    assert any("unsupported/unknown" in action for action in comparison.suggested_actions)


def test_paper_skill_gym_compare_cli_rejects_regression(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    probes = load_probes(root / "evals" / "paper_skill_gym" / "probes")
    baseline_answers = load_answers(root / "evals" / "paper_skill_gym" / "sample_answers" / "baseline_stub.yaml")
    candidate_answers = dict(baseline_answers)
    candidate_answers["citation_page_grounding_quote"] = ProbeAnswer(
        probe_id="citation_page_grounding_quote",
        answer="The claim should cite page 7.",
    )
    baseline_report = build_report(probes, baseline_answers)
    candidate_report = build_report(probes, candidate_answers)
    baseline_path = tmp_path / "baseline.json"
    candidate_path = tmp_path / "candidate.json"
    comparison_path = tmp_path / "comparison.json"
    baseline_path.write_text(json.dumps(baseline_report.model_dump(mode="json")), encoding="utf-8")
    candidate_path.write_text(json.dumps(candidate_report.model_dump(mode="json")), encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "evals.paper_skill_gym.compare_reports",
            "--baseline",
            str(baseline_path),
            "--candidate",
            str(candidate_path),
            "--out",
            str(comparison_path),
        ],
        cwd=root,
        check=False,
    )

    assert result.returncode == 1
    payload = json.loads(comparison_path.read_text(encoding="utf-8"))
    assert payload["decision"] == "reject"
    assert payload["failure_summary"]["missing_locator"] == 1
    assert any("locator" in action for action in payload["suggested_actions"])
