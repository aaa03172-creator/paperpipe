# Style Lint Schema

Status: Draft future seam
Date: 2026-04-20
Owner: Runtime/artifact maintainers
Canonical parents:
- `docs/Lattice_v3_Master_Spec.md`
- `docs/PaperPipe_Minimum_Operating_Principles.md`
- `docs/TALK_PACK.md`
- `docs/TALK_PACK_STYLE_GUIDE.md`

Related docs:
- `docs/PRESENTATION_REVIEW_SCHEMA.md`
- `docs/TALK_PACK_REFERENCE_CONTRACT.md`
- `docs/KEY_NUMBERS_SPEC.md`
- `docs/REVIEW_GATE_SCHEMA.md`
- `docs/ARTIFACT_BUNDLE_SPEC.md`

## Purpose

Define the safest future minimum schema for `style_lint.json` as an additive talk-pack style sidecar.

This schema exists to keep future style lint:
- machine-readable
- additive
- bounded to one talk pack
- clearly separated from evidence or readiness truth

without:
- turning formatting polish into a stronger owner than the talk pack
- confusing style consistency with scientific correctness
- expanding into a generic slide-design system

## Current Judgment

At the current repo stage, `style_lint.json` is only safe as:
- a future talk-pack-local style sidecar
- an additive style-normalization helper
- a deterministic rebuild target from selected generated members

It is not yet safe as:
- a standalone runtime family
- a replacement for `presentation_review.json`
- a replacement for evidence review or evaluator judgment

Current status:
- no active `style_lint.json` runtime artifact exists yet
- this doc is a bounded design target for a future talk-pack lane

## Current Scope

The safe current scope is:
- one `talk_pack_id`
- one selected output set
- style findings for generated talk-pack outputs only

Safe current target artifacts:
- `speaker_script.md`
- `quick_review.md`
- `slide_manifest.json`
- `deck.pptx`

## Non-Goals

This schema does not define:
- biomedical validity checks
- talk scoring
- design-system tokens
- live editing history

## 1. Layer Rules

### 1.1 Style lint stays additive

`style_lint.json` is a non-canonical style sidecar.

Current rule:
- it must remain subordinate to `talk_pack.json`
- it must not replace `presentation_review.json`
- it must not be used as evidence truth or scientific truth

### 1.2 Findings stay lightweight

Style findings should remain easy to normalize.

Current rule:
- prefer compact, repeatable lint categories
- keep prose short and target-artifact-specific

## 2. Minimum Shape

```json
{
  "schema_version": "draft",
  "workflow": "talk_pack_style_lint",
  "talk_pack_id": "...",
  "paper_slug": "...",
  "generated_at": "2026-04-20T09:00:00Z",
  "overall_status": "warn",
  "selected_outputs": [],
  "findings": []
}
```

Current notes:
- `overall_status` here should summarize style posture only
- it must not be interpreted as overall presentation readiness by itself

## 3. Finding Shape

Recommended minimum finding shape:

```json
{
  "name": "capitalization_inconsistent",
  "category": "nit",
  "status": "warn",
  "detail": "Slide titles mix sentence case and title case.",
  "target_artifacts": ["deck.pptx", "slide_manifest.json"],
  "fixable_by_ai": true
}
```

Recommended fields:
- `name`
- `category`
- `status`
- `detail`
- `target_artifacts`
- `fixable_by_ai`

Recommended `category` vocabulary:
- `hard_fail`
- `warn`
- `nit`

Recommended `status` vocabulary:
- `pass`
- `warn`
- `fail`

Current rule:
- `category` captures style criticality
- `status` captures the current outcome for that rule

## 4. Recommended Hard-Fail Style Findings

Recommended `hard_fail` names:
- `overclaiming_language`
- `title_content_mismatch`
- `unverified_key_number_presentation`

Current rule:
- these are only style-lint findings when the issue is expressed through rendered talk-pack language
- upstream evidence review remains the stronger owner of the underlying truth problem

## 5. Recommended Warn Findings

Recommended `warn` names:
- `slide_density_high`
- `abbreviation_not_expanded`
- `figure_takeaway_missing`
- `cut_for_time_path_missing`
- `notes_repeat_slide_text`
- `transition_language_missing`

## 6. Recommended Nit Findings

Recommended `nit` names:
- `capitalization_inconsistent`
- `title_case_inconsistent`
- `punctuation_inconsistent`
- `numeric_formatting_inconsistent`
- `terminology_drift`
- `bullet_parallelism_drift`

## 7. Relationship To The Style Guide

- `docs/TALK_PACK_STYLE_GUIDE.md` defines what should be linted
- this schema defines how to persist the additive lint sidecar

Current rule:
- do not invent lint categories that the style guide does not support
- keep lint findings narrower than the human-facing style guide prose

## 8. Relationship To Presentation Review

`style_lint.json` and `presentation_review.json` should remain separate.

Current rule:
- `style_lint.json` answers "does this read consistently and scan cleanly?"
- `presentation_review.json` answers "is this talk ready and trustworthy?"

The two may point to the same artifact member, but they should not collapse into one file.

## 9. Conclusion

The safest future `style_lint.json` is:
- additive
- non-canonical
- narrowly scoped
- easy to regenerate
- useful for normalization without pretending to judge the science by itself

That is the right role for style lint in PaperPipe.
