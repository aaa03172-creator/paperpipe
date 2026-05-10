# Talk Pack Evaluation Rubric

Status: Draft future seam  
Date: 2026-04-20  
Owner: Runtime/artifact maintainers  
Canonical parents:
- `docs/Lattice_v3_Master_Spec.md`
- `docs/PaperPipe_Minimum_Operating_Principles.md`
- `docs/ARTIFACT_BUNDLE_SPEC.md`
- `docs/EXPORT_PACK_SPEC.md`
- `docs/REVIEW_GATE_SCHEMA.md`

Related docs:
- `docs/TALK_PACK.md`
- `docs/TALK_PACK_QUALITY_BENCHMARK.md`
- `docs/MEETING_PACK.md`
- `docs/PAPER_SYNTHESIS.md`
- `docs/Evidence_and_Uncertainty_Rules.md`
- `docs/DERIVED_ARTIFACT_MANIFEST_SCHEMA.md`
- `docs/TALK_PACK_STYLE_GUIDE.md`
- `docs/TALK_PACK_REFERENCE_CONTRACT.md`
- `docs/SLIDE_MANIFEST_SCHEMA.md`
- `docs/KEY_NUMBERS_SPEC.md`
- `docs/PRESENTATION_REVIEW_SCHEMA.md`

## Purpose

Define the safest future evaluation seam for a paper-scoped `talk_pack`.

This rubric exists to keep future talk-pack review:
- evidence-linked
- paper-scoped
- additive to the owning pack manifest
- explicit about both presenter readiness and evaluator-facing quality

without:
- making `deck.pptx` the truth owner
- turning PaperPipe into a generic presentation-coaching platform
- letting delivery polish silently outrank evidence integrity or upstream lineage

## Current Judgment

At the current repo stage, a talk-pack evaluation rubric is only safe as:
- a future additive review artifact for a paper-scoped talk pack
- a bounded bridge between export generation and final handoff
- a way to keep presentation prep honest without promoting presentation files into canonical truth

It is not yet safe as:
- an active runtime family by itself
- a generalized presentation scoring engine
- a replacement for current pack manifests, review gates, or canonical paper state

Current status:
- no active `talk_pack` runtime family exists yet
- no active `presentation_review.json` runtime artifact exists yet
- this rubric is a bounded design target for a future talk-pack lane

## Current Scope

The safe current scope is:
- one paper
- one talk purpose
- one selected audience profile
- one selected duration target
- one selected export set
- one additive review artifact attached to the generated talk pack

Safe future examples of review targets:
- `slide_manifest.json`
- `speaker_script.md`
- `qa_pack.md`
- `quick_review.md`
- `deck.pptx`

Current rule:
- the rubric evaluates the talk-pack outputs and their readiness
- the rubric does not become a stronger owner than `talk_pack.json` or upstream canonical state

## Non-Goals

This spec does not define:
- a live slide editor
- a universal speech-coaching system
- a prose-only deck critique service detached from evidence lineage
- a replacement for `Meeting Pack` or other current bounded lanes
- a requirement that every future talk pack generate every possible presentation artifact

## 1. Talk-Pack Layer Rules

### 1.1 The rubric stays additive

Any future talk-pack evaluation artifact stays a sibling review artifact.

Current rule:
- it may summarize readiness, risks, and missing pieces
- it should be treated as a non-canonical `review_gate_artifact`
- it must not replace `talk_pack.json` as the pack owner
- it must not replace upstream evidence-linked state as scientific truth

### 1.2 The review stays evidence-first

Presentation quality matters, but evidence integrity remains the primary boundary.

Current rule:
- slide-level claims, key numbers, and take-home points must remain traceable to stronger upstream owners
- a polished deck with weak traceability must review as weak, partial, or warning-heavy rather than silently passing

### 1.3 Presenter and evaluator views stay distinct

The same pack needs two different review lenses:
- `presenter_view`
- `evaluator_view`

`presenter_view` asks:
- can the speaker deliver this talk safely and coherently?

