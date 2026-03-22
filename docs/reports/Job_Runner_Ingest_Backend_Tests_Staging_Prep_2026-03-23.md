# Job Runner Ingest Backend Tests Staging Prep (2026-03-23)

## Goal
Split a narrow test-only lane that locks job-runner adoption of ingest backend and table-extraction metadata contracts.

## Included
- `/Users/jangseongjin/paperpipe/tests/test_job_runner_ingest_backend.py`
- `/Users/jangseongjin/paperpipe/tests/test_job_runner_table_meta.py`
- `/Users/jangseongjin/paperpipe/docs/reports/Job_Runner_Ingest_Backend_Tests_Staging_Prep_2026-03-23.md`

## Why This Is One Lane
- Runtime support for ingest backend resolution and table extraction metadata already exists in committed code.
- These tests only pin that behavior and do not require additional source changes.
- Keeping them separate avoids mixing config or CLI workflow changes into the same commit.

## Explicitly Excluded
- `/Users/jangseongjin/paperpipe/src/config.py`
- `/Users/jangseongjin/paperpipe/src/services/cli_workflows.py`
- `/Users/jangseongjin/paperpipe/scripts/eval/compare_ingest_backends.py`
- `/Users/jangseongjin/paperpipe/tests/test_ingest_backend_eval.py`

## Verification Plan
In a temp worktree containing only this patch:
- `PAPERPIPE_CONFIG_PATH=.../config.example.yaml pytest -q tests/test_job_runner_ingest_backend.py tests/test_job_runner_table_meta.py`
- `python3 scripts/lint_docs.py`

## Expected Outcome
Job-runner regressions now explicitly cover ingest parser selection, pass-3 runtime options, and persisted table-extraction metadata.
