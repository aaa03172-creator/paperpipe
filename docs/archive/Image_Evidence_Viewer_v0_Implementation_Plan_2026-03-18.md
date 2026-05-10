# Image Evidence Viewer v0 Implementation Plan (2026-03-18)

Status: Historical implementation plan  
Date: 2026-03-18  
Owner: Runtime/design maintainers  
Canonical parent: `docs/archive/Image_Evidence_Viewer_Layer_RFC_2026-03-18.md`

Related docs:
- `docs/archive/Image_Evidence_Viewer_Layer_RFC_2026-03-18.md`
- `docs/Evidence_and_Uncertainty_Rules.md`
- `docs/API_CHAT_CONTRACT.md`
- `docs/document_artifact_v2.md`
- `docs/MEETING_PACK.md`
- `docs/archive/Method_Comparison_v0_Implementation_Plan_2026-03-18.md`
- `docs/Lattice_v3_Master_Spec.md`

## Purpose

This document turns the `Image Evidence Viewer Layer RFC` into a concrete v0 execution plan.

The goal is not to build a microscopy platform, image database, or embedded viewer runtime.

The goal is to add the smallest useful image-evidence lane that:
- registers raw image identity without mutating it
- stores view-state and derived-output provenance explicitly
- links image evidence to current paper/claim/artifact identities
- remains file-backed
- can later feed downstream surfaces such as representative-image cards in `Meeting Pack`

## Current repo reality

Current repo already has:
- paper identity and note identity
- evidence-linked claim/artifact surfaces with locator metadata
- `Meeting Pack` hints for representative figures
- file-backed bounded artifact patterns
- active evidence and uncertainty rules that already distinguish raw support from derived presentation

Current repo does not have:
- an image-evidence registry
- an ROI/segmentation store
- an embedded microscopy viewer
- a stable image-coordinate contract parallel to current PDF/table locators

Important current constraint:
- current evidence locators are PDF/table oriented
- therefore v0 should not pretend that image regions, channels, overlays, or viewer state already fit the same locator model without an explicit bounded contract

So v0 should start as:
- a metadata-first sidecar artifact family
- registered from explicit operator-provided source refs
- read-first

## V0 fixed decisions

### 1. Request shape stays register-first and metadata-first

First request contract should stay close to:
- `image_evidence_id?`
- `title?`
- `paper_id?`
- `paper_slug?`
- `source_kind`
  - `local_file`
  - `external_image_ref`
- `source_ref`
- `content_format`
- `checksum?`
- `metadata`
- `view_state?`
- `linked_claim_refs[]?`
- `linked_artifact_refs[]?`
- `derived_outputs[]?`
- `handoff_targets[]?`

Do not start with:
- bulk image ingestion pipelines
- automatic file crawling
- prompt-based image interpretation
- embedded pixel editing

### 2. Raw source registration stays explicit

V0 should not discover raw image sources implicitly.

The request should name the source directly, and the runtime should register only:
- an explicit local file path
- or an explicit external image-system reference

Recommended first source subset:
1. `local_file`
2. `external_image_ref`

Do not start with:
- automatic repository sync
- vendor-format conversion pipelines
- viewer scraping or screenshot capture as raw truth

### 3. Derived outputs stay separate and operator-scoped

V0 should not auto-generate overlays, crops, or measurements.

Instead, it should allow already-produced derived outputs to be registered with provenance such as:
- `thumbnail`
- `representative_crop`
- `overlay`
- `measurement_export`

Each derived output should carry:
- `kind`
- `path` or `external_ref`
- `created_by`
- `created_at`
- `tool_name`
- `tool_version?`
- `source_image_evidence_id`
- `view_state_ref?`
- `note?`

Do not allow:
- silent replacement of raw image identity
- derived outputs with missing lineage
- pixel edits masquerading as raw evidence

### 4. View state stays structured and reviewable

V0 should treat viewer state as scientific provenance, not convenience metadata.

The stored view-state contract should stay narrow, for example:
- active channels
- intensity ranges
- z/t slice index
- viewport / zoom
- visible overlays
- selected region labels

Do not allow:
- opaque viewer-only blobs with no documented meaning if a narrower structured form is feasible
- view state to overwrite raw metadata

### 5. Evidence linkage stays bounded

Image evidence should link into current Lattice truth only through explicit references.

That means:
- link to current paper identity
- link to current claim/artifact IDs when operator-specified
- keep representative-image rationale explicit

V0 should not claim:
- that a registered image automatically verifies a claim
- that image coordinates are already interchangeable with PDF/table locators

### 6. Handoff stays metadata-only in v0

The system may persist structured handoff metadata for local viewers, but it should not become a general process-launch subsystem.

V0 handoff should store only bounded metadata such as:
- `target`
  - `napari`
  - `omero`
  - `other_local_viewer`
- `openable_ref`
- `view_state_ref?`
- `notes?`

Do not start with:
- arbitrary shell-command execution
- server-side remote session orchestration

### 7. Storage stays file-first

Suggested root:

```text
storage/image_evidence/<image_evidence_id>/
  image_evidence.json
  view_state.json
  derivatives/
    <derived_output_id>.png
  handoff.json
```

Notes:
- `image_evidence.json` is the canonical metadata/provenance bundle
- `view_state.json` is additive viewer-state provenance
- `derivatives/` is optional and stores only derived outputs keyed by derived-output identity
- `handoff.json` stores structured external-viewer handoff metadata, not executable shell scripts

