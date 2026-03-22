# Repository Baseline Adoption

Status: Proposed repository-baseline adoption note
Date: 2026-03-13
Scope: runtime-green snapshot that is not yet fixed as git-tracked baseline

## 0. Purpose

This note separates two different truths that currently coexist in the workspace:

1. execution baseline is green
2. repository baseline is not yet frozen

As of this snapshot:

- `pytest -q` passes with `518 passed, 1 skipped`
- several files that define that passing baseline are still untracked or locally modified

This document identifies which files should be treated as repository-baseline candidates, why they matter, and in what order they should be adopted.

This note now serves as the tracked historical repository-baseline context on `master`.

For the later shared baseline-freeze execution context, use:

- `/Users/jangseongjin/paperpipe/docs/reports/Current_Baseline_Recheck_2026-03-18.md`
- `/Users/jangseongjin/paperpipe/docs/PR_M0_Meeting_Pack_Baseline_Adoption_2026-03-13.md`

## 1. Current Execution Baseline

Verified runtime facts:

- `backend/main.py` includes `meeting_packs.router`
- `src/meeting_packs/service.py` imports and uses `src/meeting_packs/source_resolver.py`
- `src/services/runtime_paths.py` is now the path contract used by:
  - `backend/services/job_runner.py`
  - `backend/main.py`
  - `backend/routers/obsidian.py`
  - `src/exporter.py`
  - `scripts/check_frontend_real_smoke_env.py`
  - `src/profiles/profile_store.py`

Verified command:

- `pytest -q`
- result: `518 passed, 1 skipped, 8 warnings`

## 2. Repository-Baseline Candidates

### 2.1 Direct runtime files

#### `/Users/jangseongjin/paperpipe/backend/routers/meeting_packs.py`

Role:

- active FastAPI surface for:
  - `POST /meeting-packs/generate`
  - `GET /meeting-packs/{pack_id}`
  - `GET /meeting-packs/{pack_id}/markdown`

Why it is baseline-critical:

- `backend/main.py` imports and includes this router
- removing it would break the currently passing API surface

Adoption judgment:

- should be tracked immediately

#### `/Users/jangseongjin/paperpipe/src/meeting_packs/source_resolver.py`

Role:

- canonical selector resolution layer for Meeting Pack generation
- resolves:
  - `paper_slug`
  - `paper_state`
  - `paper_note`
  - `project_note`
  - `research_note`
  - `screening_decision`
  - `topic`
  - projection-backed `project_profile`
  - projection-backed `research_profile`

Why it is baseline-critical:

- imported by `src/meeting_packs/service.py`
- defines the actual selector contract now exercised by tests and docs

Adoption judgment:

- should be tracked immediately

### 2.2 Runtime contract file

#### `/Users/jangseongjin/paperpipe/src/services/runtime_paths.py`

Role:

- path-contract source for:
  - storage root
  - state DB path
  - artifacts root
  - config snapshot path
  - profiles config path
  - meeting packs root
  - research DNA root
  - search eval root

Current verified contract:

1. `PAPERPIPE_STORAGE_DIR` wins
2. else if `PAPERPIPE_HOME` is set, use `<home>/storage`
3. else default to current workspace `storage/`

Why it is baseline-critical:

- recent failures in real-smoke, stats repair, and Obsidian sync all traced back to path-contract drift here
- current passing suite depends on this version

Adoption judgment:

- should be retained as the current runtime baseline

### 2.3 Regression coverage files

#### `/Users/jangseongjin/paperpipe/tests/test_meeting_pack_api.py`

Role:

- expanded Meeting Pack API regression coverage for:
  - roundtrip generation
  - project-note context-only behavior
  - screening context-only behavior
  - topic exact structured match
  - projection-backed profile selectors

Why it is baseline-critical:

- covers the current Meeting Pack selector slice more accurately than the older narrower test surface

Important note:

- this currently coexists with tracked `tests/test_meeting_packs_api.py`
- it is not a tiny patch; it is a broader successor-style test file

