from __future__ import annotations

import argparse
import json
from pathlib import Path

from evals.paper_skill_gym.schemas import (
    ProbeRegression,
    ProbeSetComparison,
    ProbeSetReport,
    ReportDelta,
    load_probe_set_report,
)

_PROTECTED_RUBRIC_TOKENS = ("locator", "unknown", "unsupported", "evidence")
_SUGGESTED_ACTIONS = {
    "missing_locator": "Require page, quote, chunk, table, or figure locator before promoting a paper-reading answer.",
    "missing_unknown_logging": "Strengthen unsupported/unknown handling so absent source support is logged instead of promoted.",
    "table_interpretation_regression": "Preserve denominators, units, comparators, and table identifiers in table-derived answers.",
    "figure_table_conflict_regression": "Force figure trends and table statistics to be reconciled before significance language is used.",
    "evidence_grounding_regression": "Require explicit evidence text or table-cell links for every promoted claim.",
    "probe_regression": "Inspect failed probe rubrics before changing active Skill.md guidance.",
}


def _failure_tags(probe_id: str, failed_rubrics: list[str]) -> list[str]:
    text = " ".join([probe_id, *failed_rubrics]).lower()
    tags: set[str] = set()
    if "locator" in text or "page" in text or "quote" in text:
        tags.add("missing_locator")
    if "unknown" in text or "unsupported" in text:
        tags.add("missing_unknown_logging")
    if "denominator" in text or "table" in text:
        tags.add("table_interpretation_regression")
    if "figure_table" in text or ("figure" in text and "table" in text):
        tags.add("figure_table_conflict_regression")
    if "evidence" in text:
        tags.add("evidence_grounding_regression")
    if not tags:
        tags.add("probe_regression")
    return sorted(tags)


def _summarize_failure_tags(regressions: list[ProbeRegression]) -> dict[str, int]:
    summary: dict[str, int] = {}
    seen: set[tuple[str, str]] = set()
    for regression in regressions:
        for tag in regression.failure_tags:
            key = (regression.probe_id, tag)
            if key in seen:
                continue
            seen.add(key)
            summary[tag] = summary.get(tag, 0) + 1
    return dict(sorted(summary.items()))


def _suggest_actions(failure_summary: dict[str, int]) -> list[str]:
    return [
        f"{tag}: {_SUGGESTED_ACTIONS.get(tag, _SUGGESTED_ACTIONS['probe_regression'])}"
        for tag in sorted(failure_summary)
    ]


def _delta(metric: str, baseline: float, candidate: float, *, allow_equal: bool = True) -> ReportDelta:
    raw_delta = round(candidate - baseline, 4)
    passed = candidate >= baseline if allow_equal else candidate > baseline
    comparator = ">=" if allow_equal else ">"
    return ReportDelta(
        metric=metric,
        baseline=baseline,
        candidate=candidate,
        delta=raw_delta,
        passed=passed,
        detail=f"candidate {candidate:.4f} {comparator} baseline {baseline:.4f}",
    )


def _result_map(report: ProbeSetReport):
    return {result.probe_id: result for result in report.results}


def _failed_rubrics(result) -> list[str]:
    return [verdict.rubric_id for verdict in result.verdicts if not verdict.passed]


def _protected_failed_rubrics(result) -> list[str]:
    failed = _failed_rubrics(result)
    return [
        rubric_id
        for rubric_id in failed
        if any(token in rubric_id.lower() for token in _PROTECTED_RUBRIC_TOKENS)
    ]


def compare_reports(
    baseline: ProbeSetReport,
    candidate: ProbeSetReport,
    *,
    baseline_path: Path | None = None,
    candidate_path: Path | None = None,
) -> ProbeSetComparison:
    deltas = [
        _delta("pass_rate", baseline.pass_rate, candidate.pass_rate),
        _delta("hard_pass_rate", baseline.hard_pass_rate, candidate.hard_pass_rate),
        _delta("easy_pass_rate", baseline.easy_pass_rate, candidate.easy_pass_rate),
        _delta("replay_balance_score", baseline.replay_balance_score, candidate.replay_balance_score),
    ]

    baseline_by_id = _result_map(baseline)
    candidate_by_id = _result_map(candidate)
    regressions: list[ProbeRegression] = []
    protected_regressions: list[ProbeRegression] = []

    for probe_id, baseline_result in sorted(baseline_by_id.items()):
        candidate_result = candidate_by_id.get(probe_id)
        if candidate_result is None:
            failed_rubrics = ["MISSING_PROBE_RESULT"]
            regression = ProbeRegression(
                probe_id=probe_id,
                baseline_passed=baseline_result.passed,
                candidate_passed=False,
                failed_rubrics=failed_rubrics,
                failure_tags=_failure_tags(probe_id, failed_rubrics),
            )
            regressions.append(regression)
            protected_regressions.append(regression)
            continue

        if baseline_result.passed and not candidate_result.passed:
            failed_rubrics = _failed_rubrics(candidate_result)
            regressions.append(
                ProbeRegression(
                    probe_id=probe_id,
                    baseline_passed=True,
                    candidate_passed=False,
                    failed_rubrics=failed_rubrics,
                    failure_tags=_failure_tags(probe_id, failed_rubrics),
                )
            )

        baseline_failed_protected = set(_protected_failed_rubrics(baseline_result))
        candidate_failed_protected = set(_protected_failed_rubrics(candidate_result))
        newly_failed = sorted(candidate_failed_protected - baseline_failed_protected)
        if newly_failed:
            protected_regressions.append(
                ProbeRegression(
                    probe_id=probe_id,
                    baseline_passed=baseline_result.passed,
                    candidate_passed=candidate_result.passed,
                    failed_rubrics=newly_failed,
                    failure_tags=_failure_tags(probe_id, newly_failed),
                )
            )

    notes: list[str] = []
    if baseline.probe_count != candidate.probe_count:
        notes.append(f"probe_count_changed:{baseline.probe_count}->{candidate.probe_count}")
    if regressions:
        notes.append(f"probe_regressions={len(regressions)}")
    if protected_regressions:
        notes.append(f"protected_rubric_regressions={len(protected_regressions)}")

    decision = "accept"
    if any(not delta.passed for delta in deltas):
        decision = "reject"
    if regressions or protected_regressions:
        decision = "reject"
    if baseline.probe_count != candidate.probe_count:
        decision = "reject"

    failure_summary = _summarize_failure_tags([*regressions, *protected_regressions])

    return ProbeSetComparison(
        decision=decision,
        baseline_report=str(baseline_path) if baseline_path is not None else None,
        candidate_report=str(candidate_path) if candidate_path is not None else None,
        deltas=deltas,
        regressions=regressions,
        protected_rubric_regressions=protected_regressions,
        failure_summary=failure_summary,
        suggested_actions=_suggest_actions(failure_summary),
        notes=notes,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare two Paper Skill Gym reports.")
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    baseline = load_probe_set_report(args.baseline)
    candidate = load_probe_set_report(args.candidate)
    comparison = compare_reports(
        baseline,
        candidate,
        baseline_path=args.baseline,
        candidate_path=args.candidate,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(comparison.model_dump(mode="json"), indent=2), encoding="utf-8")
    return 0 if comparison.decision == "accept" else 1


if __name__ == "__main__":
    raise SystemExit(main())
