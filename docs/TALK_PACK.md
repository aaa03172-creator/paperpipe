# Talk Pack

Status: Draft future seam  
Date: 2026-04-20  
Owner: Runtime/artifact maintainers  
Canonical parents:
- `docs/Lattice_v3_Master_Spec.md`
- `docs/PaperPipe_Minimum_Operating_Principles.md`
- `docs/ARTIFACT_BUNDLE_SPEC.md`
- `docs/EXPORT_PACK_SPEC.md`

Related docs:
- `docs/MEETING_PACK.md`
- `docs/PAPER_SYNTHESIS.md`
- `docs/CHART_PACK.md`
- `docs/TALK_PACK_SCHEMA_SKETCH.md`
- `docs/TALK_PACK_QUALITY_BENCHMARK.md`
- `docs/TALK_PACK_EVALUATION_RUBRIC.md`
- `docs/TALK_PACK_STYLE_GUIDE.md`
- `docs/TALK_PACK_REFERENCE_CONTRACT.md`
- `docs/SLIDE_MANIFEST_SCHEMA.md`
- `docs/KEY_NUMBERS_SPEC.md`
- `docs/PRESENTATION_REVIEW_SCHEMA.md`
- `docs/STYLE_LINT_SCHEMA.md`
- `docs/Evidence_and_Uncertainty_Rules.md`

## Purpose

`Talk Pack` is the safest future paper-scoped export lane for presentation-oriented handoff artifacts.

It exists to support:
- seminar or journal-club preparation
- evidence-linked deck generation
- speaker script and Q&A preparation
- bounded downstream handoff for one paper

without:
- making `deck.pptx` the truth owner
- turning PaperPipe into a generic slide workspace
- bypassing current paper/run/artifact truth with prompt-only presentation output

## Current Judgment

At the current repo stage, `Talk Pack` is only safe as:
- a future paper-scoped downstream artifact family
- a manifest-first export lane above current saved artifacts
- a presentation-oriented specialization beside `Meeting Pack`, not a replacement for it

It is not yet safe as:
- an active runtime family
- a prompt-to-deck generator with weak provenance
- a replacement for `Meeting Pack`, `Paper Synthesis`, or `Chart Pack`

Current status:
- no active `talk_pack` runtime family exists yet
- bounded `src/schemas/talk_pack.py`, `src/talk_packs/store.py`, `src/talk_packs/service.py`, and a thin router seam may exist without full prompt-to-pack generation
- a bounded `POST /talk-packs/{talk_pack_id}/render-deck` export step may exist for packs that already persist `slide_manifest.json` and `key_numbers.md`
- repeatable render smoke command may exist at `bash scripts/run_talk_pack_render_smoke.sh`
- repeatable verify command may exist at `bash scripts/run_talk_pack_verify.sh`
- the current render smoke may support opt-in bounded visual-source variants such as `--visual-source chart_pack` and `--visual-source image_evidence`
- this doc remains a bounded design target for fuller future implementation

## Current Scope

The safe current scope is:
- one paper
- one talk purpose
- one audience profile
- one duration target
- zero or more selected saved artifact refs for that same paper
- one bounded set of selected exports

Safe future outputs:
- `slide_manifest.json`
- `key_numbers.md`
- `speaker_script.md`
- `qa_pack.md`
- `quick_review.md`
- `deck.pptx`

Current non-owner render cache:
- `preview/slide-*.png`

Current rule:
- `Talk Pack` must stay paper-first
- it must name stronger upstream owners explicitly
- it must remain non-canonical
- render previews are review/cache files, not owner-declared `output_members[]`
- if future seed members need `evidence_refs[]`, they should directly reuse `ChatEvidenceRef` unless a stronger lane-local need appears

## Non-Goals

This spec does not define:
- a generic slide editor
- a visual design system
- multi-paper project presentation bundles
- open-ended prompt-to-presentation behavior
- direct replacement of current discussion-oriented `Meeting Pack`

## 1. Current Boundary

### 1.1 Paper-first, not prompt-first

The request must anchor to one paper and explicit saved artifacts.

Current rule:
- no freeform "make me a talk about this topic" contract
- no unscoped prompt-to-deck generation
- no multi-paper drift unless a later spec explicitly allows it

### 1.2 Owner file stays first-class

`talk_pack.json` must remain the owner file for the lane.

Current rule:
- `deck.pptx` is an export member, not the owner
- `speaker_script.md`, `qa_pack.md`, and `quick_review.md` are sibling members, not stronger truth owners
- review or style sidecars remain additive

### 1.3 Selected outputs stay explicit

The request may ask for only some outputs.

Current rule:
- selected outputs must be explicit
- required seed members and dependencies must also be explicit
- missing dependencies must remain visible rather than silently skipped

### 1.4 Upstream owners stay visible

`Talk Pack` should only package or derive from stronger saved owners.

Recommended owner kinds:
- `paper_state`
- `run_artifact`
- `derived_manifest`
- `review_gate_artifact`
- `context_artifact`

