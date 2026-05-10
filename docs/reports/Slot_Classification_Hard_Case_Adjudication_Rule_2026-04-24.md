# Slot Classification Hard-Case Adjudication Rule

Status: operational report; additive review rule
Date: 2026-04-24
Lane: slot classification tuning review
Scope: hard-case adjudication rule for review-vs-clinical and clinical-vs-methods slot boundaries

## Purpose

Turn the corrected 2026-04-24 hard-case worksheet into an explicit adjudication rule before any prompt or policy candidate is tested again.

This report is not runtime policy. It does not change prompts, schemas, database state, exports, or stored paper labels.

## Layer Classification

Layer: review/gate artifact.

The rule below is operator guidance for goldset labeling, paired-compare interpretation, and future prompt-review checks. It is not canonical paper state.

## Source Evidence

- `snapshots/slot_classification_hard_case_adjudication/slot_classification_hard_cases_20260424_r1/worksheet.csv`
- `snapshots/slot_classification_rerun_drift/slot_classification_default_rerun_drift_20260424_r2/summary.json`
- `snapshots/slot_classification_rerun_drift/slot_classification_boundary_expanded_rerun_drift_20260424_r2/summary.json`
- `docs/reports/Slot_Classification_Rerun_Stability_Followup_2026-04-24.md`
- `docs/reports/Slot_Classification_Boundary_Rubric_2026-04-22.md`

## Adjudication Rules

### Rule 1: Disease-Focused Review Fallback

In the current three-slot taxonomy, a disease-focused systematic review or meta-analysis should remain `clinical` when it primarily evaluates patient-facing benefit, intervention effects, prognosis, diagnosis, or clinical evidence quality.

Do not classify a disease-focused review as `mechanism` solely because the intervention or exposure has a biological mechanism. Use `mechanism` only when the review's main contribution is mechanistic biology, pathway synthesis, or preclinical causal explanation.

Current hard-case anchor:

- `10.3390/nu17193125`: keep `clinical` under the current three-slot taxonomy; record separate review/resource taxonomy debt if needed.

### Rule 2: Assay Benchmarking Override

Choose `methods` when the main novelty would be lost if the measurement platform, assay workflow, analytical validation, or head-to-head benchmark were removed.

This remains true even if the paper reports diagnostic or prognostic endpoints, as long as those endpoints mainly demonstrate assay or platform behavior.

Current hard-case anchor:

- `10.1186/s13195-022-01005-8`: keep `methods` because the central contribution is head-to-head p-tau217 assay benchmarking.

### Rule 3: Clinical Utility Override

Choose `clinical` when the main novelty would be lost if patient-facing screening, prognosis, risk prediction, triage, or decision-support utility were removed.

This remains true even if biomarkers or assays are prominent, as long as the assay itself is not the main object of development, calibration, or benchmarking.

Current hard-case anchors:

- `10.1212/WNL.0000000000201479`: keep `clinical` because the central contribution is dementia-risk prediction in a clinic-based cohort.
- `10.1001/jamaneurol.2025.3217`: keep `clinical` because the central contribution is preclinical AD screening/classification utility.

### Rule 4: Evidence Precedence

Use this order when evidence conflicts:

1. Main novelty claim and paper framing
2. Title plus abstract/summary
3. Methods and results snippets that explain why the cohort exists
4. Keyword frequency or isolated slot cues

Keyword frequency must not override the paper's central contribution. Biomarker-heavy language is not enough for `methods`; human-cohort language is not enough for `clinical`.

### Rule 5: Promotion Gate

Do not reopen prompt or policy promotion from these four rows until a candidate passes:

1. default-template paired compare without regression
2. default rerun drift inside tolerance
3. expanded-boundary rerun drift inside tolerance
4. no new hard-case migration across the rules above

## Expected Prompt-Review Cues

Future prompt candidates should be checked for these behaviors:

- They should not map clinical systematic reviews to `mechanism` just because the intervention has a molecular rationale.
- They should preserve `methods` for head-to-head assay comparisons with clinical endpoints.
- They should preserve `clinical` for memory-clinic risk prediction and population screening utility.
- They should explain the paper's center of gravity rather than count cue words.

## Non-Goals

- No runtime prompt change is approved here.
- No historical slot labels should be rewritten from this report alone.
- No new `review`, `guideline`, or `resource` slot is adopted here.
- No inference payload should be widened to apply these rules.

## Next PR-Sized Actions

1. Keep current runtime prompt and policy unchanged.
2. Use this rule with `docs/reports/Slot_Classification_Prompt_Candidate_Review_Checklist_2026-04-24.md` when reviewing the next prompt candidate.
3. Re-run paired compare and rerun-drift checks before any promotion decision.
