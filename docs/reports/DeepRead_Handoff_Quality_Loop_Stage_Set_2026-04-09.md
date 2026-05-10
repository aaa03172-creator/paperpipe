# DeepRead Handoff Quality Loop Stage Set

Status: exact stage boundary
Date: 2026-04-09
Lane: `deepread-handoff/quality-loop`
Parent notes:
- [Gemma_GLM51_Scion_Fit_Review_2026-04-08.md](/Users/jangseongjin/paperpipe/docs/reports/Gemma_GLM51_Scion_Fit_Review_2026-04-08.md)
- [DeepRead_Handoff_Baseline_Compare_2026-04-08.md](/Users/jangseongjin/paperpipe/docs/reports/DeepRead_Handoff_Baseline_Compare_2026-04-08.md)
- [DeepRead_Handoff_Backfill_Refresh_2026-04-08.md](/Users/jangseongjin/paperpipe/docs/reports/DeepRead_Handoff_Backfill_Refresh_2026-04-08.md)
- [DeepRead_Handoff_Multicase_Baseline_2026-04-08.md](/Users/jangseongjin/paperpipe/docs/reports/DeepRead_Handoff_Multicase_Baseline_2026-04-08.md)
- [DEEPREAD_HANDOFF_QUALITY_LOOP.md](/Users/jangseongjin/paperpipe/docs/DEEPREAD_HANDOFF_QUALITY_LOOP.md)

## Purpose

Freeze the smallest practical git-stage boundary for the concluded deep-read handoff quality-loop lane.

This note does not stage or commit anything.
It answers one narrower question:

- if this lane is packaged next, which files are whole-file safe, which files should stay out, and which generated paths should remain unstaged?

## Diff Re-check Summary

The current remaining diffs were re-read directly for:

- [DEEPREAD_HANDOFF_QUALITY_LOOP.md](/Users/jangseongjin/paperpipe/docs/DEEPREAD_HANDOFF_QUALITY_LOOP.md)
- [DeepRead_Handoff_Baseline_Compare_2026-04-08.md](/Users/jangseongjin/paperpipe/docs/reports/DeepRead_Handoff_Baseline_Compare_2026-04-08.md)
- [DeepRead_Handoff_Backfill_Refresh_2026-04-08.md](/Users/jangseongjin/paperpipe/docs/reports/DeepRead_Handoff_Backfill_Refresh_2026-04-08.md)
- [DeepRead_Handoff_Multicase_Baseline_2026-04-08.md](/Users/jangseongjin/paperpipe/docs/reports/DeepRead_Handoff_Multicase_Baseline_2026-04-08.md)
- [README.md](/Users/jangseongjin/paperpipe/docs/README.md)
- [README.md](/Users/jangseongjin/paperpipe/docs/reports/README.md)
- [check_pr_scope.py](/Users/jangseongjin/paperpipe/scripts/check_pr_scope.py)
- [backfill_deepread_handoff_artifacts.py](/Users/jangseongjin/paperpipe/scripts/backfill_deepread_handoff_artifacts.py)
- [audit_deepread_handoff.py](/Users/jangseongjin/paperpipe/scripts/eval/audit_deepread_handoff.py)
- [compare_deepread_handoff_audits.py](/Users/jangseongjin/paperpipe/scripts/eval/compare_deepread_handoff_audits.py)
- [check_deepread_handoff_gate.py](/Users/jangseongjin/paperpipe/scripts/eval/check_deepread_handoff_gate.py)
- [recommend_deepread_handoff_gate_mode.py](/Users/jangseongjin/paperpipe/scripts/eval/recommend_deepread_handoff_gate_mode.py)
- [run_recommended_deepread_handoff_gate.py](/Users/jangseongjin/paperpipe/scripts/eval/run_recommended_deepread_handoff_gate.py)
- [deepread_handoff.py](/Users/jangseongjin/paperpipe/src/schemas/deepread_handoff.py)
- [deepread_handoff_artifacts.py](/Users/jangseongjin/paperpipe/src/services/deepread_handoff_artifacts.py)
- [deepread_handoff_gate_scope.py](/Users/jangseongjin/paperpipe/src/services/deepread_handoff_gate_scope.py)
- [job_runner.py](/Users/jangseongjin/paperpipe/backend/services/job_runner.py)
- [test_deepread_handoff_artifacts.py](/Users/jangseongjin/paperpipe/tests/test_deepread_handoff_artifacts.py)
- [test_backfill_deepread_handoff_artifacts.py](/Users/jangseongjin/paperpipe/tests/test_backfill_deepread_handoff_artifacts.py)
- [test_deepread_handoff_audit.py](/Users/jangseongjin/paperpipe/tests/test_deepread_handoff_audit.py)
- [test_deepread_handoff_compare.py](/Users/jangseongjin/paperpipe/tests/test_deepread_handoff_compare.py)
- [test_check_pr_scope_script.py](/Users/jangseongjin/paperpipe/tests/test_check_pr_scope_script.py)
- [test_run_recommended_deepread_handoff_gate.py](/Users/jangseongjin/paperpipe/tests/test_run_recommended_deepread_handoff_gate.py)
- [test_worker_job_runner_chain.py](/Users/jangseongjin/paperpipe/tests/test_worker_job_runner_chain.py)