Current rule:
- if a saved derived artifact is used, the stronger owner behind it should remain reopenable
- talk-pack polish must not erase provenance

## 2. Generation Request Contract

The safest future request stays paper-first and selected-output-first.

```json
{
  "paper_slug": "wenzelShortchainFattyAcids2020",
  "title": "Optional custom title",
  "talk_mode": "journal_club",
  "audience_profile": "mixed_research_group",
  "duration_minutes": 12,
  "context": "Weekly lab journal club",
  "selected_exports": [
    "deck_pptx",
    "speaker_script",
    "qa_pack"
  ],
  "optional_extensions": [
    "clinical_implications"
  ],
  "style_profile": "paperpipe_baseline",
  "template_attachment_refs": [
    "attachment://smith-lab-journal-club-template.pptx"
  ],
  "supporting_artifact_refs": [
    {
      "artifact_family": "paper_synthesis",
      "ref": "synth_20260420_wenzel",
      "role": "preferred_summary"
    },
    {
      "artifact_family": "meeting_pack",
      "ref": "meetingpack_20260420_journal_club_wenzel",
      "role": "discussion_seed"
    },
    {
      "artifact_family": "chart_pack",
      "ref": "chartpack_20260420_wenzel",
      "role": "selected_visuals"
    }
  ],
  "max_slides": 10,
  "auto_include_dependencies": true
}
```

Current note:
- `max_slides` should be treated as a soft planning target rather than a hard runtime cap
- `duration_minutes`, `time_budget_seconds`, and `main` vs `backup` separation should outrank raw slide-count policing

Recommended `talk_mode` examples:
- `journal_club`
- `lab_meeting`
- `seminar`
- `grand_rounds`
- `coursework_presentation`

Recommended `selected_exports[]` examples:
- `slide_manifest`
- `key_numbers`
- `speaker_script`
- `qa_pack`
- `quick_review`
- `deck_pptx`

### Why this request shape

This request shape is safer because:
- it anchors to one paper
- it names the audience and time budget before rendering
- it preserves a bounded baseline `style_profile` without making the deck itself the new truth owner
- it leaves room for future user-supplied template/style attachments without requiring arbitrary pptx import today
- current runtime may use selected bounded template refs such as `attachment://paperpipe-audience-clean-16x9` as narrow render hints while keeping `talk_pack.json` as the owner
- it asks for selected outputs explicitly
- it allows saved artifact reuse without making those artifacts the new owner
- it leaves room for dependency auto-inclusion without hiding what the system actually generated

## 3. Required Seed Members And Dependency Rules

Recommended seed members:
- `slide_manifest.json`
- `key_numbers.md`

Recommended dependency rules:
- if `deck_pptx` is selected, require `slide_manifest`
- if `speaker_script` is selected, require `slide_manifest`
- if `qa_pack` is selected, require limitation-ready and contradiction-ready support
- if `quick_review` is selected, require verified key numbers

Current rule:
- seed members may be auto-included when dependencies require them
- the pack should record both `selected_outputs[]` and `required_outputs[]`

## 4. Owner Contract

The safest future owner file is a manifest-first `talk_pack.json`.

```json
{
  "talk_pack_id": "talkpack_20260420T090000123456Z_journal_club_a1b2c3d4",
  "paper_slug": "wenzelShortchainFattyAcids2020",
  "title": "Short-chain fatty acids journal club talk",
  "created_at": "2026-04-20T09:00:00Z",
  "updated_at": "2026-04-20T09:00:00Z",
  "status": "draft",
  "layer": "user_facing_artifact",
  "canonical_status": "non_canonical",
  "talk_mode": "journal_club",
  "audience_profile": "mixed_research_group",
  "duration_minutes": 12,
  "generation_request": {
    "paper_slug": "wenzelShortchainFattyAcids2020",
    "talk_mode": "journal_club",
    "selected_exports": ["deck_pptx", "speaker_script", "qa_pack"],
    "auto_include_dependencies": true
  },
  "regenerated_from_talk_pack_id": null,
  "upstream_owners": [
    {
      "owner_kind": "paper_state",
      "ref": "vault/.pp/wenzelShortchainFattyAcids2020/state.json",
      "role": "canonical",
      "note": "Primary paper-scoped truth owner"
    },
    {
      "owner_kind": "derived_manifest",
      "ref": "synth_20260420_wenzel",
      "role": "derived",
      "note": "Selected compiled summary"
    }
  ],
  "selected_outputs": [
    "deck_pptx",
    "speaker_script",
    "qa_pack"
  ],
  "required_outputs": [
    "slide_manifest",
    "key_numbers",
    "deck_pptx",
    "speaker_script",
    "qa_pack"
  ],
  "output_members": [
    {
      "kind": "slide_manifest",
      "path": "slide_manifest.json",
      "required": true,
      "status": "generated"
    },
    {
      "kind": "key_numbers",
      "path": "key_numbers.md",
      "required": true,
      "status": "generated"
    },
    {
      "kind": "speaker_script",
      "path": "exports/speaker_script.md",
      "required": true,
      "status": "generated"
    },
    {
      "kind": "qa_pack",
      "path": "exports/qa_pack.md",
      "required": true,
      "status": "generated"
    },
    {
      "kind": "deck_pptx",
      "path": "exports/deck.pptx",
      "required": true,
      "status": "generated"
    }
  ],
  "review_artifacts": [
    {
      "kind": "presentation_review",
      "path": "review/presentation_review.json",
      "role": "review_only"
    },
    {
      "kind": "style_lint",
      "path": "review/style_lint.json",
      "role": "review_only"
    }
  ],
  "warnings": [],
  "uncertainty_notes": []
}
```

