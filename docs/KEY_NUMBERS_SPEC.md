# Key Numbers Spec

Status: Draft future seam
Date: 2026-04-20
Owner: Runtime/artifact maintainers
Canonical parents:
- `docs/Lattice_v3_Master_Spec.md`
- `docs/PaperPipe_Minimum_Operating_Principles.md`
- `docs/TALK_PACK.md`
- `docs/Evidence_and_Uncertainty_Rules.md`

Related docs:
- `docs/SLIDE_MANIFEST_SCHEMA.md`
- `docs/TALK_PACK_EVALUATION_RUBRIC.md`
- `docs/TALK_PACK_STYLE_GUIDE.md`
- `docs/PRESENTATION_REVIEW_SCHEMA.md`
- `docs/STYLE_LINT_SCHEMA.md`
- `docs/TALK_PACK_REFERENCE_CONTRACT.md`

## Purpose

Define the safest future minimum contract for `key_numbers.md` as a talk-pack-local numeric sidecar.

This spec exists to keep future key-number sidecars:
- human-readable
- easy to audit
- recoverable back to stronger upstream owners
- safe to reuse across `slide_manifest.json`, scripts, quick review, and deck text

without:
- pretending to be the canonical evidence source
- collapsing all numeric output into a polished deck
- expanding into a full analysis report replacement

## Current Judgment

At the current repo stage, `key_numbers.md` is only safe as:
- a future talk-pack-local `context_artifact`
- a human-readable numeric sidecar for selected presentation-critical values
- the traceable bridge between upstream analysis outputs and downstream rendered talk members

It is not yet safe as:
- a standalone runtime family
- a replacement for analysis artifacts, canonical paper state, or evidence review
- a generic stats report format

Current status:
- no active `key_numbers.md` runtime artifact exists yet
- this doc is a bounded design target for a future talk-pack lane

## Current Scope

The safe current scope is:
- one `talk_pack_id`
- selected presentation-critical numeric statements only
- exact values, display values, units, comparators, and uncertainty notes

Safe current downstream uses:
- `slide_manifest.json`
- `speaker_script.md`
- `quick_review.md`
- `deck.pptx`
- `qa_pack.md`

## Non-Goals

This spec does not define:
- a full statistical appendix
- all values from every table
- dynamic recomputation rules
- a replacement for the stronger upstream owner of each number

## 1. Layer Rules

### 1.1 The number sheet stays non-canonical

`key_numbers.md` is a talk-pack-local `context_artifact`.

Current rule:
- it must remain subordinate to `talk_pack.json`
- it must not replace upstream analysis outputs or canonical paper state
- it must not become the only place where a scientific number can be recovered

### 1.2 Human-readable does not mean unstructured

`key_numbers.md` should be readable by a person and easy for tooling to parse conservatively.

Current rule:
- prefer stable headings and stable table columns
- avoid freeform narrative-only number lists

## 2. Minimum Layout

The safest future shape is a Markdown file with stable metadata and tables.

Recommended minimum layout:

```md
# Key Numbers

Talk Pack ID: talkpack_...
Paper Slug: wenzelShortchainFattyAcids2020
Generated At: 2026-04-20T09:00:00Z

## Must-Know Numbers

| key_number_id | label | display_value | exact_value | unit | comparator | claim_refs | upstream_owner_ref | source_location | uncertainty_note |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| kn_01 | Colonocyte butyrate concentration | 12.4 mM | 12.37 | mM | baseline stool sample | claim_4d5f89ab12cd | analysis_run_20260420_wenzel | table_2:row_4 | Rounded for oral delivery |

## Evidence Refs (optional)

### kn_01

```json
[
  {
    "paper_slug": "wenzelShortchainFattyAcids2020",
    "claim_id": "claim_4d5f89ab12cd",
    "evidence_id": "evidence_a13c09ef9201",
    "run_id": "run_20260420_090000",
    "locator": {
      "page": 5,
      "table_id": "table_2",
      "cell_id": "r4c2"
    }
  }
]
```
```

Current notes:
- the file may later add sections such as `Methods / sample`, `Main findings`, and `Limitations / caveats`
- the minimum stable contract is the metadata header plus at least one tabular section
- if optional nested `evidence_refs` are present, they should be serialized in a separate `## Evidence Refs (optional)` section keyed by `key_number_id`
- nested `evidence_refs` should not be stuffed into table columns as JSON blobs

## 3. Required Entry Fields

Recommended per-number fields:
- `key_number_id`
- `label`
- `display_value`
- `exact_value`
- `unit`
- `comparator`
- `claim_refs`
- `upstream_owner_ref`
- `source_location`
- `uncertainty_note`

Recommended optional fields when truly needed:
- `evidence_refs` (serialized in a separate keyed section, not inline table columns)
- `used_by`
- `rounding_note`
- `direction`

Current rule:
- `display_value` is what the audience may see or hear
- `exact_value` is what the system can reopen when challenged
- `claim_refs` should use current stable upstream claim ids rather than rendered prose or legacy source ids
- optional `evidence_refs` should directly reuse `ChatEvidenceRef` if span-level reopening is needed
- optional `evidence_refs` in Markdown should be serialized in a dedicated keyed section rather than as nested table cells
- `upstream_owner_ref` must point to a stronger owner than the talk pack

## 4. Recommended Number Categories

Recommended sections:
- `Must-Know Numbers`
- `Methods / sample`
- `Main findings`
- `Limitations / caveats`

Current rule:
- the file should contain only numbers that matter for the selected talk outputs
- do not dump every table cell into the talk pack

## 5. Relationship To The Slide Manifest

`slide_manifest.json` should point to `key_number_id` values rather than repeating opaque numeric prose.

Current rule:
- if a slide makes a quantitative claim, the matching `key_number_id` should be recoverable
- if a number is reused across multiple slides or outputs, the sidecar should remain the stable local reference
- the sidecar should keep at least one upstream claim-level reopening path for each presentation-critical number

## 6. Relationship To Style And Review

`key_numbers.md` supports both evidence honesty and style normalization.

Current rule:
- presentation review may fail when a key number cannot be reopened
- style lint may warn when rendered values drift from the agreed display format
- neither review file should replace the stronger numeric owner behind the sidecar

## 7. Conclusion

The safest future `key_numbers.md` is:
- additive
- non-canonical
- human-readable
- traceable
- narrow enough to support presentation outputs without replacing analysis artifacts

That is the right role for a talk-pack number sidecar in PaperPipe.
