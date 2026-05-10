# Personal Assistant Integration Review Packet

Status: queue/staging note
Date: 2026-05-10
Owner: Runtime/integration maintainers
Canonical parents:
- `docs/Product_Positioning_Principles.md`
- `docs/Lattice_v3_Master_Spec.md`
- `docs/PaperPipe_Minimum_Operating_Principles.md`
- `docs/KNOWLEDGE_LAYER_OPERATING_NOTE.md`

Review targets:
- `docs/Personal_Assistant_Integration_Seam_2026-05-10.md`
- `docs/Assistant_Facing_Summary_Contracts_2026-05-10.md`

## Purpose

Package the new personal-assistant-related docs into a maintainers-first review flow.

This packet exists so the PaperPipe project can review the proposed assistant seam on its own terms before any runtime, API, schema, or MCP implementation work is treated as open.

This packet is for:

- reading order
- boundary checks
- accept/adapt/defer/reject decisions
- identifying vocabulary or contract mismatches

This packet is not:

- a new source of truth
- permission to widen PaperPipe into a generic assistant platform
- an implementation checklist for immediate runtime work

## Current stance

The current proposal set assumes:

- PaperPipe remains the truth owner for papers, runs, artifacts, Research DNA, and Meeting Packs
- any personal assistant remains an external orchestrator
- assistant-facing summaries stay thin, non-canonical, and provenance-preserving
- no code changes are implied by these docs alone

If a maintainer disagrees with any of those four assumptions, the safest current disposition is to mark the packet `defer` or `reject` and keep the docs as future-seam notes only.

## Review order

Read in this order:

1. `docs/Product_Positioning_Principles.md`
   - Re-anchor on product identity and non-goals.
2. `docs/PaperPipe_Minimum_Operating_Principles.md`
   - Re-anchor on the current paper/job/artifact runtime boundary.
3. `docs/Lattice_v3_Master_Spec.md`
   - Re-anchor on the current runtime SSOT, route vocabulary, and schema-facing product shape.
4. `docs/KNOWLEDGE_LAYER_OPERATING_NOTE.md`
   - Re-anchor on how derived knowledge can exist without becoming a second source of truth.
5. `docs/Personal_Assistant_Integration_Seam_2026-05-10.md`
   - Review the proposed owner split, URI seam, service boundary, and mutation-safety framing.
6. `docs/Assistant_Facing_Summary_Contracts_2026-05-10.md`
   - Review the proposed thin summary projections over current PaperPipe schemas and route vocabulary.

## What is being proposed

The proposal set makes five bounded claims:

1. PaperPipe should stay the truth owner.
2. A future external personal assistant should read PaperPipe through thin summary surfaces rather than rebuilding meaning from raw payloads and files.
3. Stable IDs and canonical URIs should be standardized before assistant integration is treated as implementation-ready.
4. Assistant write paths, if ever added, should be explicitly classified by safety lane.
5. Any future CLI/API/MCP assistant adapter should remain thin over the existing service/runtime boundary.

## What is explicitly not being proposed

These docs do not propose:

- turning PaperPipe into a generic second-brain platform
- making PaperPipe the owner of personal memory, goals, or broad workspace state
- replacing existing route response models with assistant-only schemas
- introducing a parallel assistant-owned truth store
- approving an MCP server implementation now

## Maintainer review questions

Use these questions to review the packet:

1. Boundary check
   - Does the proposed owner split preserve the current product/runtime boundary?

2. Identity check
   - Is the proposed canonical URI family directionally acceptable?
   - If not, which object families or tokens need to change before this becomes useful?

3. Summary check
   - Are the proposed assistant-facing summaries appropriately thin and explicitly non-canonical?
   - Do they stay subordinate to existing paper/run/artifact truth?

4. Vocabulary check
   - Do the proposed summary anchors correctly match the current schema and route vocabulary?
   - Are any names stale, too broad, or misleading?

5. Safety check
   - Is the mutation-safety framing reasonable for future assistant-triggered actions?
   - Are any operations obviously misclassified or missing?

6. Timing check
   - Should any of this move into implementation now, or should the entire seam remain documentation-only until identity/pathing is more settled?

## Suggested dispositions

Use one of these dispositions after review:

- `accept as future seam`
  - The proposal is directionally correct and may remain as documentation for later adoption.
- `accept with vocabulary changes`
  - The shape is right, but object names, fields, or boundaries need correction.
- `accept but defer implementation`
  - The docs are useful, but no runtime work should open until a narrower prerequisite lands first.
- `reject for boundary widening`
  - The proposal risks expanding PaperPipe beyond its current product/runtime identity.

## Recommended review outcome format

When maintainers reply, the most useful format is:

1. chosen disposition
2. top 3 objections or requested edits
3. whether identity/URI work should happen before any summary work
4. whether summary work should stay docs-only or move toward implementation

## Recommended next step order if accepted

If the packet is accepted in principle, the safest next order is:

1. settle canonical identity/URI direction
2. settle assistant-facing summary projections against current schema vocabulary
3. only then decide whether any implementation slice should open

## Changed doc set in this packet

- `docs/Personal_Assistant_Integration_Seam_2026-05-10.md`
- `docs/Assistant_Facing_Summary_Contracts_2026-05-10.md`
- `docs/Personal_Assistant_Integration_Review_Packet_2026-05-10.md`

## Current recommendation

Current recommendation from this packet:

- treat the assistant seam as a future-seam planning set
- review and correct the contracts now
- avoid opening runtime work until identity/pathing and summary vocabulary are judged acceptable by maintainers

## Maintainer review outcome

Chosen disposition: `accept but defer implementation`

Top requested edits / objections:

1. Settle the canonical identity and URI direction before any summary or adapter implementation work opens.
2. Re-check assistant-facing summary vocabulary against the current FastAPI route and Pydantic schema surface before promoting any contract names.
3. Keep MCP, CLI, API, and assistant adapters out of scope until a narrow implementation slice is explicitly approved.

Identity/URI work should happen before summary implementation.

Summary work should remain docs-only for now. The next useful step is a bounded vocabulary/contract pass against the current `docs/Lattice_v3_Master_Spec.md`, `src/schemas/`, and existing route behavior.
