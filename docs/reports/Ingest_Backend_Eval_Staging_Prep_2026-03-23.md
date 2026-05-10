# Ingest Backend Eval Staging Prep (2026-03-23)

## Goal
Split a narrow evaluation lane for bounded parser-backend comparison without mixing it into runtime config adoption.

## Included
- `/Users/jangseongjin/paperpipe/scripts/eval/__init__.py`
- `/Users/jangseongjin/paperpipe/scripts/eval/compare_ingest_backends.py`
- `/Users/jangseongjin/paperpipe/tests/test_ingest_backend_eval.py`
- `/Users/jangseongjin/paperpipe/docs/reports/Ingest_Backend_Eval_Staging_Prep_2026-03-23.md`

## Why This Is One Lane
- The new script evaluates baseline vs candidate ingest backends against local PDFs and writes bounded metrics.
- The test file covers both comparison logic and CLI artifact writing.
- No config or job-runner runtime changes are required for this slice.

## Explicitly Excluded
- `/Users/jangseongjin/paperpipe/src/config.py`
- `/Users/jangseongjin/paperpipe/src/services/cli_workflows.py`
- `/Users/jangseongjin/paperpipe/src/agents/ingest_agent.py` adoption wiring beyond what is already committed
- `/Users/jangseongjin/paperpipe/src/ingest/cloud_table_fallback.py`

## Verification Plan
In a temp worktree containing only this patch:
- `pytest -q tests/test_ingest_backend_eval.py`
- `python3 scripts/lint_docs.py`

## Expected Outcome
A self-contained evaluation harness exists for bounded ingest backend comparison and metrics export.
