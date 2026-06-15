# Evidence Grounding Public Contract Draft

Status: draft public contract; not approved for stable external use.
Layer: user-facing artifact/export contract draft.
Canonical posture: non-canonical until explicitly adopted.

## Contract Boundary

Evidence-grounding contract artifacts summarize and review evidence produced by the PaperPipe runtime. They are not canonical paper state, run state, raw source data, or raw memory.

External consumers may use these artifacts only after contract readiness is approved and explicitly opted in.

## Artifact Families

- Scorecard: `evidence_grounding_scorecard.v1`
- Benchmark: `evidence_grounding_benchmark.v1`
- Benchmark packages: `evidence_grounding_benchmark_manifest_package.v1`, `evidence_grounding_benchmark_run_package.v1`
- Comparison: `evidence_grounding_scorecard_comparison.v1`, `evidence_grounding_fixed_goldset_comparison_suite.v1`, `evidence_grounding_fixed_goldset_comparison_suite_package.v1`
- Threshold review: `evidence_grounding_threshold_calibration.v1`, `evidence_grounding_threshold_adoption_review.v1`, `evidence_grounding_threshold_adoption_review_package.v1`
- Correction review: `claim_evidence_eval_candidate_export.v1`, `claim_evidence_correction_repair_plan.v1`, `claim_evidence_reviewed_eval_fixtures_bundle.v1`
- Gold release review: `paper_understanding_gold_release_package.v1`, `paper_understanding_gold_release_readiness.v1`

## Stability Rules

1. Schema versions are part of the contract.
2. Additive optional fields may be introduced without breaking the contract.
3. Removing required fields, changing metric meaning, or promoting derived artifacts to canonical truth requires a new contract review.
4. Human-review and production-readiness booleans must not be inferred from compatibility alone.
5. External consumers must treat `external_contract_ready=false` as not ready, even when individual compatibility checks pass.

## Required Readiness Evidence

- Compatibility report with every required schema version represented and `fail_count=0`.
- Migration plan.
- Backfill plan.
- Public contract document.
- Human reviewer approval reference.
- Explicit external-contract opt-in.

## Payload Handling

- Prefer masked or repository-relative paths in user-facing outputs.
- Do not expose secrets, API keys, private document contents, or personal filesystem paths in public contract artifacts.
- Keep raw sources and raw memory out of public contract payloads unless a canonical document explicitly adopts a bounded excerpt strategy.

## Current Draft Limitations

- This draft does not approve external use.
- Current roadmap evidence still has known blockers around scorecard readiness, `overstatement_rate`, raw correction-log replayability, threshold package readiness, and human approval.
- Runtime scorecards may surface warning-level `reason_codes` such as `missing_p0_gold_metrics` and `accepted_corrections_not_replayable`. These are review-gate diagnostics only; they do not promote scorecards, correction logs, or gold fixtures to canonical paper state.
