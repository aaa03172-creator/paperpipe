# Slot Classification Prompt Candidate: Boundary Clarification

Status: operational report; candidate artifact index
Date: 2026-04-24
Lane: slot classification tuning review
Scope: prompt candidate and runtime-promotion evidence for hard-case boundary clarification

## Purpose

Record the first concrete prompt candidate after the hard-case adjudication rule.

This report indexes the candidate and its later runtime-promotion evidence. It does not rewrite historical labels or replace canonical paper state.

## Candidate

Candidate ID:

- `slot_classification_boundary_clarification_candidate_20260424_r1`

Candidate artifacts:

- `snapshots/slot_classification_prompt_candidates/slot_classification_boundary_clarification_candidate_20260424_r1/candidate_prompt.md`
- `snapshots/slot_classification_prompt_candidates/slot_classification_boundary_clarification_candidate_20260424_r1/metadata.json`
- `snapshots/slot_classification_prompt_candidates/slot_classification_boundary_clarification_candidate_20260424_r1/README.md`

## Intended Change

The candidate makes these prompt-level clarifications:

- classify by center of gravity before cue-word counting
- keep disease-focused clinical evidence reviews in `clinical` unless mechanism or methods is truly central
- keep head-to-head assay benchmarking in `methods` even with clinical endpoints
- keep patient-facing screening, prognosis, risk prediction, and memory-clinic utility in `clinical`
- use `needs_adjudication=true` for mixed boundary cases or review/resource taxonomy gaps

## Current Status

- Runtime change ready: yes
- Runtime implemented: yes, with deterministic clinical-review fallback
- Evaluation ready: yes
- Evaluated: yes
- Manual review ready: yes
- Promotion ready: yes

The candidate first passed the non-runtime evaluation gate, then was implemented in runtime with a narrow deterministic fallback for disease-focused clinical review papers that the model overcalled as `Mechanism`.

Runtime implementation evidence:

- `docs/reports/Slot_Classification_Runtime_Boundary_Clarification_Patch_2026-04-24.md`

## Evaluation Results

Latest evaluation artifacts:

- `snapshots/slot_classification_predictions/slot_classification_candidate_boundary_clarification_default_generation_20260424_r1/summary.json`
- `snapshots/slot_classification_goldset_audits/slot_classification_candidate_boundary_clarification_default_audit_20260424_r1/summary.json`
- `snapshots/slot_classification_predictions/slot_classification_candidate_boundary_clarification_boundary_generation_20260424_r1/summary.json`
- `snapshots/slot_classification_goldset_audits/slot_classification_candidate_boundary_clarification_boundary_audit_20260424_r1/summary.json`
- `snapshots/slot_classification_paired_compares/slot_classification_candidate_boundary_clarification_pair_compare_20260424_r1/summary.json`
- `snapshots/slot_classification_rerun_drift/slot_classification_candidate_boundary_clarification_default_delta_20260424_r1/summary.json`
- `snapshots/slot_classification_rerun_drift/slot_classification_candidate_boundary_clarification_boundary_delta_20260424_r1/summary.json`
- `snapshots/slot_classification_tuning_review/slot_classification_candidate_boundary_clarification_tuning_review_20260424_r1/summary.json`

Observed result:

- Default template: 11/11 predictions written, accuracy `1.0`, mismatch count `0`
- Expanded boundary companion: 7/7 predictions written, accuracy `1.0`, mismatch count `0`
- Paired compare: passed with no regressions and no mismatch migration
- Default delta drift: `0.0`
- Expanded boundary delta drift: `0.0`
- Tuning review: `review_ready=true`, `prompt_change_ready=true`, `recommended_action=manual_slot_tuning_review`

Hard-case anchors were preserved:

- `10.3390/nu17193125`: `clinical`
- `10.1186/s13195-022-01005-8`: `methods`
- `10.1212/WNL.0000000000201479`: `clinical`
- `10.1001/jamaneurol.2025.3217`: `clinical`

## Required Gate

Use:

- `docs/reports/Slot_Classification_Prompt_Candidate_Review_Checklist_2026-04-24.md`
- `docs/reports/Slot_Classification_Hard_Case_Adjudication_Rule_2026-04-24.md`

The runtime implementation must preserve the four hard-case expected labels:

- `10.3390/nu17193125`: `clinical`
- `10.1186/s13195-022-01005-8`: `methods`
- `10.1212/WNL.0000000000201479`: `clinical`
- `10.1001/jamaneurol.2025.3217`: `clinical`

## Non-Goals

- No historical labels should be rewritten.
- No new `review` slot is adopted.
- No inference payload should be widened.

## Next PR-Sized Action

Monitor same-code rerun drift after the runtime patch before broadening review/resource taxonomy rules beyond the narrow clinical-review fallback.
