# CI Verification Core Staging Prep

Status: staging-prep manifest  
Date: 2026-03-20  
Lane: `ci-and-verification-core`

## Purpose

Define the self-contained CI subset that can be committed now without depending on uncommitted feature or test files.

## In Scope

These files form the safe verification core:

- `/Users/jangseongjin/paperpipe/.github/workflows/agents-smoke.yml`
- `/Users/jangseongjin/paperpipe/.github/workflows/frontend-e2e-canary.yml`
- `/Users/jangseongjin/paperpipe/.github/workflows/frontend-e2e.yml`
- `/Users/jangseongjin/paperpipe/.github/workflows/pr-scope-guard.yml`
- `/Users/jangseongjin/paperpipe/.github/workflows/soft-gate-master.yml`
- `/Users/jangseongjin/paperpipe/scripts/enable_required_checks.sh`
- `/Users/jangseongjin/paperpipe/scripts/run_agents_smoke.sh`
- `/Users/jangseongjin/paperpipe/docs/reports/CI_Verification_Core_Staging_Prep_2026-03-20.md`

## Explicitly Out Of Scope

These are dirty, but not self-contained yet:

- `/Users/jangseongjin/paperpipe/.github/workflows/backend-api-smoke.yml`
- `/Users/jangseongjin/paperpipe/.github/workflows/meeting-pack-verify.yml`
- `/Users/jangseongjin/paperpipe/.github/workflows/pr-agent.yml`
- `/Users/jangseongjin/paperpipe/scripts/run_backend_api_smoke.sh`
- `/Users/jangseongjin/paperpipe/scripts/run_meeting_pack_verify.sh`

Reason:

- `backend-api-smoke` references uncommitted files such as `/Users/jangseongjin/paperpipe/tests/test_llm_provider_json.py` and `/Users/jangseongjin/paperpipe/tests/test_obsidian_save.py`
- `meeting-pack-verify` references uncommitted files such as `/Users/jangseongjin/paperpipe/scripts/check_meeting_pack_real_smoke.py`, `/Users/jangseongjin/paperpipe/scripts/check_meeting_pack_storage_sync.py`, and `/Users/jangseongjin/paperpipe/tests/test_meeting_pack_storage_sync_script.py`
- `pr-agent.yml` is repo automation policy rather than verification core and should be reviewed separately

## Verification Performed

1. `bash -n` on all shell scripts in the CI lane
2. YAML parse check for all workflow files currently in the lane
3. dependency existence check for newly introduced workflow targets

## Safe Next Git Step

If staging this lane, stage only the in-scope files above and then inspect `git diff --cached --name-only`.
