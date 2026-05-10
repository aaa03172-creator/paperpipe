# Meeting Pack Handoff Ready-To-Stage Checklist

Status: pre-stage checklist
Date: 2026-03-30
Lane: `meeting-pack/handoff`
Parent notes:
- [Meeting_Pack_Handoff_Lane_Scoping_2026-03-30.md](/Users/jangseongjin/paperpipe/docs/reports/Meeting_Pack_Handoff_Lane_Scoping_2026-03-30.md)
- [Meeting_Pack_Handoff_Stage_Set_2026-03-30.md](/Users/jangseongjin/paperpipe/docs/reports/Meeting_Pack_Handoff_Stage_Set_2026-03-30.md)
- [Meeting_Pack_Handoff_Hunk_Map_2026-03-30.md](/Users/jangseongjin/paperpipe/docs/reports/Meeting_Pack_Handoff_Hunk_Map_2026-03-30.md)

## Purpose

Freeze the smallest safe closure patch for the current Meeting Pack handoff lane without actually staging or committing anything.

This note answers one practical question:

- if we close the handoff-core patch next, what exactly should be staged, what should be staged by hunk, what should stay out, and what is the smallest verification set to rerun right before staging?

## Current Ready-To-Stage Judgment

Yes, the handoff-core patch is ready to stage in principle.

But it is only ready if we keep the boundary narrow:

1. stage the handoff contract files whole
2. split the two mixed files by the already-frozen hunk map
3. keep readiness, fixture filtering, viewer continuity, and deep-read sibling work out

## Stage Whole

These files are safe to stage whole for the smallest handoff-core patch:

- [handoff_artifacts.py](/Users/jangseongjin/paperpipe/src/meeting_packs/handoff_artifacts.py)
- [meeting_pack_handoff.py](/Users/jangseongjin/paperpipe/src/schemas/meeting_pack_handoff.py)
- [store.py](/Users/jangseongjin/paperpipe/src/meeting_packs/store.py)
- [test_meeting_pack_handoff_artifacts.py](/Users/jangseongjin/paperpipe/tests/test_meeting_pack_handoff_artifacts.py)
- [test_meeting_pack_store.py](/Users/jangseongjin/paperpipe/tests/test_meeting_pack_store.py)
- [Meeting_Pack_Handoff_Pilot_2026-03-27.md](/Users/jangseongjin/paperpipe/docs/reports/Meeting_Pack_Handoff_Pilot_2026-03-27.md)
- [Meeting_Pack_Handoff_Lane_Scoping_2026-03-30.md](/Users/jangseongjin/paperpipe/docs/reports/Meeting_Pack_Handoff_Lane_Scoping_2026-03-30.md)
- [Meeting_Pack_Handoff_Closure_Signoff_2026-03-30.md](/Users/jangseongjin/paperpipe/docs/reports/Meeting_Pack_Handoff_Closure_Signoff_2026-03-30.md)
- [Meeting_Pack_Handoff_Stage_Set_2026-03-30.md](/Users/jangseongjin/paperpipe/docs/reports/Meeting_Pack_Handoff_Stage_Set_2026-03-30.md)
- [Meeting_Pack_Handoff_Hunk_Map_2026-03-30.md](/Users/jangseongjin/paperpipe/docs/reports/Meeting_Pack_Handoff_Hunk_Map_2026-03-30.md)
- [Meeting_Pack_Handoff_Ready_To_Stage_2026-03-30.md](/Users/jangseongjin/paperpipe/docs/reports/Meeting_Pack_Handoff_Ready_To_Stage_2026-03-30.md)

## Stage By Hunk Only

### [service.py](/Users/jangseongjin/paperpipe/src/meeting_packs/service.py)

Include only:

- handoff writer import and logger setup
- generate-time handoff write hook
- rerender-time handoff write hook
- `_write_meeting_pack_handoff_artifacts(...)` helper

Keep out:

- fixture visibility filtering in `list_meeting_packs(...)`
- readiness semantics based on direct support
- grounding-metadata uncertainty messaging

Reference anchors:

