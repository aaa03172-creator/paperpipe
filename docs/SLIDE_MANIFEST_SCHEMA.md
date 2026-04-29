# Slide Manifest Schema

Status: Draft future seam
Date: 2026-04-20
Owner: Runtime/artifact maintainers
Canonical parents:
- `docs/Lattice_v3_Master_Spec.md`
- `docs/PaperPipe_Minimum_Operating_Principles.md`
- `docs/TALK_PACK.md`
- `docs/DERIVED_ARTIFACT_MANIFEST_SCHEMA.md`

Related docs:
- `docs/TALK_PACK_QUALITY_BENCHMARK.md`
- `docs/TALK_PACK_EVALUATION_RUBRIC.md`
- `docs/TALK_PACK_STYLE_GUIDE.md`
- `docs/PRESENTATION_REVIEW_SCHEMA.md`
- `docs/KEY_NUMBERS_SPEC.md`
- `docs/TALK_PACK_REFERENCE_CONTRACT.md`

## Purpose

Define the safest future minimum schema for `slide_manifest.json` as a talk-pack-local seed artifact.

This schema exists to keep future slide manifests:
- machine-readable
- ordered
- traceable back to stronger upstream owners
- useful as the regenerateable seed for `deck.pptx` and `speaker_script.md`

without:
- turning slide layout into a new truth layer
- promoting `deck.pptx` into the owner
- expanding into a generic presentation DSL

## Current Judgment

At the current repo stage, `slide_manifest.json` is only safe as:
- a future talk-pack-local `derived_manifest`
- a machine-readable seed member that sits below `talk_pack.json`
- the strongest structured bridge between selected evidence and rendered presentation members

It is not yet safe as:
- a standalone runtime family
- a full slide-design or layout engine
- a replacement for `talk_pack.json`, upstream owners, or evidence review

Current status:
- no active `slide_manifest.json` runtime artifact exists yet
- this doc is a bounded design target for a future talk-pack lane

## Current Scope

The safe current scope is:
- one `talk_pack_id`
- one ordered slide sequence
- optional backup slides
- slide-level traceability to claims, key numbers, and supporting artifacts

Safe current target members:
- `deck.pptx`
- `speaker_script.md`
- `quick_review.md`

## Non-Goals

This schema does not define:
- x/y coordinates or visual theme tokens
- editable slide canvas state
- transcript timing analytics
- multi-paper deck composition

## 1. Layer Rules

### 1.1 The manifest stays seed-like and non-canonical

`slide_manifest.json` is a `derived_manifest`.

Current rule:
- it must remain subordinate to `talk_pack.json`
- it must not replace upstream evidence-linked owners
- it must not become the sole truth holder for the rendered deck

### 1.2 Slide identity stays pack-local

Recommended primary ids:
- `talk_pack_id`
- `slide_id`

Current rule:
- `slide_id` only needs to be stable within one talk pack
- do not create a separate slide-root identity that outranks the pack owner

### 1.3 Content intent outranks layout detail

The manifest should describe:
- slide order
- slide role
- title and primary message
- talk-time priority
- traceability

It should not describe:
- precise box geometry
- fonts, theme, or animation systems
- editor-specific canvas metadata

## 2. Minimum Shape

```json
{
  "schema_version": "draft",
  "workflow": "talk_pack_slide_manifest",
  "talk_pack_id": "...",
  "paper_slug": "...",
  "generated_at": "2026-04-20T09:00:00Z",
  "talk_mode": "journal_club",
  "audience_profile": "mixed_research_group",
  "duration_minutes": 12,
  "max_slides": 10,
  "slides": []
}
```

Current notes:
- `duration_minutes` and `max_slides` should mirror the talk-pack request when available
- `max_slides` should be treated as a soft planning target rather than a hard deck-size cap
- `time fit` and `main` vs `backup` separation matter more than raw slide count alone
- `slides[]` should remain the ordered source for downstream script or deck generation

## 3. Slide Entry Shape

Recommended minimum slide entry:

