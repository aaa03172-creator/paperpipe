# PR-M0 Meeting Pack Baseline Adoption

Status: Executed via commit `5c09619`; retained as the historical baseline-adoption note for the Meeting Pack runtime slice
Date: 2026-03-17
Current navigation parents:
- `/Users/jangseongjin/paperpipe/docs/Pending_PR_Queue.md`
- `/Users/jangseongjin/paperpipe/docs/reports/Current_Baseline_Recheck_2026-03-18.md`

Historical provenance note:
- the execution anchor for this note is commit `5c09619`
- the parent links above are current tracked navigation links, not a claim about the original planning source

## 0. Intent

`PR-M0` exists because Meeting Pack is no longer a tiny adjunct feature.

It is now a dependency-bearing runtime slice with its own package, schemas, store, selector logic, and transitive links into profile metadata, structured state, and Research DNA logs.

This slice should be adopted explicitly instead of being smuggled into `PR-R0`.

Execution follow-up:

- baseline adoption for this slice was executed as commit `5c09619` (`feat(meeting-pack): adopt baseline runtime slice`)
- later Meeting Pack follow-up slices were intentionally split into separate commits rather than folded back into this baseline note

## 1. Re-verified Baseline For This PR

Re-verified on 2026-03-17 with targeted tests:

- `/Users/jangseongjin/paperpipe/tests/test_runtime_paths_meeting_packs.py`
- `/Users/jangseongjin/paperpipe/tests/test_meeting_packs_api.py`
- `/Users/jangseongjin/paperpipe/tests/test_meeting_pack_api.py`
- `/Users/jangseongjin/paperpipe/tests/test_meeting_pack_service.py`
- `/Users/jangseongjin/paperpipe/tests/test_meeting_pack_store.py`
- `/Users/jangseongjin/paperpipe/tests/test_meeting_pack_schema.py`
- `/Users/jangseongjin/paperpipe/tests/test_meeting_pack_source_resolver.py`
- `/Users/jangseongjin/paperpipe/tests/test_profile_projection_guard.py`
- `/Users/jangseongjin/paperpipe/tests/test_profile_store_concurrency.py`

Result:

- `90 passed`
- this expanded recheck includes the profile-store/projection guard surface that Meeting Pack now depends on for projection-backed `project_profile` / `research_profile` selectors
- stage-ready dry run is additionally recorded in `/Users/jangseongjin/paperpipe/docs/archive/PR_M0_Staging_Dry_Run_2026-03-17.md`
- staged-index validation is additionally recorded in `/Users/jangseongjin/paperpipe/docs/archive/PR_M0_Staged_Candidate_Validation_2026-03-17.md`
- current disposition: this baseline-adoption slice was executed via commit `5c09619`; remaining broader worktree tails stay out of scope unless explicitly promoted into a separate lane

Re-checked on 2026-03-18 with the same targeted suite:

- `97 passed`
- the Meeting Pack baseline slice still holds after the recent additive hardening around `Research DNA` reporting and paper-note `context_trace`
- the widened passing count reflects normal test-surface growth, not a reason to broaden the `PR-M0` include/exclude boundary

## 2. Runtime Dependency Cone

Direct runtime layer:

- `/Users/jangseongjin/paperpipe/backend/routers/meeting_packs.py`
- `/Users/jangseongjin/paperpipe/src/meeting_packs/service.py`
- `/Users/jangseongjin/paperpipe/src/meeting_packs/source_resolver.py`
- `/Users/jangseongjin/paperpipe/src/meeting_packs/evidence.py`
- `/Users/jangseongjin/paperpipe/src/meeting_packs/renderer.py`
- `/Users/jangseongjin/paperpipe/src/meeting_packs/store.py`
- `/Users/jangseongjin/paperpipe/src/meeting_packs/__init__.py`

Direct schema layer:

- `/Users/jangseongjin/paperpipe/src/schemas/meeting_pack.py`

Observed transitive dependencies required by the runtime package:

- `/Users/jangseongjin/paperpipe/src/schemas/chat.py`
- `/Users/jangseongjin/paperpipe/src/schemas/skills.py`
- `/Users/jangseongjin/paperpipe/src/skills/storage.py`
- `/Users/jangseongjin/paperpipe/src/profiles/profile_schema.py`
- `/Users/jangseongjin/paperpipe/src/profiles/profile_metadata.py`
- `/Users/jangseongjin/paperpipe/src/profiles/profile_store.py`
- `/Users/jangseongjin/paperpipe/src/profiles/research_dna_schema.py`
- `/Users/jangseongjin/paperpipe/src/profiles/research_dna_store.py`
- `/Users/jangseongjin/paperpipe/src/services/identity.py`
- `/Users/jangseongjin/paperpipe/src/services/runtime_paths.py`

