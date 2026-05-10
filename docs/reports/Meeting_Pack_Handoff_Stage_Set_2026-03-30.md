# Meeting Pack Handoff Stage Set

Status: staging-boundary note
Date: 2026-03-30
Lane: `meeting-pack/handoff`
Parent notes:
- [Meeting_Pack_Handoff_Lane_Scoping_2026-03-30.md](/Users/jangseongjin/paperpipe/docs/reports/Meeting_Pack_Handoff_Lane_Scoping_2026-03-30.md)
- [Meeting_Pack_Handoff_Closure_Signoff_2026-03-30.md](/Users/jangseongjin/paperpipe/docs/reports/Meeting_Pack_Handoff_Closure_Signoff_2026-03-30.md)

## Purpose

Turn the currently verified Meeting Pack handoff lane into an exact stage boundary.

This note answers one practical question:

- if we close the smallest Meeting Pack handoff patch next, which files belong in it, which files need hunk-splitting, and which files should stay out?

## Current Judgment

The verified `meeting-pack/handoff` area is still coherent, but the dirty paths are not equally clean.

There are three different buckets:

1. whole-file safe for a handoff-closure patch
2. split-required files that currently mix handoff closure with other Meeting Pack work
3. excluded files that belong to sibling lanes

## 1. Whole-File Safe For Handoff Closure

These files are already tightly aligned with the additive handoff contract and can be treated as all-in for the closure patch:

- [handoff_artifacts.py](/Users/jangseongjin/paperpipe/src/meeting_packs/handoff_artifacts.py)
- [meeting_pack_handoff.py](/Users/jangseongjin/paperpipe/src/schemas/meeting_pack_handoff.py)
- [test_meeting_pack_handoff_artifacts.py](/Users/jangseongjin/paperpipe/tests/test_meeting_pack_handoff_artifacts.py)
- [Meeting_Pack_Handoff_Pilot_2026-03-27.md](/Users/jangseongjin/paperpipe/docs/reports/Meeting_Pack_Handoff_Pilot_2026-03-27.md)
- [Meeting_Pack_Handoff_Lane_Scoping_2026-03-30.md](/Users/jangseongjin/paperpipe/docs/reports/Meeting_Pack_Handoff_Lane_Scoping_2026-03-30.md)
- [Meeting_Pack_Handoff_Closure_Signoff_2026-03-30.md](/Users/jangseongjin/paperpipe/docs/reports/Meeting_Pack_Handoff_Closure_Signoff_2026-03-30.md)

Why they are safe:

- they define or describe the additive handoff contract directly
- they do not mix in viewer-only continuity work
- they do not pull in deep-read sibling behavior

## 2. Split-Required Files

These files are still inside the broader Meeting Pack lane, but they currently mix handoff closure with other concerns.

### [service.py](/Users/jangseongjin/paperpipe/src/meeting_packs/service.py)

Safe-for-closure sub-slice:

- handoff artifact import and logger setup
- write-time handoff artifact emission after generate/rerender
- helper that writes `acceptance_contract.json` and `quality_gate.json`

Mixed-with-other-work:

- fixture filtering in `list_meeting_packs`
- readiness semantics based on direct support / grounding metadata
- additional uncertainty wording tied to grounding-state hardening

Interpretation:

- if we want the smallest handoff-only patch, this file needs hunk splitting

### [store.py](/Users/jangseongjin/paperpipe/src/meeting_packs/store.py)

Current diff is still closure-aligned:

- `meeting_pack_artifact_path(...)`
- `save_meeting_pack_artifact_json(...)`

Interpretation:

- this file can stay in the handoff closure patch as a whole

### [test_meeting_pack_service.py](/Users/jangseongjin/paperpipe/tests/test_meeting_pack_service.py)

Safe-for-closure sub-slice:

- persistence assertions for `acceptance_contract.json`
- persistence assertions for `quality_gate.json`

Mixed-with-other-work:

- fixture-visibility tests
- `background_only` / direct-support readiness tests
- grounding-metadata uncertainty tests

Interpretation:

- split required if we keep the closure patch handoff-only

### [test_meeting_pack_store.py](/Users/jangseongjin/paperpipe/tests/test_meeting_pack_store.py)

Current diff is closure-aligned:

- additive bundle artifact save/load path coverage

Interpretation:

- safe to include whole-file

### [test_meeting_pack_api.py](/Users/jangseongjin/paperpipe/tests/test_meeting_pack_api.py)

Current diff:

- config key rename from `trial_extraction` to `specialty_trial_extraction`

Interpretation:

- unrelated to Meeting Pack handoff closure
- exclude from this patch unless another lane explicitly owns that rename

### [test_meeting_packs_api.py](/Users/jangseongjin/paperpipe/tests/test_meeting_packs_api.py)

Mixed-with-other-work:

- `background_only` readiness API behavior
- `/api/meeting-packs` mirrored listing assertion

