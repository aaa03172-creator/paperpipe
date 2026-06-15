# Evidence Grounding External Contract Backfill Plan

Status: draft review artifact; not an approval record.
Layer: review/gate artifact.
Canonical posture: non-canonical until explicitly adopted by the project.

## Scope

This plan defines how to backfill evidence-grounding contract artifacts for existing fixed-goldset evidence without changing canonical runtime truth.

## Inputs

- Paper-understanding gold release package and readiness report.
- Baseline and candidate benchmark run packages for seed, eval, and holdout.
- Scorecard-aware benchmark reports with embedded `evidence_grounding_scorecard.v1` items.
- Fixed-goldset comparison suite package.
- Threshold calibration and threshold adoption review package.
- Claim/evidence correction export, repair plan, or reviewed fixtures bundle.

## Required Backfill Outputs

- Scorecards for every benchmarked paper/run item.
- Aggregate benchmark runtime and gold-scored metrics for every split.
- Fixed-goldset comparison reports for seed, eval, and holdout.
- Threshold calibration and adoption reports that include every required P0 metric.
- Contract compatibility and readiness reports that cover the required schema versions.

## Procedure

1. Rebuild benchmark manifests from the gold release package using complete baseline and candidate run roots.
2. Rebuild baseline and candidate benchmark run packages with complete parser/model/prompt/profile lineage.
3. Attach reviewed claim/evidence fixtures where human-reviewed `OVERSTATED_RESULT` labels exist, then rebuild scorecards so `overstatement_rate` is available.
4. Rebuild the fixed-goldset comparison suite package from the rebuilt benchmark run packages.
5. Re-run threshold calibration and threshold-adoption review from the rebuilt comparison evidence.
6. Export or attach correction repair/review evidence without mutating raw correction logs by default.
7. Run contract compatibility and readiness over the resulting artifact set.

## Validation Gates

- Every split has ready baseline and candidate run evidence.
- Every benchmark item has an embedded scorecard.
- Aggregate P0 metrics include `overstatement_rate`.
- Threshold adoption is reviewed and explicitly opted in before production readiness is true.
- Contract compatibility has `fail_count=0`.
- Contract readiness has no blockers only after review documents, approval reference, and explicit opt-in are present.

## Non-Goals

- No raw PDF, raw memory, or correction-log rewriting as part of this draft plan.
- No DB/state migration.
- No automatic human-review approval.
- No production-threshold adoption without explicit review.