## 3. Files To Adopt In PR-M0

### 3.1 Core runtime files

- `/Users/jangseongjin/paperpipe/backend/main.py` (narrow supporting hunk only: router import/include for `meeting_packs`)
- `/Users/jangseongjin/paperpipe/backend/routers/meeting_packs.py`
- `/Users/jangseongjin/paperpipe/src/meeting_packs/__init__.py`
- `/Users/jangseongjin/paperpipe/src/meeting_packs/evidence.py`
- `/Users/jangseongjin/paperpipe/src/meeting_packs/renderer.py`
- `/Users/jangseongjin/paperpipe/src/meeting_packs/service.py`
- `/Users/jangseongjin/paperpipe/src/meeting_packs/source_resolver.py`
- `/Users/jangseongjin/paperpipe/src/meeting_packs/store.py`
- `/Users/jangseongjin/paperpipe/src/schemas/meeting_pack.py`

### 3.2 Required dependency files

- `/Users/jangseongjin/paperpipe/src/schemas/chat.py`
- `/Users/jangseongjin/paperpipe/src/schemas/skills.py`
- `/Users/jangseongjin/paperpipe/src/skills/storage.py`
- `/Users/jangseongjin/paperpipe/src/profiles/profile_schema.py`
- `/Users/jangseongjin/paperpipe/src/profiles/profile_metadata.py`
- `/Users/jangseongjin/paperpipe/src/profiles/profile_store.py`
- `/Users/jangseongjin/paperpipe/src/profiles/research_dna_schema.py`
- `/Users/jangseongjin/paperpipe/src/profiles/research_dna_store.py`
- `/Users/jangseongjin/paperpipe/src/services/identity.py`
- `/Users/jangseongjin/paperpipe/src/services/runtime_paths.py`

### 3.3 Regression coverage

- `/Users/jangseongjin/paperpipe/tests/test_meeting_packs_api.py`
- `/Users/jangseongjin/paperpipe/tests/test_meeting_pack_api.py`
- `/Users/jangseongjin/paperpipe/tests/test_meeting_pack_service.py`
- `/Users/jangseongjin/paperpipe/tests/test_meeting_pack_store.py`
- `/Users/jangseongjin/paperpipe/tests/test_meeting_pack_schema.py`
- `/Users/jangseongjin/paperpipe/tests/test_meeting_pack_source_resolver.py`
- `/Users/jangseongjin/paperpipe/tests/test_runtime_paths_meeting_packs.py`
- `/Users/jangseongjin/paperpipe/tests/test_profile_projection_guard.py`
- `/Users/jangseongjin/paperpipe/tests/test_profile_store_concurrency.py`

### 3.4 Explicitly excluded generated/runtime byproducts

- `__pycache__/` and `.pyc` files under `/Users/jangseongjin/paperpipe/src/meeting_packs/` or related dependency directories
- `/Users/jangseongjin/paperpipe/storage/meeting_packs/`
- `/Users/jangseongjin/paperpipe/research_dna/`
- `/Users/jangseongjin/paperpipe/storage/search_eval/`
- `/Users/jangseongjin/paperpipe/tmp/`

Reason:

- these are verification/runtime artifacts, not source baseline files
- including them would blur the repository freeze with local execution residue

### 3.5 Current working-tree shape for this slice

Locally modified tracked files that `PR-M0` depends on:

- `/Users/jangseongjin/paperpipe/backend/main.py` (only the `meeting_packs` router import/include hunk should be adopted here)
- `/Users/jangseongjin/paperpipe/src/cli.py` (only the `profiles` / `audit` guard hunk needed by the projection-guard regression tests should be adopted here)
- `/Users/jangseongjin/paperpipe/src/profiles/profile_schema.py`
- `/Users/jangseongjin/paperpipe/src/profiles/profile_store.py`
- `/Users/jangseongjin/paperpipe/src/services/runtime_paths.py`

Currently untracked files that belong to the `PR-M0` slice:

