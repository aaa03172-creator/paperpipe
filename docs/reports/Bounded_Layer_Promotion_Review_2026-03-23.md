# Bounded Layer Promotion Review (2026-03-23)

Status: Active  
Date: 2026-03-23  
Owner: Lattice runtime maintainers  
Canonical: `docs/reports/Bounded_Layer_Promotion_Review_2026-03-23.md`

## Purpose

Record the current implementation status of the recently opened bounded artifact layers and the promotion decisions that moved them from `future RFC / pilot lane` into active bounded specs.

This is a current-state review, not a replacement runtime spec.

## Scope

Reviewed lanes:
- `method_comparison`
- `chart_pack` (`research-data-visualization` implementation lane)
- `protocol_knowledge`
- `image_evidence`

Out of scope:
- promoting any of these lanes into canonical SSOT in this step
- reopening `projects/documents` style platform redesign ideas
- changing the current `papers / jobs / artifacts / notes` runtime vocabulary

## Current state summary

| Lane | Backend/API | Viewer | Verification state | Fit with current core loop | Recommendation |
| --- | --- | --- | --- | --- | --- |
| Method Comparison | Implemented | Implemented | Strong | Highest | Promoted to active spec |
| Chart Pack | Implemented | Implemented | Strong | Medium-high | Promoted to active spec |
| Protocol Knowledge | Implemented | Implemented | Strong | Medium-high | Promoted to active spec |
| Image Evidence | Implemented | Implemented | Strong | Medium | Promoted to active spec (metadata-first sidecar) |

## Applied status

As of 2026-03-23, the recommendation in this review has been applied as follows:
- `Method Comparison` is now an active bounded spec at `docs/METHOD_COMPARISON.md`
- `Chart Pack` is now an active bounded spec at `docs/CHART_PACK.md`
- `Protocol Knowledge` is now an active bounded spec at `docs/PROTOCOL_KNOWLEDGE.md`
- `Image Evidence` is now an active bounded spec at `docs/IMAGE_EVIDENCE.md`

## Evidence snapshot

### 1. Method Comparison

Current status:
- file-backed schema/store/source-loader/service/renderer implemented
- thin FastAPI surface implemented
- read-only frontend viewer implemented
- recorded fixture hardening implemented
- mock + real backend Playwright coverage implemented

Current strengths:
- most directly aligned with the current paper-first, evidence-linked runtime
- reuses existing claim/evidence lineage and `ChatEvidenceRef` locator family
- supports a repeated operator need without opening spreadsheet-platform scope

Current limits:
- still claimset-first
- document/table fallback and operator edit flow are intentionally deferred
- broader comparison/workspace scope remains intentionally out of bounds

Primary references:
- `docs/archive/Method_Comparison_Layer_RFC_2026-03-18.md`
- `docs/archive/Method_Comparison_v0_Implementation_Plan_2026-03-18.md`
- `.codex/work/2026-03-18_method-comparison-v0/progress.md`

### 2. Chart Pack

Current status:
- file-backed schema/store/source-loader/service/renderer implemented
- thin FastAPI surface implemented
- read-only frontend viewer implemented
- mock + real backend Playwright coverage implemented

Current strengths:
- operationally useful downstream artifact
- fits current artifact/storage patterns without opening a dataset platform
- already bounded around explicit source refs (`stats_report`, `document_table`)

Current limits:
- more presentation-oriented than Method Comparison
- source adapters are still intentionally narrow
- consumer boundary with downstream uses such as `Meeting Pack` remains explicitly bounded

Primary references:
- `docs/archive/Research_Data_Visualization_Layer_RFC_2026-03-18.md`
- `docs/archive/Research_Data_Visualization_v0_Implementation_Plan_2026-03-18.md`
- `.codex/work/2026-03-20_chart-pack-v0/progress.md`

### 3. Image Evidence

Current status:
- metadata-first schema/store/service implemented
- thin FastAPI surface implemented
- read-only frontend viewer implemented
- fixture hardening, mock Playwright, real backend Playwright, and backend visual regression implemented

