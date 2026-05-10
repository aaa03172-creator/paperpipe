# Talk Pack Style Guide

Status: Draft future seam  
Date: 2026-04-20  
Owner: Runtime/artifact maintainers  
Canonical parents:
- `docs/Lattice_v3_Master_Spec.md`
- `docs/PaperPipe_Minimum_Operating_Principles.md`
- `docs/ARTIFACT_BUNDLE_SPEC.md`
- `docs/EXPORT_PACK_SPEC.md`

Related docs:
- `docs/TALK_PACK.md`
- `docs/TALK_PACK_QUALITY_BENCHMARK.md`
- `docs/TALK_PACK_EVALUATION_RUBRIC.md`
- `docs/MEETING_PACK.md`
- `docs/Evidence_and_Uncertainty_Rules.md`
- `docs/DERIVED_ARTIFACT_MANIFEST_SCHEMA.md`
- `docs/TALK_PACK_REFERENCE_CONTRACT.md`
- `docs/SLIDE_MANIFEST_SCHEMA.md`
- `docs/KEY_NUMBERS_SPEC.md`
- `docs/STYLE_LINT_SCHEMA.md`

## Purpose

Define the safest future style seam for paper-scoped `talk_pack` outputs.

This guide exists to keep future talk-pack outputs:
- clear
- consistent
- audience-aware
- subordinate to evidence-linked upstream state

without:
- turning style polish into a new truth layer
- confusing formatting consistency with scientific validity
- forcing every presentation artifact into one rigid template

## Current Judgment

At the current repo stage, a talk-pack style guide is only safe as:
- a future additive writing/rendering guide for selected talk-pack outputs
- a shared vocabulary for hard rules, strong conventions, and soft lint
- a bounded companion to the talk-pack evaluation rubric

It is not yet safe as:
- an active runtime formatter by itself
- a generic slide-design system
- a replacement for evidence review, review gates, or canonical state

Current status:
- no active `talk_pack` runtime family exists yet
- no active style-lint runtime exists yet
- this guide is a bounded design target for future talk-pack generation and review

## Current Scope

The safe current scope is:
- `slide_manifest.json`
- `speaker_script.md`
- `qa_pack.md`
- `quick_review.md`
- `deck.pptx`

Current rule:
- style guidance applies only to generated or reviewed talk-pack outputs
- style guidance does not override upstream evidence, caveats, or warning state
- current bounded runtime may honor a small render-hint seam from `template_attachment_refs[]` such as `attachment://paperpipe-audience-clean-16x9`, but this remains narrower than arbitrary template import

## Non-Goals

This guide does not define:
- a visual theme engine
- a generic speechwriting handbook
- a live typography or layout editor
- a reason to rewrite `Meeting Pack` or other current bounded lanes

## 1. Layer Rule

Any future talk-pack style artifact or lint result should be treated as:
- additive
- non-canonical
- subordinate to `talk_pack.json`
- subordinate to upstream evidence-linked owners

Current rule:
- style guidance may improve readability and delivery safety
- style guidance must not mask unresolved evidence, weak support, or unverified numbers

## 2. Three Rule Classes

The safest future talk-pack style system uses three classes:

### 2.1 Hard rules

Hard rules protect scientific trust or handoff integrity.

If broken, the output should fail or warn strongly.

### 2.2 Strong conventions

Strong conventions materially improve real presentation quality.

If broken, the output may still be usable, but it should usually warn.

### 2.3 Soft lint

Soft lint improves consistency and polish.

If broken, the output may still be acceptable, but it should be easy to normalize.

## 3. Hard Rules

Recommended hard rules:

### 3.1 Verified numbers only

- Every key number must be traceable to a stronger upstream owner.
- Rounded display values must not change the scientific meaning of the number.
- Exact values should remain recoverable from a stronger sidecar such as `key_numbers.md`.

### 3.2 No overclaiming

- Observational findings must not be presented as causal effects.
- Exploratory or weak findings must remain exploratory or weak in the talk.
- Clinical or practical implications must stay proportional to the evidence.

### 3.3 Title-content alignment

- Slide titles, take-home points, and conclusions must match what the slide or section actually shows.
- A title must not promise certainty when the body only supports uncertainty.

### 3.4 Abbreviation safety

- Abbreviations should be expanded on first use for the selected audience unless they are genuinely universal in that context.
- Drug names, models, or technical sequences that are likely unfamiliar should be disambiguated early.

### 3.5 Unit and comparator consistency

- Units, comparators, and reference groups must remain explicit and consistent.
- If one slide uses `Obese vs Normal`, later slides should not silently switch the comparator.

## 4. Strong Conventions

Recommended strong conventions:

### 4.1 One primary message per slide

- Each slide should have one clear main point.
- Supporting bullets, figures, or tables should reinforce that point rather than compete with it.

### 4.2 Message-first slide titles

- Prefer message-bearing titles over generic placeholders.
- Better: `Obesity was associated with 4.5x higher odds of diabetes`
- Worse: `Results`