- `/Users/jangseongjin/paperpipe/backend/routers/meeting_packs.py`
- `/Users/jangseongjin/paperpipe/src/meeting_packs/`
- `/Users/jangseongjin/paperpipe/src/schemas/meeting_pack.py`
- `/Users/jangseongjin/paperpipe/src/schemas/chat.py`
- `/Users/jangseongjin/paperpipe/src/schemas/skills.py`
- `/Users/jangseongjin/paperpipe/src/skills/storage.py`
- `/Users/jangseongjin/paperpipe/src/profiles/profile_metadata.py`
- `/Users/jangseongjin/paperpipe/src/profiles/research_dna_schema.py`
- `/Users/jangseongjin/paperpipe/src/profiles/research_dna_store.py`
- `/Users/jangseongjin/paperpipe/src/services/identity.py`
- `/Users/jangseongjin/paperpipe/tests/test_runtime_paths_meeting_packs.py`
- `/Users/jangseongjin/paperpipe/tests/test_meeting_packs_api.py`
- `/Users/jangseongjin/paperpipe/tests/test_meeting_pack_api.py`
- `/Users/jangseongjin/paperpipe/tests/test_meeting_pack_service.py`
- `/Users/jangseongjin/paperpipe/tests/test_meeting_pack_store.py`
- `/Users/jangseongjin/paperpipe/tests/test_meeting_pack_schema.py`
- `/Users/jangseongjin/paperpipe/tests/test_meeting_pack_source_resolver.py`
- `/Users/jangseongjin/paperpipe/tests/test_profile_projection_guard.py`
- `/Users/jangseongjin/paperpipe/tests/test_profile_store_concurrency.py`
- `/Users/jangseongjin/paperpipe/docs/MEETING_PACK.md`
- `/Users/jangseongjin/paperpipe/docs/Current_Code_Baseline_Audit_2026-03-13.md`
- `/Users/jangseongjin/paperpipe/docs/Pending_PR_Queue.md`
- `/Users/jangseongjin/paperpipe/docs/Repository_Baseline_Adoption_2026-03-13.md`
- `/Users/jangseongjin/paperpipe/docs/PR_M0_Meeting_Pack_Baseline_Adoption_2026-03-13.md`
- `/Users/jangseongjin/paperpipe/docs/archive/PR_M0_Staging_Dry_Run_2026-03-17.md`
- `/Users/jangseongjin/paperpipe/docs/archive/PR_M0_Staged_Candidate_Validation_2026-03-17.md`

Meaning:

- `PR-M0` should be read as a mixed adoption PR: part tracked-diff baseline freeze, part untracked working-tree adoption
- `backend/main.py` is the main exception: the file is broadly modified in the workspace, so `PR-M0` must extract only the router-enablement hunk needed to keep `meeting_packs.router` live
- `src/cli.py` is the second narrow-hunk exception: `PR-M0` only needs the `profiles` / `audit` guard changes that align the operator surface with `profile_store` and the projection-profile read-only policy
- `src/profiles/research_dna_projection.py` is intentionally excluded from `PR-M0`; the current Meeting Pack slice consumes projection metadata but does not import the projection producer module
- `src/services/runtime_paths.py` and `src/services/identity.py` currently have broader unstaged tails in the workspace; those tails are not part of `PR-M0` and remain separate follow-up lanes
- `backend/routers/meeting_packs.py`, `src/meeting_packs/service.py`, and `docs/MEETING_PACK.md` also currently have broader unstaged tails for list/trace/debug-inspector follow-up; those tails are not part of the confirmed `PR-M0` candidate
- recent `Research DNA` eval-report hardening (`scripts/evaluate_search.py`, `tests/test_evaluate_search.py`, `docs/RESEARCH_DNA.md`) is adjacent but remains a separate additive lane
- recent paper-note `context_trace` hardening (`src/schemas/paper_notes.py`, `backend/routers/paper_notes.py`, `tests/test_paper_notes_api.py`, `docs/WEB_VIEWER.md`) shares the "operational trace only" principle but remains outside `PR-M0`

### 3.6 Stage-ready adoption outline

Dry-run verification for this outline is recorded in:

- `/Users/jangseongjin/paperpipe/docs/archive/PR_M0_Staging_Dry_Run_2026-03-17.md`

Adopt as whole files/directories:

- `/Users/jangseongjin/paperpipe/backend/routers/meeting_packs.py`
- `/Users/jangseongjin/paperpipe/src/meeting_packs/`
- `/Users/jangseongjin/paperpipe/src/schemas/meeting_pack.py`
- `/Users/jangseongjin/paperpipe/src/schemas/chat.py`
- `/Users/jangseongjin/paperpipe/src/schemas/skills.py`
- `/Users/jangseongjin/paperpipe/src/skills/storage.py`
- `/Users/jangseongjin/paperpipe/src/profiles/profile_metadata.py`
- `/Users/jangseongjin/paperpipe/src/profiles/research_dna_schema.py`
- `/Users/jangseongjin/paperpipe/src/profiles/research_dna_store.py`
- `/Users/jangseongjin/paperpipe/src/services/identity.py`
- `/Users/jangseongjin/paperpipe/tests/test_runtime_paths_meeting_packs.py`
- `/Users/jangseongjin/paperpipe/tests/test_meeting_packs_api.py`
- `/Users/jangseongjin/paperpipe/tests/test_meeting_pack_api.py`
- `/Users/jangseongjin/paperpipe/tests/test_meeting_pack_service.py`
- `/Users/jangseongjin/paperpipe/tests/test_meeting_pack_store.py`
- `/Users/jangseongjin/paperpipe/tests/test_meeting_pack_schema.py`
- `/Users/jangseongjin/paperpipe/tests/test_meeting_pack_source_resolver.py`
- `/Users/jangseongjin/paperpipe/tests/test_profile_projection_guard.py`
- `/Users/jangseongjin/paperpipe/tests/test_profile_store_concurrency.py`
- `/Users/jangseongjin/paperpipe/docs/MEETING_PACK.md`
- `/Users/jangseongjin/paperpipe/docs/Current_Code_Baseline_Audit_2026-03-13.md`
- `/Users/jangseongjin/paperpipe/docs/Pending_PR_Queue.md`
- `/Users/jangseongjin/paperpipe/docs/Repository_Baseline_Adoption_2026-03-13.md`
- `/Users/jangseongjin/paperpipe/docs/PR_M0_Meeting_Pack_Baseline_Adoption_2026-03-13.md`
- `/Users/jangseongjin/paperpipe/docs/archive/PR_M0_Staging_Dry_Run_2026-03-17.md`
- `/Users/jangseongjin/paperpipe/docs/archive/PR_M0_Staged_Candidate_Validation_2026-03-17.md`

Adopt as tracked-diff files, but review the whole diff before staging:

- `/Users/jangseongjin/paperpipe/src/cli.py` (keep only the `profiles` / `audit` guard hunk)
- `/Users/jangseongjin/paperpipe/src/profiles/profile_schema.py`
- `/Users/jangseongjin/paperpipe/src/profiles/profile_store.py`
- `/Users/jangseongjin/paperpipe/src/services/runtime_paths.py`

Adopt as a narrow extracted hunk only:

- `/Users/jangseongjin/paperpipe/backend/main.py`
  - only the `meeting_packs` router import/include wiring needed to keep the API surface live
  - do not absorb unrelated Research DNA, skills, paper notes, or ops expansion in the same adoption PR
- `/Users/jangseongjin/paperpipe/src/cli.py`
  - only the `profiles` / `audit` changes needed to replace the removed `save_profiles` path with `upsert_profile` and to enforce the ResearchDNA projection-profile read-only guard
  - do not absorb unrelated Research DNA command-group or other CLI expansion in the same adoption PR

## 4. Explicit Non-goals

- no frontend Meeting Pack UX expansion
- no Research DNA feature expansion beyond what Meeting Pack already imports
- no paper-note detail trace UI/debug surface expansion
- no use of recent additive hardening slices as a reason to broaden the baseline-adoption file set
- no identity/path redesign yet
- no event-log redesign yet

## 5. Open Cleanup Decision

There are currently two API-level test files:

- `/Users/jangseongjin/paperpipe/tests/test_meeting_packs_api.py`
- `/Users/jangseongjin/paperpipe/tests/test_meeting_pack_api.py`

Current recommendation:

- keep both in `PR-M0`
- defer deduplication to a later cleanup PR

Reason:

- both currently pass
- deleting or merging now would add avoidable review noise

## 6. Acceptance Criteria

`PR-M0` is done only if all are true:

1. the runtime files in Section 3.1 are adopted together, including the narrow `backend/main.py` router-enablement hunk
2. the transitive dependencies in Section 3.2 are explicit in the PR
3. the regression coverage in Section 3.3 remains green
4. the PR reads as "Meeting Pack baseline adoption" and not as broad product expansion
