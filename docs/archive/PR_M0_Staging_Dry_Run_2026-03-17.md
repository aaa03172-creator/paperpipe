# PR-M0 Staging Dry Run (2026-03-17)

Status: Completed dry-run verification
Date: 2026-03-17
Parent note: `/Users/jangseongjin/paperpipe/docs/PR_M0_Meeting_Pack_Baseline_Adoption_2026-03-13.md`

## 0. Purpose

Verify that the current `PR-M0` working set is not only documented, but also stageable as a narrow baseline-adoption slice without touching unrelated runtime residue or broad product diffs.

## 1. Dry-run result

Whole-file/untracked working-set dry run:

```bash
git add -n \
  backend/routers/meeting_packs.py \
  src/meeting_packs \
  src/schemas/meeting_pack.py \
  src/schemas/chat.py \
  src/schemas/skills.py \
  src/skills/storage.py \
  src/profiles/profile_metadata.py \
  src/profiles/research_dna_schema.py \
  src/profiles/research_dna_store.py \
  src/services/identity.py \
  tests/test_runtime_paths_meeting_packs.py \
  tests/test_meeting_packs_api.py \
  tests/test_meeting_pack_api.py \
  tests/test_meeting_pack_service.py \
  tests/test_meeting_pack_store.py \
  tests/test_meeting_pack_schema.py \
  tests/test_meeting_pack_source_resolver.py \
  tests/test_profile_projection_guard.py \
  tests/test_profile_store_concurrency.py \
  docs/MEETING_PACK.md \
  docs/Current_Code_Baseline_Audit_2026-03-13.md \
  docs/Repository_Baseline_Adoption_2026-03-13.md \
  docs/PR_M0_Meeting_Pack_Baseline_Adoption_2026-03-13.md
```

Result:

- all listed files/directories were accepted by `git add -n`
- no generated/runtime byproduct path was included in this dry run

Tracked-diff dry run:

```bash
git add -n \
  src/profiles/profile_schema.py \
  src/profiles/profile_store.py \
  src/services/runtime_paths.py \
  docs/Pending_PR_Queue.md
```

Result:

- all listed tracked files were accepted by `git add -n`

## 2. Important exception: backend/main.py

`backend/main.py` cannot be staged as a whole-file baseline adoption.

Current relevant lines:

- import line: `/Users/jangseongjin/paperpipe/backend/main.py:66`
- router include line: `/Users/jangseongjin/paperpipe/backend/main.py:1161`

Observed issue:

- the router import line currently reads:
  - `from .routers import feedback, meeting_packs, obsidian, paper_notes, skills`
- this means a naive hunk stage would also absorb `paper_notes` and `skills` router wiring

Required handling:

- use `git add -p backend/main.py` with edited patch mode
- keep only:
  - `meeting_packs` in the import line
  - `app.include_router(meeting_packs.router)`
- do not absorb unrelated `paper_notes`, `skills`, Research DNA, or ops/API expansion hunks

## 3. Excluded paths re-confirmed

Still excluded from `PR-M0`:

- `__pycache__/` and `.pyc`
- `/Users/jangseongjin/paperpipe/storage/meeting_packs/`
- `/Users/jangseongjin/paperpipe/research_dna/`
- `/Users/jangseongjin/paperpipe/storage/search_eval/`
- `/Users/jangseongjin/paperpipe/tmp/`
- `/Users/jangseongjin/paperpipe/src/profiles/research_dna_projection.py`

Reason:

- these are either runtime byproducts or adjacent producer logic outside the current Meeting Pack runtime consumer slice

## 4. Conclusion

`PR-M0` is stageable as a narrow adoption slice, but only if `backend/main.py` is handled as a manually edited patch rather than a normal whole-file or naive hunk stage.
