# Remaining Dirty Worktree Lanes

Status: repository triage note  
Date: 2026-03-20  
Branch: `codex/agents-smoke-ci-check`  
Last frozen lane: `ced75fb feat(runtime): freeze memory-ready hardening lane`

## Purpose

Define the remaining dirty worktree as separate lanes so later staging and commits do not mix unrelated work.

This document is not a request to clean the whole repository at once.

## Current Snapshot

`git status --short` at capture time:

- `M`: 99
- `D`: 31
- `??`: 209

Top-level concentration:

- `docs`: 185
- `tests`: 52
- `frontend`: 22
- `src`: 19
- `scripts`: 16
- `.github`: 8
- `snapshots`: 5
- `storage`: 4

## Lane Map

### L1. Docs archive and report migration

Size: 89 paths

Main signals:

- `docs/archive/*`
- `docs/README.md`
- `docs/reports/Local_*`
- `docs/reports/release_notes_*`
- many tracked deletions from old `docs/*` roots with corresponding untracked additions under `docs/archive/*`

Interpretation:

This is mainly an information-architecture move, not runtime product work.

Do not mix with runtime or frontend commits.

Recommended handling:

1. Decide whether the archive move is intentional as a full lane.
2. Stage only the delete/add pairs plus archive index files.
3. Verify docs lint only.

### L2. Docs general strategy/spec lane

Size: 91 paths

Main signals:

- `docs/PR_*`
- `docs/*Audit*`
- `docs/*Spec*`
- `docs/RESEARCH_DNA.md`
- `docs/SKILLS_*`
- `docs/UX_REVIEW_REPORT_*`
- product/reference/spec documents outside `docs/archive/`

Interpretation:

This is a broad documentation lane containing planning, audits, specs, policy, and UX notes.

It is too large for one safe commit.

Recommended split:

1. `docs/spec-and-audit`
2. `docs/ux-review-artifacts`
3. `docs/skills-and-policy`

### L3. Meeting Pack lane

Size: 9 directly classified paths, with nearby dependencies in frontend/tests/docs

Main signals:

- `docs/MEETING_PACK.md`
- `scripts/check_meeting_pack_real_smoke.py`
- `scripts/check_meeting_pack_storage_sync.py`
- `scripts/run_meeting_pack_verify.sh`
- `storage/meeting_packs/`
- `tests/test_meeting_pack_schema.py`
- `tests/test_meeting_pack_store.py`
- `tests/test_meeting_packs_api.py`
- plus likely related frontend and schema files already elsewhere in the tree

Interpretation:

This is a real feature lane and should be handled as its own closure pass.

Do not stage only tests/docs. Expect runtime, store, API, scripts, and some frontend to move together.

### L4. Method comparison lane

Size: 7 directly classified paths

Main signals:

- `backend/routers/method_comparisons.py`
- `src/method_comparisons/service.py`
- `tests/test_method_comparison_service.py`
- `tests/test_method_comparisons_api.py`
- `tests/fixtures/method_comparison_case/`
- `storage/method_comparisons/`

Interpretation:

This is a separate feature lane with backend, fixtures, tests, and likely frontend viewer work.

Keep it isolated from Meeting Pack.

### L5. Research DNA lane

Size: 6 directly classified paths, with additional docs nearby

Main signals:

- `research_dna/`
- `docs/RESEARCH_DNA.md`
- `tests/test_research_dna_projection.py`
- `tests/test_research_dna_schema.py`
- `tests/test_research_dna_store.py`
- `tests/test_research_dna_api.py`

Interpretation:

This is another independent product lane. It should not be mixed with memory-ready runtime hardening or viewer-only work.

### L6. CI and verification lane

Size: 11 paths

Main signals:

- `.github/workflows/*`
- `scripts/run_backend_api_smoke.sh`
- `scripts/run_meeting_pack_verify.sh`
- `scripts/enable_required_checks.sh`
- `scripts/run_agents_smoke.sh`

Interpretation:

This is repo operations and CI policy work.

Treat it as infrastructure. Keep separate from product runtime changes.

### L7. Frontend general lane

Size: 13 paths

Main signals:

