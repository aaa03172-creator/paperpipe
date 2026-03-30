# Meeting Pack / Handoff Lane Scoping

Status: scoped execution note
Date: 2026-03-30
Lane: `meeting-pack/handoff`
Parent triage: [Current_Worktree_Lane_Triage_2026-03-29.md](/Users/jangseongjin/paperpipe/docs/reports/Current_Worktree_Lane_Triage_2026-03-29.md)

## Purpose

Turn the current Meeting Pack and adjacent handoff-artifact dirty surface into one bounded execution lane with:

- concrete owner files
- explicit exclusions
- one recommended PR-sized next slice
- one exact verification set

This note does not reopen extraction/runtime-specialty work, and it does not treat all meeting-pack-adjacent or deep-read handoff work as one patch.

## Current Judgment

`meeting-pack/handoff` is a coherent medium-sized lane, but it is still too wide to treat as one mixed pass.

The safe interpretation is:

- keep [MEETING_PACK.md](/Users/jangseongjin/paperpipe/docs/MEETING_PACK.md) as the canonical contract
- keep `acceptance_contract.json` and `quality_gate.json` additive bundle-local metadata only
- treat `meeting_pack_handoff` as the primary closure target
- treat `deepread_handoff` as a sibling reference lane, not part of the first Meeting Pack closure pass

The main reason to keep it narrow is that Meeting Pack already has a stable runtime shape:

- saved bundle contract
- generate / regenerate / rerender flow
- trace and validate operational surfaces
- bounded viewer coverage

The current handoff additions should make that runtime easier to inspect, not redefine it.

## Existing Anchors

Primary contract and pilot anchors already in the tree:

- [MEETING_PACK.md](/Users/jangseongjin/paperpipe/docs/MEETING_PACK.md)
- [Meeting_Pack_Handoff_Pilot_2026-03-27.md](/Users/jangseongjin/paperpipe/docs/reports/Meeting_Pack_Handoff_Pilot_2026-03-27.md)
- [Meeting_Pack_Readiness_Real_Spot_Check_2026-03-27.md](/Users/jangseongjin/paperpipe/docs/reports/Meeting_Pack_Readiness_Real_Spot_Check_2026-03-27.md)
- [UX_REVIEW_REPORT_meeting-pack-viewer.md](/Users/jangseongjin/paperpipe/docs/UX_REVIEW_REPORT_meeting-pack-viewer.md)
- [meeting-pack-verifier skill](/Users/jangseongjin/paperpipe/.codex/skills/meeting-pack-verifier/SKILL.md)

These already imply the right boundary:

- `validate` stays authoritative for current regenerate availability
- trace stays operational metadata only
- handoff artifacts stay additive bundle-local summaries
- viewer work stays downstream of the runtime contract instead of becoming a second spec

## Owner Map

### 1. Canonical contract owners

These files define what the lane is allowed to mean:

- [MEETING_PACK.md](/Users/jangseongjin/paperpipe/docs/MEETING_PACK.md)
- [Meeting_Pack_Handoff_Pilot_2026-03-27.md](/Users/jangseongjin/paperpipe/docs/reports/Meeting_Pack_Handoff_Pilot_2026-03-27.md)
- [Meeting_Pack_Readiness_Real_Spot_Check_2026-03-27.md](/Users/jangseongjin/paperpipe/docs/reports/Meeting_Pack_Readiness_Real_Spot_Check_2026-03-27.md)
- [UX_REVIEW_REPORT_meeting-pack-viewer.md](/Users/jangseongjin/paperpipe/docs/UX_REVIEW_REPORT_meeting-pack-viewer.md)

Responsibilities:

- lock the current Meeting Pack runtime boundary
- keep handoff metadata additive
- keep readiness wording honest
- keep viewer guidance aligned with the saved-pack contract

### 2. Core Meeting Pack runtime owners

These files own the actual pack bundle and lifecycle:

- [service.py](/Users/jangseongjin/paperpipe/src/meeting_packs/service.py)
- [store.py](/Users/jangseongjin/paperpipe/src/meeting_packs/store.py)

