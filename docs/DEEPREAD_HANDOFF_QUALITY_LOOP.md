# DeepRead Handoff Quality Loop

Status: Active
Date: 2026-04-08
Owner: Runtime/backend maintainers
Canonical: `docs/DEEPREAD_HANDOFF_QUALITY_LOOP.md`

Related docs:
- `docs/reports/DeepRead_Handoff_Baseline_Compare_2026-04-08.md`
- `docs/reports/DeepRead_Handoff_Backfill_Refresh_2026-04-08.md`
- `docs/reports/DeepRead_Handoff_Multicase_Baseline_2026-04-08.md`
- `docs/reports/DeepRead_Context_Manifest_Artifact_2026-04-01.md`
- `docs/PaperPipe_Minimum_Operating_Principles.md`

## Purpose

Run the bounded local-first quality loop for saved deep-read handoff artifacts.

This loop is for:
- fixed saved-run manifests
- derived handoff artifact refresh
- audit snapshot generation
- baseline compare and optional promotion

This loop is not:
- a new runtime owner
- a provider-selection framework
- a reason to reopen generalized multi-agent orchestration

## Current scope

The current deep-read handoff loop measures:
- `review_ready`
- `goal_drift`
- `step_stability`
- `failure_recovery`
- `context_manifest` coverage

The loop stays additive.

It only reads or refreshes derived files under saved run directories:
- `acceptance_contract.json`
- `quality_gate.json`
- `context_manifest.json`

Canonical paper state, DB state, provider routing, and note ownership do not change here.

## Active batches and baselines

Current fixed regression manifests:
- `goldset/manifests/deepread_handoff_coric_regression_20260408.json`
- `goldset/manifests/deepread_handoff_multicase_regression_20260408.json`

Current preferred baselines:
- `baselines/deepread_handoff/deepread_handoff_coric_regression_20260408_backfilled/summary.json`
- `baselines/deepread_handoff/deepread_handoff_multicase_regression_20260408_backfilled/summary.json`

Historical migration baseline:
- `baselines/deepread_handoff/deepread_handoff_coric_regression_20260408_baseline/summary.json`

Use the backfilled baselines for current compare work.

Keep the earlier baseline only as migration evidence showing how much summary coverage improved after derived-artifact refresh.

Use the coric batch when the question is tight continuity on the original saved-paper slice.

Use the multicase batch when the question is whether a change holds across more than one biomedical paper lane.

For changes that can affect cross-paper deep-read behavior, run both.

Use `continuity` gate mode when the change is limited to the original saved-paper slice or you only need to confirm the coric continuity baseline still holds.

Use `cross-paper` gate mode when the change touches shared deep-read handoff builders, backfill logic, audit aggregation, compare thresholds, or other behavior that can surface across more than one biomedical paper lane.

Docs-only edits usually do not require this gate.

## Commands

Examples below use the coric batch for brevity.

Swap in the multicase manifest, run id, and baseline path when you want the broader mixed-paper regression slice.

### 1) Dry-run derived-artifact backfill

```bash
python3 scripts/backfill_deepread_handoff_artifacts.py \
  --manifest goldset/manifests/deepread_handoff_coric_regression_20260408.json
```

Use this first.

Expected result for an already-refreshed batch:
- `runs_needing_update=0`

### 2) Apply derived-artifact backfill

```bash
python3 scripts/backfill_deepread_handoff_artifacts.py \
  --manifest goldset/manifests/deepread_handoff_coric_regression_20260408.json \
  --apply
```

Use this only after the dry-run output is bounded and expected.

### 3) Build an audit snapshot

```bash
python3 scripts/eval/audit_deepread_handoff.py \
  --manifest goldset/manifests/deepread_handoff_coric_regression_20260408.json \
  --out-dir snapshots/deepread_handoff_eval \
  --run-id deepread_handoff_<tag>
```

Main outputs:
- `summary.json`
- `details.json`

### 4) Compare against the current baseline

```bash
python3 scripts/eval/compare_deepread_handoff_audits.py \
  --baseline baselines/deepread_handoff/deepread_handoff_coric_regression_20260408_backfilled \
  --new snapshots/deepread_handoff_eval/deepread_handoff_<tag> \
  --out snapshots/deepread_handoff_eval/deepread_handoff_<tag>_compare/report.json
```

### 5) Recommend the gate mode from changed files

```bash
python3 scripts/eval/recommend_deepread_handoff_gate_mode.py \
  --files src/services/deepread_handoff_artifacts.py tests/test_deepread_handoff_artifacts.py
```

Current branch diff against an integration ref:

```bash
python3 scripts/eval/recommend_deepread_handoff_gate_mode.py \
  --against-ref origin/main
```

Possible outputs:
- `mode=not_applicable`
- `mode=continuity`
- `mode=cross-paper`

Use this as an operator aid.

It does not replace judgment, but it keeps the current coric-only vs coric+multicase rule explicit and machine-readable.

`--against-ref <ref>` compares `merge-base(<ref>, HEAD)...HEAD`, so it is the shortest path for asking "what gate mode does my current branch diff imply?"

