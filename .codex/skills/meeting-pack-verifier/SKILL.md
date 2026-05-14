---
name: meeting-pack-verifier
description: Developer-only workflow skill for verifying Meeting Pack source selection, bundle readiness, trace visibility, and regenerateability against the current canonical contract.
---

# Meeting Pack Verifier

## Overview

Use this skill when reviewing, debugging, or hardening the current Meeting Pack runtime.
It wraps repeatable verification work around the existing canonical contract in `docs/MEETING_PACK.md`.

This is a developer workflow helper only.
It does not create a product runtime feature by folder presence alone.

## Trigger conditions

Use this skill when:
- a Meeting Pack output looks suspicious or under-specified
- you need to verify whether a saved pack is evidence-backed, trace-visible, and regenerateable
- you are reviewing a Meeting Pack code change and need a bounded verification path
- you need to compare bundle-local metadata against current runtime behavior

Do not use this skill to redefine Meeting Pack schema, storage shape, or readiness semantics.

## Inputs and expected context

Gather or infer:
- `pack_id`
- the saved bundle path under `storage/meeting_packs/<pack_id>/`
- the expected mode or output family
- whether the task is code review, runtime diagnosis, or verification signoff

Useful supporting surfaces:
- `docs/MEETING_PACK.md`
- `backend/routers/meeting_packs.py`
- `src/meeting_packs/service.py`
- `src/meeting_packs/store.py`
- `GET /meeting-packs/{pack_id}`
- `GET /meeting-packs/{pack_id}/trace`
- `GET /meeting-packs/{pack_id}/validate`

## Output contract

Return:
1. `Bundle status`
2. `Canonical input check`
3. `Trace and regenerateability check`
4. `Mismatch or risk`
5. `Smallest follow-up`

If useful, use the bundled template in `templates/meeting-pack-review-note.md`.

## Workflow

1. Confirm the current contract.
   Read the relevant sections of `docs/MEETING_PACK.md` before making claims about what a pack should do.
2. Check bundle-local artifacts.
   Inspect `meeting_pack.json`, `meeting_pack.md`, and any additive metadata such as `acceptance_contract.json` or `quality_gate.json`.
3. Verify canonical input ownership.
   Confirm that the pack is still a derived artifact over canonical paper state, Research DNA, or explicitly named source artifacts rather than a second truth store.
4. Verify operator-facing readiness.
   Check `trace`, `validate`, regenerateability, and readiness wording against the current runtime.
5. Report bounded findings.
   Prefer a small follow-up tied to source selection, trace visibility, regenerateability, or wording drift.

## Bundled resource map

- `references/verification-checklist.md`
- `templates/meeting-pack-review-note.md`

## Guardrails and non-goals

- Do not rewrite Meeting Pack architecture as a first move.
- Do not treat trace metadata as scientific truth.
- Do not let skill-local notes become the canonical source of pack readiness.
- Do not widen scope into generic planner/evaluator orchestration.

## Verification or handoff expectations

When closing the task, separate:
- what was inspected directly
- what was inferred from code or docs
- what remains unverified
- the smallest safe next patch if a change is needed
