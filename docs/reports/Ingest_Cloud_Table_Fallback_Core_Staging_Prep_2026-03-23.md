# Ingest Cloud Table Fallback Core Staging Prep (2026-03-23)

## Goal
Split a narrow ingest-runtime lane that adds pass-3 cloud table fallback and parser-backend-driven table extraction without dragging config or CLI workflow changes into the same commit.

## Included
- `/Users/jangseongjin/paperpipe/src/agents/ingest_agent.py`
- `/Users/jangseongjin/paperpipe/src/ingest/__init__.py`
- `/Users/jangseongjin/paperpipe/src/ingest/cloud_table_fallback.py`
- `/Users/jangseongjin/paperpipe/tests/test_cloud_table_fallback.py`
- `/Users/jangseongjin/paperpipe/docs/reports/Ingest_Cloud_Table_Fallback_Core_Staging_Prep_2026-03-23.md`

## Why This Is One Lane
- `IngestAgent` now owns parser-backend selection, pass-2 OCR table retry, and optional pass-3 cloud fallback.
- `src/ingest/cloud_table_fallback.py` is the new runtime module implementing best-effort LLM table extraction with explicit failure taxonomy.
- `test_cloud_table_fallback.py` pins the quality guards for the new fallback logic.
- Config and job-runner glue are intentionally excluded because they are mixed with other dirty changes.

## Explicitly Excluded
- `/Users/jangseongjin/paperpipe/src/config.py`
- `/Users/jangseongjin/paperpipe/src/services/cli_workflows.py`
- `/Users/jangseongjin/paperpipe/tests/test_job_runner_ingest_backend.py`
- `/Users/jangseongjin/paperpipe/tests/test_job_runner_table_meta.py`
- `/Users/jangseongjin/paperpipe/scripts/eval/compare_ingest_backends.py`
- `/Users/jangseongjin/paperpipe/tests/test_ingest_backend_eval.py`

## Verification Plan
In a temp worktree containing only this patch:
- `pytest -q tests/test_cloud_table_fallback.py tests/test_ingest_parser_backend.py`
- `python3 scripts/lint_docs.py`

## Expected Outcome
The ingest runtime can perform explicit pass-3 cloud table fallback with stable failure taxonomy, while broader config and workflow adoption remain for a later lane.
