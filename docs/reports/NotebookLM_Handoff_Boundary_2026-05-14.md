# NotebookLM Handoff Boundary

Status: Active product-boundary decision
Date: 2026-05-14
Owner: Runtime/product maintainers
Canonical parent: `docs/Product_Positioning_Principles.md`

## Decision

NotebookLM handoff is no longer a core product assumption for Lattice/PaperPipe.

The current recommended product stance is:

- Lattice owns the paper-centered review loop directly.
- NotebookLM-style workflows may remain optional export destinations or compatibility adapters.
- NotebookLM should not be described as the intended next step after a successful paper run.
- Any future NotebookLM support should export from canonical structured state or source-backed bundles rather than becoming a new truth owner.

## Rationale

Early PaperPipe planning treated the system as a pipeline that prepared research material for external tools, including Obsidian, Zotero, and NotebookLM upload folders.

The current runtime has moved beyond that handoff shape. Lattice now directly owns:

- paper ingestion and deep-read jobs
- schema-backed paper state
- evidence-linked review surfaces
- workbench inspection
- bounded downstream artifacts such as Research DNA and Meeting Pack

Because those capabilities are now implemented inside the product, NotebookLM is best treated as an external port rather than a product destination.

## Current Boundary

Core:

- ingest a paper
- preserve source and evidence lineage
- generate schema-backed structured state
- inspect and correct the result in Lattice surfaces
- produce bounded downstream artifacts without silent truth-store replacement

Optional adapter:

- export a source-backed bundle for use in NotebookLM or a similar external tool
- keep the export clearly downstream from Lattice canonical state
- avoid implying that external upload is required for the product to be useful

Out of scope for the current first-product promise:

- NotebookLM as the main reading surface
- NotebookLM as the canonical source of paper interpretation
- NotebookLM upload folders as a required runtime path
- a chat-first product shape justified by NotebookLM parity

## Documentation Implication

Historical archive docs may keep NotebookLM references as evidence of the older pipeline design.

Active product docs should use language such as:

- "optional export adapter"
- "external compatibility destination"
- "source-backed export bundle"

Active product docs should avoid language such as:

- "handoff to NotebookLM"
- "prepare for NotebookLM as the next step"
- "NotebookLM upload folder" unless documenting a legacy fixture or explicit export adapter

## Smallest Follow-Up

1. Keep this decision linked from active product-positioning docs once they are present on the target branch.
2. When touching active docs, replace core-flow NotebookLM wording with optional export-adapter wording.
3. If active runtime code still uses `NotebookLM_Upload`, classify it as legacy fixture, compatibility export, or rename it behind a generic export path in a separate bounded change.
