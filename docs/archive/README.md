# Archive Index

Status: Active  
Date: 2026-03-09  
Owner: Repository maintainers  
Canonical: `docs/archive/README.md`

This directory stores historical project documents that are useful for audit or reconstruction but are not part of the active documentation surface.

## Typical contents
- old checklists and working plans
- dated snapshots and health reports
- historical execution notes with no active references
- historical audits and handoff packets
- superseded specs and one-off proposals that no longer belong in the active docs root

## Recent grouped sets

### External reference fit-review set (2026-03-18)
- `docs/archive/External_Reference_Fit_Review_2026-03-18.md`

This note consolidates recent external reference judgments across OCR/parser, retrieval/reranking, enrichment, note/memory, and agentic RAG references into a single current-system-safe review. It belongs here because it is a dated fit-review record, not an active runtime spec.

### External proposal adaptation set (2026-03-18)
- `docs/archive/Agent_Proposal_Fit_Review_2026-03-18.md`
- `docs/archive/Proposal_to_Lattice_Mapping_2026-03-18.md`
- `docs/archive/Protocol_Knowledge_Layer_RFC_2026-03-18.md`
- `docs/archive/Method_Comparison_Layer_RFC_2026-03-18.md`
- `docs/archive/Project_Memory_Layer_RFC_2026-03-18.md`
- `docs/archive/Local_Backup_and_Restore_Semantics_RFC_2026-03-18.md`

These belong here because they are future-direction adaptation notes and bounded RFC inputs, not active runtime SSOT.

### Deep research visualization adaptation set (2026-03-18)
- `docs/archive/Deep_Research_Reports_2_3_4_Fit_Review_2026-03-18.md`
- `docs/archive/Research_Data_Visualization_Layer_RFC_2026-03-18.md`
- `docs/archive/Research_Data_Visualization_v0_Implementation_Plan_2026-03-18.md`
- `docs/archive/Image_Evidence_Viewer_Layer_RFC_2026-03-18.md`
- `docs/archive/Image_Evidence_Viewer_v0_Implementation_Plan_2026-03-18.md`

These belong here because they reinterpret external visualization/microscopy research reports as current-system-safe future RFC inputs rather than active runtime specs.

## Rules
- Do not treat archived files as SSOT.
- When an archived file still matters, summarize its durable conclusion into a canonical doc under `docs/`.
- Prefer moving zero-reference historical files here instead of leaving them in the `docs/` root.
- Prefer keeping the active docs root limited to current specs, contracts, runbooks, templates, and live working queues.
