# Bounded Artifact Handoff Surface Inventory

Date: 2026-04-21

## Purpose

This inventory locks the current active bounded artifact families against a simple question:

- if a sibling artifact is already persisted, is there an intentional read/handoff surface for it?
- if yes, is that surface typed, plain-text, or explicitly bounded raw file access?
- if no, is the omission intentional?

This is an inventory report, not a new runtime spec. It does not introduce a shared artifact platform or widen any existing family into a generic bundle browser.

## Current Matrix

| Family | Owner file | Persisted sibling artifacts | Current read/handoff surface | Boundary note | Status |
| --- | --- | --- | --- | --- | --- |
| `meeting_pack` | `meeting_pack.json` | `meeting_pack.md`, additive handoff JSON sidecars | `GET /meeting-packs/{pack_id}`, `GET /meeting-packs/{pack_id}/trace`, `GET /meeting-packs/{pack_id}/validate`, `GET /meeting-packs/{pack_id}/markdown` | Markdown is directly readable; trace/validate remain typed API surfaces rather than raw sidecar download. | `aligned` |
| `paper_synthesis` | `paper_synthesis.json` | `paper_synthesis.md` | `GET /paper-syntheses/{synthesis_id}`, `GET /paper-syntheses/{synthesis_id}/manifest`, `GET /paper-syntheses/{synthesis_id}/markdown` | Compatibility bundle route stays additive; structured provenance prefers `manifest`, prose handoff prefers `markdown`. | `aligned` |
| `talk_pack` | `talk_pack.json` | `slide_manifest.json`, `key_numbers.md`, selected `exports/*`, selected `review/*` | `GET /talk-packs`, `GET /talk-packs/{talk_pack_id}`, `GET /talk-packs/{talk_pack_id}/artifacts/{artifact_path}` | Raw access is bounded to declared generated/review artifacts only; no generic undeclared file browsing. | `aligned` |
| `method_comparison` | `comparison.json` | `comparison.csv`, `comparison.md` | `GET /method-comparisons/{comparison_id}`, `GET /method-comparisons/{comparison_id}/markdown`, `GET /method-comparisons/{comparison_id}/export.csv` | Markdown and CSV each have first-class bounded surfaces; no generic raw bundle route. | `aligned` |
| `chart_pack` | `chart_pack.json` | `chart_pack.md`, `data/*.csv`, `specs/*.json`, `renders/*.svg` | `GET /chart-packs/{chart_pack_id}`, `GET /chart-packs/{chart_pack_id}/markdown`, `GET /chart-packs/{chart_pack_id}/charts/{chart_id}/data.csv`, `.../spec.json`, `.../render.svg` | Markdown is pack-level; raw exports remain chart-scoped and declared, not bundle-generic. | `aligned` |
| `protocol_card` | `protocol_card.json` | `protocol_card.md`, `versions/*.json` | `GET /protocol-cards/{protocol_id}`, `GET /protocol-cards/{protocol_id}/markdown`, `GET /protocol-cards/{protocol_id}/versions`, `GET /protocol-cards/{protocol_id}/versions/{version_id}` | Markdown is plain-text handoff; version files remain typed JSON routes instead of raw file download. | `aligned` |
| `protocol_attachment` | attachment bundle JSON | preserved uploaded source, extracted markdown helper | `GET /protocol-cards/attachments/{attachment_bundle_id}`, `.../source`, `.../extracted-markdown` | Source and extracted markdown are both explicit attachment-scoped surfaces. | `aligned` |
| `image_evidence` | `image_evidence.json` | `view_state.json`, `handoff.json`, declared `derivatives/*` | `GET /image-evidence/{image_evidence_id}`, `GET /image-evidence/{image_evidence_id}/view-state`, `.../handoff`, `.../derivatives/{artifact_subpath}` | Derivatives are the only raw file surface; `view_state` and `handoff` intentionally stay typed metadata routes. | `aligned` |

## Findings

- No remaining `P1` handoff-symmetry gap was found in the active bounded families reviewed here.
- The current exceptions are intentional boundary choices, not missing routes:
  - `image_evidence` keeps `view_state.json` and `handoff.json` on typed routes instead of raw download.
  - `protocol_card` keeps `versions/*.json` on typed routes instead of raw download.
  - `chart_pack` exposes raw files only at declared chart-member surfaces (`data/spec/render`), not at pack-root generic paths.
  - `talk_pack` permits raw file reads only for artifacts explicitly declared by `talk_pack.json`.

## Out Of Scope

- `paper_notes`, `obsidian`, and vault note markdown were not treated as bounded artifact-family handoff lanes in this pass.
- Frontend consumption of these surfaces was not re-audited here.
- Write/generate surfaces were not expanded.

## Recommendation

- Keep the current lane boundaries.
- Use a shared regression to guard same-origin `/api/*` browser reads for these bounded handoff surfaces.
- Avoid adding any generic raw artifact browser unless a canonical doc explicitly adopts that model.