The existing `python3 scripts/check_pr_scope.py --base <base> --head <head>` branch guard now also prints this deep-read gate recommendation as a non-blocking advisory in the same log stream.

### 6) Run the bounded gate summary

Continuity-only gate:

```bash
python3 scripts/eval/check_deepread_handoff_gate.py \
  --mode continuity \
  --coric-new snapshots/deepread_handoff_eval/deepread_handoff_<tag> \
  --run-id deepread_handoff_gate_<tag>
```

Cross-paper gate:

```bash
python3 scripts/eval/check_deepread_handoff_gate.py \
  --mode cross-paper \
  --coric-new snapshots/deepread_handoff_eval/deepread_handoff_coric_<tag> \
  --multicase-new snapshots/deepread_handoff_eval/deepread_handoff_multicase_<tag> \
  --run-id deepread_handoff_gate_<tag>
```

Main output:
- `snapshots/deepread_handoff_gate/<run_id>/summary.json`

### 7) Recommend and run in one step

Current branch diff against an integration ref, then run the implied gate:

```bash
python3 scripts/eval/run_recommended_deepread_handoff_gate.py \
  --against-ref origin/main \
  --coric-new snapshots/deepread_handoff_eval/deepread_handoff_coric_<tag> \
  --multicase-new snapshots/deepread_handoff_eval/deepread_handoff_multicase_<tag> \
  --run-id deepread_handoff_gate_run_<tag>
```

If the changed files are docs-only or otherwise out of deep-read handoff scope, this command records `mode=not_applicable` and does not force a gate run.

Main output:
- `snapshots/deepread_handoff_gate_runs/<run_id>/summary.json`

### 8) Seed or promote a fresh baseline intentionally

```bash
python3 scripts/eval/compare_deepread_handoff_audits.py \
  --baseline snapshots/deepread_handoff_eval/deepread_handoff_<tag> \
  --new snapshots/deepread_handoff_eval/deepread_handoff_<tag> \
  --out snapshots/deepread_handoff_eval/deepread_handoff_<tag>_seed_compare/report.json \
  --promote-dir baselines/deepread_handoff
```

Only do this when the new snapshot reflects a deliberate measurement reset, not an accidental observability jump.

## What the metrics mean

- `review_ready_rate`
  - Higher is better.
  - This tracks whether the saved run is still a review-ready promotion candidate under the current handoff rules.
- `goal_drift_warn_or_fail_rate`
  - Lower is better.
  - This tracks fallback-heavy or off-order attempt selection behavior.
- `step_stability_warn_or_fail_rate`
  - Lower is better.
  - This tracks whether runs surface instability such as verifier failure or timeout-related drift.
- `failure_recovery_warn_or_fail_rate`
  - Lower is better.
  - This tracks whether failure and cancel paths preserve enough terminal metadata and guidance.
- `goal_drift_missing_rate`
  - Lower is better.
  - This tracks whether `goal_drift_summary` is present at all.
- `step_stability_missing_rate`
  - Lower is better.
  - This tracks whether `step_stability_summary` is present at all.
- `failure_recovery_missing_rate`
  - Lower is better.
  - This tracks whether `failure_recovery_summary` is present at all.
- `context_manifest_missing_rate`
  - Lower is better.
  - This tracks whether the run has any `context_manifest.json`.

## Guardrails

- Prefer fixed manifests over broad recursive scans.
- Do not backfill all of `storage/artifacts` as a first move.
- Treat increased warning visibility differently from true behavioral regression.
- If observability improves enough to expose previously hidden warnings, cut a fresh baseline instead of loosening thresholds silently.
- Keep the loop paper/job/artifact-scoped.
- Do not use this loop as justification for model/provider replacement on its own.

## Current judgment

As of 2026-04-08:
- the original migration baseline is still useful as history
- the refreshed coric backfilled baseline is the right continuity comparator for the original saved-paper slice
- the refreshed multicase backfilled baseline is the right companion comparator for reducing single-paper bias
- both fixed batches are currently clean under backfill dry-run

## Verification

Smallest relevant checks for this lane:

```bash
pytest -q \
  tests/test_backfill_deepread_handoff_artifacts.py \
  tests/test_deepread_handoff_artifacts.py \
  tests/test_deepread_handoff_audit.py \
  tests/test_deepread_handoff_gate.py \
  tests/test_deepread_handoff_gate_scope.py \
  tests/test_recommend_deepread_handoff_gate_mode.py \
  tests/test_run_recommended_deepread_handoff_gate.py \
  tests/test_check_pr_scope_script.py \
  tests/test_deepread_handoff_compare.py \
  tests/test_worker_job_runner_chain.py::test_worker_uses_real_job_runner_chain_smoke \
  tests/test_worker_job_runner_chain.py::test_worker_not_ready_claimset_queues_manual_review_followup \
  tests/test_worker_job_runner_chain.py::test_worker_reader_timeout_budget_is_recorded_and_failed_explicitly
```
