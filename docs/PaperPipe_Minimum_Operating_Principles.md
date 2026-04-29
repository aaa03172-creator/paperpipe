# PaperPipe Minimum Operating Principles

Status: Active operating note
Date: 2026-04-08
Owner: Runtime/product maintainers
Canonical: `docs/PaperPipe_Minimum_Operating_Principles.md`

Related docs:
- `docs/Lattice_v3_Master_Spec.md`
- `docs/Product_Positioning_Principles.md`
- `docs/working-files.md`
- `docs/reports/First_Shippable_Product_Bar_2026-03-24.md`
- `docs/reports/Project_Memory_API_Gate_2026-03-23.md`

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

## 1A. Raw memory stays support-only and non-canonical

- Activity logs, execution traces, working files, backend-only `Project Memory`, and future conversation-like memory may help retrieval, resume, and operator context.
- Those layers must not silently outrank current canonical structured state or upstream source/evidence lineage.
- A promoted biomedical answer may use raw memory as navigation help, but not as its sole truth source.

Current anchors:
- `src/services/event_log.py`
- `docs/reports/Project_Memory_API_Gate_2026-03-23.md`
- `docs/API_CHAT_CONTRACT.md`

## 1B. Promoted answers stay canonical-state and evidence-routed

- When PaperPipe presents a biomedical answer as evidence-backed, the safest current route is:
  - canonical structured state first
  - upstream claim/evidence/source lineage second
  - additive review/gate or compiled artifacts only as support inputs
- Compiled knowledge pages, method comparisons, meeting packs, review gates, and raw-memory helpers may guide retrieval, selection, framing, or wording.
- Those surfaces must not become stronger truth owners than current evidence-linked structured state.
- If a future answer surface cannot recover a clear canonical/evidence path, it should stay explicitly background-only, draft-like, or uncertain instead of sounding fully grounded.

Current anchors:
- `docs/Evidence_and_Uncertainty_Rules.md`
- `docs/KNOWLEDGE_LAYER_OPERATING_NOTE.md`
- `docs/API_CHAT_CONTRACT.md`

## 1C. Compiled knowledge stays explicitly non-canonical

- Compiled knowledge artifacts should carry explicit layer and boundary metadata rather than relying on prose alone.
- The minimum current contract is:
  - `artifact_family`
  - `template_kind`
  - `layer=compiled_knowledge`
  - `canonical_status=non_canonical`
  - source refs back to canonical structured state plus selected run artifacts
- If markdown is emitted for a compiled asset, keep those boundary cues in the file itself so the artifact stays reviewable outside the app shell.
- Safe current runtime target: paper-scoped compiled synthesis.
- Not yet approved as first-class runtime families: project, meeting, decision, or concept compiled notes.

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

## 8. Long-running work should use lightweight contracts and additive review artifacts

- Long multi-step work should externalize the smallest executable contract instead of relying on chat/session continuity.
- The useful minimum is:
  - current scope
  - expected outputs or artifacts
  - verification method
  - hard fail conditions
- Handoff and review artifacts should stay additive and subordinate to existing canonical owners.
- Independent review is useful when it clarifies whether a bounded change really meets its contract, but it should stay proportional to the size and risk of the change.
- Prefer the smallest relevant verification for the touched surface rather than forcing one heavyweight universal protocol across all lanes.

Current anchors:
- `docs/working-files.md`
- `docs/INDEPENDENT_REVIEW_TEMPLATE.md`
- `backend/services/job_runner.py`
- `src/services/deepread_handoff_artifacts.py`
- `docs/reports/Launch_Readiness_Checklist_2026-03-24.md`

## What This Note Deliberately Does Not Adopt

This note does not adopt the following as current PaperPipe minimum runtime requirements:

- `project_id` as a universal common field
- a generic `object_type` model across all current entities
- universal `lifecycle_state` and `approval_state`
- a top-level `next_action` object family
- a universal 4-state UI model applied across all lanes
- a broad `claim/evidence/artifact` registry detached from current canonical structured state
- a generalized compiled wiki or memory layer treated as a new source of truth above current canonical state
- raw-memory retrieval treated as a stronger owner than canonical evidence-linked state
- a repo-wide planner/generator/evaluator orchestration framework
- autonomous maintenance loops that silently rewrite runtime truth, notes, or code without bounded review
- a mandatory worker/validator protocol for every small task
- universal binary `PASS/FAIL` review semantics for every lane and every note

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
- lightweight contracts and additive review artifacts for long-running work, without a heavy universal protocol

That gives PaperPipe a conservative operating posture without forcing the repo into a premature generic platform architecture.