- `frontend/src/App.tsx`
- `frontend/src/app/pages/MeetingPackPage.tsx`
- `frontend/src/app/pages/MethodComparisonPage.tsx`
- `frontend/src/app/pages/PaperNotesListPage.tsx`
- `frontend/src/app/components/PdfPanel.tsx`
- `frontend/src/app/components/ui/command.tsx`
- `frontend/src/app/components/ui/input.tsx`
- `frontend/index.css`
- `frontend/playwright.*`
- `frontend/e2e/meeting-pack.mock.spec.ts`
- `frontend/e2e/method-comparison.mock.spec.ts`

Interpretation:

This is a mixed UI lane. It likely needs to be split by surface:

1. shared app-shell/routing
2. meeting-pack UI
3. method-comparison UI
4. paper-notes/PDF surface

Do not commit as one block.

### L8. Runtime and backend general lane

Size: 59 paths

Main signals:

- `src/agents/ingest_agent.py`
- `src/agents/stats_agent.py`
- `src/config.py`
- `src/llm_provider.py`
- `src/processor.py`
- `src/services/cli_workflows.py`
- `src/services/deepread_note_writer.py`
- `src/sandbox/docker_runner.py`
- `src/watcher.py`
- many tests under `tests/`
- scripts like `evaluate_search.py`, `generate_teacher_outputs.py`, `review_teacher_quarantine.py`

Interpretation:

This is not one lane. It is a pile of runtime changes that still need further decomposition.

Recommended sub-splits:

1. ingest/downloader/runtime-paths
2. stats/docker/verification
3. teacher-quality / quarantine review
4. llm-provider / JSON / timeout policy
5. watcher / issue-state / obsidian-save

### L9. Chart pack and data views lane

Size: 9 paths

Main signals:

- `src/chart_packs/`
- `src/schemas/chart_pack.py`
- `tests/test_chart_pack_*`
- `tests/test_runtime_paths_chart_packs.py`
- `storage/search_eval/`
- `storage/obsidian/`

Interpretation:

This looks like a new feature lane. Keep separate from method comparison and Research DNA unless there is an explicit shared schema dependency.

### L10. Skills and policy lane

Size: 7 paths

Main signals:

- `.codex/`
- `config/skills_policy.yaml`
- `docs/SKILLS_*`
- `scripts/skills_audit.py`
- `scripts/sync_scientific_skills.sh`

Interpretation:

This is repo policy and tooling work. Keep it away from product feature commits.

### L11. Visual snapshots and eval artifacts lane

Size: 14 paths

Main signals:

- `frontend/e2e/visual-*.spec.ts-snapshots/*`
- `snapshots/*`
- updated visual backend tests

Interpretation:

These are verification artifacts. They should only move with the exact UI/test lane that changed the visual contract.

Do not stage them by default.

### L12. Misc repository lane

Size: 11 paths

Main signals:

- `.gitignore`
- `AGENTS.md`
- `README.md`
- `config.example.yaml`
- `config/profiles.yaml`
- `pyproject.toml`
- `.omx/`
- `.serena/`
- `baselines/`
- `goldset/*`

Interpretation:

This bucket is not safe as a single commit. Each file here needs explicit intent.

`AGENTS.md`, `README.md`, `pyproject.toml`, and config files can affect the whole repo contract.

## Recommended Order

If further cleanup or commits are needed, use this order:

1. `docs-archive-and-report-migration`
2. `ci-and-verification`
3. `meeting-pack`
4. `method-comparison`
5. `research-dna`
6. `chart-pack-and-data-views`
7. `runtime-and-backend-general` sub-splits
8. `frontend-general` sub-splits
9. `skills-and-policy`
10. `visual-snapshots-and-eval-artifacts`
11. `misc`

Rationale:

- archive and CI lanes are easiest to isolate
- feature lanes should move with their own runtime/tests/frontend closure
- snapshots should move last, only with the UI lane that requires them
- misc/root files require the most care and should not be dragged into feature commits by accident

## Immediate Safe Next Step

Do not stage blindly.

Instead:

1. pick one lane from this document
2. make a lane-specific allowlist manifest
3. verify dependency closure in a temp worktree if the lane has frontend or backend imports
4. only then stage and commit

## Explicit Non-Goal

This document does not try to normalize the whole repository in one pass.

That would be high-risk and would likely mix unrelated work.
