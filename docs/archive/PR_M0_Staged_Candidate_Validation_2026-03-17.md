# PR-M0 Staged Candidate Validation

Status: Index-validated candidate snapshot
Date: 2026-03-17
Scope: confirm that the currently staged `PR-M0` candidate is syntactically valid, documents the intended baseline slice, and does not accidentally absorb known out-of-scope runtime tails

## 0. Validation Summary

The currently staged `PR-M0` candidate is valid as a baseline-adoption candidate.

Rechecked:

- `git diff --cached --check`
- staged-index AST parse for the core Python files
- `python3 scripts/lint_docs.py`
- isolated snapshot test run with `PAPERPIPE_CONFIG_PATH=config.example.yaml`

Result:

- staged index syntax: pass
- staged patch formatting: pass
- docs lint: pass
- isolated snapshot targeted test set: `90 passed`

## 1. Exact Staged Candidate

Current staged set:

- `backend/main.py`
- `backend/routers/meeting_packs.py`
- `src/cli.py`
- `docs/Current_Code_Baseline_Audit_2026-03-13.md`
- `docs/MEETING_PACK.md`
- `docs/PR_M0_Meeting_Pack_Baseline_Adoption_2026-03-13.md`
- `docs/Pending_PR_Queue.md`
- `docs/Repository_Baseline_Adoption_2026-03-13.md`
- `docs/archive/PR_M0_Staging_Dry_Run_2026-03-17.md`
- `src/meeting_packs/__init__.py`
- `src/meeting_packs/evidence.py`
- `src/meeting_packs/renderer.py`
- `src/meeting_packs/service.py`
- `src/meeting_packs/source_resolver.py`
- `src/meeting_packs/store.py`
- `src/profiles/profile_metadata.py`
- `src/profiles/profile_schema.py`
- `src/profiles/profile_store.py`
- `src/profiles/research_dna_schema.py`
- `src/profiles/research_dna_store.py`
- `src/schemas/chat.py`
- `src/schemas/meeting_pack.py`
- `src/schemas/skills.py`
- `src/services/identity.py`
- `src/services/runtime_paths.py`
- `src/skills/storage.py`
- `tests/test_meeting_pack_api.py`
- `tests/test_meeting_pack_schema.py`
- `tests/test_meeting_pack_service.py`
- `tests/test_meeting_pack_source_resolver.py`
- `tests/test_meeting_pack_store.py`
- `tests/test_meeting_packs_api.py`
- `tests/test_profile_projection_guard.py`
- `tests/test_profile_store_concurrency.py`
- `tests/test_runtime_paths_meeting_packs.py`

## 2. Narrow-Hunk Exception

`backend/main.py` remains a special-case file.

Accepted staged scope:

- `meeting_packs` router import
- `app.include_router(meeting_packs.router)`
- `profiles` / `audit` guard compatibility hunk in `src/cli.py`

Rejected for `PR-M0`:

- broader Research DNA
- paper notes
- skills
- stats repair
- chat stub
- event-log/runtime expansion
- broader CLI expansion outside the `profiles` / `audit` guard path

## 3. Known Unstaged Tails That Must Stay Out

These worktree changes remain intentionally unstaged for `PR-M0`:

- `backend/main.py`
  - broader product/runtime diff outside the narrow router wiring hunk
- `src/services/runtime_paths.py`
  - legacy artifact fallback helpers and candidate-path expansion
- `src/services/identity.py`
  - sanitized artifact segment and legacy-path helper expansion
- `backend/routers/meeting_packs.py`
  - list endpoint and trace endpoint follow-up
- `src/meeting_packs/service.py`
  - list/trace service helpers and summaries
- `docs/MEETING_PACK.md`
  - list/trace/debug-inspector follow-up wording

These are not treated as `PR-M0` blockers.
They are separate follow-up lanes.

## 4. Why This Matters

Without this split, `PR-M0` would stop being a baseline-freeze PR and start absorbing broader runtime-path and product-surface changes.

The current staged candidate is therefore acceptable specifically because:

- Meeting Pack runtime files are staged
- required baseline docs are staged
- `backend/main.py` is narrowed
- known broader tails remain unstaged

## 5. Recheck Commands

Commands used for this validation:

- `git diff --cached --check`
- `python3 scripts/lint_docs.py`
- `PAPERPIPE_CONFIG_PATH=config.example.yaml pytest -q tests/test_runtime_paths_meeting_packs.py tests/test_meeting_packs_api.py tests/test_meeting_pack_api.py tests/test_meeting_pack_service.py tests/test_meeting_pack_store.py tests/test_meeting_pack_schema.py tests/test_meeting_pack_source_resolver.py tests/test_profile_projection_guard.py tests/test_profile_store_concurrency.py`
- staged-index AST parse of:
  - `src/cli.py`
  - `backend/main.py`
  - `backend/routers/meeting_packs.py`
  - `src/meeting_packs/service.py`
  - `src/meeting_packs/source_resolver.py`
  - `src/meeting_packs/store.py`
  - `src/services/runtime_paths.py`
  - `src/services/identity.py`
  - `src/profiles/profile_schema.py`
  - `src/profiles/profile_store.py`
