# Research DNA Web Viewer Gate (2026-03-28)

Status: Active
Date: 2026-03-28
Owner: Lattice runtime maintainers
Canonical parent: `docs/RESEARCH_DNA.md`

## Purpose

Record whether `Research DNA` should move from the current API/CLI-first operator lane into a dedicated web viewer route now.

This is a product-shape decision note, not a new runtime spec.

## Current implemented state

Implemented today:
- FastAPI endpoints in `backend/main.py` for:
  - create
  - get
  - update
  - interview
  - approve-pilot
  - pilot
  - screening
  - refine
  - lock
  - unlock
  - project-profile
- CLI wrappers under `paperpipe research-dna ...`
- canonical spec in `docs/RESEARCH_DNA.md`
- explicit current-boundary notes in:
  - `README.md`
  - `docs/WEB_VIEWER.md`
  - `docs/Product_Positioning_Principles.md`
  - `docs/reports/First_Shippable_Product_Bar_2026-03-24.md`
  - `docs/reports/First_Product_Baseline_QA_2026-03-25.md`

Not implemented today:
- no frontend route in `frontend/src/App.tsx`
- no dedicated `/ui/research-dna` list or detail surface
- no bounded read-first inspection shell for DNA intent, status, query versions, pilot outcomes, or screening history

## Decision

Do not open a dedicated `Research DNA` web viewer yet.

Keep `Research DNA` as an API/CLI-first operator lane in the current product stage.

If it becomes web-visible later, it should start as a narrow read-first inspection surface rather than a broad creation, interview, pilot, screening, or refinement workflow.

## Why the web viewer should stay closed for now

### 1. The current first-product value is elsewhere

The current user-facing product has only recently become honest and repeatable around:
- `papers`
- workbench
- runtime readiness
- bounded artifact creation lanes such as `Meeting Pack`, `Method Comparison`, and `Chart Pack`

That is the clearest current product story for first-time users.

Opening a `Research DNA` viewer now would introduce another surface before the current paper-first flow has fully settled.

### 2. The implemented lane is lifecycle-heavy, not inspection-first

Current `Research DNA` implementation is not just a saved object viewer.

It already owns:
- multi-step state transitions
- interview logs
- pilot runs
- screening decisions
- query refinement
- lock and unlock transitions
- projected profile materialization

A web viewer would therefore imply a much broader product promise than a simple read-only card list.

### 3. A thin read-first boundary is not yet product-defined

There is still no approved answer for:
- where a user would enter the lane from the current web product
- what the minimal read model should show first
- whether the viewer is paper-adjacent, operator-adjacent, or search-program-adjacent
- how projected profiles should be explained without exposing the full operator workflow

Until that is defined, opening a route would create confusion faster than value.

### 4. A premature viewer would look like a hidden operator console

Current product risk is not that `Research DNA` is absent from the web.

The bigger risk is that a premature viewer would:
- surface an operator-heavy object without a clear first-session payoff
- invite users into a lifecycle they cannot finish comfortably in the current UI
- reintroduce the same “implemented but not truly productized” trust problem the repo has been actively reducing

## What is safe to do now

Safe now:
- keep the current API/CLI-first lane
- keep the current explicit boundary language in onboarding and runtime docs
- use `Research DNA` in operator workflows and bounded demos where that lane is relevant
- collect concrete evidence of repeated browser-based inspection demand

Not safe yet:
- adding `/ui/research-dna`
- adding a `Research DNA` tile to the primary navigation
- building a broad wizard for create/interview/pilot/screening/refine
- implying that `Research DNA` is already part of the main self-serve web journey

## Reopen conditions

Revisit the web viewer only if at least one of these becomes true:

1. repeated demos or operator workflows need browser-based read-only inspection of DNA state
2. there is a clear entry path from the current paper/workbench/artifact flow
3. the minimal read-first payload is agreed:
   - intent
   - status
   - latest query version
   - most recent pilot outcome
   - screening summary
   - projection status
4. the team explicitly wants a bounded search-design surface in the main web product

## Recommended next move

Do not implement a `Research DNA` viewer now.

Preferred next move:
- continue productizing currently visible workflow lanes
- reopen `Research DNA` only with a follow-up RFC for a narrow read-first detail view
- if reopened later, start with a known-`dna_id` detail page, not a full list/create/edit flow

## Conclusion

`Research DNA` is real, important, and implemented.

It is not yet a good fit for the current main web product surface.

Holding the lane at API/CLI-first is the more honest and lower-regret product decision for this stage.
