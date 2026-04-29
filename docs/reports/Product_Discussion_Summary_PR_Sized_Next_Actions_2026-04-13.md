# Product Discussion Summary PR-Sized Next Actions

Status: active execution note
Date: 2026-04-13
Owner: Runtime/product maintainers
Inputs:
- `docs/reports/PaperPipe_Product_Discussion_Summary_Fit_Review_2026-04-13.md`
- `docs/reports/Lattice_Current_Safe_Product_Summary_2026-04-13.md`

Canonical parents:
- `docs/Product_Positioning_Principles.md`
- `docs/Lattice_v3_Master_Spec.md`
- `docs/PaperPipe_Minimum_Operating_Principles.md`

## Purpose

Convert the discussion-summary review into a few bounded next actions that fit the current repo.

This note is not:
- a roadmap rewrite
- permission to widen the product into a project/workspace platform
- permission to promote `Project Memory` or `/api/chat` into active product surfaces

## Current judgment

The external summary does not call for architecture work right now.

The highest-value next steps are smaller:
- current-safe wording
- clearer day-one guidance on the existing paper-first shell
- stronger boundary visibility before any project-context or memory-like surface expands

## Action order

### 1. Docs-only messaging anchor

Title:
- `docs: adopt current-safe product summary as the reuse anchor`

Why this first:
- the repo already has most of the right runtime boundary docs
- the external summary mainly creates messaging pressure, not a missing subsystem
- a current-safe wording anchor lowers the chance of future project/workspace overclaim

Smallest safe scope:
- use `docs/reports/Lattice_Current_Safe_Product_Summary_2026-04-13.md` as the reference for future product-facing wording
- update only docs or demo materials that still risk implying:
  - project dashboard
  - generalized research operating system
  - memory-first product

Likely files:
- `README.md`
- `docs/README.md`
- active demo/runbook docs when touched

Verification:
- `python3 scripts/lint_docs.py`

Do not:
- rewrite canonical runtime docs around new product abstractions
- introduce new schema or API concepts just to match wording

### 2. Beginner-first paper shell copy cleanup

Title:
- `frontend: tighten triage-shell day-one guidance around the paper-first loop`

Why this next:
- the external summary's strongest product-side insight is beginner clarity
- the current triage shell already has the right basic route structure
- the likely win is copy and emphasis, not a new information architecture

Smallest safe scope:
- refine the current home/triage wording so the first action reads as:
  - bring in a paper
  - inspect saved state
  - continue evidence review
- keep navigation and route truth aligned with the current paper-first shell

Likely files:
- `frontend/src/app/pages/TriageDashboard.tsx`
- `frontend/src/App.tsx`
- matching UX review artifact(s)

Verification:
- required UX review artifact update before implementation
- `cd frontend && npm run build`
- if the touched surface already has browser coverage, run the relevant frontend verification path too

Do not:
- imply a first-class project dashboard
- add new top-level project routes
- expose provider setup, prompt editing, or debug surfaces as the main first-run story

### 3. Boundary-first project-context wording before any surface growth

Title:
- `docs/backend: freeze project-context capture as support-only before any viewer/API widening`

Why this belongs third:
- the repo now has real project-context capture primitives
- those primitives are useful as supervision and support context
- they become dangerous only if product messaging outruns their non-canonical boundary

Smallest safe scope:
- keep any project-context wording explicitly tied to:
  - `raw_memory`
  - `non_canonical`
  - support-only relevance capture
- if a future API/viewer proposal appears, land boundary wording first before UI or route growth

Likely files:
- `src/schemas/project_memory.py`
- `src/schemas/project_context_link.py`
- `backend/routers/project_context_links.py`
- `docs/reports/Project_Memory_API_Gate_2026-03-23.md`
- `docs/PaperPipe_Minimum_Operating_Principles.md`

Verification:
- docs lint for docs changes
- targeted tests only if schema/route behavior changes

Do not:
- open `/projects` routes
- imply a first-class project owner
- let support-only context capture become stronger truth than paper-side canonical state

## Recommended default

If only one action is taken now, do action 1.

Reason:
- it has the lowest risk
- it reduces future wording drift
- it helps every later discussion stay consistent with the current runtime

If one product-facing UI slice is worth doing after that, do action 2.

Reason:
- it captures the most useful beginner-facing insight from the external summary without changing runtime ownership

Action 3 should remain boundary-first and defensive.
It is mainly there to prevent future scope leakage.

## Not next

Do not treat the discussion summary as a reason to:
- open a first-class `Project` lane
- build a broad memory/chat surface
- add canonical `Decision`, `Open Question`, or `Next Action` families
- introduce account-link or provider-marketplace UX
- describe the current repo as a generalized research operating system

## Bottom line

The external summary is most useful when turned into:
- safer product wording
- clearer beginner guidance on the current paper-first shell
- stronger guardrails around support-only context capture

The next PRs should stay that small.
