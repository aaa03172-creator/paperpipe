# Backend API Smoke Staging Prep

Status: staging-prep manifest  
Date: 2026-03-20  
Lane: `backend-api-smoke`

## Purpose

Define the narrow backend API smoke subset needed to enable the backend smoke workflow without pulling broader runtime or frontend lanes into the same commit.

## In Scope

- `/Users/jangseongjin/paperpipe/.github/workflows/backend-api-smoke.yml`
- `/Users/jangseongjin/paperpipe/scripts/run_backend_api_smoke.sh`
- `/Users/jangseongjin/paperpipe/tests/test_llm_provider_json.py`
- `/Users/jangseongjin/paperpipe/tests/test_obsidian_save.py`
- `/Users/jangseongjin/paperpipe/docs/reports/Backend_API_Smoke_Staging_Prep_2026-03-20.md`

## Out Of Scope

Keep these out of this commit:

- broader runtime/backend changes already dirty under `/Users/jangseongjin/paperpipe/src/` and `/Users/jangseongjin/paperpipe/backend/`
- frontend E2E or UI files
- Meeting Pack verify files
- PR automation workflow `/Users/jangseongjin/paperpipe/.github/workflows/pr-agent.yml`

## Verification Performed

1. `bash -n /Users/jangseongjin/paperpipe/scripts/run_backend_api_smoke.sh`
2. `pytest -q`
   - `/Users/jangseongjin/paperpipe/tests/test_chat_api_stub.py`
   - `/Users/jangseongjin/paperpipe/tests/test_personas_api.py`
   - `/Users/jangseongjin/paperpipe/tests/test_paper_notes_api.py`
   - `/Users/jangseongjin/paperpipe/tests/test_obsidian_artifacts_api.py`
   - `/Users/jangseongjin/paperpipe/tests/test_ops_repair_stats_api.py`
   - `/Users/jangseongjin/paperpipe/tests/test_jobs_api_smoke.py`
   - `/Users/jangseongjin/paperpipe/tests/test_artifacts_runs_api.py`
   - `/Users/jangseongjin/paperpipe/tests/test_api_key_auth.py`
   - `/Users/jangseongjin/paperpipe/tests/full_integration_test.py`
   - `/Users/jangseongjin/paperpipe/tests/test_llm_provider_json.py`
   - `/Users/jangseongjin/paperpipe/tests/test_downloads_watcher.py`
   - `/Users/jangseongjin/paperpipe/tests/test_obsidian_save.py`
   - `/Users/jangseongjin/paperpipe/tests/test_processor_gate_integration.py`
   - `/Users/jangseongjin/paperpipe/tests/test_processor_pdf_context.py`
3. workflow/script target existence check for all files referenced by `/Users/jangseongjin/paperpipe/scripts/run_backend_api_smoke.sh`

## Safe Next Git Step

Stage only the five files listed in scope above and inspect `git diff --cached --name-only` before commit.
