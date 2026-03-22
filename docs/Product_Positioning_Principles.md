# Product Positioning and Principles

Status: Active positioning note  
Date: 2026-03-18  
Owner: Runtime/design maintainers  
Canonical: `docs/Product_Positioning_Principles.md`

Related docs:
- `docs/Lattice_v3_Master_Spec.md`
- `docs/PERSONA_MODE_BOUNDARY.md`
- `docs/Evidence_and_Uncertainty_Rules.md`
- `docs/RESEARCH_DNA.md`
- `docs/MEETING_PACK.md`
- `docs/archive/Agent_Proposal_Fit_Review_2026-03-18.md`
- `docs/archive/Proposal_to_Lattice_Mapping_2026-03-18.md`

## Purpose

This document separates product positioning from runtime contract.

Use this doc for:
- why the product exists
- who it is for
- what hidden costs it removes
- which product principles should stay stable even as runtime contracts evolve

Do not use this doc as:
- the API contract
- the DB contract
- the canonical source for schema or route details

For runtime truth, use `docs/Lattice_v3_Master_Spec.md` and the bounded spec family listed in `docs/README.md`.

## Product statement

Lattice is a local-first biomedical research workspace centered on papers, evidence-linked outputs, and reproducible operator-visible workflows.

It is designed to help a researcher move from:
- source paper
- to structured claims and checks
- to reusable note state
- to downstream artifacts such as search-design assets and meeting drafts

without losing evidence lineage or hiding uncertainty.

## Who it is for

Current best-fit users:
- individual researchers
- operator-style scientific readers
- small lab or project contexts that need evidence-linked paper understanding

Current best-fit usage shape:
- paper-first
- local-first
- reviewable by a human operator
- additive rather than fully autonomous

## Hidden costs this product is meant to reduce

- repeated manual paper re-reading because prior judgments were not preserved in reusable form
- evidence getting separated from summary, claim, or draft output
- uncertainty being flattened away when a paper is turned into notes or presentation material
- repeated reformatting work between PDF, note, search-design, and meeting-prep surfaces
- brittle one-off automation that cannot be inspected or rerun safely

## Core product principles

### 1. Local-first by default

- The system should preserve a useful local operating mode.
- File-backed artifacts, notes, and bounded assets are a feature, not an implementation accident.
- Cloud or remote expansion may exist later, but it should not erase local inspectability and recovery.

### 2. Evidence-linked outputs

- Scientific outputs should stay connected to evidence and locators whenever the runtime has them.
- Downstream artifacts should reuse existing claim/evidence identity rather than inventing detached truth.

### 3. Uncertainty should stay visible

- Weak support, missing location, conflict, or ambiguity should be surfaced rather than normalized away.
- Presentation quality must not come from pretending the evidence is cleaner than it is.

### 4. Non-destructive automation

- Jobs, generated artifacts, and draft outputs should prefer additive writes, rerenderability, or explicit rollback-safe behavior.
- Automation should reduce work without quietly destroying operator context.

### 5. Bounded subsystems over platform sprawl

- New ideas should start as bounded layers that fit the current paper/job/artifact architecture.
- Do not redefine the whole product around a new top-level model unless there is an explicit product-shape decision.

### 6. Separation of reasoning, context, and presentation

- Reasoning persona, profile context, and output/view mode are different concerns.
- Different audiences or deliverables should not automatically create separate agents or truth policies.

## Current product shape

As of 2026-03-18, the live product shape is best described as:
- `papers`
- deep-read `jobs`
- run `artifacts`
- Obsidian note state and mirror
- bounded `Research DNA`
- bounded `Meeting Pack`

This is the active product reality.

## Explicit non-positioning traps

The product should not currently be described as:
- a generic `projects/documents` research platform
- a first-class protocol database
- a multi-user collaboration suite
- a broad workspace memory platform
- a system where output mode changes evidence truth

Those may become future product decisions, but they are not the current canonical positioning.

## How to use external proposal material

External proposal docs from the 2026-03-18 review are useful as:
- product-framing input
- future bounded RFC source material
- a source of pressure toward clearer local-first, evidence, and uncertainty language

They should not be treated as a drop-in replacement for the current runtime contract.

## Relationship to the runtime spec

- `docs/Product_Positioning_Principles.md` answers `why this product exists and what should remain true at the product level`.
- `docs/Lattice_v3_Master_Spec.md` answers `how the current runtime is actually structured`.

Both should remain aligned, but they should not be collapsed into one document again.