Current judgment:

- the runbook, historical reports, fixed manifests, promoted baselines, dedicated audit/backfill/gate scripts, deep-read handoff schema/artifact files, and their dedicated tests are whole-file safe for this lane
- [check_pr_scope.py](/Users/jangseongjin/paperpipe/scripts/check_pr_scope.py) is whole-file safe because the remaining diff is only additive deep-read gate advisory output plus a docs-only formatting fix
- [job_runner.py](/Users/jangseongjin/paperpipe/backend/services/job_runner.py) is mixed with clinical-extraction, evidence-extraction, and optional verifier-import work and should stay out of the smallest safe stage set
- [test_worker_job_runner_chain.py](/Users/jangseongjin/paperpipe/tests/test_worker_job_runner_chain.py) is mixed with evidence-extraction assertions and should stay out of the smallest safe stage set
- [README.md](/Users/jangseongjin/paperpipe/docs/README.md) and [README.md](/Users/jangseongjin/paperpipe/docs/reports/README.md) are mixed with unrelated canonical-doc and runtime-index additions and should stay out of the smallest safe stage set

## Whole-File Safe For This Lane

These files can be staged as whole files for the deep-read handoff quality-loop lane:

- [DEEPREAD_HANDOFF_QUALITY_LOOP.md](/Users/jangseongjin/paperpipe/docs/DEEPREAD_HANDOFF_QUALITY_LOOP.md)
- [DeepRead_Handoff_Baseline_Compare_2026-04-08.md](/Users/jangseongjin/paperpipe/docs/reports/DeepRead_Handoff_Baseline_Compare_2026-04-08.md)
- [DeepRead_Handoff_Backfill_Refresh_2026-04-08.md](/Users/jangseongjin/paperpipe/docs/reports/DeepRead_Handoff_Backfill_Refresh_2026-04-08.md)
- [DeepRead_Handoff_Multicase_Baseline_2026-04-08.md](/Users/jangseongjin/paperpipe/docs/reports/DeepRead_Handoff_Multicase_Baseline_2026-04-08.md)
- [DeepRead_Handoff_Quality_Loop_Stage_Set_2026-04-09.md](/Users/jangseongjin/paperpipe/docs/reports/DeepRead_Handoff_Quality_Loop_Stage_Set_2026-04-09.md)
- [deepread_handoff_coric_regression_20260408.json](/Users/jangseongjin/paperpipe/goldset/manifests/deepread_handoff_coric_regression_20260408.json)
- [deepread_handoff_multicase_regression_20260408.json](/Users/jangseongjin/paperpipe/goldset/manifests/deepread_handoff_multicase_regression_20260408.json)
- [deepread_handoff_coric_regression_20260408_baseline](/Users/jangseongjin/paperpipe/baselines/deepread_handoff/deepread_handoff_coric_regression_20260408_baseline)
- [deepread_handoff_coric_regression_20260408_backfilled](/Users/jangseongjin/paperpipe/baselines/deepread_handoff/deepread_handoff_coric_regression_20260408_backfilled)
- [deepread_handoff_multicase_regression_20260408_backfilled](/Users/jangseongjin/paperpipe/baselines/deepread_handoff/deepread_handoff_multicase_regression_20260408_backfilled)
- [backfill_deepread_handoff_artifacts.py](/Users/jangseongjin/paperpipe/scripts/backfill_deepread_handoff_artifacts.py)
- [audit_deepread_handoff.py](/Users/jangseongjin/paperpipe/scripts/eval/audit_deepread_handoff.py)
- [compare_deepread_handoff_audits.py](/Users/jangseongjin/paperpipe/scripts/eval/compare_deepread_handoff_audits.py)
- [check_deepread_handoff_gate.py](/Users/jangseongjin/paperpipe/scripts/eval/check_deepread_handoff_gate.py)
- [recommend_deepread_handoff_gate_mode.py](/Users/jangseongjin/paperpipe/scripts/eval/recommend_deepread_handoff_gate_mode.py)
- [run_recommended_deepread_handoff_gate.py](/Users/jangseongjin/paperpipe/scripts/eval/run_recommended_deepread_handoff_gate.py)
- [check_pr_scope.py](/Users/jangseongjin/paperpipe/scripts/check_pr_scope.py)
- [deepread_handoff.py](/Users/jangseongjin/paperpipe/src/schemas/deepread_handoff.py)
- [deepread_handoff_artifacts.py](/Users/jangseongjin/paperpipe/src/services/deepread_handoff_artifacts.py)
- [deepread_handoff_gate_scope.py](/Users/jangseongjin/paperpipe/src/services/deepread_handoff_gate_scope.py)
- [test_deepread_handoff_artifacts.py](/Users/jangseongjin/paperpipe/tests/test_deepread_handoff_artifacts.py)
- [test_backfill_deepread_handoff_artifacts.py](/Users/jangseongjin/paperpipe/tests/test_backfill_deepread_handoff_artifacts.py)
- [test_deepread_handoff_audit.py](/Users/jangseongjin/paperpipe/tests/test_deepread_handoff_audit.py)
- [test_deepread_handoff_compare.py](/Users/jangseongjin/paperpipe/tests/test_deepread_handoff_compare.py)
- [test_deepread_handoff_gate.py](/Users/jangseongjin/paperpipe/tests/test_deepread_handoff_gate.py)
- [test_deepread_handoff_gate_scope.py](/Users/jangseongjin/paperpipe/tests/test_deepread_handoff_gate_scope.py)
- [test_recommend_deepread_handoff_gate_mode.py](/Users/jangseongjin/paperpipe/tests/test_recommend_deepread_handoff_gate_mode.py)
- [test_run_recommended_deepread_handoff_gate.py](/Users/jangseongjin/paperpipe/tests/test_run_recommended_deepread_handoff_gate.py)
- [test_check_pr_scope_script.py](/Users/jangseongjin/paperpipe/tests/test_check_pr_scope_script.py)

