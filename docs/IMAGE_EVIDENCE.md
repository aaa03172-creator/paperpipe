# Image Evidence

Status: Active spec
Date: 2026-03-23
Owner: Paper notes/runtime maintainers
Canonical parent: `docs/Lattice_v3_Master_Spec.md`

Related docs:
- `docs/Evidence_and_Uncertainty_Rules.md`
- `docs/document_artifact_v2.md`
- `docs/UX_REVIEW_REPORT_image-evidence-viewer.md`
- `docs/reports/Image_Evidence_Backend_Core_Staging_Prep_2026-03-22.md`
- `docs/archive/Image_Evidence_Viewer_Layer_RFC_2026-03-18.md`
- `docs/archive/Image_Evidence_Viewer_v0_Implementation_Plan_2026-03-18.md`

## Purpose

`Image Evidence` is a bounded, metadata-first image-evidence sidecar artifact family.

It exists to let operators preserve:
- raw image identity
- explicit source registration
- structured view-state provenance
- derived-output lineage
- note and viewer handoff metadata
- warning-visible review state

without introducing:
- a microscopy platform
- an image-analysis runtime
- pixel editing or ROI authoring UI
- a second claim-grounding system beside current paper/artifact evidence rules

The current lane is intentionally:
- file-backed
- metadata-first
- warning-forward
- read-first
- bounded around saved image-evidence bundles

## Current Implementation Status

Implemented in current runtime slice:
- `src/schemas/image_evidence.py`
- `src/image_evidence/store.py`
- `src/image_evidence/service.py`
- `src/services/runtime_paths.py::image_evidence_root()`
- `backend/routers/image_evidence.py`
- read-only frontend viewer:
  - `/image-evidence`
  - `/image-evidence/:imageEvidenceId`
- recorded fixture hardening for local-file, external-ref, checksum-mismatch, and missing-local cases
- frontend mock Playwright coverage
- frontend real-backend Playwright coverage
- backend visual regression coverage for index/detail

Currently deferred:
- ROI/segmentation storage
- image-coordinate locator semantics parallel to PDF/table locators
- embedded microscopy/image viewer runtime
- automatic crawling or bulk ingestion
- prompt-based image interpretation
- editing or launch-control UI

## Current Judgment

At the current repo stage, `Image Evidence` is mature enough to freeze as an active bounded spec.

That judgment is based on:
- implemented schema/store/service/API/viewer slices
- explicit raw-vs-derived separation in the schema and bundle layout
- repeated real-backend verification across warning-heavy, clean, and missing-local cases
- a read-only viewer that preserves the bounded metadata-review role instead of expanding into image analysis

Promotion here does not make `Image Evidence` part of the claim-truth core.

It freezes the current sidecar contract so the lane stays narrow and defensible.

## Current Boundary

### 1. Registration stays explicit and metadata-first

Current supported source kinds:
- `local_file`
- `external_image_ref`

Current rule:
- raw image sources must be named explicitly in the request
- do not auto-discover image sources through crawling, scraping, or sync jobs
- do not treat screenshots or downstream crops as raw source truth

### 2. Raw-vs-derived separation stays literal

Current rule:
- `source_ref` represents raw image identity
- `derived_outputs[]` represent downstream artifacts such as thumbnails, representative crops, overlays, or measurement exports
- derived outputs must keep lineage back to `source_image_evidence_id`
- derived outputs must not silently replace or overwrite the raw source

### 3. View state and handoff stay bounded

Current rule:
- `view_state` is structured scientific provenance, not an opaque convenience blob by default
- `handoff_targets[]` store metadata for local/external viewers only
- the lane must not become a server-side process-launch or orchestration subsystem

### 4. Image linkage stays explicit but non-upgrading

Current rule:
- image evidence may link to `paper_id`, `paper_slug`, claim ids, or artifact ids when explicitly provided
- a registered image does not automatically verify a claim
- image metadata and view state must not pretend to be interchangeable with current PDF/table locator semantics

### 5. Storage stays file-backed

Current storage root:

```text
storage/image_evidence/<image_evidence_id>/
  image_evidence.json
  view_state.json
  derivatives/
    <derived_output_id>.png
  handoff.json
```

Current rule:
- `image_evidence.json` remains the primary bundle-local metadata and provenance file
- it does not replace canonical paper/run truth elsewhere in the runtime
- optional files stay additive and bundle-relative
- the bundle is a bounded sidecar artifact, not a generalized image-data platform

### 6. API stays thin

Current API surface:
- `POST /image-evidence/register`
- `GET /image-evidence`
- `GET /image-evidence/{image_evidence_id}`
- `GET /image-evidence/{image_evidence_id}/view-state`
- `GET /image-evidence/{image_evidence_id}/handoff`

Current rule:
- the API remains a thin wrapper over schema/service/store code
- register-time validation may emit warnings such as missing-local-file or checksum-mismatch
- the API does not open editing, analysis, or viewer-control workflows

### 7. Viewer stays read-only and metadata-first

Current viewer surface:
- `/image-evidence`
- `/image-evidence/:imageEvidenceId`

Current rule:
- the viewer is for bundle inspection, not image manipulation
- source identity, warning state, derived-output lineage, view state, and handoff metadata should stay visible together
- the UI must not imply that the system has verified image interpretation or measurement correctness

### 8. Image Evidence must not become a hidden microscopy platform

Current rule:
- this lane is a reviewable sidecar artifact family
- it is not a microscopy runtime, an image database, or an execution surface for external viewers
- active spec status freezes the current metadata-first contract; it does not authorize broader platform scope

## Current Non-Goals

The current spec does not include:
- embedded image rendering as canonical truth
- ROI editing
- segmentation or mask storage
- measurement computation
- automatic image-analysis inference
- microscopy workflow orchestration
- replacing claim/paper/artifact evidence rules with image-native rules

## Relationship To Other Bounded Lanes

- `Method Comparison` remains a separate evidence-linked comparison artifact and must not consume image-evidence bundles as hidden cell truth.
- `Chart Pack` may later visualize image-derived metadata only through explicit downstream adapters; it is not the truth surface for image provenance.
- `Protocol Knowledge` may link to image evidence as context, but image-evidence bundles do not become protocol execution state.
- `Meeting Pack` may later consume representative-image outputs, but those outputs must remain explicitly downstream of an image-evidence bundle.

## Verification Expectations

Current verification lanes should remain:
- targeted pytest coverage for schema/store/service/API/runtime-path behavior
- recorded fixture hardening for representative local/external/warning cases
- mock Playwright coverage for index/detail viewer behavior
- real-backend Playwright coverage for registered bundle review and note handoff
- backend visual coverage for `/image-evidence` index/detail

When this spec changes:
- keep raw-vs-derived separation explicit
- keep warning semantics visible
- keep viewer behavior metadata-first
- avoid widening into image-analysis or execution semantics without updating both tests and this bounded spec

## Conclusion

`Image Evidence` is now an active bounded spec because the lane is implemented, verified, and narrow enough to freeze without overstating its product role.

The next changes in this area should harden or extend this bounded sidecar artifact family.

They should not reopen the broader question of whether Lattice should become a microscopy platform, image-analysis runtime, or alternate claim-grounding system.
