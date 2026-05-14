# Visual Evidence Ledger Contract

Status: Proposed additive contract
Date: 2026-05-10
Owner: PaperPipe/Lattice runtime maintainers
Canonical parent: `docs/Lattice_v3_Master_Spec.md`

## Purpose

PaperPipe reads biomedical PDFs where figure, table, plot, microscopy, diagram, and supplementary visual content can support claims. Long reader, synthesis, and report generation can lose visual grounding even when text evidence remains grounded. This contract defines a workflow-level persistent visual memory layer: visual evidence is recorded as reviewable ledger entries and replayed before final user-facing generation.

This contract does not adopt model-internal visual memory, model training, VLM attention changes, Qwen fine-tuning, or a PDF parser replacement.

## Layer Boundary

`visual_evidence_ledger.json` is a `review_gate_artifact` with `canonical_status=non_canonical`.

It is subordinate to:

- raw PDF/source files
- `document_artifact.json`
- `claimset.resolved.json`
- schema-backed canonical structured state

It may support review gates, report generation, and UI inspection, but it must not become a second scientific truth store.

## Schema Sketch

Runtime schema: `src/schemas/visual_evidence.py`

Sidecar builder: `src/services/visual_evidence_ledger.py`

`VisualEvidenceLedger`

- `schema_version`: `visual_evidence_ledger.v1`
- `layer`: `review_gate_artifact`
- `canonical_status`: `non_canonical`
- `paper_id`
- `run_id`
- `generated_at`
- `source_artifacts`: normally `document_artifact.json`, `figure_captions.json`, and `claimset.resolved.json`
- `entries`: `VisualEvidenceObject[]`
- `metrics`
- `generation_replay_required`: default `true`
- `final_answer_validation_required`: default `true`

`VisualEvidenceObject`

- `evidence_id`
- `kind`: `figure`, `table`, `plot`, `microscopy`, `diagram`, `supplementary_figure`, or `other`
- `page`: 0-indexed PDF page number
- `figure_id` or `table_id`
- `caption`
- `bbox`: optional PDF or percentage bbox
- `observed_elements`: direct visual observations only
- `observed_text`: OCR or visible text observations only
- `extracted_values`: table or visual numeric/value observations, with `table_id + cell_id` when cell-specific
- `allowed_claims`: claims that may be made from the observed visual evidence
- `not_allowed_claims`: claims that must not be made from this visual evidence alone
- `inferred_notes`: interpretation candidates that remain inference, not observation
- `status`: `observed`, `partially_observed`, `unknown`, or `unsupported`
- `failure_reason`: required for `unknown` or `unsupported`
- `linked_claim_ids`
- `source_artifact`

## Observed vs Inferred Rule

`observed_elements`, `observed_text`, and `extracted_values` must describe what the PDF visual/table actually exposes. Mechanism, causality, statistical significance, clinical translation, or biological interpretation belongs in `inferred_notes` unless the source text/table directly supports it.

Final generated claims may only cite visual evidence when the claim is present in `allowed_claims` or directly follows from `observed_elements`, `observed_text`, or `extracted_values`. If support is ambiguous, the claim remains `unknown` or `unsupported`.

## Replay Rule

Before final deep-read notes, paper syntheses, meeting packs, or long reports promote visual/table-backed claims, the generator should replay compact ledger entries:

- page
- figure_id or table_id
- caption
- observed_elements
- observed_text
- extracted_values
- allowed_claims
- not_allowed_claims
- status and failure_reason

The replay packet should be small and local. It should not resend full PDFs or raw memory to external inference paths.

## Validation Rule

Generated output fails visual grounding review when:

- it makes a figure/table claim with no matching ledger entry
- it turns `inferred_notes` into direct observation
- it ignores a `not_allowed_claims` constraint
- it uses `unknown` or `unsupported` evidence as if observed
- it cites a table-derived value without a table locator, or a cell locator when available
- it drops page plus figure/table identity in a long output that presents the claim as evidence-backed

## BBox Policy

BBox is optional in v1. Current runtime can store PDF text block bbox, but figure-region and panel-level bbox detection are not reliable enough to be mandatory. The v1 minimum is:

- `page`
- `figure_id` or `table_id`
- `caption` when available
- observed/unknown status
- allowed and not-allowed claim boundaries

Add figure bbox later only after the parser or visual extraction path can produce stable, reviewable regions.

## Failure Policy

OCR, vision, caption, or parser failures should not be repaired by guessing. Use:

- `status=unknown` with `failure_reason=vision_unavailable`, `ocr_failed`, `caption_only`, `ambiguous_panel`, or `not_reviewed`
- empty `allowed_claims`
- explicit `not_allowed_claims` when a common overclaim should be blocked

Unknown visual evidence may still be useful for navigation, but it is not evidence-backed support.

## Minimal Adoption Path

1. Keep the additive schema and sidecar builder isolated from parser/runtime rewrites.
2. Write `visual_evidence_ledger.json` from existing `document_artifact.json`, `figure_captions.json`, tables, and resolved claim links.
3. Replay the ledger in deep-read notes and paper synthesis before promoting figure/table-backed claims.
4. Add meeting pack replay only after meeting pack source resolution carries selected run artifact lineage, not just canonical structured state.
5. Add figure/table UI inspection only after the sidecar is stable.
