from __future__ import annotations

import argparse
import json
from pathlib import Path

from evals.paper_skill_gym.schemas import (
    BinaryRubric,
    PaperSkillProbe,
    ProbeAnswer,
    ProbeResult,
    ProbeSetReport,
    RubricVerdict,
    load_answers,
    load_probes,
)


def _norm(text: str) -> str:
    return " ".join(str(text or "").lower().split())


def _contains_all(text: str, terms: list[str]) -> bool:
    normalized = _norm(text)
    return all(_norm(term) in normalized for term in terms)


def _contains_any(text: str, terms: list[str]) -> bool:
    normalized = _norm(text)
    return any(_norm(term) in normalized for term in terms)


def _claim_text(answer: ProbeAnswer) -> str:
    return "\n".join(claim.text for claim in answer.claims)


def _evidence_text(answer: ProbeAnswer) -> str:
    rows: list[str] = []
    rows.extend(evidence.text for evidence in answer.evidence)
    for claim in answer.claims:
        rows.extend(evidence.text for evidence in claim.evidence)
    return "\n".join(rows)


def _has_locator(answer: ProbeAnswer) -> bool:
    evidence_rows = list(answer.evidence)
    for claim in answer.claims:
        evidence_rows.extend(claim.evidence)
    for evidence in evidence_rows:
        locator = evidence.locator
        if locator is None:
            continue
        if (
            locator.page is not None
            or locator.chunk_id
            or locator.table_id
            or locator.figure_id
            or locator.quote
        ):
            return True
    return False


def evaluate_rubric(rubric: BinaryRubric, answer: ProbeAnswer) -> RubricVerdict:
    if rubric.kind == "answer_contains_all":
        passed = _contains_all(answer.answer, rubric.terms)
    elif rubric.kind == "answer_contains_any":
        passed = _contains_any(answer.answer, rubric.terms)
    elif rubric.kind == "answer_not_contains":
        passed = not _contains_any(answer.answer, rubric.terms)
    elif rubric.kind == "claim_contains_all":
        passed = _contains_all(_claim_text(answer), rubric.terms)
    elif rubric.kind == "evidence_contains_any":
        passed = _contains_any(_evidence_text(answer), rubric.terms)
    elif rubric.kind == "locator_present":
        passed = _has_locator(answer)
    elif rubric.kind == "unknown_logged":
        passed = bool(answer.unknowns)
    else:
        passed = False
    detail = "pass" if passed else f"fail:{rubric.kind}"
    return RubricVerdict(rubric_id=rubric.rubric_id, passed=passed, detail=detail)


def evaluate_probe(probe: PaperSkillProbe, answer: ProbeAnswer) -> ProbeResult:
    verdicts = [evaluate_rubric(rubric, answer) for rubric in probe.rubrics]
    passed_count = sum(1 for verdict in verdicts if verdict.passed)
    pass_rate = round(passed_count / len(verdicts), 4) if verdicts else 0.0
    return ProbeResult(
        probe_id=probe.probe_id,
        taxonomy=probe.taxonomy,
        difficulty=probe.difficulty,
        passed=passed_count == len(verdicts),
        pass_rate=pass_rate,
        verdicts=verdicts,
    )


def build_report(probes: list[PaperSkillProbe], answers: dict[str, ProbeAnswer]) -> ProbeSetReport:
    results = [evaluate_probe(probe, answers.get(probe.probe_id, ProbeAnswer(probe_id=probe.probe_id))) for probe in probes]
    passed_count = sum(1 for result in results if result.passed)
    hard = [result for result in results if result.difficulty == "hard"]
    easy = [result for result in results if result.difficulty == "easy"]

    def _rate(rows: list[ProbeResult]) -> float:
        return round(sum(1 for row in rows if row.passed) / len(rows), 4) if rows else 0.0

    hard_pass_rate = _rate(hard)
    easy_pass_rate = _rate(easy)
    return ProbeSetReport(
        probe_count=len(results),
        passed_count=passed_count,
        pass_rate=round(passed_count / len(results), 4) if results else 0.0,
        hard_pass_rate=hard_pass_rate,
        easy_pass_rate=easy_pass_rate,
        replay_balance_score=round(hard_pass_rate * easy_pass_rate, 4),
        results=results,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the eval-only Paper Skill Gym binary judge.")
    parser.add_argument("--probes-dir", type=Path, default=Path("evals/paper_skill_gym/probes"))
    parser.add_argument("--answers", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    probes = load_probes(args.probes_dir)
    answers = load_answers(args.answers)
    report = build_report(probes, answers)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report.model_dump(mode="json"), indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

