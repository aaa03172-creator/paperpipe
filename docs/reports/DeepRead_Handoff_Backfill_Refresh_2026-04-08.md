# DeepRead Handoff Backfill Refresh (2026-04-08)

Status: Historical validation report
Date: 2026-04-08
Owner: Runtime/backend maintainers
Canonical parents:
- `docs/reports/DeepRead_Handoff_Baseline_Compare_2026-04-08.md`
- `docs/reports/DeepRead_Context_Manifest_Artifact_2026-04-01.md`

## Purpose

Capture the first derived-artifact backfill and refreshed baseline cut for the fixed coric deep-read handoff batch.

This note is intentionally narrow.

It does not change the deep-read runtime.
It records a bounded operator action:

- rebuild additive handoff artifacts from saved `run_meta.json` and `bootstrap_meta.json`
- reduce legacy `missing` summary rates on the existing fixed coric regression slice
- cut a fresh baseline once the saved runs expose the new summary fields

## Why this was needed

The first seed baseline from earlier on 2026-04-08 was honest but migration-heavy:

- `goal_drift_missing_rate=1.0`
- `step_stability_missing_rate=1.0`
- `failure_recovery_missing_rate=1.0`
- `context_manifest_missing_rate=0.7`

That was acceptable as an initial anchor, but it was too legacy-heavy to serve as the long-term baseline for the new handoff diagnostics.

The repo already had enough saved inputs to rebuild these artifacts safely because the handoff files are derived from:

- `run_meta.json`
- `bootstrap_meta.json`

No canonical DB state or paper note content needed to change.

## Commands

```bash
# 1) dry-run the fixed coric handoff batch
python3 scripts/backfill_deepread_handoff_artifacts.py \
  --manifest goldset/manifests/deepread_handoff_coric_regression_20260408.json

# 2) apply the derived-artifact refresh for that same batch
python3 scripts/backfill_deepread_handoff_artifacts.py \
  --manifest goldset/manifests/deepread_handoff_coric_regression_20260408.json \
  --apply

# 3) rebuild the audit snapshot after backfill
python3 scripts/eval/audit_deepread_handoff.py \
  --manifest goldset/manifests/deepread_handoff_coric_regression_20260408.json \
  --out-dir snapshots/deepread_handoff_eval \
  --run-id deepread_handoff_coric_regression_20260408_backfilled

# 4) seed and promote the refreshed baseline
python3 scripts/eval/compare_deepread_handoff_audits.py \
  --baseline snapshots/deepread_handoff_eval/deepread_handoff_coric_regression_20260408_backfilled \
  --new snapshots/deepread_handoff_eval/deepread_handoff_coric_regression_20260408_backfilled \
  --out snapshots/deepread_handoff_eval/deepread_handoff_coric_regression_20260408_backfilled_seed_compare/report.json \
  --promote-dir baselines/deepread_handoff
```

## Results

Dry-run candidate counts on the fixed coric batch:

- `runs_scanned=10`
- `runs_needing_update=10`
- `acceptance_contract_needing_update=8`
- `quality_gate_needing_update=10`
- `context_manifest_needing_update=9`

Refreshed audit snapshot:

- `run_count=10`
- `overall pass=7`
- `overall warn=3`
- `review_ready_count=7`
- `promotion_candidate_count=10`
- `step_stability_status_counts={"pass": 6, "warn": 4}`
- `failure_recovery_status_counts={"pass": 10}`
- `goal_drift_status_counts={"missing": 1, "pass": 8, "warn": 1}`
- `context_manifest_missing_count=1`

Visible reason-code distribution after refresh:

- `VERIFIER_FAILED=6`
- `HEURISTIC_FALLBACK_USED=2`

Compared with the earlier migration baseline, the refreshed batch now exposes:

- `goal_drift_missing_rate=0.1`
- `step_stability_missing_rate=0.0`
- `failure_recovery_missing_rate=0.0`
- `context_manifest_missing_rate=0.1`

## Interpretation

The refreshed baseline is stricter, not looser.

Two important effects happened at the same time:

1. `missing` rates dropped sharply because the saved runs now carry the new derived summaries.
2. `step_stability_warn_or_fail_rate` increased from the migration baseline because verifier failures are now surfaced explicitly instead of hiding behind missing summaries.

That is why a fresh baseline cut is the correct move here.

Using the legacy seed baseline as the long-term comparator would incorrectly treat improved observability as a regression.

## Artifacts

- backfill script:
  - `scripts/backfill_deepread_handoff_artifacts.py`
- refreshed audit snapshot:
  - `snapshots/deepread_handoff_eval/deepread_handoff_coric_regression_20260408_backfilled/summary.json`
  - `snapshots/deepread_handoff_eval/deepread_handoff_coric_regression_20260408_backfilled/details.json`
- refreshed promoted baseline:
  - `baselines/deepread_handoff/deepread_handoff_coric_regression_20260408_backfilled/summary.json`
  - `baselines/deepread_handoff/deepread_handoff_coric_regression_20260408_backfilled/details.json`
  - `baselines/deepread_handoff/deepread_handoff_coric_regression_20260408_backfilled/promotion_report.json`

## Notes

- This was a derived-artifact refresh only.
- The action did not modify canonical paper state, queue semantics, or provider behavior.
- One run still lacks a context manifest and therefore still contributes one `goal_drift` `missing` entry.
- The old baseline is still useful as migration evidence, but the refreshed baseline is the better comparator for future long-run handoff changes.
