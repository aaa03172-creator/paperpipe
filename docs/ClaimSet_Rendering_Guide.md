# ClaimSet Rendering Guide

Status: Active reference
Date: 2026-03-09
Owner: Export/runtime maintainers
Canonical: `docs/ClaimSet_Rendering_Guide.md`
Canonical parent: `docs/Lattice_v3_Master_Spec.md`

This note explains how PaperPipe currently renders ClaimSet in exported Obsidian markdown.

## Render Location
- File: `src/exporter.py`
- Section title in note: `## Critical Review (ClaimSet)`

## Rendering Rules
- If a ClaimSet-like payload is available in `feedback_json` (`claims`, `ClaimSet.claims`, or `claimset.claims`), each claim is rendered as:
  - Claim
  - Evidence (`quote`, `page_num`, optional `link`)
  - Limitations
  - Confidence
- If ClaimSet is missing or invalid, exporter does not fail.
  - It renders: `ClaimSet: unavailable`
  - Other note content (summary/tags/references) is still exported.

## Evidence Link Behavior
- `page_num` is shown when available.
- `link` is optional and only shown when resolvable from existing context (currently Zotero key + page).
- No fabricated link is generated.

## Interpretation Tips
- `ClaimSet: unavailable` means the current DB row does not contain parseable claim structure.
- `NEEDS_READER` in `review_queue` means claim extraction should be run/recovered.
- `NEEDS_EVIDENCE_LINK` means claim evidence exists but location metadata is incomplete.
- `NEEDS_STATS_CHECK` means stats verdict includes `unverifiable` or `inconsistent`.
