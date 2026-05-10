# Slot Classification Tuning Advisory Hold Runbook

Status: operational report; additive review-artifact runbook
Date: 2026-04-24
Lane: slot classification tuning review
Scope: latest paired-compare and rerun-drift evidence for slot prompt/policy tuning

## Purpose

Record why the current slot-classification prompt or policy candidate should stay on hold without changing runtime slot classification behavior.

This report is not a canonical state store and does not replace slot runtime code, prompt policy, or the paper/run/artifact model. It summarizes a completed advisory review-artifact lane.

## Layer Classification

Layer: review/gate artifact.

The source run artifacts are derived from paired benchmark comparison and same-code rerun-drift evidence. They are useful for calibration and operator guidance, but they are not replacement truth stores.

## Source Artifacts

Latest tuning review:

- `snapshots/slot_classification_tuning_review/slot_classification_tuning_review_advisory_hold_20260424_r1/summary.json`
- `snapshots/slot_classification_tuning_review/slot_classification_tuning_review_advisory_hold_20260424_r1/audit.md`

Inputs:

- `snapshots/slot_classification_paired_compares/slot_classification_tie_breaker_compare_20260422_r1/summary.json`
- `snapshots/slot_classification_rerun_drift/slot_classification_default_rerun_drift_20260422_r1/summary.json`
- `snapshots/slot_classification_rerun_drift/slot_classification_boundary_rerun_drift_20260422_r1/summary.json`

Operator surface:

```bash
.venv/bin/paperpipe doctor
```

## Current Decision

The latest review supports this interpretation:

- Keep the current slot prompt/policy in place.
- Do not treat the candidate slot prompt or policy as an improvement.
- Treat the review as advisory-only.
- Require paired-compare recovery and rerun-stability evidence before promoting any slot prompt/policy change.

Current artifact state:

- `recommended_action=hold_current_prompt_policy`
- `review_ready=false`
- `prompt_change_ready=false`
- `prompt_change_status=blocked_advisory`
- `paired_compare_status=regressed`
- `default_rerun_status=warn`
- `boundary_rerun_status=warn`
- `paired_compare_failed_checks=["default_template_accuracy", "default_template_mismatch_count"]`
- `paired_compare_regressions=["default_template_accuracy", "default_template_mismatch_count"]`
- `default_rerun_drift_rate=0.09090909090909091`
- `boundary_rerun_drift_rate=0.25`

## Rerun Stability Follow-up

Follow-up report:

- `docs/reports/Slot_Classification_Rerun_Stability_Followup_2026-04-24.md`

The corrected 2026-04-24 follow-up (`r2`) strengthens this advisory hold:

- Default template rerun drift remains nonzero: `1/11`
- Expanded boundary rerun drift is high: `3/7`
- Expanded boundary accuracy fell to `0.5714`
- The unstable rows are concentrated in clinical-vs-methods hard cases

Do not use the superseded `20260424_r1` follow-up artifacts as tuning evidence; those generation runs omitted `--fallback-current-slot unknown` and produced `missing_current_slot` rows.

## Operator Rule

If this lane appears in future status checks, use the following default:

- Runtime behavior: keep current slot classification prompt/policy unchanged.
- Prompt or policy candidates: require paired compare plus rerun-drift evidence before treating any apparent improvement as durable.
- Benchmark interpretation: single-run live replay deltas remain advisory when rerun drift is nonzero.
- Promotion work: require a separate artifact with `review_ready=true` and `prompt_change_ready=true`.

## Do Not Do

Do not use this runbook to:

- change slot classification runtime behavior
- promote the candidate prompt or policy
- treat a single replay artifact as promotion-grade evidence
- ignore same-code rerun drift on hard benchmark rows
- treat review artifacts as canonical paper state
- widen inference payloads or send raw state externally

## Reopen Criteria

Reopen the lane only if one of these occurs:

- A new paired compare no longer regresses `default_template_accuracy` or `default_template_mismatch_count`.
- Default benchmark rerun drift is within the configured tolerance.
- Boundary benchmark rerun drift is within the configured tolerance.
- Additional adjudicated boundary rows materially change the review conclusion.
- A separate review artifact explicitly marks the prompt change as ready.

## Verification Snapshot

Last checked on 2026-04-24:

```bash
.venv/bin/python scripts/eval/recommend_slot_classification_tuning_review.py --paired-compare-summary snapshots/slot_classification_paired_compares/slot_classification_tie_breaker_compare_20260422_r1 --default-rerun-drift-summary snapshots/slot_classification_rerun_drift/slot_classification_default_rerun_drift_20260422_r1 --boundary-rerun-drift-summary snapshots/slot_classification_rerun_drift/slot_classification_boundary_rerun_drift_20260422_r1 --out-dir snapshots/slot_classification_tuning_review --run-id slot_classification_tuning_review_advisory_hold_20260424_r1
.venv/bin/paperpipe doctor
python3 scripts/lint_docs.py
```

Result:

- latest tuning review emits `recommended_action=hold_current_prompt_policy`
- latest tuning review emits `review_ready=false`
- latest tuning review emits `prompt_change_ready=false`
- `paperpipe doctor` surfaces the advisory hold
- docs lint passed

## Next PR-Sized Actions

1. Leave runtime slot classification behavior unchanged.
2. Add or adjudicate more boundary rows before another prompt/policy candidate.
3. Re-run paired compare and rerun-drift checks before any future promotion decision.
