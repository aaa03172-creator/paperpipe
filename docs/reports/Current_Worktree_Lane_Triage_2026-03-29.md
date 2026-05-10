# Current Worktree Lane Triage

Status: repository triage note
Date: 2026-03-29
Lane: `smallest-safe-patch`

## Purpose

Turn the current dirty worktree into a small set of operational lanes so the next execution pass does not mix unrelated work.

This note is not:

- a request to clean the whole repository at once
- a claim that every modified path should ship together
- a reason to reopen already-frozen extraction/runtime-specialty work by default

It answers one narrower question:

- given the current tree, what should we treat as separate lanes, and what should we do next?

## Current Snapshot

`git status --short` at capture time:

- total dirty paths: `289`
- modified tracked paths: `159`
- untracked paths: `130`

Top-level concentration:

- `tests`: `76`
- `docs`: `69`
- `frontend`: `46`
- `src`: `38`
- `scripts`: `22`
- `goldset`: `16`
- `snapshots`: `7`
- `backend`: `4`

Highest-concentration second-level paths:

- `docs/reports`: `43`
- `frontend/src`: `26`
- `goldset/manifests`: `15`
- `frontend/e2e`: `12`
- `src/services`: `10`
- `scripts/eval`: `8`
- `src/agents`: `7`
- `src/schemas`: `6`

Interpretation:

- the current tree is not one active lane
- it is several partially overlapping lanes plus a large background docs/runtime pile
- the next safe move is lane selection, not more broad implementation

## Lane Map

### L1. Extraction / Runtime-Specialty Evidence Lane

Estimated size: `41` paths

Main signals:

- `scripts/eval/*` for extraction/runtime-specialty audits
- `goldset/extraction_regression/*`
- `goldset/manifests/extraction_regression_*`
- `snapshots/extraction_*`
- `tests/test_extraction_*`
- `tests/test_specialty_runtime_*`
- [Extraction_Regression_Repo_Grounded_Pilot_2026-03-27.md](/Users/jangseongjin/paperpipe/docs/reports/Extraction_Regression_Repo_Grounded_Pilot_2026-03-27.md)
- [Specialty_Runtime_Posture_Decision_2026-03-29.md](/Users/jangseongjin/paperpipe/docs/reports/Specialty_Runtime_Posture_Decision_2026-03-29.md)

Current judgment:

- treat this lane as frozen by default
- canonical baseline is the sixteen-document sidecar replay
- runtime specialty stays blocked

Primary anchors:

- [extraction_repo_grounded_preclinical_therapeutic_realpred_20260328_r1_repair29/metrics.json](/Users/jangseongjin/paperpipe/snapshots/extraction_regression_eval/extraction_repo_grounded_preclinical_therapeutic_realpred_20260328_r1_repair29/metrics.json)
- [extraction_runtime_promotion_gate_20260329_r2/summary.json](/Users/jangseongjin/paperpipe/snapshots/extraction_runtime_promotion_gate/extraction_runtime_promotion_gate_20260329_r2/summary.json)

Recommended handling:

1. Do not widen this lane further by default.
2. Do not mix it into unrelated frontend/runtime commits.
3. Reopen only through an explicit Coric-only RFC.

### L2. Frontend / Viewer / Runtime-Readiness Lane

Estimated size: `73` paths

Main signals:

- `frontend/src/*`
- `frontend/e2e/*`
- `frontend/playwright*.ts`
- `frontend/README.md`
- `docs/UX_REVIEW_REPORT_*`
- `docs/WEB_VIEWER.md`
- `backend/main.py`
- `backend/routers/paper_notes.py`
- `backend/routers/obsidian.py`
- runtime-readiness UI/API tests

Current judgment:

- this is the largest coherent user-facing lane still open in the tree
- if we want one active non-extraction lane next, this is the best candidate
- it already has concentrated verification surfaces

Why this is the best next candidate:

- it is big enough to justify isolation
- it already spans UI, docs, tests, and a small backend surface
- it is more coherent than the broad backend/runtime pile

Recommended handling:

1. Treat this as the first candidate if we want to keep executing now.
2. Keep it separate from packaging and meeting-pack work.
3. Verify through the existing frontend/backend Playwright path instead of ad hoc runtime edits.

### L3. Personal Runtime / Packaging Lane

Estimated size: `21` paths

Main signals:

- `packaging/`
- `scripts/build_personal_runtime_*`
- `scripts/release_macos_personal_runtime.py`
- `scripts/check_windows_personal_runtime_smoke.py`
- `scripts/measure_deepread_runtime.py`
- `src/services/runtime_readiness.py`
- `src/services/runtime_paths.py`
- `tests/test_build_personal_runtime_*`
- `tests/test_runtime_paths_*`
- `docs/reports/Personal_Runtime_*`

Current judgment:

- this is a distinct packaging/distribution lane
- it should not be mixed with viewer work or extraction work

Recommended handling:

1. Open only if the current goal is packaging or local runtime delivery.
2. Keep it isolated from frontend/viewer polish.

### L4. Meeting Pack / Handoff Lane

Estimated size: `15` paths

Main signals:

- `docs/MEETING_PACK.md`
- `src/meeting_packs/*`
- `src/meeting_packs/handoff_artifacts.py`
- `src/services/deepread_handoff_artifacts.py`
- `src/schemas/deepread_handoff.py`
- `src/schemas/meeting_pack_handoff.py`
- `tests/test_meeting_pack*`
- `tests/test_deepread_handoff_artifacts.py`
- `docs/reports/Meeting_Pack_*`

Current judgment:

- this is a medium-sized feature lane with a clear owner surface
- it should be executed separately from the viewer lane

Recommended handling:

1. Keep this as its own closure pass.
2. Do not mix it into packaging or extraction commits.

### L5. Broad Runtime / Backend / Docs Pile

Estimated size: `95+` paths after the four lanes above are removed

Main signals:

- `src/agents/*`
- `src/config.py`
- `src/jobs/worker.py`
- `src/processor.py`
- `src/exporter.py`
- `src/services/*` outside clearly scoped lanes
- `tests/*` across many runtime surfaces
- many strategy/spec/report docs outside one owner lane

Current judgment:

- this is not a safe execution lane
- it is a mixed pile that needs a second decomposition pass before anyone should stage it

Recommended handling:

1. Do not pick this as “the next thing.”
2. If we need to work here, split it again first by behavior owner.

## Recommended Action Order

### 1. Keep L1 frozen

Default posture:

- extraction sidecar remains canonical
- runtime specialty remains blocked
- no more widening unless a user explicitly asks for the Coric-only RFC

### 2. If we continue implementation now, choose exactly one lane

Recommended first choice:

- `L2. Frontend / Viewer / Runtime-Readiness`

Recommended alternatives:

- `L4. Meeting Pack / Handoff` if the goal is demo/handoff flow
- `L3. Personal Runtime / Packaging` if the goal is packaging or local delivery

### 3. Keep L5 out of scope until it is split further

This is the main anti-pattern to avoid:

- do not treat the remaining broad runtime/backend/docs pile as one safe patch

## Short Version

The repo is currently a multi-lane dirty worktree, not one unfinished branch.
The safe default is:

1. keep extraction/runtime-specialty frozen
2. pick one next lane only
3. do not touch the broad runtime/backend pile until it is decomposed again

If we want the highest-signal next execution lane right now, pick the frontend/viewer/runtime-readiness lane.