Adoption judgment:

- should be adopted, but repository owners should decide whether:
  - to keep both files temporarily, or
  - to replace/supersede the older tracked API test file after one cleanup pass

#### `/Users/jangseongjin/paperpipe/tests/test_meeting_pack_source_resolver.py`

Role:

- direct regression coverage for source resolution semantics

Why it is baseline-critical:

- protects the selector contract implemented by `src/meeting_packs/source_resolver.py`

Adoption judgment:

- should be tracked immediately

#### `/Users/jangseongjin/paperpipe/tests/test_runtime_paths_research_dna.py`

Role:

- regression coverage for runtime path rules

Why it is baseline-critical:

- covers path precedence and workspace-default behavior that multiple runtime surfaces now rely on

Adoption judgment:

- should be tracked with `src/services/runtime_paths.py`

### 2.4 Audit/state documentation

#### `/Users/jangseongjin/paperpipe/docs/Current_Code_Baseline_Audit_2026-03-13.md`

Role:

- current best audit of:
  - intent vs implementation
  - queue/spec vs code
  - execution baseline vs repository baseline
  - known missing infrastructure lanes

Why it is baseline-critical:

- it is the best current handoff artifact for the next structure-hardening pass

Adoption judgment:

- should be tracked together with the code baseline so the repository state and audit state do not drift again

## 3. Adoption Order

Recommended order:

1. runtime contract
   - `/Users/jangseongjin/paperpipe/src/services/runtime_paths.py`
   - `/Users/jangseongjin/paperpipe/tests/test_runtime_paths_research_dna.py`

2. Meeting Pack runtime entrypoints
   - `/Users/jangseongjin/paperpipe/backend/routers/meeting_packs.py`
   - `/Users/jangseongjin/paperpipe/src/meeting_packs/source_resolver.py`

3. Meeting Pack regression coverage
   - `/Users/jangseongjin/paperpipe/tests/test_meeting_pack_api.py`
   - `/Users/jangseongjin/paperpipe/tests/test_meeting_pack_source_resolver.py`

4. audit artifact
   - `/Users/jangseongjin/paperpipe/docs/Current_Code_Baseline_Audit_2026-03-13.md`

Reason for this order:

- runtime contract first prevents path regressions from invalidating later verification
- runtime code before tests avoids adopting tests that refer to code not yet fixed as baseline
- audit last ensures the document reflects the exact code snapshot adopted

## 4. Acceptance Criteria For Adoption

Repository baseline should not be considered frozen until all of the following are true:

1. the candidate files above are tracked
2. `pytest -q` remains green
3. Meeting Pack router is still included from `backend/main.py`
4. path precedence remains:
   - `PAPERPIPE_STORAGE_DIR`
   - else `PAPERPIPE_HOME`
   - else workspace `storage/`
5. no duplicate test files remain with conflicting product assumptions

## 5. Open Decisions

### 5.1 Meeting Pack API test duplication

Tracked file:

- `tests/test_meeting_packs_api.py`

Untracked candidate:

- `tests/test_meeting_pack_api.py`

Current recommendation:

- adopt the broader file now
- defer deduplication to a cleanup pass

Reason:

- execution baseline is currently green with both present
- premature deletion/replacement would add churn without improving the baseline immediately

### 5.2 Projection-only profile selector policy

Current implementation and docs align on:

- `project_profile` / `research_profile` are deterministic selectors
- they are currently open only for ResearchDNA projection profiles
- free-text/manual profile expansion is intentionally not part of the current slice

Recommendation:

- keep this policy as baseline
- do not broaden it during repository-freeze work

## 6. Immediate Next Work After Adoption

Once the repository baseline is frozen, the next structural audit should proceed in this order:

1. identity/pathing
2. event logging
3. output contracts
4. citation grounding

This sequencing matches the current risk profile:

- pathing is now stable enough to build on
- the bigger missing pieces are still contract/infrastructure, not Meeting Pack behavior