```json
{
  "slide_id": "s01",
  "order": 1,
  "slide_kind": "main",
  "section": "opening",
  "title": "Short-chain fatty acids may shape colonic immune tone",
  "primary_message": "The paper matters because SCFAs are the mechanistic hook.",
  "speaker_priority": "must_say",
  "time_budget_seconds": 45,
  "claim_refs": ["claim_4d5f89ab12cd"],
  "key_number_refs": ["kn_01"],
  "evidence_refs": [],
  "source_artifact_refs": ["synth_20260420_wenzel"],
  "visual_refs": [],
  "visual_layout": "pair_equal",
  "visual_labels": [],
  "notes_focus": [
    "Define SCFAs in audience-appropriate language",
    "State why this paper matters before methods"
  ],
  "warnings": []
}
```

Recommended fields:
- `slide_id`
- `order`
- `slide_kind`
- `section`
- `title`
- `primary_message`
- `speaker_priority`
- `time_budget_seconds`
- `claim_refs`
- `key_number_refs`
- `evidence_refs`
- `source_artifact_refs`
- `visual_refs`
- `visual_layout`
- `visual_labels`
- `notes_focus`
- `warnings`

Current rule:
- every main slide should expose the one message it is trying to carry
- references should point to stronger owners or talk-pack-local seed artifacts rather than freeform prose only
- `claim_refs[]` should use current stable upstream claim ids
- optional `evidence_refs[]` should directly reuse `ChatEvidenceRef` rather than a talk-pack-only locator shape
- when a slide carries two visuals, the current bounded runtime supports `pair_equal`, `primary_supporting`, or `main_plus_inset` rather than arbitrary canvas geometry

## 4. Recommended Vocabulary

Recommended `slide_kind` values:
- `main`
- `backup`

Recommended `section` values:
- `opening`
- `background`
- `question`
- `methods`
- `results`
- `limitations`
- `conclusion`
- `backup`

Recommended `speaker_priority` values:
- `must_say`
- `nice_to_say`
- `skip_if_short_on_time`

Current rule:
- keep vocabularies compact
- put nuance in prose fields rather than exploding enum counts

## 5. Required Traceability

Minimum talk-pack traceability should work like this:
- `claim_refs[]` point to stronger claim-bearing upstream artifacts when available
- `key_number_refs[]` point to rows or ids from `key_numbers.md`
- `evidence_refs[]` may reuse the current `paper_slug` / `claim_id` / `evidence_id` / `run_id` / `locator` family when direct evidence reopening matters
- `source_artifact_refs[]` point to saved upstream artifacts such as `paper_synthesis`, `meeting_pack`, or `chart_pack`
- `visual_refs[]` point to selected bounded visual members when a slide depends on them
- `visual_labels[]` may carry short audience-facing labels for those visuals without replacing raw refs
- top-level `style_profile` may carry the bounded deck baseline style used for render
- top-level `template_attachment_refs[]` may carry future user-supplied template/style references without making them stronger than `talk_pack.json`

Current rule:
- a slide should never depend on an untraceable key numeric statement
- if a slide makes a quantitative claim, `key_number_refs[]` should not be empty
- current runtime lane allows at most two bounded `visual_ref` entries per slide
- `visual_layout` may currently be omitted, `pair_equal`, `primary_supporting`, or `main_plus_inset`
- a future manifest target may allow a slide to carry as many visuals as it needs to explain the claim, but not more than the audience can parse in the allotted time
- current bounded visual-ref examples include:
  - `chart_pack_render:<chart_pack_id>:<chart_id>[:svg]`
  - `image_evidence_derivative:<image_evidence_id>:<artifact_subpath>`

## 6. Relationship To Other Talk-Pack Members

`slide_manifest.json` is the structured bridge between upstream evidence and downstream exports.

Current rule:
- `deck.pptx` should render from the manifest rather than bypassing it
- `speaker_script.md` should align with manifest order and primary messages
- `key_numbers.md` should hold the exact numeric sidecar that the manifest points to

Direct deck edits may exist later, but they should not silently rewrite the manifest or sever traceability.

## 7. Conclusion

The safest future `slide_manifest.json` is:
- additive to the owner file
- non-canonical
- ordered
- traceable
- focused on message structure rather than editor geometry

That is enough structure to support regenerateable talk-pack outputs without turning PaperPipe into a slide editor.
