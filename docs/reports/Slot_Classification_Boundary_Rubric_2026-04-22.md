# Slot Classification Boundary Rubric

## Goal

Make `methods` versus `clinical` decisions more reviewable for biomarker, assay, and platform papers that sit on the boundary between technical validation and patient-facing utility.

This rubric is additive only. It does not create a new runtime truth path. It exists so future prompt or policy changes can be judged against a stable human-readable rule set.

## Primary Rule

Choose the slot that best matches the paper's **main novelty claim**, not the population used for evaluation.

- Human cohorts alone do not force `clinical`.
- Biomarkers alone do not force `clinical`.
- Assay validation alone does not force `methods`.

The deciding question is:

`What would be lost if this paper's central contribution were removed?`

## Choose `Methods` When

The paper would lose its main contribution if you removed the **measurement platform, assay workflow, or benchmarking comparison**.

Common signals:

- new assay or platform
- analytical validation
- precision, linearity, calibration, cutoff optimization
- throughput, automation, deployment-readiness
- head-to-head assay comparison
- platform benchmarking against an established method
- workflow or sample-processing optimization

Typical paper shape:

- patient data is used mainly to validate or compare the method
- clinical outcomes are evidence of assay usefulness, not the main novelty

Examples from the current goldset:

- `10.3389/fneur.2025.1568971`
- `10.1002/dad2.12204`
- `10.1186/s13195-022-01116-2`
- `10.1186/s13195-022-01005-8`

## Choose `Clinical` When

The paper would lose its main contribution if you removed the **patient-facing prediction, screening, prognosis, or decision-support claim**.

Common signals:

- real-world cohort utility
- screening performance in an asymptomatic or diagnostic population
- prognostic value for conversion or disease progression
- risk prediction beyond routine clinical information
- triage, diagnosis, or patient-management usefulness
- memory-clinic or real-world care pathway framing

Typical paper shape:

- biomarker or assay is a tool inside a clinical decision problem
- the novelty is improved patient classification or prediction, not improved measurement technology

Examples from the current goldset:

- `10.1212/WNL.0000000000201479`
- `10.1016/j.ebiom.2024.105345`
- `10.1001/jamaneurol.2025.3217`

## Tie-Breakers

When a paper strongly exhibits both categories:

1. Prefer `Methods` if the title or abstract foregrounds assay comparison, assay validation, benchmarking, analytical performance, or platform readiness.
2. Prefer `Clinical` if the title or abstract foregrounds screening, prognosis, risk prediction, or real-world utility in a patient pathway.
3. If the wording is still mixed, inspect whether the evaluation cohorts are primarily there to prove the technology works or to answer a patient-management question.
4. If uncertainty remains, keep the disagreement visible in the audit lane rather than forcing a fake certainty.

## Hard-Case Adjudication Rules

Follow-up rule document:

- `docs/reports/Slot_Classification_Hard_Case_Adjudication_Rule_2026-04-24.md`

Use these additional hard-case rules before testing another prompt or policy candidate:

1. Disease-focused systematic reviews or meta-analyses stay `clinical` in the current three-slot taxonomy when they primarily evaluate patient-facing benefit, intervention effects, prognosis, diagnosis, or clinical evidence quality.
2. Do not classify a disease-focused review as `mechanism` solely because the intervention or exposure has a biological mechanism.
3. Head-to-head assay comparison, analytical validation, platform benchmarking, cutoff calibration, precision, or linearity stays `methods` when clinical endpoints mainly demonstrate assay or platform behavior.
4. Risk prediction, prognosis, population screening, triage, memory-clinic utility, or patient-management usefulness stays `clinical` when the assay is a tool rather than the object of development or benchmarking.
5. Judge the paper's center of gravity before counting cue words. Biomarker-heavy language is not enough for `methods`; human-cohort language is not enough for `clinical`.

## Current Hard Cases

### `10.1186/s13195-022-01005-8`

Current rubric decision: `methods`

Why:

- the main novelty is a head-to-head comparison of a novel plasma p-tau217 assay against an established assay
- diagnostic and prognostic endpoints are present, but they serve the benchmarking claim

### `10.1212/WNL.0000000000201479`

Current rubric decision: `clinical`

Why:

- the main novelty is prediction of future Alzheimer or mixed dementia in a clinic-based population
- the biomarker panel is being judged as a clinical prognostic tool rather than as a new measurement platform

### `10.3390/nu17193125`

Current rubric decision: `clinical`

Why:

- the current taxonomy has no separate review/resource slot
- the paper is a disease-focused systematic review of clinical evidence and potential clinical benefits
- mechanism is not supported unless the review's main contribution is pathway synthesis or preclinical causal explanation

### `10.1001/jamaneurol.2025.3217`

Current rubric decision: `clinical`

Why:

- the main novelty is population screening/classification utility for preclinical Alzheimer disease
- plasma p-tau217 is the tool inside the clinical screening question, not the object of assay construction or platform benchmarking

## How To Use This Rubric

Use it in this order:

1. Goldset labeling for new boundary rows
2. Review of prompt/policy tweaks
3. Interpretation of remaining mismatches in audit artifacts

If a prompt change improves one hard row but breaks another, prefer updating the rubric examples and reevaluating against both the default eleven-row set and the boundary companion before making additional runtime changes.