`evaluator_view` asks:
- would an experienced reviewer judge this talk as clear, honest, and appropriately evidence-backed?

Current rule:
- do not collapse these into one vague score
- keep the two perspectives visible even if some checks overlap

### 1.4 Output selection stays explicit

A future talk pack may not generate every possible artifact.

Current rule:
- review only the selected outputs plus any required dependencies
- missing optional artifacts should not fail the pack
- missing required dependencies should fail or warn explicitly

### 1.5 Delivery polish stays subordinate

Slide aesthetics, phrasing smoothness, and notes quality are downstream concerns.

Current rule:
- delivery polish may improve the talk pack
- delivery polish must not mask missing evidence, missing caveats, or unverified numbers

## 2. Recommended Generation Workflow Checkpoints

The safest future talk-pack workflow is:

1. `Intent lock`
   - capture `talk_mode`, `audience_profile`, `duration_minutes`, `context`, `selected_exports[]`
2. `Outline lock`
   - produce or approve a slide-level outline before deck/script generation
3. `Evidence lock`
   - compile the key claims, key numbers, limitations, and required supporting references for the selected outline
4. `Pack seed generation`
   - write `talk_pack.json`
   - write `slide_manifest.json`
   - write `key_numbers.md` or equivalent machine-readable key-number sidecar
5. `Selected export generation`
   - generate only the chosen outputs plus required dependencies
6. `Additive review`
   - run presenter-view and evaluator-view checks
7. `Handoff summary`
   - keep generated, skipped, blocked, and warning-heavy outputs explicit

Current rule:
- do not generate `deck.pptx` as the first or only structured artifact
- create the manifest-like owner and slide/evidence scaffolding first

## 3. Minimum Selected-Output Rules

Recommended talk-pack outputs:
- `deck.pptx`
- `speaker_script.md`
- `qa_pack.md`
- `quick_review.md`
- `slide_manifest.json`
- `key_numbers.md`

Recommended dependency rules:
- if `deck.pptx` is selected, require `slide_manifest.json`
- if `speaker_script.md` is selected, require `slide_manifest.json`
- if `qa_pack.md` is selected, require limitations and contradiction-ready source context
- if `quick_review.md` is selected, require verified key numbers and take-home points

Current rule:
- the system should review missing required dependencies explicitly
- it should not pretend a selected output is ready when its upstream prerequisites were skipped

## 4. Presenter-View Rubric

The presenter view is about delivery readiness without drifting into pure performance coaching.

Recommended presenter-view categories:

### 4.1 Audience fit

Check whether:
- the framing matches the selected audience profile
- specialized terms are introduced at the right depth
- unnecessary detail is removed for the chosen audience

### 4.2 Time fit

Check whether:
- the deck fits the target duration even when raw slide count is not minimal
- `main` slide count and `backup` slide count are judged separately
- the script length fits the target duration
- the pack identifies what is core vs optional if time runs short
- the pack makes a `cut-for-time` path explicit when the selected talk mode needs one

### 4.3 Narrative flow

Check whether:
- the talk has a clear opening, problem, methods/results arc, and close
- slide transitions are coherent
- take-home messages are explicit rather than buried

### 4.4 Slide economy

Check whether:
- each slide has one primary message
- text density is reasonable
- visual or numeric overload is flagged

### 4.5 Figure explainability

Check whether:
- every figure-heavy slide says what the audience should notice
- the pack distinguishes descriptive visuals from inferential claims
- the speaker can explain axis, comparator, and key contrast without improvising
- the deck includes enough visuals for the claim rather than enforcing an artificially low one-visual ceiling

### 4.6 Q&A readiness

Check whether:
- common methodological, domain, generalist, and trainee questions are covered
- answers acknowledge limitations honestly before defending the contribution
- contradiction-ready or limitation-ready prompts exist when needed

## 5. Evaluator-View Rubric

The evaluator view is about how an experienced seminar reviewer, PI, faculty evaluator, or discussant would judge the talk.

Recommended evaluator-view categories:

### 5.1 Scientific fidelity