Interpretation:

- still Meeting Pack work, but not required for a minimal handoff-closure patch
- keep out unless we intentionally widen into Meeting Pack readiness/listing hardening

### [UX_REVIEW_REPORT_meeting-pack-viewer.md](/Users/jangseongjin/paperpipe/docs/UX_REVIEW_REPORT_meeting-pack-viewer.md)

Current diff is viewer-lane work:

- first-draft create path
- header context strip
- continue-in-note continuity
- rerender/regenerate browser continuity checkpoints

Interpretation:

- valid Meeting Pack lane work
- not part of the smallest handoff closure patch

### [meeting-pack.mock.spec.ts](/Users/jangseongjin/paperpipe/frontend/e2e/meeting-pack.mock.spec.ts)

Current diff is viewer-lane work:

- create flow
- header context strip
- continue-in-note assertions

Interpretation:

- keep out of a handoff-only patch

### [backend.spec.ts](/Users/jangseongjin/paperpipe/frontend/e2e/backend.spec.ts)

Relevant Meeting Pack portion:

- [backend.spec.ts:670](/Users/jangseongjin/paperpipe/frontend/e2e/backend.spec.ts#L670)

Current problem:

- the file is heavily mixed with unrelated backend e2e changes

Interpretation:

- do not include this file in a smallest handoff-closure patch without explicit hunk-splitting

## 3. Excluded Sibling Files

Keep these out of the Meeting Pack handoff closure patch:

- [deepread_handoff.py](/Users/jangseongjin/paperpipe/src/schemas/deepread_handoff.py)
- [deepread_handoff_artifacts.py](/Users/jangseongjin/paperpipe/src/services/deepread_handoff_artifacts.py)
- [test_deepread_handoff_artifacts.py](/Users/jangseongjin/paperpipe/tests/test_deepread_handoff_artifacts.py)
- [meeting-pack-verifier skill](/Users/jangseongjin/paperpipe/.codex/skills/meeting-pack-verifier/SKILL.md)
- [Meeting_Pack_Readiness_Real_Spot_Check_2026-03-27.md](/Users/jangseongjin/paperpipe/docs/reports/Meeting_Pack_Readiness_Real_Spot_Check_2026-03-27.md)

Why:

- `deepread_handoff` is a sibling handoff pattern, not the same runtime surface
- the skill is developer workflow support, not product runtime closure
- the readiness spot check belongs with Meeting Pack readiness hardening, not the smallest additive handoff closure

## Recommended Smallest Stage Set

If we want the smallest defensible Meeting Pack handoff closure patch, the safest set is:

- [handoff_artifacts.py](/Users/jangseongjin/paperpipe/src/meeting_packs/handoff_artifacts.py)
- [meeting_pack_handoff.py](/Users/jangseongjin/paperpipe/src/schemas/meeting_pack_handoff.py)
- [store.py](/Users/jangseongjin/paperpipe/src/meeting_packs/store.py)
- handoff-only hunks from [service.py](/Users/jangseongjin/paperpipe/src/meeting_packs/service.py)
- [test_meeting_pack_handoff_artifacts.py](/Users/jangseongjin/paperpipe/tests/test_meeting_pack_handoff_artifacts.py)
- handoff-only hunks from [test_meeting_pack_service.py](/Users/jangseongjin/paperpipe/tests/test_meeting_pack_service.py)
- [test_meeting_pack_store.py](/Users/jangseongjin/paperpipe/tests/test_meeting_pack_store.py)
- [Meeting_Pack_Handoff_Pilot_2026-03-27.md](/Users/jangseongjin/paperpipe/docs/reports/Meeting_Pack_Handoff_Pilot_2026-03-27.md)
- [Meeting_Pack_Handoff_Lane_Scoping_2026-03-30.md](/Users/jangseongjin/paperpipe/docs/reports/Meeting_Pack_Handoff_Lane_Scoping_2026-03-30.md)
- [Meeting_Pack_Handoff_Closure_Signoff_2026-03-30.md](/Users/jangseongjin/paperpipe/docs/reports/Meeting_Pack_Handoff_Closure_Signoff_2026-03-30.md)
- [Meeting_Pack_Handoff_Stage_Set_2026-03-30.md](/Users/jangseongjin/paperpipe/docs/reports/Meeting_Pack_Handoff_Stage_Set_2026-03-30.md)

## Practical Meaning

The current Meeting Pack lane is ready for closure, but not as one blind file-level stage of every dirty `meeting*` path.

The safest next step is:

1. keep the handoff contract core
2. split out readiness and viewer continuity follow-ups
3. leave deep-read handoff out entirely

## Short Version

The Meeting Pack lane is stageable, but the smallest safe closure patch is narrower than “all dirty Meeting Pack files.”

Use this rule:

- include handoff contract files
- split mixed runtime/test files
- exclude deep-read, viewer-only, and unrelated config-renaming changes
