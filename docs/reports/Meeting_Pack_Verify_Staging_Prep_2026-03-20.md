# Meeting Pack Verify Staging Prep

Status: staging-prep manifest  
Date: 2026-03-20  
Lane: `meeting-pack-verify`

## Purpose

Define the narrow verification subset needed to enable the Meeting Pack verification workflow without pulling in the broader Meeting Pack UI lane.

## In Scope

- `/Users/jangseongjin/paperpipe/.github/workflows/meeting-pack-verify.yml`
- `/Users/jangseongjin/paperpipe/scripts/run_meeting_pack_verify.sh`
- `/Users/jangseongjin/paperpipe/scripts/check_meeting_pack_real_smoke.py`
- `/Users/jangseongjin/paperpipe/scripts/check_meeting_pack_storage_sync.py`
- `/Users/jangseongjin/paperpipe/tests/test_meeting_pack_storage_sync_script.py`
- `/Users/jangseongjin/paperpipe/tests/test_meeting_pack_schema.py`
- `/Users/jangseongjin/paperpipe/tests/test_meeting_pack_store.py`
- `/Users/jangseongjin/paperpipe/tests/test_meeting_packs_api.py`
- `/Users/jangseongjin/paperpipe/docs/MEETING_PACK.md`
- `/Users/jangseongjin/paperpipe/docs/reports/Meeting_Pack_Verify_Staging_Prep_2026-03-20.md`

## Out Of Scope

Keep these out of this commit:

- `/Users/jangseongjin/paperpipe/frontend/src/app/pages/MeetingPackPage.tsx`
- `/Users/jangseongjin/paperpipe/frontend/e2e/meeting-pack.mock.spec.ts`
- `/Users/jangseongjin/paperpipe/storage/meeting_packs/`
- broader Meeting Pack runtime files already clean in the worktree
- unrelated method-comparison or frontend-routing changes

## Verification Performed

1. `bash -n /Users/jangseongjin/paperpipe/scripts/run_meeting_pack_verify.sh`
2. `pytest -q`
   - `/Users/jangseongjin/paperpipe/tests/test_meeting_pack_storage_sync_script.py`
   - `/Users/jangseongjin/paperpipe/tests/test_meeting_pack_schema.py`
   - `/Users/jangseongjin/paperpipe/tests/test_meeting_pack_store.py`
   - `/Users/jangseongjin/paperpipe/tests/test_meeting_packs_api.py`
   - `/Users/jangseongjin/paperpipe/tests/test_meeting_pack_api.py`
   - `/Users/jangseongjin/paperpipe/tests/test_meeting_pack_service.py`
   - `/Users/jangseongjin/paperpipe/tests/test_meeting_pack_source_resolver.py`
   - `/Users/jangseongjin/paperpipe/tests/test_runtime_paths_meeting_packs.py`
3. `python3 /Users/jangseongjin/paperpipe/scripts/lint_docs.py`

## Safe Next Git Step

Stage only the files listed in scope above. Do not include frontend Meeting Pack pages or local `storage/meeting_packs/` output.