Check whether:
- key claims and key numbers trace back to upstream owners
- caveats and limitations are present
- causal or clinical overclaiming is avoided

### 5.2 Structure and clarity

Check whether:
- the objectives are explicit
- methods and results are separated cleanly
- the conclusion matches what the talk actually showed

### 5.3 Evidence honesty

Check whether:
- contradictory evidence is acknowledged when relevant
- weak or uncertain findings remain weak or uncertain in the talk
- summary slides do not overcompress away important nuance

### 5.4 Slide judgment

Check whether:
- slide titles say what the slide is for
- figures and tables are legible enough for the audience and setting
- decorative choices do not obscure the scientific point

### 5.5 Discussion quality

Check whether:
- implications are proportional to the evidence
- limitations are discussed in an intellectually honest way
- the speaker is prepared to answer "why should we care?" and "what would change your conclusion?"

### 5.6 Overall seminar readiness

Check whether:
- the deck would read as competent and prepared in a real lab meeting, journal club, or coursework talk
- the generated outputs would help an evaluator trust the talk rather than merely admire the formatting

## 6. Minimum Review Artifact Shape

The safest future talk-pack review artifact is:

```json
{
  "schema_version": "draft",
  "workflow": "talk_pack_review",
  "talk_pack_id": "...",
  "paper_slug": "...",
  "overall_status": "warn",
  "reason_codes": [],
  "presenter_view": {
    "overall_status": "warn",
    "checks": []
  },
  "evaluator_view": {
    "overall_status": "warn",
    "checks": []
  },
  "required_outputs": [],
  "selected_outputs": [],
  "missing_dependencies": [],
  "warnings": []
}
```

Recommended check shape:

```json
{
  "name": "time_fit",
  "perspective": "presenter_view",
  "status": "warn",
  "severity": "medium",
  "detail": "Script length exceeds the selected duration target.",
  "target_artifacts": ["speaker_script.md", "slide_manifest.json"],
  "fixable_by_ai": true
}
```

Current rule:
- keep the artifact machine-readable
- keep the target artifacts explicit
- keep the reason for failure or warning visible without turning the file into a prose essay

## 7. Recommended Hard-Fail And Warn Conditions

Recommended hard-fail conditions:
- selected output is missing a required dependency
- key numeric claim is unverified
- slide-level claim cannot reopen trust to an upstream owner
- the talk conclusion materially overstates the evidence

Recommended warn conditions:
- script length likely exceeds target duration
- slide density is high
- Q&A preparation is shallow for the talk type
- limitations are present but underdeveloped
- evaluator-facing objections are not well covered

Current rule:
- hard-fail logic should stay narrow and explicit
- warning logic should help the operator decide whether to regenerate, trim, or continue manually

## 8. Presenter-Ready Vs Evaluator-Ready

A future implementation may expose two bounded readiness summaries:
- `presenter_ready`
- `evaluator_ready`

Recommended interpretation:
- `presenter_ready=true`
  - the speaker can plausibly deliver the talk safely with the current pack
- `evaluator_ready=true`
  - the talk would likely hold up under experienced academic review for the selected context

Current rule:
- do not equate these states automatically
- a talk can be presenter-ready but still evaluator-warning-heavy

## 9. Relationship To Current Bounded Lanes

- `Meeting Pack` remains the strongest current discussion-oriented bounded lane.
- A future `talk_pack` should not replace `Meeting Pack`; it should specialize the presentation/export branch.
- `Chart Pack` may contribute selected visuals or figures, but it should remain a separate owner lane.
- `Paper Synthesis` or other compiled-knowledge artifacts may feed the talk pack, but they must remain stronger owners than any polished presentation export.

## 10. Conclusion

The most valuable future use of a talk-pack rubric is not scoring presentation style for its own sake.

It is to keep future presentation artifacts:
- honest about evidence strength
- explicit about audience and time fit
- explicit about missing dependencies
- explicit about what a speaker can safely present
- explicit about what an experienced evaluator would likely challenge

That is the safest way to let PaperPipe support presentation outputs without letting `deck.pptx` become the product's hidden truth owner.
