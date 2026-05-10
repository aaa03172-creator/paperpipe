# Optional Verifier Import And Handoff Assertions Stage Set

Status: exact stage boundary
Date: 2026-04-10
Lane: `runtime/optional-verifier-import-and-handoff-assertions`
Parent notes:
- [DeepRead_Handoff_Quality_Loop_Stage_Set_2026-04-09.md](/Users/jangseongjin/paperpipe/docs/reports/DeepRead_Handoff_Quality_Loop_Stage_Set_2026-04-09.md)
- [Clinical_Evidence_Extraction_Stage_Set_2026-04-09.md](/Users/jangseongjin/paperpipe/docs/reports/Clinical_Evidence_Extraction_Stage_Set_2026-04-09.md)
- [External_Reference_Lane_Stage_Set_2026-04-02.md](/Users/jangseongjin/paperpipe/docs/reports/External_Reference_Lane_Stage_Set_2026-04-02.md)

## Purpose

Freeze the next safe boundary for the remaining mixed diff that still lives in:

- [job_runner.py](/Users/jangseongjin/paperpipe/backend/services/job_runner.py)
- [test_worker_job_runner_chain.py](/Users/jangseongjin/paperpipe/tests/test_worker_job_runner_chain.py)

This note does not stage or commit anything.
It answers one narrower question:

- after the clinical extraction and deep-read quality-loop slices are already present on `HEAD`, which remaining hunks still form a coherent follow-up lane?

## Diff Re-check Summary

Current re-read result:

- the remaining runtime diff in [job_runner.py](/Users/jangseongjin/paperpipe/backend/services/job_runner.py) is now mostly about:
  - optional `StatsVerificationAgent` import hardening
  - preserving `reader_analysis` persistence helper placement
  - reusing the earlier-resolved `note_path` before the best-effort note upsert
- the remaining test diff in [test_worker_job_runner_chain.py](/Users/jangseongjin/paperpipe/tests/test_worker_job_runner_chain.py) is now mostly about:
  - asserting `step_stability_summary`
  - asserting `failure_recovery_summary`
  - asserting `goal_drift_summary`
  - asserting `hard_fail_codes`
  - asserting timeout-path quality-gate outcomes

Current judgment:

- these remaining hunks are coherent enough to treat as one bounded lane
- they are not the same lane as clinical extraction or evidence-bundle generation
- they are not broad enough to reopen a larger runtime or external-reference split

## Files In Scope

These files belong to this lane:

- [job_runner.py](/Users/jangseongjin/paperpipe/backend/services/job_runner.py)
- [test_worker_job_runner_chain.py](/Users/jangseongjin/paperpipe/tests/test_worker_job_runner_chain.py)
- [Optional_Verifier_Import_And_Handoff_Assertions_Stage_Set_2026-04-10.md](/Users/jangseongjin/paperpipe/docs/reports/Optional_Verifier_Import_And_Handoff_Assertions_Stage_Set_2026-04-10.md)

## Split-Required File: `job_runner.py`

Only these remaining hunks belong to this lane:

- top-level optional import hardening for `StatsVerificationAgent`
- the guarded runtime check:
  - `if StatsVerificationAgent is None: raise RuntimeError(...)`
- the local move of `_persist_reader_analysis_metrics(...)` that keeps the helper available before timeout-handling and success paths
- the `if note_path is None:` reuse guard before best-effort note upsert
- the local `llm_timeout_default` placement change that keeps timeout-budget calculation on the same path as the persisted helper move

Leave out from this file:

- any already-landed clinical extraction / evidence-bundle hunks
- any already-landed deep-read quality-loop artifact writes
- any future provider, parser, or workspace-surface changes

Why this split is safe:

- it hardens import-time behavior when optional verifier dependencies are absent
- it keeps failure handling inside guarded runtime execution instead of crashing import
- it does not change the canonical paper/job/artifact owner model

## Split-Required File: `test_worker_job_runner_chain.py`

Only these remaining hunks belong to this lane:

- pass-path assertions for:
  - `step_stability_summary`
  - `failure_recovery_summary`
  - `goal_drift_summary`
  - `hard_fail_codes`
- warn-path assertions that the new summary fields stay present and sane
- timeout-path assertions that the quality gate records:
  - `overall_status == "fail"`
  - `step_stability_summary.status == "fail"`
  - `failure_recovery_summary.status == "pass"`

Leave out from this file:

- the already-landed evidence-bundle existence and metrics assertions
- unrelated future worker-chain additions

Why this split is safe:

- it locks the current deep-read handoff summary expectations on the worker smoke path
- it directly proves the runtime writes the summary fields that the handoff audit lane now depends on

## Verification Re-check

Commands rerun on the current worktree:

```bash
cd /Users/jangseongjin/paperpipe && pytest -q \
  tests/test_worker_job_runner_chain.py::test_worker_not_ready_claimset_queues_manual_review_followup \
  tests/test_worker_job_runner_chain.py::test_worker_reader_timeout_budget_is_recorded_and_failed_explicitly
cd /Users/jangseongjin/paperpipe && pytest -q tests/test_fake_worker_import.py
cd /Users/jangseongjin/paperpipe && pytest -q \
  tests/test_job_runner_ingest_backend.py \
  tests/test_jobs_api_smoke.py -k parser_backend
cd /Users/jangseongjin/paperpipe && git diff --check \
  backend/services/job_runner.py \
  tests/test_worker_job_runner_chain.py
```

Observed result:

- targeted worker-chain follow-up tests passed
- fake-worker import smoke passed
- parser-backend regression subset passed
- the current remaining diff in these two files is whitespace-clean

## Manual Stage Recipe

If this lane is staged next, do not add either file wholesale from a broad dirty tree.

Use:

```bash
git add -p /Users/jangseongjin/paperpipe/backend/services/job_runner.py
git add -p /Users/jangseongjin/paperpipe/tests/test_worker_job_runner_chain.py
git add /Users/jangseongjin/paperpipe/docs/reports/Optional_Verifier_Import_And_Handoff_Assertions_Stage_Set_2026-04-10.md
```

Accept only the hunks described above.

## Short Version

The remaining mixed tail after the clinical extraction split is now a small runtime-hardening lane:

- keep optional verifier imports from crashing module import
- keep worker-chain quality-gate summary assertions aligned with the deep-read handoff audit contract

This lane is small, but it is still patch-stage-only because both touched files are shared owner files.