Responsibilities:

- generate / regenerate / rerender flow
- bundle writes and rollback safety
- write-time handoff artifact emission
- saved bundle-local artifact persistence

### 3. Meeting Pack handoff artifact owners

These files own the additive handoff contract itself:

- [handoff_artifacts.py](/Users/jangseongjin/paperpipe/src/meeting_packs/handoff_artifacts.py)
- [meeting_pack_handoff.py](/Users/jangseongjin/paperpipe/src/schemas/meeting_pack_handoff.py)
- [test_meeting_pack_handoff_artifacts.py](/Users/jangseongjin/paperpipe/tests/test_meeting_pack_handoff_artifacts.py)

Responsibilities:

- `acceptance_contract.json` shape
- `quality_gate.json` shape
- `bundle_ready` vs `discussion_ready` interpretation
- reason-code stability for bounded operator review

### 4. API and runtime verification owners

These files verify that the additive artifacts stay attached to the current Meeting Pack runtime instead of becoming a disconnected sidecar:

- [test_meeting_pack_service.py](/Users/jangseongjin/paperpipe/tests/test_meeting_pack_service.py)
- [test_meeting_pack_store.py](/Users/jangseongjin/paperpipe/tests/test_meeting_pack_store.py)
- [test_meeting_pack_api.py](/Users/jangseongjin/paperpipe/tests/test_meeting_pack_api.py)
- [test_meeting_packs_api.py](/Users/jangseongjin/paperpipe/tests/test_meeting_packs_api.py)

Responsibilities:

- confirm the pack runtime still emits additive artifact files
- confirm storage paths and persistence behavior stay stable
- confirm API surfaces still expose the same saved-pack contract

### 5. Viewer and browser verification owners

These files verify that the saved-pack route still reads like a downstream draft-review surface:

- [meeting-pack.mock.spec.ts](/Users/jangseongjin/paperpipe/frontend/e2e/meeting-pack.mock.spec.ts)
- [backend.spec.ts](/Users/jangseongjin/paperpipe/frontend/e2e/backend.spec.ts)
- [UX_REVIEW_REPORT_meeting-pack-viewer.md](/Users/jangseongjin/paperpipe/docs/UX_REVIEW_REPORT_meeting-pack-viewer.md)

Responsibilities:

- first-draft create path
- header context strip continuity
- continue-in-note handoff continuity
- rerender / regenerate safety in the browser

### 6. Deep-read handoff sibling owners

These files are related by idea, but not part of the first Meeting Pack closure slice:

- [deepread_handoff.py](/Users/jangseongjin/paperpipe/src/schemas/deepread_handoff.py)
- [deepread_handoff_artifacts.py](/Users/jangseongjin/paperpipe/src/services/deepread_handoff_artifacts.py)
- [job_runner.py](/Users/jangseongjin/paperpipe/backend/services/job_runner.py)
- [test_deepread_handoff_artifacts.py](/Users/jangseongjin/paperpipe/tests/test_deepread_handoff_artifacts.py)

Responsibilities:

- deep-read acceptance / quality-gate metadata
- run-level promotion candidate semantics
- job-runner artifact emission

Current handling:

- keep these visible as a sibling pattern
- do not mix them into the first Meeting Pack handoff closure pass

## Explicitly Out Of Scope For The First Pass

Do not mix these into the first PR-sized slice:

- broad Meeting Pack viewer polish beyond already-open UX checkpoints
- general handoff-framework unification across Meeting Pack and deep-read
- extraction/runtime-specialty work
- personal runtime / packaging work
- broad backend/runtime refactors outside the Meeting Pack owner files
- any change that redefines `validate`, `retrieval_trace[]`, `meeting_pack.json`, or `meeting_pack.md`

Reason:

- the lane is valuable because it is already coherent
- broadening it into a generic handoff framework would erase that advantage
- the current repo already has one active meeting-pack runtime contract, and the next safe step is closure, not abstraction

## Recommended PR-Sized Next Action

### Slice: Meeting Pack handoff artifact closure

