# Meeting Pack Handoff Hunk Map

Status: staging-detail note
Date: 2026-03-30
Lane: `meeting-pack/handoff`
Parent notes:
- [Meeting_Pack_Handoff_Lane_Scoping_2026-03-30.md](/Users/jangseongjin/paperpipe/docs/reports/Meeting_Pack_Handoff_Lane_Scoping_2026-03-30.md)
- [Meeting_Pack_Handoff_Stage_Set_2026-03-30.md](/Users/jangseongjin/paperpipe/docs/reports/Meeting_Pack_Handoff_Stage_Set_2026-03-30.md)

## Purpose

Freeze the exact mixed-file hunk boundaries for the smallest handoff-core closure patch.

This note is narrower than the stage-set note.
It assumes we already accepted the stage-set boundary and answers:

- inside the mixed files, which exact line ranges belong to handoff-core?
- which line ranges should stay out because they belong to readiness or viewer follow-up work?

## Mixed File 1: `src/meeting_packs/service.py`

File: [service.py](/Users/jangseongjin/paperpipe/src/meeting_packs/service.py)

### Include in handoff-core patch

- import and logger setup for handoff writing:
  - [service.py:6](/Users/jangseongjin/paperpipe/src/meeting_packs/service.py#L6)
  - [service.py:11](/Users/jangseongjin/paperpipe/src/meeting_packs/service.py#L11)
  - [service.py:56](/Users/jangseongjin/paperpipe/src/meeting_packs/service.py#L56)
- write handoff artifacts after generate:
  - [service.py:249](/Users/jangseongjin/paperpipe/src/meeting_packs/service.py#L249)
  - [service.py:251](/Users/jangseongjin/paperpipe/src/meeting_packs/service.py#L251)
- write handoff artifacts after rerender:
  - [service.py:337](/Users/jangseongjin/paperpipe/src/meeting_packs/service.py#L337)
  - [service.py:341](/Users/jangseongjin/paperpipe/src/meeting_packs/service.py#L341)
- helper that materializes the bundle-local handoff artifacts:
  - [service.py:735](/Users/jangseongjin/paperpipe/src/meeting_packs/service.py#L735)
  - [service.py:751](/Users/jangseongjin/paperpipe/src/meeting_packs/service.py#L751)

### Exclude from handoff-core patch

- fixture filtering in saved-pack listing:
  - [service.py:28](/Users/jangseongjin/paperpipe/src/meeting_packs/service.py#L28)
  - [service.py:262](/Users/jangseongjin/paperpipe/src/meeting_packs/service.py#L262)
  - [service.py:266](/Users/jangseongjin/paperpipe/src/meeting_packs/service.py#L266)
- uncertainty-building changes tied to readiness/grounding hardening:
  - [service.py:391](/Users/jangseongjin/paperpipe/src/meeting_packs/service.py#L391)
  - [service.py:397](/Users/jangseongjin/paperpipe/src/meeting_packs/service.py#L397)
- readiness semantics change from “claim rows exist” to “direct support exists”:
  - [service.py:427](/Users/jangseongjin/paperpipe/src/meeting_packs/service.py#L427)
  - [service.py:652](/Users/jangseongjin/paperpipe/src/meeting_packs/service.py#L652)
  - [service.py:658](/Users/jangseongjin/paperpipe/src/meeting_packs/service.py#L658)

### Interpretation

If the goal is the smallest handoff-only closure patch, `service.py` must be staged by hunk, not by file.

## Mixed File 2: `tests/test_meeting_pack_service.py`

File: [test_meeting_pack_service.py](/Users/jangseongjin/paperpipe/tests/test_meeting_pack_service.py)

### Include in handoff-core patch

- generate-path handoff artifact persistence assertions:
  - [test_meeting_pack_service.py:347](/Users/jangseongjin/paperpipe/tests/test_meeting_pack_service.py#L347)
  - [test_meeting_pack_service.py:356](/Users/jangseongjin/paperpipe/tests/test_meeting_pack_service.py#L356)
- regenerate-path handoff artifact continuity assertions:
  - [test_meeting_pack_service.py:559](/Users/jangseongjin/paperpipe/tests/test_meeting_pack_service.py#L559)
  - [test_meeting_pack_service.py:567](/Users/jangseongjin/paperpipe/tests/test_meeting_pack_service.py#L567)
- rerender-path handoff artifact rewrite assertions:
  - [test_meeting_pack_service.py:587](/Users/jangseongjin/paperpipe/tests/test_meeting_pack_service.py#L587)
  - [test_meeting_pack_service.py:612](/Users/jangseongjin/paperpipe/tests/test_meeting_pack_service.py#L612)

### Exclude from handoff-core patch

- fixture-filtering coverage:
  - [test_meeting_pack_service.py:399](/Users/jangseongjin/paperpipe/tests/test_meeting_pack_service.py#L399)
  - [test_meeting_pack_service.py:471](/Users/jangseongjin/paperpipe/tests/test_meeting_pack_service.py#L471)
- background-only readiness and missing-direct-support coverage:
  - [test_meeting_pack_service.py:665](/Users/jangseongjin/paperpipe/tests/test_meeting_pack_service.py#L665)
  - [test_meeting_pack_service.py:717](/Users/jangseongjin/paperpipe/tests/test_meeting_pack_service.py#L717)
- grounding-metadata uncertainty coverage:
  - [test_meeting_pack_service.py:719](/Users/jangseongjin/paperpipe/tests/test_meeting_pack_service.py#L719)
  - [test_meeting_pack_service.py:742](/Users/jangseongjin/paperpipe/tests/test_meeting_pack_service.py#L742)

### Interpretation

The handoff-core patch should carry only the persistence and continuity assertions.
Readiness-hardening tests are valid work, but they belong to a broader Meeting Pack readiness slice.

## Whole-File Safe Core Still Unchanged

These files can still be staged whole in the smallest handoff-core patch:

- [handoff_artifacts.py](/Users/jangseongjin/paperpipe/src/meeting_packs/handoff_artifacts.py)
- [meeting_pack_handoff.py](/Users/jangseongjin/paperpipe/src/schemas/meeting_pack_handoff.py)
- [store.py](/Users/jangseongjin/paperpipe/src/meeting_packs/store.py)
- [test_meeting_pack_handoff_artifacts.py](/Users/jangseongjin/paperpipe/tests/test_meeting_pack_handoff_artifacts.py)
- [test_meeting_pack_store.py](/Users/jangseongjin/paperpipe/tests/test_meeting_pack_store.py)

## Narrowest Verification Set For The Handoff-Core Patch

If the actual staged patch follows this hunk map, the narrow verification set can be tighter than the broader lane signoff:

```bash
python3 -m pytest \
  /Users/jangseongjin/paperpipe/tests/test_meeting_pack_handoff_artifacts.py \
  /Users/jangseongjin/paperpipe/tests/test_meeting_pack_store.py \
  /Users/jangseongjin/paperpipe/tests/test_meeting_pack_service.py \
  -k 'persists_json_and_markdown or regenerate_meeting_pack_uses_saved_generation_request_and_creates_new_pack or rerender_meeting_pack_rebuilds_markdown_from_saved_json or meeting_pack_handoff or additive_bundle_artifact_json' -q
```

Optional broader confirmation after staging:

```bash
python3 -m pytest \
  /Users/jangseongjin/paperpipe/tests/test_meeting_pack_handoff_artifacts.py \
  /Users/jangseongjin/paperpipe/tests/test_meeting_pack_service.py \
  /Users/jangseongjin/paperpipe/tests/test_meeting_pack_store.py \
  /Users/jangseongjin/paperpipe/tests/test_meeting_pack_api.py \
  /Users/jangseongjin/paperpipe/tests/test_meeting_packs_api.py -q
```

## Short Version

For the smallest handoff-core closure patch:

- stage `handoff_artifacts.py`, `meeting_pack_handoff.py`, `store.py`, `test_meeting_pack_handoff_artifacts.py`, and `test_meeting_pack_store.py` whole
- split `service.py` and `test_meeting_pack_service.py` by the line anchors above
- leave fixture filtering, readiness hardening, and viewer continuity in their own follow-up slice
