# Knowledge Layer Operating Note

Status: Active bounded operating note
Date: 2026-04-08
Owner: Runtime/product maintainers
Canonical: `docs/KNOWLEDGE_LAYER_OPERATING_NOTE.md`
Canonical parents:
- `docs/Lattice_v3_Master_Spec.md`
- `docs/Evidence_and_Uncertainty_Rules.md`
- `docs/PaperPipe_Minimum_Operating_Principles.md`

Related docs:
- `docs/Product_Positioning_Principles.md`
- `docs/MEETING_PACK.md`
- `docs/PROTOCOL_KNOWLEDGE.md`
- `docs/METHOD_COMPARISON.md`
- `docs/reports/Project_Memory_API_Gate_2026-03-23.md`

## Purpose

Define the safest current interpretation of a future PaperPipe/Lattice "knowledge layer" without reopening the product as a generic memory or workspace platform.

This note is for:
- deciding whether a compiled knowledge artifact fits the current repo
- keeping raw sources, canonical structured state, and compiled views separate
- preventing future wiki-style proposals from silently becoming a second source of truth

This note is not:
- a new runtime spec
- an approval to open a broad memory/chat platform lane
- an approval to make `Project Memory` a first-class runtime owner

## Current Judgment

At the current repo stage, a knowledge layer is only safe when it is treated as a **derived, reviewable, file-backed compiled artifact family**.

That means:
- raw source owners stay raw source owners
- canonical scientific/runtime truth stays in current schema-backed structured state and bounded artifact lanes
- compiled knowledge assets may summarize, connect, or compress that truth, but they do not replace it

## 0. Layer taxonomy reference

Current safe layer split:
- raw source layer
  - original PDFs, bibliographic inputs, imported notes, transcripts, and other preserved source-side inputs
- raw memory layer
  - execution logs, work traces, additive activity records, backend-only `Project Memory`, and similar retrieval/support material
- compiled knowledge layer
  - derived, reviewable synthesis pages or bundles that compress or connect current upstream state
- canonical structured state
  - current schema-backed scientific/runtime truth for the active paper/job/artifact runtime
- review/gate layer
  - additive acceptance, quality, eval, or review artifacts that summarize trust/readiness without replacing truth ownership
- user-facing artifact layer
  - reports, packs, note mirrors, exports, and other presentation/handoff outputs

Current rules:
- every new artifact, store, or lane should be classified into one of these layers before implementation
- raw memory may help retrieval, resume, and navigation, but it does not become canonical scientific truth
- review/gate artifacts may summarize readiness or trust, but they do not become the owner of underlying evidence
- if a proposed compiled or memory artifact cannot preserve upstream lineage clearly enough, keep it explicitly draft-like, review-only, or non-canonical

## 1. Ownership stays split

Current safe owner split:
- raw paper/PDF/bibliographic inputs stay source-side owners
- current runtime structured state stays the canonical scientific/runtime owner
- compiled knowledge assets stay downstream derived outputs

Current rule:
- do not treat markdown pages, wiki pages, or compiled summaries as the new owner of scientific truth
- do not let a knowledge layer silently replace `state.json`, saved run artifacts, or bounded lane contracts

## 2. Compiled knowledge stays derived and reviewable

A compiled knowledge asset may:
- summarize repeated findings across current canonical inputs
- provide a human-readable navigation layer across papers, claims, notes, or bounded artifacts
- preserve cross-links, open questions, uncertainties, and reusable context

A compiled knowledge asset must not:
- become a second canonical truth store
- silently overwrite upstream paper/job/artifact truth
- hide missing support, conflict, or freshness gaps behind polished prose

## 3. Biomedical answers must jump back upstream

In this repo, compiled knowledge is not enough by itself for promoted biomedical truth.

Current rule:
- a compiled asset may guide retrieval and framing
- a promoted biomedical answer must still be traceable to upstream claim/evidence/source data
- if the compiled layer lacks upstream support, the output must remain explicitly uncertain or background-only

## 4. Provenance, uncertainty, and freshness stay explicit

A future compiled knowledge asset should preserve, or point back to, at least:
- source references or upstream lineage
- visible uncertainty and conflict notes
- visible freshness or staleness state when relevant
- a clear distinction between evidence-backed synthesis and background/context synthesis

Current rule:
- knowledge-layer convenience must not erase locator quality, missing support, or unresolved grounding
- "compiled" does not mean "verified"

## 4A. Current compiled-knowledge asset contract

The safest currently active compiled-knowledge family is:
- `paper_synthesis`

For the current runtime, a compiled-knowledge asset should carry explicit machine-readable metadata such as:
- `artifact_family`
- `template_kind`
- `layer=compiled_knowledge`
- `canonical_status=non_canonical`
- `source_refs`
- `warnings`
- `uncertainty_notes`
- freshness/readiness summary fields

Current backlink rule:
- every compiled asset must point back to the minimum upstream lineage needed to reopen trust:
  - canonical structured state
  - selected run metadata
  - selected resolved claim/evidence artifact
- optional review/gate artifacts may be attached as additive refs, but they stay secondary

Current rendering rule:
- if a compiled markdown file is emitted, keep the layer/canonical/provenance summary visible in the file itself rather than only in hidden app state

## 4B. Safe template scope right now

Current safe template vocabulary for compiled knowledge:
- `paper`
- `project`
- `meeting`
- `decision`
- `concept`

Current approval boundary:
- only `paper` is an active runtime-safe compiled-knowledge target today
- `project`, `meeting`, `decision`, and `concept` may exist as naming conventions or future templates, but they are not approved as new canonical owners or new runtime artifact families yet
- do not claim those additional template kinds are already first-class supported product lanes unless the runtime actually lands them

## 5. Automation may maintain, but not silently promote

The repo may later automate parts of:
- extraction into compiled pages
- cross-link maintenance
- refresh or rerender of compiled knowledge bundles

But the current safe posture remains:
- automatic generation is draft-like by default
- important promotion points stay explicit and reviewable
- bounded independent review or lane-owned operator review is preferred over silent auto-promotion

## 6. Safe first target

If this repo adopts a knowledge layer later, the safest first target is:
- paper-reading synthesis derived from existing paper-scoped canonical state and run artifacts

Not yet safe as the initial target:
- a generalized project memory platform
- meeting-note truth that overrides upstream paper evidence
- protocol execution semantics
- broad chat memory as a canonical owner

## 7. What this note deliberately does not adopt

This note does not adopt:
- a generalized wiki as the product's new source of truth
- a repo-wide compiled memory layer above current canonical structured state
- broad semantic memory/chat retrieval as a new runtime owner
- autonomous maintenance loops that rewrite runtime truth or code without bounded review
- `Project Memory` API or viewer expansion by implication

## Conclusion

The safest current PaperPipe/Lattice knowledge layer is:
- derived, not canonical
- file-backed, not hidden
- evidence-aware, not source-substituting
- reviewable, not silently promoted

That keeps future compiled knowledge work aligned with the repo's current biomedical, local-first, provenance-first runtime shape.
