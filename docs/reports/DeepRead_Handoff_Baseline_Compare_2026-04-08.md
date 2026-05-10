# DeepRead Handoff Baseline Compare (2026-04-08)

Status: Historical validation report
Date: 2026-04-08
Owner: Runtime/backend maintainers
Canonical parents:
- `docs/reports/Gemma_GLM51_Scion_Fit_Review_2026-04-08.md`
- `docs/reports/DeepRead_Context_Manifest_Artifact_2026-04-01.md`

## Purpose

Capture the first fixed-batch baseline seed and baseline-vs-new compare cycle for the deep-read handoff audit lane.

This note is intentionally narrow.

It does not define a new runtime contract.
It records that the current additive audit lane can now:

- load a repo-grounded saved-run manifest
- aggregate long-run handoff summaries into a repeatable audit snapshot
- compare a new audit snapshot against a promoted baseline
- preserve manifest provenance in the audit output

## Inputs

- fixed regression manifest:
  - `goldset/manifests/deepread_handoff_coric_regression_20260408.json`
- bounded paper lane:
  - `zotero:coricTargetingProdromalAlzheimer2015`
- saved run count:
  - `10`

Important caveat:

- this is a seed baseline for the current saved coric artifact batch
- it is intentionally honest about legacy coverage gaps
- most saved runs predate the new `goal_drift_summary`, `step_stability_summary`, and `failure_recovery_summary` fields
- the resulting baseline therefore keeps the current `missing` rates instead of pretending those summaries already exist

## Commands

```bash
# 1) audit the fixed saved-run manifest into a reproducible snapshot
python3 scripts/eval/audit_deepread_handoff.py \
  --manifest goldset/manifests/deepread_handoff_coric_regression_20260408.json \
  --out-dir snapshots/deepread_handoff_eval \
  --run-id deepread_handoff_coric_regression_20260408_baseline

# 2) seed and promote the first baseline snapshot
python3 scripts/eval/compare_deepread_handoff_audits.py \
  --baseline snapshots/deepread_handoff_eval/deepread_handoff_coric_regression_20260408_baseline \
  --new snapshots/deepread_handoff_eval/deepread_handoff_coric_regression_20260408_baseline \
  --out snapshots/deepread_handoff_eval/deepread_handoff_coric_regression_20260408_seed_compare/report.json \
  --promote-dir baselines/deepread_handoff

# 3) re-check a separate snapshot against the promoted baseline
python3 scripts/eval/compare_deepread_handoff_audits.py \
  --baseline baselines/deepread_handoff/deepread_handoff_coric_regression_20260408_baseline \
  --new snapshots/deepread_handoff_eval/coric_handoff_manifest_smoke \
  --out snapshots/deepread_handoff_eval/deepread_handoff_coric_regression_20260408_recheck/report.json
```

## Results

- audit snapshot:
  - `run_count=10`
  - `overall pass=7`
  - `overall warn=3`
  - `review_ready_count=7`
  - `promotion_candidate_count=10`
  - `context_manifest_missing_count=7`
- reason-code distribution:
  - `VERIFIER_FAILED=3`
- summary-field coverage:
  - `goal_drift_missing_rate=1.0`
  - `step_stability_missing_rate=1.0`
  - `failure_recovery_missing_rate=1.0`
- seed compare decision:
  - `passed=true`
  - `failed_checks=[]`
  - `regressions=[]`
- baseline re-check against a separate manifest-driven snapshot:
  - `passed=true`
  - `failed_checks=[]`
  - `regressions=[]`

## Artifacts

- manifest-driven audit snapshot:
  - `snapshots/deepread_handoff_eval/deepread_handoff_coric_regression_20260408_baseline/summary.json`
  - `snapshots/deepread_handoff_eval/deepread_handoff_coric_regression_20260408_baseline/details.json`
- seed compare and promotion record:
  - `snapshots/deepread_handoff_eval/deepread_handoff_coric_regression_20260408_seed_compare/report.json`
  - `baselines/deepread_handoff/deepread_handoff_coric_regression_20260408_baseline/summary.json`
  - `baselines/deepread_handoff/deepread_handoff_coric_regression_20260408_baseline/details.json`
  - `baselines/deepread_handoff/deepread_handoff_coric_regression_20260408_baseline/promotion_report.json`
- baseline re-check report:
  - `snapshots/deepread_handoff_eval/deepread_handoff_coric_regression_20260408_recheck/report.json`

## Notes

- The new compare gate now checks not only warn/fail rates but also `missing`-summary rates for:
  - `goal_drift`
  - `step_stability`
  - `failure_recovery`
- This matters because a later run could otherwise appear stable simply by omitting the derived summaries entirely.
- The current baseline should not be misread as a target quality bar.
- It is a migration-era anchor for the existing saved coric runs.
- Once enough saved runs include the new handoff summaries, the next safe move is to cut a fresh baseline rather than loosening the current thresholds.
