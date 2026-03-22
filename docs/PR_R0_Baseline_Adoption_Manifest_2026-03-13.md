# PR-R0 Baseline Adoption Manifest

Status: Ready-to-execute baseline adoption manifest  
Date: 2026-03-13  
Parent roadmap: `/Users/jangseongjin/paperpipe/docs/Audit_Driven_Roadmap_2026-03-13.md`

## 0. Intent

`PR-R0` must not attempt to absorb the whole dirty workspace.

Its only job is to freeze the currently verified narrow runtime slice that is needed before structural hardening work can start.

That slice is:

- runtime path contract
- runtime path regression coverage
- the audit documents that define the next hardening sequence

## 1. Verified Baseline For This PR

Re-verified on 2026-03-13 with targeted tests:

- `/Users/jangseongjin/paperpipe/tests/test_runtime_paths_research_dna.py`
- `/Users/jangseongjin/paperpipe/tests/test_runtime_paths_meeting_packs.py`
- `/Users/jangseongjin/paperpipe/tests/test_jobs_events_persistence.py`
- `/Users/jangseongjin/paperpipe/tests/test_document_artifact_v2.py`
- `/Users/jangseongjin/paperpipe/tests/test_claimset_policy.py`

Result:

- `29 passed`

This is enough to freeze the audited narrow baseline subset.

Re-checked on 2026-03-18 with the same verification command:

- `32 passed`
- current result still supports the same narrow `PR-R0` baseline-freeze boundary
- recent additive hardening in `Research DNA` reporting and paper-note `context_trace` did not require widening this manifest

## 2. Files To Adopt In PR-R0

### 2.1 Runtime contract

Required:

- `/Users/jangseongjin/paperpipe/src/services/runtime_paths.py`
- `/Users/jangseongjin/paperpipe/tests/test_runtime_paths_research_dna.py`
- `/Users/jangseongjin/paperpipe/tests/test_runtime_paths_meeting_packs.py`

Reason:

- this contract was directly responsible for recent path drift and has already been re-verified

### 2.2 Audit documents

Required:

- `/Users/jangseongjin/paperpipe/docs/Current_Code_Baseline_Audit_2026-03-13.md`
- `/Users/jangseongjin/paperpipe/docs/Repository_Baseline_Adoption_2026-03-13.md`
- `/Users/jangseongjin/paperpipe/docs/Identity_Pathing_Audit_2026-03-13.md`
- `/Users/jangseongjin/paperpipe/docs/Event_Logging_Audit_2026-03-13.md`
- `/Users/jangseongjin/paperpipe/docs/Output_Contract_Audit_2026-03-13.md`
- `/Users/jangseongjin/paperpipe/docs/Citation_Grounding_Audit_2026-03-13.md`
- `/Users/jangseongjin/paperpipe/docs/Audit_Driven_Roadmap_2026-03-13.md`
- `/Users/jangseongjin/paperpipe/docs/PR_R0_Baseline_Adoption_Manifest_2026-03-13.md`
- `/Users/jangseongjin/paperpipe/docs/PR_M0_Meeting_Pack_Baseline_Adoption_2026-03-13.md`

Reason:

- these documents are now the working SSOT for the hardening sequence

## 3. Files Explicitly Deferred Out Of PR-R0

The following areas should stay out of `PR-R0` even if they are also untracked or modified.

### 3.1 Meeting Pack runtime package adoption

Defer examples:

- `/Users/jangseongjin/paperpipe/backend/routers/meeting_packs.py`
- `/Users/jangseongjin/paperpipe/src/meeting_packs/`
- `/Users/jangseongjin/paperpipe/src/schemas/meeting_pack.py`
- `/Users/jangseongjin/paperpipe/tests/test_meeting_pack_api.py`
- `/Users/jangseongjin/paperpipe/tests/test_meeting_pack_source_resolver.py`
- `/Users/jangseongjin/paperpipe/tests/test_meeting_pack_service.py`
- `/Users/jangseongjin/paperpipe/tests/test_meeting_pack_store.py`
- `/Users/jangseongjin/paperpipe/tests/test_meeting_pack_schema.py`
- `/Users/jangseongjin/paperpipe/tests/test_meeting_packs_api.py`

Reason:

- dependency review showed that Meeting Pack now pulls a wider transitive cone than `PR-R0` should absorb
- this slice should move to its own baseline-adoption PR (`PR-M0`)

### 3.2 Research DNA expansion

Defer examples:

- `/Users/jangseongjin/paperpipe/src/profiles/research_dna_*`
- `/Users/jangseongjin/paperpipe/tests/test_research_dna_*`
- `/Users/jangseongjin/paperpipe/docs/RESEARCH_DNA.md`
- `/Users/jangseongjin/paperpipe/scripts/evaluate_search.py`
- `/Users/jangseongjin/paperpipe/tests/test_evaluate_search.py`

Reason:

- these are product-surface expansions, not baseline-freeze prerequisites
- recent keep/discard reporting hardening is additive and useful, but it still belongs to the active `Research DNA` lane rather than the narrow `PR-R0` freeze

### 3.3 Skills/chat structured state expansion

Defer examples:

- `/Users/jangseongjin/paperpipe/backend/routers/skills.py`
- `/Users/jangseongjin/paperpipe/src/skills/`
- `/Users/jangseongjin/paperpipe/src/schemas/skills.py`
- `/Users/jangseongjin/paperpipe/src/schemas/chat.py`
- `/Users/jangseongjin/paperpipe/tests/test_skills_api.py`
- `/Users/jangseongjin/paperpipe/tests/test_skill_state_contract.py`
- `/Users/jangseongjin/paperpipe/src/schemas/paper_notes.py`
- `/Users/jangseongjin/paperpipe/backend/routers/paper_notes.py`
- `/Users/jangseongjin/paperpipe/tests/test_paper_notes_api.py`
- `/Users/jangseongjin/paperpipe/docs/WEB_VIEWER.md`

Reason:

- these belong to later output-contract convergence work, not baseline adoption
- recent note-detail `context_trace` hardening is additive operational metadata and should not widen `PR-R0`

### 3.4 Frontend expansion and UX changes

Defer examples:

- `/Users/jangseongjin/paperpipe/frontend/src/app/pages/PaperNoteDetailPage.tsx`
- `/Users/jangseongjin/paperpipe/frontend/src/app/components/ui/`
- `/Users/jangseongjin/paperpipe/docs/UX_REVIEW_*`

Reason:

- baseline adoption should not absorb unrelated UI churn

### 3.5 Broad docs/import cleanup

Defer examples:

- deleted legacy docs
- large README/spec rewrites unrelated to the audited baseline slice

Reason:

- too much unrelated churn hides the actual baseline freeze

### 3.6 Broad tracked-file diffs that contain unrelated product expansion

Defer examples:

- `/Users/jangseongjin/paperpipe/backend/main.py`
- `/Users/jangseongjin/paperpipe/backend/services/job_runner.py`
- `/Users/jangseongjin/paperpipe/src/profiles/profile_store.py`

Reason:

- these files contain some relevant baseline-fix hunks, but the current total diff also includes much broader product expansion
- raw inclusion would make `PR-R0` unreadable
- if needed, the narrow baseline-fix hunks should be extracted in a dedicated follow-up instead of bundled here

## 4. Expected PR-R0 Shape

`PR-R0` should be intentionally small and boring.

Allowed changes:

- add/track the files listed in Section 2
- minimal touch-ups only if required to keep the slice internally consistent
- no architecture changes
- no schema migrations
- no new helper layers yet

Not allowed in `PR-R0`:

- identity redesign
- event-log redesign
- output contract bridge work
- citation resolver work
- frontend refactors
- Meeting Pack package adoption

## 5. Verification Command For PR-R0

Minimum verification command:

```bash
pytest -q \
  /Users/jangseongjin/paperpipe/tests/test_runtime_paths_research_dna.py \
  /Users/jangseongjin/paperpipe/tests/test_runtime_paths_meeting_packs.py \
  /Users/jangseongjin/paperpipe/tests/test_jobs_events_persistence.py \
  /Users/jangseongjin/paperpipe/tests/test_document_artifact_v2.py \
  /Users/jangseongjin/paperpipe/tests/test_claimset_policy.py
```

Secondary verification after adoption:

```bash
git status --short
```

Expected result:

- adopted files are no longer untracked in the target slice
- deferred areas may still remain dirty

## 6. Acceptance Criteria

`PR-R0` is done only if all are true:

1. all files in Section 2 are present and treated as the repository baseline slice
2. the verification command remains green
3. the deferred areas in Section 3 are still excluded from this PR
4. the resulting PR is readable as "baseline freeze" rather than "feature expansion"

## 7. Immediate Follow-up

After `PR-R0`, the next correct implementation targets are:

1. `PR-M0 Meeting Pack Baseline Adoption`
2. `PR-I1 Identity And Path Helper Layer`

Reason:

- the narrow baseline slice will then be stable enough to support actual hardening work