## Phase 1: Schema + Runtime Path + Store

Purpose:
- fix the artifact contract before registration logic exists

Scope:
- `src/schemas/image_evidence.py`
- `src/services/runtime_paths.py`
  - `image_evidence_root()`
- `src/image_evidence/store.py`
- schema/store/path regression tests

Suggested schema pieces:
- `ImageEvidenceRequest`
- `ImageEvidence`
- `ImageEvidenceSummary`
- `ImageSourceRef`
- `ImageMetadata`
- `ImageViewState`
- `ImageDerivedOutput`
- `ImageHandoffTarget`
- `ImageClaimLink`

Suggested bundle-level fields:
- `image_evidence_id`
- `title`
- `paper_id?`
- `paper_slug?`
- `source_ref`
- `metadata`
- `view_state_ref?`
- `derived_outputs[]`
- `linked_claim_refs[]`
- `linked_artifact_refs[]`
- `handoff_targets[]`
- `warnings[]`

Acceptance:
- an image-evidence bundle can be validated, saved, and loaded
- root path supports env override plus repo-relative fallback
- save/load helpers are deterministic
- raw vs derived separation is explicit in the schema

## Phase 2: Deterministic Source Registration + Metadata Validation

Purpose:
- build a conservative source-registration lane

Scope:
- `src/image_evidence/service.py`
- source validators for:
  - local file refs
  - external image refs
- checksum verification when a local file exists
- bounded metadata normalization

Recommended first validation subset:
- local file exists or missing
- checksum matches when provided
- content format is explicit
- linked paper identity is syntactically valid

Do not start with:
- vendor-specific binary parsing
- auto-derived axes/channel introspection for every file format
- ROI extraction

Acceptance:
- the same source request produces the same stored identity metadata
- missing files or checksum mismatches become warnings or reject states explicitly
- local-path verification does not mutate the source file

## Phase 3: View State + Derived Output Registration

Purpose:
- persist representative-image and viewer-state provenance without creating a rendering platform

Scope:
- save `view_state.json`
- register derived outputs already produced outside the runtime
- representative-image metadata and rationale fields

Generation rules:
- derived outputs always point back to the raw source bundle
- representative-image choice records rationale and source linkage
- missing provenance keeps the derived output in warning state

Non-goals:
- auto-cropping
- auto-thumbnail generation
- overlay authoring

Acceptance:
- a representative-image card can be reconstructed from saved metadata
- derived output lineage remains explicit and auditable

## Phase 4: Thin FastAPI Surface

Purpose:
- expose the image-evidence bundle through the current API-first contract

Scope:
- `backend/routers/image_evidence.py`
- `backend/main.py` router wiring
- endpoints:
  - `POST /image-evidence/register`
  - `GET /image-evidence`
  - `GET /image-evidence/{image_evidence_id}`
  - `GET /image-evidence/{image_evidence_id}/view-state`
  - `GET /image-evidence/{image_evidence_id}/handoff`

Non-goals:
- embedded image viewer
- edit-in-browser workflow
- server-side viewer launch

Acceptance:
- API layer stays thin and delegates to service/store code
- response payload matches Pydantic contracts
- read endpoints return stored metadata bundles, not live binary processing

## Phase 5: Real-Fixture Hardening

Purpose:
- prove the lane on realistic raw-plus-derived registration examples before any UI expansion

Scope:
- recorded fixtures for:
  - one local-file image evidence case
  - one external-ref image evidence case
  - one representative-image derived-output case
- regression coverage for:
  - raw/derived separation
  - checksum mismatch behavior
  - missing-file warning behavior
  - handoff metadata persistence

Non-goals:
- visual rendering QA
- binary format compatibility matrix

Acceptance:
- saved bundles reproduce deterministically from recorded fixtures
- weak or incomplete provenance stays visibly weak

## Phase 6: Optional Read Surface

Purpose:
- only after bundle and API contracts are stable, add a lightweight read surface

Scope:
- saved bundle index
- detail page with:
  - source metadata
  - derived outputs
  - representative-image rationale
  - linked claims/artifacts
  - handoff metadata

Non-goals:
- microscopy workbench
- pixel overlay editing
- collaborative annotation platform

Acceptance:
- reader can inspect raw identity, derived lineage, and caution state before trusting an image-backed artifact

## Suggested PR sequence

### PR-DOC-BE-ImageEvidence-v0

Scope:
- implementation-plan doc
- schema contract
- runtime path
- store
- tests

### PR-BE-ImageEvidence-Register-v0

Scope:
- source registration
- metadata validation
- checksum handling

### PR-BE-ImageEvidence-Derived-v0

Scope:
- view-state persistence
- derived-output registration
- representative-image metadata

### PR-BE-ImageEvidence-API-v0

Scope:
- thin FastAPI routes
- response models
- read endpoints

### PR-QA-ImageEvidence-Fixtures-v0

Scope:
- recorded fixtures
- deterministic regression coverage

## Explicitly out of scope

- full microscopy repository ingestion
- OMERO replacement
- napari embedding
- server-side viewer orchestration
- binary annotation editors
- automatic image interpretation or claim verification
- treating screenshots or crops as raw truth

## Bottom line

The safe first implementation is:
- `image_evidence` as a bounded, metadata-first, file-backed sidecar layer with explicit raw/derived separation and structured external-viewer handoff metadata

The unsafe first implementation would be:
- a stealth microscopy platform
- a binary processing pipeline as product root
- a viewer runtime that blurs raw evidence with derived presentation
