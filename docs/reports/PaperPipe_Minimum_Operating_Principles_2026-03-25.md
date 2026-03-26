Status: Active bounded operating note
Date: 2026-03-25
Owner: Runtime/product maintainers
Canonical parents:
- `docs/Lattice_v3_Master_Spec.md`
- `docs/Product_Positioning_Principles.md`
- `docs/reports/First_Shippable_Product_Bar_2026-03-24.md`
- `docs/reports/Project_Memory_API_Gate_2026-03-23.md`

# PaperPipe Minimum Operating Principles

## Purpose

Capture only the smallest operating guardrails that fit the current PaperPipe/Lattice runtime shape.

This note exists to reject premature generic platform modeling, not to define a second runtime spec.

This note is:
- a bounded operating note
- a translation of useful governance principles into current PaperPipe terms
- subordinate to `docs/Lattice_v3_Master_Spec.md`

This note is not:
- a new master spec
- a DB contract
- a generic entity/object schema proposal

For runtime truth, keep using:
- `docs/Lattice_v3_Master_Spec.md`
- `docs/WEB_VIEWER.md`
- the current schema and bounded-lane docs

## Current Product Boundary

Current PaperPipe remains:
- paper-first
- artifact-first
- local-first
- single-operator-first
- evidence-linked
- reviewable by a human operator

Current PaperPipe is not yet:
- a first-class project/workspace platform
- a generic object registry
- a broad approval workflow engine

So the current minimum operating model should stay close to:
- papers
- jobs/runs/artifacts
- paper-scoped canonical structured state
- bounded downstream lanes such as `Research DNA` and `Meeting Pack`

## Minimum Operating Principles

## 1. Canonical truth stays schema-backed and paper/job/artifact-scoped

- Canonical truth should remain schema-backed structured state, not free-form notes or downstream summaries.
- Paper-backed state, job/run artifacts, and downstream artifacts should stay distinct.
- Do not introduce a generic `object_type + lifecycle_state + approval_state` layer as the current minimum runtime model.

Current anchors:
- `src/schemas/skills.py::StructuredPaperState`
- `docs/WEB_VIEWER.md`
- `docs/reports/First_Shippable_Product_Bar_2026-03-24.md`

## 2. Generated outputs default to draft-like state

- AI- or automation-produced outputs should never silently become reviewed truth.
- Trust rises more slowly than generation speed.
- Drafts may be useful immediately, but they must remain distinguishable from reviewed, approved, or validated state.

Current anchors:
- `docs/Product_Positioning_Principles.md`
- `docs/Evidence_and_Uncertainty_Rules.md`
- `docs/MEETING_PACK.md`

## 3. Approval and promotion stay few, explicit, and lane-owned

- Do not add broad approval gates everywhere.
- Keep approval or promotion only where the current repo already has a real operator decision surface and lane-owned lifecycle.

Current safe examples:
- `Research DNA` screening and promotion decisions within the existing `DRAFT -> PILOT -> LOCKED` flow
- downstream artifact finalization or release-style actions where the lane already has bounded lifecycle semantics
- explicit replacement or promotion moments only where the lane already owns canonical state

Do not assume a generic current approval workflow for:
- every claim
- every evidence item
- every artifact family

Current anchors:
- `docs/RESEARCH_DNA.md`
- `docs/MEETING_PACK.md`
- `docs/reports/Launch_Readiness_Checklist_2026-03-24.md`

## 4. Provenance and activity logging should be automatic

- Upload, ingest, extract, generate, rerender, regenerate, verify, and approval-like actions should prefer automatic event/activity recording.
- Operators should not be asked to manually enter provenance structure, relation types, or lineage metadata as part of normal work.
- Provenance should exist even when the default UI keeps it folded.

Current anchors:
- `docs/Event_Logging_Audit_2026-03-13.md`
- `docs/Product_Positioning_Principles.md`
- `docs/WEB_VIEWER.md`

## 5. Regeneration should be additive or guarded

- Reruns, rerenders, and regenerations should favor additive or guarded writes.
- Existing trusted state should not be silently clobbered by a weaker or unrelated source.
- Legacy fallback behavior should stay bounded and explicit.

Current anchors:
- `docs/MEETING_PACK.md`
- `docs/reports/Deep_Read_Note_State_Promotion_Design_2026-03-24.md`

## 6. Lane-specific states stay lane-specific

- Do not flatten all UI/runtime status into one small global set.
- Some lane-specific states are part of product trust and should remain explicit.

Examples already present in the repo:
- `Research DNA`: `DRAFT`, `PILOT`, `LOCKED`
- paper ops: `healthy`, `action_needed`
- `Meeting Pack`: `readiness`, `in_sync`, `drifted`, regenerate availability

Use shared language sparingly:
- draft-like
- review-needed
- blocked
- stale

But treat those as presentation vocabulary, not as a new global runtime state machine.

Current anchors:
- `docs/RESEARCH_DNA.md`
- `docs/MEETING_PACK.md`
- `src/schemas/paper_notes.py`

## 7. Minimal operator burden beats universal modeling

- Users should not be forced to manage relation types, trigger types, provenance edges, or ontology categories directly.
- If a structure is needed, it should usually be derived from existing runtime context.
- A smaller operator workload is preferable to a theoretically elegant but overly generic internal model.

## What This Note Deliberately Does Not Adopt

This note does not adopt the following as current PaperPipe minimum runtime requirements:

- `project_id` as a universal common field
- a generic `object_type` model across all current entities
- universal `lifecycle_state` and `approval_state`
- a top-level `next_action` object family
- a universal 4-state UI model applied across all lanes
- a broad `claim/evidence/artifact` registry detached from current canonical structured state

Those may become future RFC material, but they are not the safest description of the current system.

## Safest Use Of This Note

Use this note when:
- evaluating future governance or workflow proposals
- checking whether a new lane is introducing too much generic control structure
- deciding whether a proposed approval/status/provenance feature fits current PaperPipe shape

Do not use this note to:
- redefine the current runtime schema
- backdoor a project/workspace platform model
- replace the current lane-specific contracts

## Conclusion

The current PaperPipe minimum operating model should stay guardrail-first, not object-model-first.

The safest minimum is:
- paper-first boundaries
- paper/job/artifact-scoped canonical state
- AI outputs default draft
- automatic provenance/activity logging
- few approval or promotion points tied to real lanes
- additive or guarded rerun/regenerate behavior
- lane-specific state models kept intact

That gives PaperPipe a conservative operating posture without forcing the repo into a premature generic platform architecture.