Current strengths:
- strongest viewer/test hardening of the three lanes
- raw-vs-derived separation is explicit and defensible
- good bounded sidecar pattern for image-adjacent metadata QA

Current limits:
- still intentionally metadata-first, not image-analysis runtime
- farther from the current paper-first core loop than Method Comparison
- should not be mistaken for a microscopy platform or stronger claim-grounding layer
- should stay bounded as a metadata-first sidecar even after active-spec promotion

Primary references:
- `docs/archive/Image_Evidence_Viewer_Layer_RFC_2026-03-18.md`
- `docs/archive/Image_Evidence_Viewer_v0_Implementation_Plan_2026-03-18.md`
- `docs/reports/Image_Evidence_Backend_Core_Staging_Prep_2026-03-22.md`
- `.codex/work/2026-03-22_image-evidence-viewer/progress.md`

### 4. Protocol Knowledge

Current status:
- file-backed schema/store/service/renderer implemented
- thin FastAPI surface implemented
- read-only frontend inspector implemented
- mock + real backend Playwright coverage implemented
- backend visual regression implemented

Current strengths:
- clean separation between protocol identity and version snapshots
- direct fit with paper-linked note review and downstream knowledge reuse
- reuses the current evidence locator family instead of inventing a protocol-specific provenance layer

Current limits:
- still read-first and intentionally non-authoring
- append-only version write and activation workflows remain deferred
- should not be mistaken for a protocol execution runtime or generalized protocol platform

Primary references:
- `docs/archive/Protocol_Knowledge_Layer_RFC_2026-03-18.md`
- `docs/UX_REVIEW_REPORT_protocol-knowledge-inspector.md`
- `.codex/work/2026-03-23_protocol-knowledge-v0/progress.md`

## Applied promotion record

### Promoted: Method Comparison

Reason:
- it is the most paper-centric lane
- it already fits current evidence lineage rules
- it solves a repeated comparison task without introducing a new platform model
- it has enough backend, viewer, and test coverage to justify writing an active bounded spec next

Applied decision:
- completed on 2026-03-23 via `docs/METHOD_COMPARISON.md`

### Promoted: Chart Pack

Reason:
- the runtime slice is real and useful
- but it is still more downstream and presentation-oriented than Method Comparison
- promoting it before Method Comparison would prioritize a communication artifact over the more directly evidence-linked operator workflow

Applied decision:
- completed on 2026-03-23 via `docs/CHART_PACK.md`

### Promoted: Image Evidence

Reason:
- the implementation is strong and now has schema/store/API/viewer plus mock, real-backend, and visual verification
- the raw-vs-derived boundary is explicit enough to freeze without reopening platform scope
- promotion clarifies the current metadata-first sidecar contract instead of leaving a mature lane in pilot limbo

Applied decision:
- completed on 2026-03-23 via `docs/IMAGE_EVIDENCE.md`

### Promoted: Protocol Knowledge

Reason:
- it now has implemented backend/API/viewer slices plus real-backend and visual coverage
- it fits the current knowledge-review loop more directly than `Image Evidence`
- its protocol identity/version split is clear enough to freeze without opening authoring or execution semantics

Applied decision:
- completed on 2026-03-23 via `docs/PROTOCOL_KNOWLEDGE.md`

## Queue impact

Queue order should now read:
1. `project-memory` backend-only hold with API explicitly gated
2. remaining future/deferred lanes: `future/project-memory-api-v0`, `local-backup-restore`

## Non-recommendations

Do not do these next:
- do not create a new master spec for these lanes
- do not promote all three lanes at once
- do not reinterpret their implementation status as permission to redesign the runtime around a new generalized data platform
- do not merge `image_evidence` semantics into claim-grounding or PDF/table locator semantics

## Conclusion

The current repo is no longer at the stage where these lanes are just ideas. All four have real implementations. But they are not equally central.

The current result is:
- `Method Comparison` promoted
- `Chart Pack` promoted
- `Protocol Knowledge` promoted
- `Image Evidence` promoted

The next move is not to demote `Image Evidence` back into a vague pilot lane. It should stay an explicitly bounded, metadata-first sidecar artifact family unless a later product decision broadens it.
