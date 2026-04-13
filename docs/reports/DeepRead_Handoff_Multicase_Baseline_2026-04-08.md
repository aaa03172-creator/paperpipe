# DeepRead Handoff Multicase Baseline (2026-04-08)

Status: Historical validation report
Date: 2026-04-08
Owner: Runtime/backend maintainers
Canonical parents:
- `docs/DEEPREAD_HANDOFF_QUALITY_LOOP.md`
- `docs/reports/DeepRead_Handoff_Backfill_Refresh_2026-04-08.md`

## Purpose

Capture the second fixed-batch deep-read handoff baseline cut that reduces single-paper bias without widening the runtime shape.

This note is intentionally narrow.

It does not add a new runtime owner.
It records a bounded operator action:

- define a broader saved-run manifest spanning multiple biomedical papers
- refresh additive handoff artifacts for that bounded batch
- audit the batch under the existing handoff quality loop
- promote a companion baseline once the saved runs expose the derived summaries cleanly

## Why this was needed

The refreshed coric baseline is still useful, but it is a single-paper slice.

That is enough for continuity checks inside the original saved lane, but not enough for confident statements about cross-paper stability.

The repo already had a small, bounded set of saved runs that could broaden the batch safely:

- `zotero:parkDiscoveryDualactionSmall2022`
- `zotero:decarliMildCognitiveImpairment2003`
- `zotero:duboisClinicalDiagnosisAlzheimers2021`

This mix preserves the current paper/job/artifact boundary while adding:

- one review-ready positive control
- one explicit failure path
- repeated verifier-failed warn paths across multiple biomedical papers

## Commands

```bash
# 1) dry-run the multicase fixed batch
python3 scripts/backfill_deepread_handoff_artifacts.py \
  --manifest goldset/manifests/deepread_handoff_multicase_regression_20260408.json

# 2) apply the derived-artifact refresh for that same batch
python3 scripts/backfill_deepread_handoff_artifacts.py \
  --manifest goldset/manifests/deepread_handoff_multicase_regression_20260408.json \
  --apply

# 3) rebuild the audit snapshot after backfill
python3 scripts/eval/audit_deepread_handoff.py \
  --manifest goldset/manifests/deepread_handoff_multicase_regression_20260408.json \
  --out-dir snapshots/deepread_handoff_eval \
  --run-id deepread_handoff_multicase_regression_20260408_backfilled

# 4) seed and promote the multicase baseline
python3 scripts/eval/compare_deepread_handoff_audits.py \
  --baseline snapshots/deepread_handoff_eval/deepread_handoff_multicase_regression_20260408_backfilled \
  --new snapshots/deepread_handoff_eval/deepread_handoff_multicase_regression_20260408_backfilled \
  --out snapshots/deepread_handoff_eval/deepread_handoff_multicase_regression_20260408_seed_compare/report.json \
  --promote-dir baselines/deepread_handoff
```

## Results

Initial dry-run candidate counts on the multicase batch:

- `runs_scanned=8`
- `runs_needing_update=8`
- `acceptance_contract_needing_update=3`
- `quality_gate_needing_update=8`
- `context_manifest_needing_update=8`

Clean dry-run after apply:

- `runs_needing_update=0`
- `acceptance_contract_needing_update=0`
- `quality_gate_needing_update=0`
- `context_manifest_needing_update=0`

Refreshed audit snapshot:

- `run_count=8`
- `overall pass=1`
- `overall warn=6`
- `overall fail=1`
- `review_ready_count=1`
- `promotion_candidate_count=7`
- `step_stability_status_counts={"fail": 1, "pass": 1, "warn": 6}`
- `failure_recovery_status_counts={"pass": 8}`
- `goal_drift_status_counts={"pass": 7, "warn": 1}`
- `context_manifest_missing_count=0`

Visible reason-code distribution after refresh:

- `VERIFIER_FAILED=12`
- `RUN_NOT_SUCCEEDED=2`
- `MISSING_CLAIMSET_RESOLVED=1`
- `CLAIMSET_NOT_READY=1`
- `FINAL_CLAIM_COUNT_ZERO=1`
- `READER_TIMEOUT_TRIGGERED=1`

Seed compare decision:

- `passed=true`
- `failed_checks=[]`
- `regressions=[]`

Baseline re-check against the promoted multicase baseline:

- `passed=true`
- `failed_checks=[]`
- `regressions=[]`

## Interpretation

This multicase baseline is a companion, not a replacement.

The coric baseline remains useful for tight continuity on the original single-paper slice.

The multicase baseline is better when the change under review could affect:

- cross-paper verifier behavior
- timeout and recovery visibility
- goal-drift summaries outside one saved-paper lane

It is also a cleaner observability baseline than the original migration-era coric seed because this batch now has:

- `goal_drift_missing_rate=0.0`
- `step_stability_missing_rate=0.0`
- `failure_recovery_missing_rate=0.0`
- `context_manifest_missing_rate=0.0`

## Artifacts

- fixed multicase manifest:
  - `goldset/manifests/deepread_handoff_multicase_regression_20260408.json`
- refreshed audit snapshot:
  - `snapshots/deepread_handoff_eval/deepread_handoff_multicase_regression_20260408_backfilled/summary.json`
  - `snapshots/deepread_handoff_eval/deepread_handoff_multicase_regression_20260408_backfilled/details.json`
- seed compare and promoted baseline:
  - `snapshots/deepread_handoff_eval/deepread_handoff_multicase_regression_20260408_seed_compare/report.json`
  - `baselines/deepread_handoff/deepread_handoff_multicase_regression_20260408_backfilled/summary.json`
  - `baselines/deepread_handoff/deepread_handoff_multicase_regression_20260408_backfilled/details.json`
  - `baselines/deepread_handoff/deepread_handoff_multicase_regression_20260408_backfilled/promotion_report.json`
- baseline re-check report:
  - `snapshots/deepread_handoff_eval/deepread_handoff_multicase_regression_20260408_recheck/report.json`

## Notes

- This was a derived-artifact refresh and baseline promotion only.
- The action did not modify canonical paper state, queue semantics, provider routing, or viewer behavior.
- The temporary audit inconsistency seen before re-running the multicase snapshot was resolved by rebuilding the audit from the refreshed saved-run files; no audit-script logic change was required.
