# Evidence Grounding External Contract Migration Plan

Status: draft review artifact; not an approval record.
Layer: review/gate artifact.
Canonical posture: non-canonical until explicitly adopted by the project.

## Scope

This plan covers the additive evidence-grounding artifacts used by the PR1 roadmap lane:

- `evidence_grounding_scorecard.v1`
- `evidence_grounding_benchmark.v1`
- `evidence_grounding_benchmark_manifest_package.v1`
- `evidence_grounding_benchmark_run_package.v1`
- `evidence_grounding_scorecard_comparison.v1`
- `evidence_grounding_fixed_goldset_comparison_suite.v1`
- `evidence_grounding_fixed_goldset_comparison_suite_package.v1`
- `evidence_grounding_threshold_calibration.v1`
- `evidence_grounding_threshold_adoption_review.v1`
- `evidence_grounding_threshold_adoption_review_package.v1`
- `evidence_grounding_fixed_goldset_run_readiness.v1`
- `claim_evidence_eval_candidate_export.v1`
- `claim_evidence_correction_repair_plan.v1`
- `claim_evidence_reviewed_eval_fixtures_bundle.v1`
- `paper_understanding_gold_release_package.v1`
- `paper_understanding_gold_release_readiness.v1`

## Migration Rules

1. Keep existing deepread outputs, raw correction logs, run directories, and paper-understanding gold files as their current layers. Do not promote derived scorecards, threshold reports, or audit reports to canonical truth.
2. Introduce external contract usage as an opt-in reader behavior. Existing internal readers should continue to load artifacts by their current schema versions and fail closed on unknown required fields.
3. Treat scorecard and benchmark artifacts as additive evidence summaries. They may reference canonical state and raw/source evidence, but they must not replace paper/run/artifact state in `src/db_utils.py` or FastAPI paper/run models.
4. Require contract compatibility evidence before any public contract adoption. Compatibility must cover the schema versions listed in this document and must report `fail_count=0`.
5. Keep production-threshold adoption separate from contract migration. Threshold adoption requires complete P0 metrics, human review, and explicit production opt-in.
6. Keep correction repair handoff separate from raw log mutation. A `claim_evidence_correction_repair_plan.v1` artifact can prove repair coverage for external contract review, but it does not make the raw correction JSONL replayable.

## Compatibility Expectations

- New readers should tolerate additive fields.
- Required fields in the listed schema versions should remain stable once the external contract is approved.
- Path-like evidence in public outputs should be masked or repository-relative when possible.
- Review/gate artifacts must remain traceable to upstream benchmark, gold release, threshold, and correction evidence.

## Rollout Steps

1. Generate or collect all required review/gate artifacts for seed, eval, and holdout splits.
2. Run contract compatibility over the collected artifact set.
3. Resolve compatibility findings and stale package artifacts.
4. Run contract readiness with this migration plan, the backfill plan, the public contract draft, a human approval reference, and explicit opt-in.
5. Only after readiness passes, document the adopted external contract version and supported artifact paths.

## Rollback

If compatibility or readiness fails after adoption, disable external contract consumers and continue using internal artifact readers. Because this lane is additive and non-canonical, rollback must not require DB migration or raw evidence rewriting.
