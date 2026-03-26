# Bounded Lane Terminology Consistency Review

Status: Dated review note  
Date: 2026-03-24  
Owner: Runtime/design maintainers  
Scope: `Meeting Pack`, `Method Comparison`, `Chart Pack`, `Image Evidence`, `Protocol Knowledge`

## Purpose

Check whether the active bounded-lane specs use the same core terminology for:
- derived vs canonical
- bundle-local primary files
- read-first viewers
- second-truth-store rejection

This note is not a new spec.

## Current judgment

The bounded-lane family is already mostly consistent.

Shared vocabulary that is now stable:
- bounded artifact family or bounded sidecar artifact family
- file-backed storage
- read-first or read-only inspection surface
- no second canonical truth store
- explicit provenance/lineage reuse

The remaining drift was small and wording-level, not architectural:
- `Chart Pack` used `artifact-first`, which can read like a product-shape shorthand instead of a lane-local source rule
- `Method Comparison` did not explicitly name `comparison.json` as the primary bundle-local manifest
- `Protocol Knowledge` still used the broader phrase `saved knowledge artifacts` and did not explicitly call out `protocol_card.json` as the primary bundle-local file

## Repo-grounded anchors

- `src/chart_packs/store.py`
  - `chart_pack.json` is the root JSON manifest written and loaded for the pack bundle
- `src/method_comparisons/store.py`
  - `comparison.json` is the root JSON manifest written and loaded for the comparison bundle
- `src/protocol_cards/store.py`
  - `protocol_card.json` is the root JSON manifest written and loaded for the protocol bundle

## Small fixes applied

### 1. `Chart Pack`

Patched:
- `artifact-first` -> `source-artifact-driven`
- storage section now explicitly says `chart_pack.json` is the primary bundle-local manifest and that markdown/data/spec files are sibling derived bundle members

Why:
- this keeps the lane about named source artifacts, not about claiming `artifact-first` as a broader product identity

### 2. `Method Comparison`

Patched:
- `comparison artifact` -> `comparison artifact family`
- storage section now explicitly says `comparison.json` is the primary bundle-local manifest and CSV/Markdown are sibling derived exports

Why:
- this aligns the lane with the rest of the bounded artifact family wording and makes the bundle contract easier to compare with other lanes

### 3. `Protocol Knowledge`

Patched:
- storage section now explicitly says `protocol_card.json` is the primary bundle-local identity/metadata file and `versions/*.json` remain bundle-local version members
- `saved knowledge artifacts` -> `saved protocol-reference artifacts`

Why:
- this keeps the lane narrow and avoids broader “knowledge platform” overtones

## Result after patch

After the patch, the bounded-lane family reads more consistently:
- each lane has a primary bundle-local manifest or metadata file
- sibling files are additive derived members inside the same bundle
- each lane stays read-first and file-backed
- each lane rejects becoming a second canonical truth store

## Remaining minor differences that are acceptable

- `Meeting Pack` remains the richest readiness/regeneration lane and therefore uses more operational vocabulary than the others
- `Image Evidence` remains a sidecar/metadata-first lane and therefore uses raw-vs-derived wording that is slightly more specific than the others
- `Protocol Knowledge` is version-first, so it needs explicit version-member language that other lanes do not

These are bounded functional differences, not terminology bugs.

## Bottom line

No new family-wide spec is needed.

The bounded-lane terminology is now consistent enough that future work should prefer reusing:
- `primary bundle-local manifest` or `primary bundle-local metadata file`
- `sibling derived bundle members`
- `read-first` / `read-only inspector`
- `derived artifact, not a second canonical truth store`

over inventing a new lane-local phrasing.
