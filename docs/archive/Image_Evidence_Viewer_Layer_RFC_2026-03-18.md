# Image Evidence Viewer Layer RFC

Status: Future RFC  
Date: 2026-03-18  
Owner: Runtime/design maintainers  
Canonical parent: `docs/Lattice_v3_Master_Spec.md`

Related docs:
- `docs/Product_Positioning_Principles.md`
- `docs/Evidence_and_Uncertainty_Rules.md`
- `docs/MEETING_PACK.md`
- `docs/archive/Deep_Research_Reports_2_3_4_Fit_Review_2026-03-18.md`
- `docs/archive/Image_Evidence_Viewer_v0_Implementation_Plan_2026-03-18.md`

## Purpose

Define a bounded future lane for image-backed scientific evidence without turning current Lattice into a full microscopy/image-management platform.

This RFC preserves the strongest ideas from the microscopy reports:
- image display choices are scientific provenance, not just UI state
- raw and derived image outputs must be separated
- representative images should be reproducible, attributable, and reviewable
- local viewer handoff and optional server connectors should stay distinct

## Current judgment

This is a valid future bounded layer, but not a current runtime contract.

The right starting position is:
- image evidence registry
- provenance-bearing view-state and derived-output references
- external viewer handoff

The wrong starting position is:
- immediate in-product microscopy platform
- immediate OMERO-class server behavior inside PaperPipe
- pixel-editing workflows that blur raw and derived state

## Problem statement

Current Lattice evidence is mostly:
- text-linked
- table-linked
- PDF/page/span-linked

There is no bounded way to express:
- raw microscopy image references
- ROI/segmentation overlays
- representative image selections
- measurement outputs tied to image evidence
- image-specific view state used in a scientific claim or pack

## Design goals

- keep raw image identity immutable
- store view state and derived overlays as separate provenance-bearing objects
- allow evidence linkage from images to claims/packs without pretending images are just another note
- support local-first handoff first
- keep OMERO-class collaboration concerns optional and connector-scoped

## Non-goals

- no full image database platform in v0
- no in-core replacement for OMERO
- no destructive image editing
- no silent conflation of representative image output with raw evidence
- no requirement to support every microscopy vendor format on day one

## Fit with current Lattice

Closest current analogs:
- evidence-linked downstream outputs
- `Meeting Pack` representative content selection
- file-backed bounded artifacts

The likely current-system-safe shape is:
- `image_evidence` as a future evidence-linked sidecar family
- file-backed metadata and derived outputs
- external viewer launch or connector references

## Proposed v0 boundary

### Inputs

Start with:
- local file references
- explicit external image-system references
- manually curated image evidence attached to current papers/claims

Do not start with:
- a full ingestion/management pipeline for arbitrary microscopy repositories

### Outputs

Possible bounded bundle:
- `storage/image_evidence/<image_evidence_id>/image_evidence.json`
- `storage/image_evidence/<image_evidence_id>/thumbnail.png`
- `storage/image_evidence/<image_evidence_id>/view_state.json`
- optional derived ROI/label/measurement sidecars

### Minimum model

Future contract should likely include:
- `image_evidence_id`
- `source_ref`
- `checksum`
- `content_format`
- `axes/shape/channel metadata`
- `view_state`
- `derived_outputs[]`
- `linked_claim_ids[]`
- `linked_artifact_ids[]`

## Raw / derived rule

This is the main boundary:
- raw image identity stays immutable and read-only
- thumbnails, crops, overlays, labels, measurements, and figure exports are derived outputs
- every derived output records provenance and tool context

## Viewer stance

The reports distinguish two external tool roles correctly:
- `napari` is the local viewer/overlay/handoff lane
- `OMERO` is the optional server/metadata/permission connector lane

Current recommendation:
- preserve that distinction
- do not collapse both into one immediate PaperPipe-native subsystem

## Integration points

### With claims and evidence

- a future image-evidence object should be attachable to a claim/evidence lineage path
- the image layer should augment current evidence rules, not replace them

### With Meeting Pack

- representative image cards are a plausible future downstream artifact
- but representative-image choice must preserve:
  - source image identity
  - view state
  - selection rationale
  - derived export provenance

## Suggested first slice

If this lane is reopened, the smallest current-system-safe slice is:
- metadata-only image evidence registry
- representative image card metadata
- view-state persistence
- external handoff to a local viewer
- no embedded microscopy platform

## Adoption gate

Promote this RFC only if all are true:
- users have repeated need to connect image evidence to claims/packs
- representative-image provenance matters enough to justify a bounded layer
- the first slice can remain metadata/provenance-first rather than platform-first

## Bottom line

This should become:
- an evidence-linked image sidecar layer

It should not become:
- a stealth microscopy platform rewrite inside current Lattice
