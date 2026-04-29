# Slot Classification Post-Promotion Stability

Status: operational report; post-promotion same-code rerun evidence
Date: 2026-04-25
Lane: slot classification tuning review
Scope: same-code rerun drift check after runtime boundary-clarification promotion

## Purpose

Record the first same-code rerun stability check after the runtime boundary-clarification patch.

This report is a review/gate artifact. It does not replace canonical paper state, rewrite historical labels, or broaden runtime inference behavior.

## Compared Runtime Evidence

Prior runtime evidence:

- `slot_classification_runtime_boundary_clarification_default_audit_20260424_r3`
- `slot_classification_runtime_boundary_clarification_boundary_audit_20260424_r2`

New same-code rerun evidence:

- `snapshots/slot_classification_predictions/slot_classification_runtime_boundary_clarification_default_generation_20260425_r1/summary.json`
- `snapshots/slot_classification_goldset_audits/slot_classification_runtime_boundary_clarification_default_audit_20260425_r1/summary.json`
- `snapshots/slot_classification_predictions/slot_classification_runtime_boundary_clarification_boundary_generation_20260425_r1/summary.json`
- `snapshots/slot_classification_goldset_audits/slot_classification_runtime_boundary_clarification_boundary_audit_20260425_r1/summary.json`
- `snapshots/slot_classification_rerun_drift/slot_classification_runtime_boundary_clarification_default_delta_20260425_r1/summary.json`
- `snapshots/slot_classification_rerun_drift/slot_classification_runtime_boundary_clarification_boundary_delta_20260425_r1/summary.json`
- `snapshots/slot_classification_tuning_review/slot_classification_runtime_boundary_clarification_stability_review_20260425_r1/summary.json`

## Result

- Default template: accuracy `1.0`, mismatch count `0`, prediction status `ok=11`
- Expanded boundary companion: accuracy `1.0`, mismatch count `0`, prediction status `ok=7`
- Default same-code drift: `0.0`
- Expanded boundary same-code drift: `0.0`
- Tuning review: `review_ready=true`, `prompt_change_ready=true`, `recommended_action=manual_slot_tuning_review`

## Interpretation

The promoted runtime path stayed stable on the existing default and boundary benchmark surfaces across this same-code rerun.

The result supports keeping the current boundary-clarification prompt and deterministic clinical-review fallback as-is. It does not justify broadening the fallback to other review/resource taxonomy cases without a new paired-compare and rerun-drift pack.

## Verification Commands

```bash
.venv/bin/python scripts/eval/generate_slot_classification_predictions.py --goldset-csv tests/gold_set/gold_standard_template.csv --out-dir snapshots/slot_classification_predictions --run-id slot_classification_runtime_boundary_clarification_default_generation_20260425_r1 --fallback-current-slot unknown
.venv/bin/python scripts/eval/audit_slot_classification_goldset.py --goldset-csv tests/gold_set/gold_standard_template.csv --predictions-jsonl snapshots/slot_classification_predictions/slot_classification_runtime_boundary_clarification_default_generation_20260425_r1/predictions.jsonl --out-dir snapshots/slot_classification_goldset_audits --run-id slot_classification_runtime_boundary_clarification_default_audit_20260425_r1
.venv/bin/python scripts/eval/generate_slot_classification_predictions.py --goldset-csv tests/gold_set/slot_classification_boundary_companion_expanded_20260422.csv --out-dir snapshots/slot_classification_predictions --run-id slot_classification_runtime_boundary_clarification_boundary_generation_20260425_r1 --fallback-current-slot unknown
.venv/bin/python scripts/eval/audit_slot_classification_goldset.py --goldset-csv tests/gold_set/slot_classification_boundary_companion_expanded_20260422.csv --predictions-jsonl snapshots/slot_classification_predictions/slot_classification_runtime_boundary_clarification_boundary_generation_20260425_r1/predictions.jsonl --out-dir snapshots/slot_classification_goldset_audits --run-id slot_classification_runtime_boundary_clarification_boundary_audit_20260425_r1
.venv/bin/python scripts/eval/audit_slot_classification_rerun_drift.py --prior-run snapshots/slot_classification_goldset_audits/slot_classification_runtime_boundary_clarification_default_audit_20260424_r3 --new-run snapshots/slot_classification_goldset_audits/slot_classification_runtime_boundary_clarification_default_audit_20260425_r1 --out-dir snapshots/slot_classification_rerun_drift --run-id slot_classification_runtime_boundary_clarification_default_delta_20260425_r1
.venv/bin/python scripts/eval/audit_slot_classification_rerun_drift.py --prior-run snapshots/slot_classification_goldset_audits/slot_classification_runtime_boundary_clarification_boundary_audit_20260424_r2 --new-run snapshots/slot_classification_goldset_audits/slot_classification_runtime_boundary_clarification_boundary_audit_20260425_r1 --out-dir snapshots/slot_classification_rerun_drift --run-id slot_classification_runtime_boundary_clarification_boundary_delta_20260425_r1
.venv/bin/python scripts/eval/recommend_slot_classification_tuning_review.py --paired-compare-summary snapshots/slot_classification_paired_compares/slot_classification_runtime_boundary_clarification_pair_compare_20260424_r2 --default-rerun-drift-summary snapshots/slot_classification_rerun_drift/slot_classification_runtime_boundary_clarification_default_delta_20260425_r1 --boundary-rerun-drift-summary snapshots/slot_classification_rerun_drift/slot_classification_runtime_boundary_clarification_boundary_delta_20260425_r1 --out-dir snapshots/slot_classification_tuning_review --run-id slot_classification_runtime_boundary_clarification_stability_review_20260425_r1
```

## Remaining Risk

- This is still a small benchmark slice.
- Same-code stability does not guarantee broader review/resource taxonomy correctness.
- Before broadening fallback logic, add new labeled boundary rows first.