Why these are safe together:

- they all support the same bounded story:
  - saved-run derived-artifact refresh
  - fixed-batch handoff audit and compare
  - baseline promotion
  - bounded gate recommendation and operator guidance
- they stay additive to the current paper/job/artifact runtime
- none of them require DB migration, provider replacement, or a new orchestration layer

## Keep-Out Files

Do not include these in the same smallest stage set:

- [job_runner.py](/Users/jangseongjin/paperpipe/backend/services/job_runner.py)
- [test_worker_job_runner_chain.py](/Users/jangseongjin/paperpipe/tests/test_worker_job_runner_chain.py)
- [README.md](/Users/jangseongjin/paperpipe/docs/README.md)
- [README.md](/Users/jangseongjin/paperpipe/docs/reports/README.md)
- [deepread_handoff_eval](/Users/jangseongjin/paperpipe/snapshots/deepread_handoff_eval)
- [deepread_handoff_gate](/Users/jangseongjin/paperpipe/snapshots/deepread_handoff_gate)
- [deepread_handoff_gate_runs](/Users/jangseongjin/paperpipe/snapshots/deepread_handoff_gate_runs)
- [2026-04-08_reference-fit-review](/Users/jangseongjin/paperpipe/.codex/work/2026-04-08_reference-fit-review)

Why they stay out:

- [job_runner.py](/Users/jangseongjin/paperpipe/backend/services/job_runner.py) is currently dominated by clinical-extraction, evidence-bundle, and optional verifier-import changes that widen past the deep-read quality-loop boundary
- [test_worker_job_runner_chain.py](/Users/jangseongjin/paperpipe/tests/test_worker_job_runner_chain.py) mirrors that widened boundary by mixing deep-read summary assertions with evidence-extraction bundle assertions in the same remaining diff
- the two README files are mixed index updates for other canonical-doc promotions and runtime packaging work, so whole-file staging would overclaim this lane
- the `snapshots/` paths are generated local evidence, not curated baseline truth
- the `.codex/work/` path is task-local planning context, not product/runtime state

## Manual Stage Recipe

If this lane is staged next, the safest exact sequence is:

```bash
git add \
  /Users/jangseongjin/paperpipe/docs/DEEPREAD_HANDOFF_QUALITY_LOOP.md \
  /Users/jangseongjin/paperpipe/docs/reports/DeepRead_Handoff_Baseline_Compare_2026-04-08.md \
  /Users/jangseongjin/paperpipe/docs/reports/DeepRead_Handoff_Backfill_Refresh_2026-04-08.md \
  /Users/jangseongjin/paperpipe/docs/reports/DeepRead_Handoff_Multicase_Baseline_2026-04-08.md \
  /Users/jangseongjin/paperpipe/docs/reports/DeepRead_Handoff_Quality_Loop_Stage_Set_2026-04-09.md \
  /Users/jangseongjin/paperpipe/goldset/manifests/deepread_handoff_coric_regression_20260408.json \
  /Users/jangseongjin/paperpipe/goldset/manifests/deepread_handoff_multicase_regression_20260408.json \
  /Users/jangseongjin/paperpipe/baselines/deepread_handoff/deepread_handoff_coric_regression_20260408_baseline \
  /Users/jangseongjin/paperpipe/baselines/deepread_handoff/deepread_handoff_coric_regression_20260408_backfilled \
  /Users/jangseongjin/paperpipe/baselines/deepread_handoff/deepread_handoff_multicase_regression_20260408_backfilled \
  /Users/jangseongjin/paperpipe/scripts/backfill_deepread_handoff_artifacts.py \
  /Users/jangseongjin/paperpipe/scripts/eval/audit_deepread_handoff.py \
  /Users/jangseongjin/paperpipe/scripts/eval/compare_deepread_handoff_audits.py \
  /Users/jangseongjin/paperpipe/scripts/eval/check_deepread_handoff_gate.py \
  /Users/jangseongjin/paperpipe/scripts/eval/recommend_deepread_handoff_gate_mode.py \
  /Users/jangseongjin/paperpipe/scripts/eval/run_recommended_deepread_handoff_gate.py \
  /Users/jangseongjin/paperpipe/scripts/check_pr_scope.py \
  /Users/jangseongjin/paperpipe/src/schemas/deepread_handoff.py \
  /Users/jangseongjin/paperpipe/src/services/deepread_handoff_artifacts.py \
  /Users/jangseongjin/paperpipe/src/services/deepread_handoff_gate_scope.py \
  /Users/jangseongjin/paperpipe/tests/test_deepread_handoff_artifacts.py \
  /Users/jangseongjin/paperpipe/tests/test_backfill_deepread_handoff_artifacts.py \
  /Users/jangseongjin/paperpipe/tests/test_deepread_handoff_audit.py \
  /Users/jangseongjin/paperpipe/tests/test_deepread_handoff_compare.py \
  /Users/jangseongjin/paperpipe/tests/test_deepread_handoff_gate.py \
  /Users/jangseongjin/paperpipe/tests/test_deepread_handoff_gate_scope.py \
  /Users/jangseongjin/paperpipe/tests/test_recommend_deepread_handoff_gate_mode.py \
  /Users/jangseongjin/paperpipe/tests/test_run_recommended_deepread_handoff_gate.py \
  /Users/jangseongjin/paperpipe/tests/test_check_pr_scope_script.py
```

Do not add:

- `/Users/jangseongjin/paperpipe/backend/services/job_runner.py`
- `/Users/jangseongjin/paperpipe/tests/test_worker_job_runner_chain.py`
- `/Users/jangseongjin/paperpipe/docs/README.md`
- `/Users/jangseongjin/paperpipe/docs/reports/README.md`
- `/Users/jangseongjin/paperpipe/snapshots/deepread_handoff_eval/`
- `/Users/jangseongjin/paperpipe/snapshots/deepread_handoff_gate/`
- `/Users/jangseongjin/paperpipe/snapshots/deepread_handoff_gate_runs/`

## Smallest Relevant Verification Before Staging

Run:

```bash
cd /Users/jangseongjin/paperpipe && python3 -m py_compile \
  scripts/backfill_deepread_handoff_artifacts.py \
  scripts/eval/audit_deepread_handoff.py \
  scripts/eval/compare_deepread_handoff_audits.py \
  scripts/eval/check_deepread_handoff_gate.py \
  scripts/eval/recommend_deepread_handoff_gate_mode.py \
  scripts/eval/run_recommended_deepread_handoff_gate.py \
  scripts/check_pr_scope.py
cd /Users/jangseongjin/paperpipe && pytest -q \
  tests/test_deepread_handoff_artifacts.py \
  tests/test_backfill_deepread_handoff_artifacts.py \
  tests/test_deepread_handoff_audit.py \
  tests/test_deepread_handoff_compare.py \
  tests/test_deepread_handoff_gate.py \
  tests/test_deepread_handoff_gate_scope.py \
  tests/test_recommend_deepread_handoff_gate_mode.py \
  tests/test_run_recommended_deepread_handoff_gate.py \
  tests/test_check_pr_scope_script.py
cd /Users/jangseongjin/paperpipe && python3 scripts/lint_docs.py
cd /Users/jangseongjin/paperpipe && git diff --check
```

Current result at re-check time:

- targeted deep-read quality-loop verification passed before this stage note was cut
- docs lint passed again after adding this note

## Short Version

The deep-read handoff quality-loop lane is stageable next as a whole-file eval/docs/baseline patch.

The safe boundary is:

- stage the dedicated runbook, historical reports, manifests, promoted baselines, eval scripts, schema/artifact builders, gate-advisory files, and dedicated tests
- keep [job_runner.py](/Users/jangseongjin/paperpipe/backend/services/job_runner.py) and [test_worker_job_runner_chain.py](/Users/jangseongjin/paperpipe/tests/test_worker_job_runner_chain.py) out because the current remaining diff there is mixed with clinical and evidence-extraction work
- keep mixed README index updates and generated `snapshots/` evidence out
