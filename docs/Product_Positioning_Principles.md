# Product Positioning and Principles

Status: Active positioning note  
Date: 2026-03-24  
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

Lattice is a local-first, paper-centered biomedical research workspace built around evidence-linked outputs and reproducible operator-visible workflows.

It is designed to help a researcher move from:
- source paper
- to structured claims and checks
- to reusable note state
- to downstream artifacts such as search-design assets and meeting drafts

without losing evidence lineage or hiding uncertainty.

Natural language may operate the workspace, but schema-backed structured state remains the source of truth.
Answers, notes, and downstream drafts are derived outputs, not canonical truth by themselves.

## Core Assertions

When future prompts, review notes, or proposals pull in different directions, these assertions should win unless an explicit product-shape decision replaces them.

- Lattice is a local-first, paper-centered biomedical research workspace.
- The current runtime and first-product story are paper-first and single-operator-first.
- Natural language is interface; schema-backed structured state is source of truth.
- Source data, canonical structured state, and derived outputs stay separate.
- Derived artifacts and bounded bundles are not second canonical truth stores.
- Provenance and uncertainty are mandatory parts of product trust, not optional metadata.
- External systems and file formats are adapters or ports, not the canonical owner of current runtime truth.
- AI or automation may draft quickly, but trusted state must stay distinguishable from reviewed, verified, or approved state.
- First-class `Project`, broad memory/chat, and generalized workspace/platform lanes remain future-only until explicitly adopted.

## Who it is for

Current best-fit users:
- individual researchers
- operator-style scientific readers
- small lab or project contexts that need evidence-linked paper understanding

Current best-fit usage shape:
- paper-first
- local-first
- single-operator-first
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
- In practice, local-first means data ownership, recovery, portability, offline survivability, and limited dependence on external providers.

### 2. Natural language is interface, structured state is source of truth

- Operators may use language, notes, uploads, and bounded automation to drive the product.
- Canonical truth should still live in schema-backed structured state, not in free-form answers, summaries, or chat-like surfaces.
- Derived outputs may explain, mirror, or package the truth, but they must not silently replace it.

### 3. Evidence-linked outputs

- Scientific outputs should stay connected to evidence and locators whenever the runtime has them.
- Downstream artifacts should reuse existing claim/evidence identity rather than inventing detached truth.
- When the runtime externalizes understanding into notes, packs, charts, or protocol-oriented artifacts, the result should keep source, canonical-state, or generating-run lineage rather than becoming a detached truth store.

### 4. Uncertainty should stay visible

- Weak support, missing location, conflict, or ambiguity should be surfaced rather than normalized away.
- Presentation quality must not come from pretending the evidence is cleaner than it is.

### 5. Non-destructive automation

- Jobs, generated artifacts, and draft outputs should prefer additive writes, rerenderability, or explicit rollback-safe behavior.
- Automation should reduce work without quietly destroying operator context.
- The product should allow fast offloading into drafts and bounded artifacts, but trust should rise more slowly through explicit review, approval, or verification signals.
- AI- or automation-authored draft state must remain distinguishable from reviewed, user-verified, or otherwise human-approved state.

### 6. Visible system truth over narrated demos

- A product-ready flow should expose the real saved state, provenance, and runtime boundaries directly enough that an operator can inspect them.
- A demo does not count as readiness if it depends on someone verbally patching over hidden storage, missing provenance, or manual reconstruction steps.

### 7. Bounded subsystems over platform sprawl

- New ideas should start as bounded layers that fit the current paper/job/artifact architecture.
- Do not redefine the whole product around a new top-level model unless there is an explicit product-shape decision.

### 8. Separation of reasoning, context, and presentation

- Reasoning persona, profile context, and output/view mode are different concerns.
- Different audiences or deliverables should not automatically create separate agents or truth policies.

## Current exposure boundary note

`Research DNA` is part of the active product shape, but its current operator-facing surface is API/CLI-first rather than web-viewer-first.

That means:
- `Research DNA` remains part of the core paper-first story
- current main web viewer routes do not yet include a dedicated `Research DNA` viewer
- current frontend absence should be described as an intentional product-boundary choice for this stage, not as hidden or missing truth
- if `Research DNA` becomes web-visible later, it should start as a bounded read-first surface rather than a broad workflow wizard

## Current product shape

As of 2026-03-24, the live product shape is best described as:
- `papers`
- deep-read `jobs`
- run `artifacts`
- Obsidian note state and mirror
- bounded `Research DNA`
- bounded `Meeting Pack`

This is the active core product reality.

Current exposure note:
- `papers`, workbench, and bounded artifact viewers are today’s primary web surfaces
- `Research DNA` is currently a real core lane with API/CLI/operator workflows, but not yet a first-class web viewer route

Current bounded extensions also exist and are real:
- `Method Comparison`
- `Chart Pack`
- `Protocol Knowledge`
- `Image Evidence`

These are active bounded artifact families, but they are not the first-product identity by themselves.
They should be presented as secondary extensions to the paper-first core loop, not as evidence that the product has already become a generalized workspace platform.

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
