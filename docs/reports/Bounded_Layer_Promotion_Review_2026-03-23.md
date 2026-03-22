# Bounded Layer Promotion Review (2026-03-23)

Status: Active  
Date: 2026-03-23  
Owner: Lattice runtime maintainers  
Canonical: `docs/reports/Bounded_Layer_Promotion_Review_2026-03-23.md`

## Purpose

Record the current implementation status of the recently opened bounded artifact layers and recommend which lane should be promoted next from `future RFC / pilot lane` into an active bounded-spec candidate.

This is a current-state review, not a replacement runtime spec.

## Scope

Reviewed lanes:
- `method_comparison`
- `chart_pack` (`research-data-visualization` implementation lane)
- `image_evidence`

Out of scope:
- promoting any of these lanes into canonical SSOT in this step
- reopening `projects/documents` style platform redesign ideas
- changing the current `papers / jobs / artifacts / notes` runtime vocabulary

## Current state summary

| Lane | Backend/API | Viewer | Verification state | Fit with current core loop | Recommendation |
| --- | --- | --- | --- | --- | --- |
| Method Comparison | Implemented | Implemented | Strong | Highest | Promote next |
| Chart Pack | Implemented | Implemented | Strong | Medium-high | Keep as bounded pilot, next after Method Comparison |
| Image Evidence | Implemented | Implemented | Strong | Medium | Keep as bounded pilot / experimental sidecar |

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
- active bounded spec under `docs/` does not exist yet; current reference remains an archive RFC + implementation plan

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
- consumer boundary with downstream uses such as `Meeting Pack` is still a policy question, not yet an active bounded spec

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
- active bounded spec under `docs/` does not exist yet; current reference remains an archive RFC + implementation plan

Primary references:
- `docs/archive/Image_Evidence_Viewer_Layer_RFC_2026-03-18.md`
- `docs/archive/Image_Evidence_Viewer_v0_Implementation_Plan_2026-03-18.md`
- `docs/reports/Image_Evidence_Backend_Core_Staging_Prep_2026-03-22.md`
- `.codex/work/2026-03-22_image-evidence-viewer/progress.md`

## Recommendation

### Promote next: Method Comparison

Reason:
- it is the most paper-centric lane
- it already fits current evidence lineage rules
- it solves a repeated comparison task without introducing a new platform model
- it has enough backend, viewer, and test coverage to justify writing an active bounded spec next

Recommended next step:
- write `docs/METHOD_COMPARISON.md` as an active bounded spec candidate that formalizes the already-implemented v0 scope and guardrails

### Keep as bounded pilot: Chart Pack

Reason:
- the runtime slice is real and useful
- but it is still more downstream and presentation-oriented than Method Comparison
- promoting it before Method Comparison would prioritize a communication artifact over the more directly evidence-linked operator workflow

Recommended next step:
- keep it implemented and usable
- defer active bounded-spec promotion until the consumer boundary with `Meeting Pack`, `Stats Verification`, and future chart usage is explicitly frozen

### Keep as bounded pilot / experimental sidecar: Image Evidence

Reason:
- the implementation is strong, but the product fit is narrower
- it is intentionally metadata-first and should remain carefully bounded
- promoting it too early would overstate its role in the current paper-first product loop

Recommended next step:
- keep it as a hardened sidecar lane
- only consider active bounded-spec promotion when repeated real usage proves it is part of the core review loop rather than an adjacent specialist tool

## Queue impact

Queue order should now read:
1. `method-comparison` active bounded-spec promotion candidate
2. `chart-pack` bounded pilot with later promotion decision
3. `image-evidence` bounded pilot / experimental sidecar
4. remaining future RFCs: `protocol-knowledge`, `project-memory`, `local-backup-restore`

## Non-recommendations

Do not do these next:
- do not create a new master spec for these lanes
- do not promote all three lanes at once
- do not reinterpret their implementation status as permission to redesign the runtime around a new generalized data platform
- do not merge `image_evidence` semantics into claim-grounding or PDF/table locator semantics

## Conclusion

The current repo is no longer at the stage where these lanes are just ideas. All three have real implementations. But they are not equally central.

The best next move is not to open another new bounded layer. It is to promote `Method Comparison` first, keep `Chart Pack` and `Image Evidence` as bounded pilots, and leave the remaining RFC-only ideas in the future bucket.