### Notes on the owner contract

- `talk_pack.json` is the owner file.
- `output_members[]` track actual generated members rather than implying everything requested succeeded.
- `review_artifacts[]` remain additive.
- top-level readiness booleans such as `presenter_ready` or `evaluator_ready` should only be surfaced if they are derived from an additive review artifact rather than invented independently.

## 5. Recommended Storage Layout

```text
storage/talk_packs/<talk_pack_id>/
  talk_pack.json
  slide_manifest.json
  key_numbers.md
  exports/
    speaker_script.md
    qa_pack.md
    quick_review.md
    deck.pptx
  preview/
    slide-01.png
    slide-02.png
  review/
    presentation_review.json
    style_lint.json
```

Current rule:
- `talk_pack.json` stays the owner
- exported members remain sibling outputs
- `preview/slide-*.png` files are non-canonical render-cache files regenerated from `deck.pptx` render inputs, not declared output members
- loaders that enforce declared artifacts should reject preview-cache paths unless a later spec explicitly promotes previews into the manifest contract
- API clients may use a dedicated preview-cache route such as `/talk-packs/{talk_pack_id}/preview/slide-01.png`; they should not retrieve preview files through `/artifacts/...`
- review artifacts remain additive sidecars

## 6. Generation Flow

The safest future generation sequence is:

1. validate the request
2. resolve the anchored paper and any selected supporting artifacts
3. reopen key claims, key numbers, and limitations from stronger upstream owners
4. compute `required_outputs[]` from `selected_outputs[]`
5. generate seed members first
   - `slide_manifest.json`
   - `key_numbers.md`
6. persist `talk_pack.json` with the original `generation_request`
7. generate selected export members
8. persist additive review and style sidecars
9. surface generated, skipped, blocked, and warning-heavy members explicitly

Current rule:
- do not make `deck.pptx` the first or only persisted artifact
- do not hide partial generation behind a complete-looking owner file

## 7. Failure And Regeneration Rules

Recommended failure rules:
- missing paper anchor is a hard failure
- missing required dependency is a hard failure for the dependent output
- partial generation must remain explicit in `output_members[]`

Recommended regeneration rules:
- persist the original `generation_request`
- allow regenerate from saved intent when the current vault can still resolve the same paper and supporting refs
- treat member rerender and full regenerate as different actions

Current rule:
- avoid leaving a polished export behind without a coherent owner file
- avoid silently rewriting selected outputs with a different upstream owner set

## 8. Relationship To Current Bounded Lanes

### 8.1 Meeting Pack

`Meeting Pack` remains the strongest current discussion-oriented lane.

Current rule:
- `Talk Pack` should not replace `Meeting Pack`
- `Talk Pack` should specialize the presentation/export branch

### 8.2 Paper Synthesis

`Paper Synthesis` is a strong upstream compiled-knowledge input.

Current rule:
- it may be a preferred summary input
- it must remain a stronger owner than any polished presentation member

### 8.3 Chart Pack

`Chart Pack` is the bounded visual/data appendix lane.

Current rule:
- selected chart-pack members may feed a talk pack
- `Chart Pack` remains a separate owner lane

### 8.4 Image Evidence

`Image Evidence` is the bounded image-derived visual lane.

Current rule:
- selected declared image-evidence derivatives may feed a talk pack
- `Image Evidence` remains a separate owner lane

## 9. Future API Surface

If a runtime is added later, the safest first surface is:
- `GET /talk-packs`
- `GET /talk-packs/{talk_pack_id}`
- `POST /talk-packs/{talk_pack_id}/render-deck`
- `GET /talk-packs/{talk_pack_id}/artifacts/{artifact_path}`
- `POST /talk-packs/generate`
- `POST /talk-packs/{talk_pack_id}/regenerate`
- optional member rerender or export routes only after the owner contract is stable

Current rule:
- keep core logic in schema/service/store layers
- keep artifact reads bounded to paths declared by `talk_pack.json`
- keep routers thin
- do not create a CLI-only presentation path

## 10. Conclusion

The safest future `Talk Pack` is:
- paper-first
- manifest-first
- selected-output-first
- non-canonical
- explicit about dependencies and partial generation

That is the right boundary for PaperPipe:
- presentation-friendly
- provenance-visible
- additive to current lanes
- never a replacement for upstream evidence-linked truth.
