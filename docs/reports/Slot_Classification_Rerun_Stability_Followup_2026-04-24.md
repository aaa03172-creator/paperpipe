# Slot Classification Rerun Stability Follow-up

Status: operational report; additive review-artifact follow-up
Date: 2026-04-24
Lane: slot classification tuning review
Scope: same-prompt rerun stability evidence for default and expanded boundary slot goldsets

## Purpose

Record the next bounded slot-classification check after the advisory hold decision. This follow-up tests whether the current local slot-classification path is stable enough to justify reopening prompt or policy tuning.

It does not change runtime slot classification behavior, prompt policy, schemas, database state, or exported paper artifacts.

## Layer Classification

Layer: review/gate artifact.

The artifacts below are derived benchmark and drift checks. They support operator decisions but are not canonical paper state or replacement truth stores.

## Valid Follow-up Artifacts

Corrected valid run set using `--fallback-current-slot unknown`:

- `snapshots/slot_classification_predictions/slot_classification_default_template_generation_20260424_r2/summary.json`
- `snapshots/slot_classification_goldset_audits/slot_classification_default_template_live_20260424_r2/summary.json`
- `snapshots/slot_classification_rerun_drift/slot_classification_default_rerun_drift_20260424_r2/summary.json`
- `snapshots/slot_classification_predictions/slot_classification_boundary_companion_expanded_generation_20260424_r2/summary.json`
- `snapshots/slot_classification_goldset_audits/slot_classification_boundary_companion_expanded_live_20260424_r2/summary.json`
- `snapshots/slot_classification_rerun_drift/slot_classification_boundary_expanded_rerun_drift_20260424_r2/summary.json`
- `snapshots/slot_classification_hard_case_adjudication/slot_classification_hard_cases_20260424_r1/worksheet.csv`

Superseded run set:

- `slot_classification_default_template_generation_20260424_r1`
- `slot_classification_default_template_live_20260424_r1`
- `slot_classification_default_rerun_drift_20260424_r1`
- `slot_classification_boundary_companion_expanded_generation_20260424_r1`
- `slot_classification_boundary_companion_expanded_live_20260424_r1`
- `slot_classification_boundary_expanded_rerun_drift_20260424_r1`

The `r1` runs are superseded because the source CSV rows omit `current_slot`, and the first generation pass did not provide a fallback. Those artifacts therefore recorded `missing_current_slot` rather than evaluating the classifier.

## Result

The corrected `r2` evidence does not support reopening prompt or policy tuning.

Default 11-row template:

- Prediction generation: 11/11 rows written
- Audit accuracy: `0.9091`
- Mismatch count: `1`
- Mismatch: `10.3390/nu17193125`
- Rerun drift versus `slot_classification_default_template_live_20260422_r3`: `1/11`
- Drift rate: `0.09090909090909091`

Expanded 7-row boundary companion:

- Prediction generation: 7/7 rows written
- Audit accuracy: `0.5714`
- Mismatch count: `3`
- Mismatches:
  - `10.1186/s13195-022-01005-8`
  - `10.1212/WNL.0000000000201479`
  - `10.1001/jamaneurol.2025.3217`
- Rerun drift versus `slot_classification_boundary_companion_expanded_live_20260422_r2`: `3/7`
- Drift rate: `0.42857142857142855`

## Interpretation

This follow-up strengthens the advisory hold:

- Same-prompt rerun behavior is still unstable on the default template.
- Expanded boundary rows are materially unstable and fail exactly where the methods-vs-clinical rubric is supposed to protect quality.
- The current evidence should be treated as calibration debt, not as prompt-improvement evidence.

## Operator Rule

Keep the current slot-classification prompt and policy unchanged.

Use the explicit hard-case adjudication rule before reviewing another prompt candidate:

- `docs/reports/Slot_Classification_Hard_Case_Adjudication_Rule_2026-04-24.md`
- `docs/reports/Slot_Classification_Prompt_Candidate_Review_Checklist_2026-04-24.md`

Do not promote a candidate slot prompt or policy until a later evidence pack shows:

- paired-compare recovery without default-template regression
- default rerun drift inside tolerance
- expanded boundary rerun drift inside tolerance
- no migration of methods-vs-clinical hard cases into new failures

## Verification Commands

```bash
.venv/bin/python scripts/eval/generate_slot_classification_predictions.py --goldset-csv tests/gold_set/gold_standard_template.csv --out-dir snapshots/slot_classification_predictions --run-id slot_classification_default_template_generation_20260424_r2 --fallback-current-slot unknown
.venv/bin/python scripts/eval/audit_slot_classification_goldset.py --goldset-csv tests/gold_set/gold_standard_template.csv --predictions-jsonl snapshots/slot_classification_predictions/slot_classification_default_template_generation_20260424_r2/predictions.jsonl --out-dir snapshots/slot_classification_goldset_audits --run-id slot_classification_default_template_live_20260424_r2
.venv/bin/python scripts/eval/generate_slot_classification_predictions.py --goldset-csv tests/gold_set/slot_classification_boundary_companion_expanded_20260422.csv --out-dir snapshots/slot_classification_predictions --run-id slot_classification_boundary_companion_expanded_generation_20260424_r2 --fallback-current-slot unknown
.venv/bin/python scripts/eval/audit_slot_classification_goldset.py --goldset-csv tests/gold_set/slot_classification_boundary_companion_expanded_20260422.csv --predictions-jsonl snapshots/slot_classification_predictions/slot_classification_boundary_companion_expanded_generation_20260424_r2/predictions.jsonl --out-dir snapshots/slot_classification_goldset_audits --run-id slot_classification_boundary_companion_expanded_live_20260424_r2
.venv/bin/python scripts/eval/audit_slot_classification_rerun_drift.py --prior-run snapshots/slot_classification_goldset_audits/slot_classification_default_template_live_20260422_r3 --new-run snapshots/slot_classification_goldset_audits/slot_classification_default_template_live_20260424_r2 --out-dir snapshots/slot_classification_rerun_drift --run-id slot_classification_default_rerun_drift_20260424_r2
.venv/bin/python scripts/eval/audit_slot_classification_rerun_drift.py --prior-run snapshots/slot_classification_goldset_audits/slot_classification_boundary_companion_expanded_live_20260422_r2 --new-run snapshots/slot_classification_goldset_audits/slot_classification_boundary_companion_expanded_live_20260424_r2 --out-dir snapshots/slot_classification_rerun_drift --run-id slot_classification_boundary_expanded_rerun_drift_20260424_r2
```

## Next PR-Sized Actions

1. Keep the advisory hold in place.
2. Use the bounded hard-case adjudication worksheet before trying another prompt candidate.
3. Re-run paired compare only after the hard-case adjudication worksheet is complete.
