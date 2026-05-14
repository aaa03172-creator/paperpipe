# DocumentArtifact v2 Contract

Status: Active contract  
Date: 2026-03-09  
Owner: Artifact/runtime maintainers  
Canonical: `docs/document_artifact_v2.md`  
Canonical parent: `docs/Lattice_v3_Master_Spec.md`

## Purpose
- Provide a stable, shared artifact for Ingest/Reader/Stats/Indexer integration.
- Keep current v1 artifact intact; v2 is additive.

## Schema
- `DocumentArtifactV2`
  - `document_id`: stable document identifier (reuses legacy `doc_id`)
  - `meta`: title/authors/year/journal/doi/source_ref
  - `pages[]`
  - `tables[]` (table_id/caption/data/source_page)
- `PageV2`
  - `page_index`: 0-indexed page number
  - `width`, `height`: page dimensions in PDF points
  - `blocks[]`
- `BlockV2`
  - `block_id`: deterministic stable ID
  - `bbox_pdf`: `[x0, y0, x1, y1]` or `null`
  - `lines[]`
- `LineV2`
  - `line_id`: deterministic stable ID
  - `bbox_pdf`: `[x0, y0, x1, y1]` or `null`
  - `spans[]`
- `SpanV2`
  - `span_id`: deterministic stable ID
  - `bbox_pdf`: `[x0, y0, x1, y1]` or `null`
  - `source_ref` optional

## BBox Convention
- Coordinate system: PDF page coordinates in points.
- Origin: top-left.
- Order: `[x0, y0, x1, y1]`.
- Rule: if bbox is present, it must satisfy:
  - non-negative
  - `x0 <= x1`, `y0 <= y1`
  - inside page bounds (`x1 <= page.width`, `y1 <= page.height`)
- If bbox cannot be computed, set `bbox_pdf = null` and `bbox_unavailable = true`.

## Stable ID Guarantees
- IDs are deterministic hashes of immutable local features.
- Same PDF + same parser behavior => same IDs for page/block/line/span.
- Minimum compatibility guarantee for PR#2:
  - page and block IDs remain stable across repeated runs.

## Current Availability
- Implemented entrypoint:
  - `IngestAgent.process_v2(pdf_path)` in `src/agents/ingest_agent.py`
- Legacy path remains:
  - `IngestAgent.process(pdf_path)` -> `DocumentArtifact` v1
