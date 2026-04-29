# Slot Classification Prompt Candidate Review Checklist

Status: operational checklist; non-runtime
Date: 2026-04-24
Lane: slot classification tuning review
Scope: checklist for reviewing any future slot-classification prompt or policy candidate

## Purpose

Define the minimum review steps before any future slot-classification prompt or policy candidate can be treated as promotion-ready.

This checklist is intentionally non-runtime. It does not change prompts, schemas, database state, exports, or stored paper labels.

## Required Inputs

A prompt or policy candidate is reviewable only when all inputs are present:

- Candidate description with the exact changed prompt text or policy delta
- Baseline default-template audit summary
- Candidate default-template audit summary
- Baseline expanded-boundary audit summary
- Candidate expanded-boundary audit summary
- Default-template rerun-drift summary
- Expanded-boundary rerun-drift summary
- Hard-case adjudication rule:
  - `docs/reports/Slot_Classification_Hard_Case_Adjudication_Rule_2026-04-24.md`

## P0 Blockers

Do not promote the candidate if any blocker is true:

- Default-template accuracy regresses.
- Default-template mismatch count increases.
- Expanded-boundary accuracy regresses materially.
- Expanded-boundary rerun drift remains above tolerance.
- The candidate flips any hard-case anchor against the adjudication rule.
- The candidate improves one hard case by creating a new hard-case migration elsewhere.
- The review artifact is based on a generation run with missing `current_slot` and no `--fallback-current-slot unknown`.

## Hard-Case Checks

For each candidate, explicitly answer:

- Does `10.3390/nu17193125` remain `clinical` under the current three-slot taxonomy?
- Does `10.1186/s13195-022-01005-8` remain `methods` as a head-to-head assay benchmark?
- Does `10.1212/WNL.0000000000201479` remain `clinical` as clinic-based dementia-risk prediction?
- Does `10.1001/jamaneurol.2025.3217` remain `clinical` as preclinical AD screening/classification utility?

If any answer is no, the candidate needs manual review before another benchmark run is interpreted as an improvement.

## Required Commands

Use the existing evaluation path. Replace run IDs with the candidate-specific IDs.

```bash
.venv/bin/python scripts/eval/generate_slot_classification_prompt_candidate_predictions.py --goldset-csv tests/gold_set/gold_standard_template.csv --candidate-prompt <candidate_prompt_path> --candidate-id <candidate_id> --out-dir snapshots/slot_classification_predictions --run-id <candidate_default_generation_run_id> --fallback-current-slot unknown
.venv/bin/python scripts/eval/audit_slot_classification_goldset.py --goldset-csv tests/gold_set/gold_standard_template.csv --predictions-jsonl snapshots/slot_classification_predictions/<candidate_default_generation_run_id>/predictions.jsonl --out-dir snapshots/slot_classification_goldset_audits --run-id <candidate_default_audit_run_id>
.venv/bin/python scripts/eval/generate_slot_classification_prompt_candidate_predictions.py --goldset-csv tests/gold_set/slot_classification_boundary_companion_expanded_20260422.csv --candidate-prompt <candidate_prompt_path> --candidate-id <candidate_id> --out-dir snapshots/slot_classification_predictions --run-id <candidate_boundary_generation_run_id> --fallback-current-slot unknown
.venv/bin/python scripts/eval/audit_slot_classification_goldset.py --goldset-csv tests/gold_set/slot_classification_boundary_companion_expanded_20260422.csv --predictions-jsonl snapshots/slot_classification_predictions/<candidate_boundary_generation_run_id>/predictions.jsonl --out-dir snapshots/slot_classification_goldset_audits --run-id <candidate_boundary_audit_run_id>
.venv/bin/python scripts/eval/compare_slot_classification_paired_benchmarks.py --baseline-default <baseline_default_summary_or_run> --baseline-boundary <baseline_boundary_summary_or_run> --candidate-default <candidate_default_summary_or_run> --candidate-boundary <candidate_boundary_summary_or_run> --out-dir snapshots/slot_classification_paired_compares --run-id <candidate_paired_compare_run_id>
.venv/bin/python scripts/eval/audit_slot_classification_rerun_drift.py --prior-run <prior_default_audit_run> --new-run <candidate_default_audit_run> --out-dir snapshots/slot_classification_rerun_drift --run-id <candidate_default_rerun_drift_run_id>
.venv/bin/python scripts/eval/audit_slot_classification_rerun_drift.py --prior-run <prior_boundary_audit_run> --new-run <candidate_boundary_audit_run> --out-dir snapshots/slot_classification_rerun_drift --run-id <candidate_boundary_rerun_drift_run_id>
.venv/bin/python scripts/eval/recommend_slot_classification_tuning_review.py --paired-compare-summary <candidate_paired_compare_run> --default-rerun-drift-summary <candidate_default_rerun_drift_run> --boundary-rerun-drift-summary <candidate_boundary_rerun_drift_run> --out-dir snapshots/slot_classification_tuning_review --run-id <candidate_tuning_review_run_id>
```

## Promotion-Ready Criteria

A candidate can be considered for runtime change only if the tuning review emits:

- `review_ready=true`
- `prompt_change_ready=true`
- no paired-compare regression
- default rerun status not `warn`
- expanded-boundary rerun status not `warn`
- no unresolved hard-case anchor violation

Any runtime prompt or policy change still needs a separate implementation patch and targeted tests.

## Non-Goals

- This checklist does not approve a prompt change.
- This checklist does not introduce a review/resource slot.
- This checklist does not rewrite historical labels.
- This checklist does not widen inference payloads.
