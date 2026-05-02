# Slot Classification Runtime Boundary Clarification Patch

Status: operational report; runtime patch evidence
Date: 2026-04-24
Lane: slot classification tuning review
Scope: runtime slot-classification prompt boundary clarification plus deterministic clinical-review fallback

## Purpose

Record the runtime implementation of the boundary clarification candidate after the non-runtime candidate passed manual-review gates.

This report documents the applied runtime behavior and the evaluation evidence. It does not replace canonical paper state or rewrite historical labels.

## Runtime Change

Updated `src/llm_provider.py` in `LLMProvider.classify_slot()`:

- Replaced the slot-classification prompt with the boundary-clarification prompt.
- Added explicit center-of-gravity reasoning.
- Added review fallback, methods boundary, clinical utility boundary, mechanism boundary, and hard-case anchor instructions.
- Added a deterministic clinical-review fallback for cases where the model overcalls `Mechanism` on disease-focused clinical benefit systematic reviews or meta-analyses.

The deterministic fallback is intentionally narrow:

- It only activates when the first-pass predicted slot is `Mechanism`.
- It requires systematic-review or meta-analysis language.
- It requires clinical-benefit or patient-facing evidence language.
- It avoids methods-focused and explicitly mechanistic reviews.

## Superseded Runtime Attempt

First runtime evaluation:

- `slot_classification_runtime_boundary_clarification_tuning_review_20260424_r1`

Result:

- Boundary companion passed.
- Default template still had one mismatch:
  - `10.3390/nu17193125`
- Tuning review remained blocked:
  - `review_ready=false`
  - `recommended_action=hold_current_prompt_policy`

Interpretation:

- Prompt clarification alone improved the methods-vs-clinical boundary but did not reliably fix the clinical-review-vs-mechanism hard case.

## Final Runtime Evidence

Corrected runtime evidence:

- `snapshots/slot_classification_predictions/slot_classification_runtime_boundary_clarification_default_generation_20260424_r3/summary.json`
- `snapshots/slot_classification_goldset_audits/slot_classification_runtime_boundary_clarification_default_audit_20260424_r3/summary.json`
- `snapshots/slot_classification_predictions/slot_classification_runtime_boundary_clarification_boundary_generation_20260424_r2/summary.json`
- `snapshots/slot_classification_goldset_audits/slot_classification_runtime_boundary_clarification_boundary_audit_20260424_r2/summary.json`
- `snapshots/slot_classification_paired_compares/slot_classification_runtime_boundary_clarification_pair_compare_20260424_r2/summary.json`
- `snapshots/slot_classification_rerun_drift/slot_classification_runtime_boundary_clarification_default_delta_20260424_r2/summary.json`
- `snapshots/slot_classification_rerun_drift/slot_classification_runtime_boundary_clarification_boundary_delta_20260424_r2/summary.json`
- `snapshots/slot_classification_tuning_review/slot_classification_runtime_boundary_clarification_tuning_review_20260424_r2/summary.json`

Observed result:

- Default template: accuracy `1.0`, mismatch count `0`
- Expanded boundary companion: accuracy `1.0`, mismatch count `0`
- Paired compare: passed with no regressions and no mismatch migration
- Default delta drift: `0.0`
- Expanded boundary delta drift: `0.0`
- Tuning review: `review_ready=true`, `prompt_change_ready=true`, `recommended_action=manual_slot_tuning_review`

## Hard-Case Result

The final runtime evaluation preserved the four hard-case anchors:

- `10.3390/nu17193125`: `clinical`
- `10.1186/s13195-022-01005-8`: `methods`
- `10.1212/WNL.0000000000201479`: `clinical`
- `10.1001/jamaneurol.2025.3217`: `clinical`

## Post-Promotion Stability

First same-code rerun stability check:

- `docs/reports/Slot_Classification_Post_Promotion_Stability_2026-04-25.md`

Result:

- Default template rerun: accuracy `1.0`, mismatch count `0`, drift `0.0`
- Expanded boundary companion rerun: accuracy `1.0`, mismatch count `0`, drift `0.0`
- Tuning review: `review_ready=true`, `prompt_change_ready=true`, `recommended_action=manual_slot_tuning_review`

## Verification

Commands run:

```bash
python3 -m py_compile src/llm_provider.py tests/test_llm_provider_canonical_language.py
.venv/bin/python -m pytest tests/test_llm_provider_canonical_language.py -q
.venv/bin/python scripts/eval/generate_slot_classification_predictions.py --goldset-csv tests/gold_set/gold_standard_template.csv --out-dir snapshots/slot_classification_predictions --run-id slot_classification_runtime_boundary_clarification_default_generation_20260424_r3 --fallback-current-slot unknown
.venv/bin/python scripts/eval/audit_slot_classification_goldset.py --goldset-csv tests/gold_set/gold_standard_template.csv --predictions-jsonl snapshots/slot_classification_predictions/slot_classification_runtime_boundary_clarification_default_generation_20260424_r3/predictions.jsonl --out-dir snapshots/slot_classification_goldset_audits --run-id slot_classification_runtime_boundary_clarification_default_audit_20260424_r3
.venv/bin/python scripts/eval/generate_slot_classification_predictions.py --goldset-csv tests/gold_set/slot_classification_boundary_companion_expanded_20260422.csv --out-dir snapshots/slot_classification_predictions --run-id slot_classification_runtime_boundary_clarification_boundary_generation_20260424_r2 --fallback-current-slot unknown
.venv/bin/python scripts/eval/audit_slot_classification_goldset.py --goldset-csv tests/gold_set/slot_classification_boundary_companion_expanded_20260422.csv --predictions-jsonl snapshots/slot_classification_predictions/slot_classification_runtime_boundary_clarification_boundary_generation_20260424_r2/predictions.jsonl --out-dir snapshots/slot_classification_goldset_audits --run-id slot_classification_runtime_boundary_clarification_boundary_audit_20260424_r2
.venv/bin/python scripts/eval/compare_slot_classification_paired_benchmarks.py --baseline-default snapshots/slot_classification_goldset_audits/slot_classification_default_template_live_20260422_r3 --baseline-boundary snapshots/slot_classification_goldset_audits/slot_classification_boundary_companion_expanded_live_20260422_r2 --candidate-default snapshots/slot_classification_goldset_audits/slot_classification_runtime_boundary_clarification_default_audit_20260424_r3 --candidate-boundary snapshots/slot_classification_goldset_audits/slot_classification_runtime_boundary_clarification_boundary_audit_20260424_r2 --out-dir snapshots/slot_classification_paired_compares --run-id slot_classification_runtime_boundary_clarification_pair_compare_20260424_r2
.venv/bin/python scripts/eval/audit_slot_classification_rerun_drift.py --prior-run snapshots/slot_classification_goldset_audits/slot_classification_default_template_live_20260422_r3 --new-run snapshots/slot_classification_goldset_audits/slot_classification_runtime_boundary_clarification_default_audit_20260424_r3 --out-dir snapshots/slot_classification_rerun_drift --run-id slot_classification_runtime_boundary_clarification_default_delta_20260424_r2
.venv/bin/python scripts/eval/audit_slot_classification_rerun_drift.py --prior-run snapshots/slot_classification_goldset_audits/slot_classification_boundary_companion_expanded_live_20260422_r2 --new-run snapshots/slot_classification_goldset_audits/slot_classification_runtime_boundary_clarification_boundary_audit_20260424_r2 --out-dir snapshots/slot_classification_rerun_drift --run-id slot_classification_runtime_boundary_clarification_boundary_delta_20260424_r2
.venv/bin/python scripts/eval/recommend_slot_classification_tuning_review.py --paired-compare-summary snapshots/slot_classification_paired_compares/slot_classification_runtime_boundary_clarification_pair_compare_20260424_r2 --default-rerun-drift-summary snapshots/slot_classification_rerun_drift/slot_classification_runtime_boundary_clarification_default_delta_20260424_r2 --boundary-rerun-drift-summary snapshots/slot_classification_rerun_drift/slot_classification_runtime_boundary_clarification_boundary_delta_20260424_r2 --out-dir snapshots/slot_classification_tuning_review --run-id slot_classification_runtime_boundary_clarification_tuning_review_20260424_r2
```

## Remaining Risk

- Evidence is still a small benchmark slice.
- The deterministic fallback intentionally covers only disease-focused clinical benefit reviews, not all possible review/resource taxonomy debt.
- Continue monitoring same-code rerun drift before broadening this rule.
