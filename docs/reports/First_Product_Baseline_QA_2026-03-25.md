# First Product Baseline Q&A

Status: Active handoff note
Date: 2026-03-25
Owner: Lattice runtime maintainers
Purpose: answer the recurring baseline questions for the current first shipped/demo-ready product slice without reopening broader platform or future-lane assumptions.
Canonical parent: `docs/Product_Positioning_Principles.md`, `docs/Lattice_v3_Master_Spec.md`

## 1. What is the product identity, exactly?

Lattice's current first-product identity is:

> a local-first, paper-centered, paper-first, single-operator-first biomedical research workspace built around evidence-linked outputs and reproducible operator-visible workflows.

What that means in practice:

- the product story starts from papers, not from a generic `Project` shell
- the product is not chat-first, copilot-first, or memory-first
- the product is not a general knowledge-management or collaboration platform
- the product promise is evidence-linked, inspectable research work, not polished autonomous narration

Current anchors:

- `docs/Product_Positioning_Principles.md`
- `docs/reports/First_Shippable_Product_Bar_2026-03-24.md`
- `docs/Lattice_v3_Master_Spec.md`

## 2. What is the source of truth, and what are LLM outputs?

The source of truth is schema-backed structured state owned by the Lattice runtime.

Current canonical truth roots:

- `StructuredPaperState`
- job / run / event trail
- `ResearchDNA`

Current source layers that are not canonical owners:

- Zotero metadata, PDFs, raw note content
- Obsidian note body and frontmatter

Current LLM or automation outputs are derived outputs or intermediate artifacts, for example:

- claimsets and reader outputs
- downstream packs and artifact bundles
- summaries, drafts, and generated notes

Rule:

- natural language may operate the workspace
- schema-backed structured state remains the source of truth
- derived outputs must not become second canonical truth stores

Current anchors:

- `docs/Product_Positioning_Principles.md`
- `docs/Lattice_v3_Master_Spec.md`
- `docs/reports/Canonical_Objects_Scope_Cut_And_Supported_Journey_2026-03-24.md`

## 3. Who is the v1 user?

The current first-product user is a single primary operator working in a local biomedical research workflow.

More concretely:

- one researcher is the primary operator
- the operating environment is a local research workspace
- the core value is turning papers into structured understanding, reproducible search-design state, and meeting-ready artifacts

This does not promise:

- multi-user collaboration
- lab-wide shared governance
- generalized assistant memory across unrelated domains

Current anchors:

- `docs/Product_Positioning_Principles.md`
- `docs/reports/First_Shippable_Product_Bar_2026-03-24.md`

## 4. Which biomedical workflow is the first one we are trying to do well?

The first workflow is:

> paper -> structured understanding -> reproducible search design -> meeting-ready artifact

Current end-to-end loop:

1. start from a biomedical paper
2. run or inspect deep-read output
3. review evidence and uncertainty in paper detail or workbench
4. create, refine, and lock `ResearchDNA`
5. generate a `MeetingPack`
6. optionally inspect bounded extensions such as protocol, method, chart, or image artifacts

This is the first workflow the repo can currently support honestly.

Current anchors:

- `docs/reports/First_Shippable_Product_Bar_2026-03-24.md`
- `docs/reports/Canonical_Objects_Scope_Cut_And_Supported_Journey_2026-03-24.md`
- `docs/reports/Release_Rehearsal_Run_2026-03-25.md`

## 5. Which objects must be treated as first-class entities right now?

Current first-class canonical entities are intentionally narrow.

Current canonical roots:

- `StructuredPaperState`
- job / run / event trail
- `ResearchDNA`

Current important but bounded derived families:

- `MeetingPack`
- `ProtocolCard`
- `Method Comparison`
- `Chart Pack`
- `Image Evidence`

Current runtime metadata projection:

- paper-note index metadata surface

Not current canonical roots:

- first-class `Project`
- repo-wide `Decision`
- repo-wide `Open Question` / `Blocked Reason`
- generalized `Experiment`
- `Project Memory` as a product lane
- `/api/chat` as a real product surface

Current anchors:

- `docs/reports/Canonical_Objects_Scope_Cut_And_Supported_Journey_2026-03-24.md`
- `docs/reports/First_Shippable_Product_Bar_2026-03-24.md`

## 6. How are meeting notes, papers, protocol, experiment, and decision connected?

The honest current answer is: they are not all connected as first-class canonical objects yet.

What is currently strong:

- papers connect to `StructuredPaperState`, evidence review surfaces, and run/job provenance
- `ResearchDNA` connects the reproducible search-design lane
- `MeetingPack` is the strongest current downstream artifact lane
- `ProtocolCard` exists as a bounded protocol-reference artifact family

What is not yet first-class:

- repo-wide meeting-note ingestion that promotes canonical `Decision` or `Task` objects
- repo-wide `Decision -> Next Action -> Blocked Reason` flow
- generalized experiment workspace coordination
- a stable cross-surface graph tying paper, meeting, protocol, experiment, and decision together

So the current truthful connection model is narrower:

- paper -> structured paper state -> evidence review -> `ResearchDNA` -> `MeetingPack`
- protocol remains a bounded reference lane
- meeting remains strongest as `MeetingPack`, not as a canonical meeting-note object
- decision and experiment stay future-only

Current anchors:

- `docs/reports/Canonical_Objects_Scope_Cut_And_Supported_Journey_2026-03-24.md`
- `docs/PROTOCOL_KNOWLEDGE.md`
- `docs/MEETING_PACK.md`

## 7. What are we still not promising?

The current first-product bar does not promise:

- a project-first runtime
- a generic projects/documents platform
- a broad workspace memory platform
- chat-first or copilot-first operation
- repo-wide canonical `Decision`, `Task`, or `Experiment` objects
- multi-user lab collaboration
- a full ELN/LIMS replacement

These may become future bounded RFCs, but they are not part of the current first-product contract.

Current anchors:

- `docs/Product_Positioning_Principles.md`
- `docs/reports/First_Shippable_Product_Bar_2026-03-24.md`
- `docs/API_CHAT_CONTRACT.md`

## 8. Where do current implementation and docs still diverge?

The biggest conflicts have already been reduced.
The remaining gaps are mostly strength gaps, not identity conflicts.

Current remaining divergence or unevenness:

- provenance and uncertainty rules are stronger in the docs than in every current surface
- non-destructive regeneration guarantees are strongest in `MeetingPack`, not yet equally proven across every lane
- legacy and partial older bundles still exist, but they are now explicitly outside the bounded v1 proof slice unless backfilled
- some historical or proposal docs still describe broader project/memory/platform ideas, but active canonical docs no longer treat those as current runtime truth

So the current repo is mostly aligned on product identity and scope.
The remaining work is operational hardening and proof consistency, not another product-definition reset.

Current anchors:

- `docs/reports/Launch_Readiness_Checklist_2026-03-24.md`
- `docs/reports/Deep_Read_Legacy_Bundle_Release_Boundary_2026-03-25.md`
- `docs/reports/Release_Rehearsal_Run_2026-03-25.md`

## Bottom Line

If someone asks what Lattice v1 is, the shortest honest answer is:

> Lattice v1 is a local-first, paper-centered biomedical research workspace for a single primary operator, where schema-backed structured paper state, run/audit state, and bounded reproducible search design are the truth, and meeting-ready artifacts are evidence-linked downstream outputs rather than the truth store themselves.