### 4.3 Bounded slide density

- Prefer `3-5` bullets over dense prose blocks.
- Prefer one major figure or table focus per slide.
- When a slide is dense by necessity, the notes or manifest should say what the audience should focus on.

### 4.4 Methods / Results / Discussion separation

- Methods should explain what was done.
- Results should say what was found.
- Discussion should say what it means and what the limits are.
- Do not blur these modes on the same slide without explicit reason.

### 4.5 Core vs optional content

- The pack should distinguish what must be said from what can be skipped if time runs short.
- `cut-for-time` guidance is especially important for short talks or heavily loaded decks.

### 4.6 Figure guidance

- Figure-heavy slides should say what to notice.
- If a chart or table is easy to misread, notes should name the key comparison explicitly.
- A figure slide should not leave the speaker improvising the main takeaway.

### 4.7 Q&A realism

- Prepare likely methodological, domain, generalist, and trainee questions.
- Include at least the highest-risk objections, not only easy clarifications.

## 5. Soft Lint

Recommended soft-lint rules:

### 5.1 Sentence casing and capitalization

- The first letter of the first sentence should be capitalized.
- Choose `sentence case` or `title case` for slide titles and stay consistent across the pack.
- Do not mix capitalization styles without a clear reason.

### 5.2 Punctuation consistency

- Decide whether slide titles end with punctuation and keep the rule consistent.
- Keep bullets either all fragment-style or all full-sentence-style within the same slide family.
- Avoid alternating between semicolons, commas, and periods without a pattern.

### 5.3 Numeric formatting consistency

- Keep `%`, `n=`, `95% CI`, odds-ratio notation, and p-value style consistent.
- Do not vary decimal precision arbitrarily across equivalent values.
- Avoid false precision in slides; keep the exact value available in a stronger sidecar when needed.

### 5.4 Terminology consistency

- Use one preferred term per concept unless a contrast is intentional.
- If the pack starts with `body mass index (BMI)`, do not drift into mixed naming without reason.

### 5.5 Bullet parallelism

- Bullets within a list should use similar grammatical structure.
- Avoid mixing full paragraphs, noun phrases, and sentence fragments in the same cluster unless the difference is deliberate.

### 5.6 Layout-facing copy hygiene

- Avoid ALL CAPS except for truly standard abbreviations.
- Avoid overly long parenthetical chains.
- Prefer short, readable bullets that scan cleanly on a slide.

## 6. Notes And Script Conventions

Recommended script and notes conventions:

### 6.1 Notes should not merely repeat slide text

- Notes should tell the speaker what to emphasize, clarify, or contrast.
- Repeating the exact slide text wastes the notes surface.

### 6.2 Transition language should be explicit

- Notes or script should make section transitions visible.
- The speaker should not need to improvise how one slide leads to the next.

### 6.3 Closing discipline

- Closing content should usually include:
  - `3` key takeaways or fewer
  - at least `1` live limitation or caveat when relevant
  - a clear invitation for questions

### 6.4 Quick review sheet discipline

- `quick_review.md` should prioritize:
  - must-know numbers
  - high-risk confusions
  - key takeaways
- It should not become a second full script.

## 7. Audience Adaptation Conventions

Recommended audience adaptation conventions:

### 7.1 Mixed audience

- Add short plain-language framing for specialized concepts.
- Avoid assuming everyone shares the same subfield vocabulary.

### 7.2 Expert audience

- Reduce introductory explanation when it adds no value.
- Use the extra space for limitations, comparator choices, and edge cases.

### 7.3 Coursework or trainee audience

- Make study design and core methods more explicit.
- Clarify what the figure or statistic means before why it matters.

## 8. Recommended Lint Categories

If a future style-lint artifact exists, the safest categories are:
- `hard_fail`
- `warn`
- `nit`

Recommended examples:
- `hard_fail`
  - unverified_key_number
  - title_content_mismatch
  - overclaiming_language
- `warn`
  - slide_density_high
  - abbreviation_not_expanded
  - figure_takeaway_missing
  - cut_for_time_path_missing
- `nit`
  - capitalization_inconsistent
  - title_case_inconsistent
  - punctuation_inconsistent
  - bullet_parallelism_drift

## 9. Relationship To The Evaluation Rubric

This style guide and `docs/TALK_PACK_EVALUATION_RUBRIC.md` should remain separate.

Current rule:
- the style guide defines how talk-pack outputs should read and scan
- the evaluation rubric defines how ready and trustworthy those outputs are

The style guide should inform review, but it should not replace evidence, readiness, or evaluator judgment.

## 10. Conclusion

The safest future use of a talk-pack style guide is not to make every deck look the same.

It is to make future talk-pack outputs:
- easier to present
- easier to evaluate
- more consistent under time pressure
- more honest about what is known, what is uncertain, and what the audience should actually notice

That is the right level for style in PaperPipe:
- useful
- bounded
- non-canonical
- always subordinate to evidence-linked upstream truth.