- include: [service.py:6](/Users/jangseongjin/paperpipe/src/meeting_packs/service.py#L6), [service.py:11](/Users/jangseongjin/paperpipe/src/meeting_packs/service.py#L11), [service.py:56](/Users/jangseongjin/paperpipe/src/meeting_packs/service.py#L56), [service.py:249](/Users/jangseongjin/paperpipe/src/meeting_packs/service.py#L249), [service.py:251](/Users/jangseongjin/paperpipe/src/meeting_packs/service.py#L251), [service.py:337](/Users/jangseongjin/paperpipe/src/meeting_packs/service.py#L337), [service.py:341](/Users/jangseongjin/paperpipe/src/meeting_packs/service.py#L341), [service.py:735](/Users/jangseongjin/paperpipe/src/meeting_packs/service.py#L735), [service.py:751](/Users/jangseongjin/paperpipe/src/meeting_packs/service.py#L751)
- exclude: [service.py:28](/Users/jangseongjin/paperpipe/src/meeting_packs/service.py#L28), [service.py:262](/Users/jangseongjin/paperpipe/src/meeting_packs/service.py#L262), [service.py:266](/Users/jangseongjin/paperpipe/src/meeting_packs/service.py#L266), [service.py:391](/Users/jangseongjin/paperpipe/src/meeting_packs/service.py#L391), [service.py:397](/Users/jangseongjin/paperpipe/src/meeting_packs/service.py#L397), [service.py:427](/Users/jangseongjin/paperpipe/src/meeting_packs/service.py#L427), [service.py:652](/Users/jangseongjin/paperpipe/src/meeting_packs/service.py#L652), [service.py:658](/Users/jangseongjin/paperpipe/src/meeting_packs/service.py#L658)

### [test_meeting_pack_service.py](/Users/jangseongjin/paperpipe/tests/test_meeting_pack_service.py)

Include only:

- generate-path handoff artifact persistence assertions
- regenerate-path handoff continuity assertions
- rerender-path handoff rewrite assertions

Important note:

- the rerender assertion is now meaningful because it corrupts `acceptance_contract.json` and deletes `quality_gate.json` before rerender, so stale file reuse can no longer false-pass

Keep out:

- fixture filtering tests
- background-only / direct-support readiness tests
- grounding-metadata uncertainty tests

Reference anchors:

- include: [test_meeting_pack_service.py:347](/Users/jangseongjin/paperpipe/tests/test_meeting_pack_service.py#L347), [test_meeting_pack_service.py:356](/Users/jangseongjin/paperpipe/tests/test_meeting_pack_service.py#L356), [test_meeting_pack_service.py:559](/Users/jangseongjin/paperpipe/tests/test_meeting_pack_service.py#L559), [test_meeting_pack_service.py:567](/Users/jangseongjin/paperpipe/tests/test_meeting_pack_service.py#L567), [test_meeting_pack_service.py:587](/Users/jangseongjin/paperpipe/tests/test_meeting_pack_service.py#L587), [test_meeting_pack_service.py:612](/Users/jangseongjin/paperpipe/tests/test_meeting_pack_service.py#L612)
- exclude: [test_meeting_pack_service.py:399](/Users/jangseongjin/paperpipe/tests/test_meeting_pack_service.py#L399), [test_meeting_pack_service.py:471](/Users/jangseongjin/paperpipe/tests/test_meeting_pack_service.py#L471), [test_meeting_pack_service.py:665](/Users/jangseongjin/paperpipe/tests/test_meeting_pack_service.py#L665), [test_meeting_pack_service.py:717](/Users/jangseongjin/paperpipe/tests/test_meeting_pack_service.py#L717), [test_meeting_pack_service.py:719](/Users/jangseongjin/paperpipe/tests/test_meeting_pack_service.py#L719), [test_meeting_pack_service.py:742](/Users/jangseongjin/paperpipe/tests/test_meeting_pack_service.py#L742)

## Keep Out Of This Patch

Do not stage these with the smallest handoff-core closure:

- [test_meeting_pack_api.py](/Users/jangseongjin/paperpipe/tests/test_meeting_pack_api.py)
- [test_meeting_packs_api.py](/Users/jangseongjin/paperpipe/tests/test_meeting_packs_api.py)
- [meeting-pack.mock.spec.ts](/Users/jangseongjin/paperpipe/frontend/e2e/meeting-pack.mock.spec.ts)
- [backend.spec.ts](/Users/jangseongjin/paperpipe/frontend/e2e/backend.spec.ts)
- [UX_REVIEW_REPORT_meeting-pack-viewer.md](/Users/jangseongjin/paperpipe/docs/UX_REVIEW_REPORT_meeting-pack-viewer.md)
- [deepread_handoff.py](/Users/jangseongjin/paperpipe/src/schemas/deepread_handoff.py)
- [deepread_handoff_artifacts.py](/Users/jangseongjin/paperpipe/src/services/deepread_handoff_artifacts.py)
- [test_deepread_handoff_artifacts.py](/Users/jangseongjin/paperpipe/tests/test_deepread_handoff_artifacts.py)
- [meeting-pack-verifier skill](/Users/jangseongjin/paperpipe/.codex/skills/meeting-pack-verifier/SKILL.md)
- [Meeting_Pack_Readiness_Real_Spot_Check_2026-03-27.md](/Users/jangseongjin/paperpipe/docs/reports/Meeting_Pack_Readiness_Real_Spot_Check_2026-03-27.md)

## Pre-Stage Verification

Rerun this exact narrow set immediately before staging:

```bash
python3 -m pytest \
  /Users/jangseongjin/paperpipe/tests/test_meeting_pack_handoff_artifacts.py \
  /Users/jangseongjin/paperpipe/tests/test_meeting_pack_store.py \
  /Users/jangseongjin/paperpipe/tests/test_meeting_pack_service.py \
  -k 'persists_json_and_markdown or regenerate_meeting_pack_uses_saved_generation_request_and_creates_new_pack or rerender_meeting_pack_rebuilds_markdown_from_saved_json or meeting_pack_handoff or additive_bundle_artifact_json' -q
```

Current spot-check status:

- rerun on 2026-03-30 after the rerender false-pass fix
- result: `7 passed`
- only existing dependency warnings

## Manual Stage Recipe

If we actually move to git staging next, use this sequence and stop if any extra diff appears outside the handoff-core boundary:

1. stage the whole-file-safe handoff contract files first
2. rerun the narrow pytest set
3. hunk-stage only the allowed sections from the two mixed files
4. rerun the same narrow pytest set if the mixed-file selection changed during staging

Whole-file-safe starting point:

```bash
git add \
  /Users/jangseongjin/paperpipe/src/meeting_packs/handoff_artifacts.py \
  /Users/jangseongjin/paperpipe/src/schemas/meeting_pack_handoff.py \
  /Users/jangseongjin/paperpipe/src/meeting_packs/store.py \
  /Users/jangseongjin/paperpipe/tests/test_meeting_pack_handoff_artifacts.py \
  /Users/jangseongjin/paperpipe/tests/test_meeting_pack_store.py \
  /Users/jangseongjin/paperpipe/docs/reports/Meeting_Pack_Handoff_Pilot_2026-03-27.md \
  /Users/jangseongjin/paperpipe/docs/reports/Meeting_Pack_Handoff_Lane_Scoping_2026-03-30.md \
  /Users/jangseongjin/paperpipe/docs/reports/Meeting_Pack_Handoff_Closure_Signoff_2026-03-30.md \
  /Users/jangseongjin/paperpipe/docs/reports/Meeting_Pack_Handoff_Stage_Set_2026-03-30.md \
  /Users/jangseongjin/paperpipe/docs/reports/Meeting_Pack_Handoff_Hunk_Map_2026-03-30.md \
  /Users/jangseongjin/paperpipe/docs/reports/Meeting_Pack_Handoff_Ready_To_Stage_2026-03-30.md
```

Mixed files to stage by hunk only:

```bash
git add -p /Users/jangseongjin/paperpipe/src/meeting_packs/service.py
git add -p /Users/jangseongjin/paperpipe/tests/test_meeting_pack_service.py
```

Use the line anchors from:

- [Meeting_Pack_Handoff_Hunk_Map_2026-03-30.md](/Users/jangseongjin/paperpipe/docs/reports/Meeting_Pack_Handoff_Hunk_Map_2026-03-30.md)

Do not add these as part of the handoff-core closure:

- [test_meeting_pack_api.py](/Users/jangseongjin/paperpipe/tests/test_meeting_pack_api.py)
- [test_meeting_packs_api.py](/Users/jangseongjin/paperpipe/tests/test_meeting_packs_api.py)
- [meeting-pack.mock.spec.ts](/Users/jangseongjin/paperpipe/frontend/e2e/meeting-pack.mock.spec.ts)
- [backend.spec.ts](/Users/jangseongjin/paperpipe/frontend/e2e/backend.spec.ts)
- [UX_REVIEW_REPORT_meeting-pack-viewer.md](/Users/jangseongjin/paperpipe/docs/UX_REVIEW_REPORT_meeting-pack-viewer.md)
- [deepread_handoff.py](/Users/jangseongjin/paperpipe/src/schemas/deepread_handoff.py)
- [deepread_handoff_artifacts.py](/Users/jangseongjin/paperpipe/src/services/deepread_handoff_artifacts.py)
- [test_deepread_handoff_artifacts.py](/Users/jangseongjin/paperpipe/tests/test_deepread_handoff_artifacts.py)

Optional broader reconfirmation after the handoff-core stage is assembled:

```bash
python3 -m pytest \
  /Users/jangseongjin/paperpipe/tests/test_meeting_pack_handoff_artifacts.py \
  /Users/jangseongjin/paperpipe/tests/test_meeting_pack_service.py \
  /Users/jangseongjin/paperpipe/tests/test_meeting_pack_store.py \
  /Users/jangseongjin/paperpipe/tests/test_meeting_pack_api.py \
  /Users/jangseongjin/paperpipe/tests/test_meeting_packs_api.py -q
```

## Final Rule

This note does not authorize broad staging.

It only says:

- the handoff-core patch is ready
- the safe boundary is now explicit
- the next actual git action should be a narrow handoff-core stage, not a full Meeting Pack sweep