Goal:

- keep the current Meeting Pack runtime unchanged
- make the additive handoff artifacts legible, test-backed, and explicitly bounded
- keep the handoff contract attached to the saved-pack runtime rather than drifting into a generic framework

Include:

- [handoff_artifacts.py](/Users/jangseongjin/paperpipe/src/meeting_packs/handoff_artifacts.py)
- [meeting_pack_handoff.py](/Users/jangseongjin/paperpipe/src/schemas/meeting_pack_handoff.py)
- [service.py](/Users/jangseongjin/paperpipe/src/meeting_packs/service.py)
- [store.py](/Users/jangseongjin/paperpipe/src/meeting_packs/store.py)
- [test_meeting_pack_handoff_artifacts.py](/Users/jangseongjin/paperpipe/tests/test_meeting_pack_handoff_artifacts.py)
- [test_meeting_pack_service.py](/Users/jangseongjin/paperpipe/tests/test_meeting_pack_service.py)
- [test_meeting_pack_store.py](/Users/jangseongjin/paperpipe/tests/test_meeting_pack_store.py)
- [test_meeting_pack_api.py](/Users/jangseongjin/paperpipe/tests/test_meeting_pack_api.py)
- [test_meeting_packs_api.py](/Users/jangseongjin/paperpipe/tests/test_meeting_packs_api.py)
- [Meeting_Pack_Handoff_Pilot_2026-03-27.md](/Users/jangseongjin/paperpipe/docs/reports/Meeting_Pack_Handoff_Pilot_2026-03-27.md) if wording or operator interpretation changes

Do not include:

- `deepread_handoff` schema/service/job-runner work
- generic promotion-gate abstractions
- new Meeting Pack viewer features beyond what existing tests already cover
- any broadened readiness RFC

Expected result:

- `acceptance_contract.json` and `quality_gate.json` stay clearly additive
- pack-local operator status is easier to inspect without weakening the current contract
- the lane becomes stageable on its own without dragging in deep-read or broad viewer work

## Smallest Relevant Verification Set

If the patch only touches Meeting Pack handoff artifacts and their runtime wiring:

- `python3 -m pytest /Users/jangseongjin/paperpipe/tests/test_meeting_pack_handoff_artifacts.py /Users/jangseongjin/paperpipe/tests/test_meeting_pack_service.py /Users/jangseongjin/paperpipe/tests/test_meeting_pack_store.py /Users/jangseongjin/paperpipe/tests/test_meeting_pack_api.py /Users/jangseongjin/paperpipe/tests/test_meeting_packs_api.py -q`
- `python3 /Users/jangseongjin/paperpipe/scripts/lint_docs.py`

If the patch changes meeting-pack viewer wording or action labeling:

- `cd /Users/jangseongjin/paperpipe/frontend && npx playwright test -c playwright.mock.config.ts e2e/meeting-pack.mock.spec.ts`

If the patch touches live viewer continuity around create / rerender / regenerate:

- `cd /Users/jangseongjin/paperpipe/frontend && npx playwright test -c playwright.backend.config.ts e2e/backend.spec.ts -g "backend meeting pack create keeps the continuation card and note handoff on the real route"`

Do not escalate to broader frontend or runtime verify lanes unless the touched files cross those boundaries directly.

## Why This Slice First

This is the best next step because it has a strong ratio of:

- coherent ownership
- existing spec coverage
- already-built tests
- bounded operator value

Compared with the rest of the dirty tree, this lane is one of the few places where:

- the contract already exists
- the additive extension is explicit
- the verification path is already concentrated

That means the safest next move is not invention. It is closure.

## Short Version

Treat `meeting-pack/handoff` as one bounded closure lane, not as a generic handoff-framework project.

The next safe implementation slice is:

1. Meeting Pack handoff artifact contract
2. Meeting Pack service/store/runtime wiring
3. only the minimum API/browser verification needed to prove the current saved-pack contract still holds

Leave `deepread_handoff`, broad viewer polish, extraction, and packaging out of that first pass.
