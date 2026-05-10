# Talk Pack Quality Benchmark

Status: Draft working benchmark  
Date: 2026-04-22  
Owner: Runtime/artifact maintainers  
Canonical parents:
- `docs/Lattice_v3_Master_Spec.md`
- `docs/PaperPipe_Minimum_Operating_Principles.md`
- `docs/TALK_PACK.md`
- `docs/TALK_PACK_EVALUATION_RUBRIC.md`

Related docs:
- `docs/TALK_PACK_STYLE_GUIDE.md`
- `docs/SLIDE_MANIFEST_SCHEMA.md`
- `docs/KEY_NUMBERS_SPEC.md`
- `docs/TALK_PACK_REFERENCE_CONTRACT.md`
- `docs/Evidence_and_Uncertainty_Rules.md`

## Purpose

Define a practical quality bar for deciding whether a `Talk Pack` deck is good enough to count as a real presentation artifact rather than a merely valid export.

This benchmark exists to keep future talk-pack decks:
- audience-appropriate
- time-fit
- evidence-linked
- visually sufficient for explanation
- useful to a real presenter and legible to a real evaluator

without:
- turning `deck.pptx` into a canonical truth layer
- confusing pretty slides with good talks
- forcing every talk into one rigid slide count or one rigid visual template

## Current Judgment

At the current repo stage, this benchmark is only safe as:
- a bounded operator/evaluator checklist
- a design target for actual-paper deck review
- a companion to talk-pack review and style docs

It is not yet safe as:
- a generic automated scoring engine
- a reason to override upstream evidence rules
- a universal presentation-quality model across every possible talk mode

Current rule:
- benchmark outcomes are additive judgment, not stronger truth than `talk_pack.json`
- evidence honesty still outranks delivery polish
- generated preview PNGs are visual-review cache files; they help operators inspect screens but do not replace `talk_pack.json`, `slide_manifest.json`, or `deck.pptx`

## Non-Goals

This benchmark does not define:
- a universal corporate slide template
- a live slide editor
- a generic conference-coaching system
- a reason to backfit every deck to the same slide count

## 1. Core Definition

A good talk-pack deck is not just a valid PPTX.

It should let a presenter deliver the right message to the right audience in the available time, while preserving evidence traceability and enough visual support for the audience to understand the claim.

Current rule:
- `time fit` matters more than raw slide count
- `slide-specific evidence` matters more than repeated generic sidebars
- `figure sufficiency` matters more than a one-visual-only dogma

## 2. Slide Count Policy

`max_slides` should be treated as a soft planning target, not a hard runtime cap.

Current rule:
- do not fail a deck only because it exceeds a requested slide count
- evaluate whether the deck still fits the selected `duration_minutes`
- separate `main` slides from `backup` slides when judging deck size
- prefer warnings such as `too_dense_for_time_budget` over hard failure when the problem is pacing rather than contract breakage

Why:
- different talk modes need different pacing
- a six-slide journal club and a ten-slide seminar can both be good
- a rigid slide cap can force removal of necessary context, methods, or discussion framing

## 3. Figure Policy

Figures should be included when they are needed to explain or justify the slide's claim.

Current rule:
- a slide may have zero visuals when the message is framing, context, or transition
- an evidence-bearing slide should usually have the figure, table, or visual reference needed to understand the claim
- current runtime lane supports up to two bounded visuals per slide
- when two visuals are present, the current runtime supports simple `pair_equal`, `primary_supporting`, or `main_plus_inset` layouts rather than an open-ended slide-design DSL
- visible figure labels should read like audience-facing slide captions, not leaked raw artifact filenames
- adding more figures is not automatically better; the benchmark asks whether the audience can understand the point faster and more honestly because the figure is there

Future target:
- main slides should usually stay within `0-2` primary visuals
- backup slides may carry additional supplementary visuals when clearly marked as backup

## 4. Must-Pass Gates

A deck should fail the benchmark if any of these gates fail.

### 4.1 Intent fit

Check whether:
- the talk purpose is clear
- the audience level is recognizable
- the deck reads like the selected talk mode rather than a generic summary

### 4.2 Time fit

Check whether:
- the deck can realistically be delivered in the selected duration
- `main` slides are not overloaded for the allotted time
- backup slides are visibly separable from the main path

### 4.3 Message clarity

Check whether:
- each main slide has one primary message
- the title and body point in the same direction
- the audience can tell what each slide is for

### 4.4 Evidence traceability

Check whether:
- claims remain traceable to upstream owners
- key numbers remain reopenable
- notes or seed artifacts preserve the necessary refs

### 4.5 Slide-specific numbers

Check whether:
- quantitative evidence appears only on slides that actually use it
- the deck avoids repeating generic number panels everywhere
- number labels and exact meaning remain stable

### 4.6 Figure sufficiency

Check whether:
- figure-heavy claims have enough visual support
- the deck does not omit a needed figure just to keep a slide visually sparse
- the deck does not pile on extra figures that do not improve understanding

### 4.7 Narrative structure

Check whether the talk includes the roles it needs:
- opening
- context or framing
- evidence-bearing slides
- discussion or implication
- backup when relevant

### 4.8 Presenter usability

Check whether:
- speaker notes help the presenter speak rather than repeat slide text
- cautionary notes and priorities are visible
- the deck identifies what is `must say` vs optional

## 5. Strong-Pass Checks

These are not hard blockers, but they materially improve deck quality.

### 5.1 Context before evidence

A good journal-club deck usually explains what kind of paper this is before asking the audience to care about detailed figures.

### 5.2 Discussion fuel

A good deck should create at least one credible discussion question instead of ending as a static summary.

### 5.3 Visual economy

Good decks avoid both:
- empty text-only evidence slides
- overloaded visual collages with no obvious focal point

### 5.4 Methods and scope honesty

The deck should make it reasonably clear whether it is:
- a recommendation paper
- a methods paper
- a trial
- a review
- an abstract-aligned baseline rather than a full-text deep read

### 5.5 Style coherence

Style should support the deck rather than fight it.

Check whether:
- the chosen style profile is consistent
- slide badges and side panels help more than they distract
- decorative structure does not drown the message

### 5.6 Preview freshness

Rendered previews should reflect the current deck render, not an older sibling artifact.

Check whether:
- the number of `preview/slide-*.png` files matches the rendered slide count
- preview images are regenerated after `deck.pptx` is rerendered
- operators do not treat preview files as stronger evidence than the manifest, notes, or upstream source refs

## 6. Failure Patterns

A deck should review as weak even if it renders cleanly when it shows any of these patterns:
- slide count looks tidy, but the deck clearly does not fit the speaking time
- every slide repeats the same numbers regardless of relevance
- figures are missing where the core evidence depends on them
- figures are present but unexplained
- the deck has no context slide, so the audience cannot tell what kind of paper they are seeing
- the deck has no discussion prompt, so it reads like a static note export
- backup material is mixed into the main path without warning
- titles sound stronger than the evidence

## 7. Pass Levels

### 7.1 Benchmark fail

Use `fail` when:
- any must-pass gate breaks
- evidence traceability is missing
- the deck is clearly not time-fit
- essential visual support is absent for the main evidence claims

### 7.2 Benchmark pass

Use `pass` when:
- all must-pass gates clear
- the deck is usable for the selected talk mode
- the deck preserves enough context, evidence, and notes support to be delivered safely

### 7.3 Strong pass

Use `strong pass` when:
- all must-pass gates clear
- strong-pass checks are mostly satisfied
- the deck feels discussion-ready and presenter-ready rather than merely technically valid

## 8. Operator Checklist

Use this quick checklist when reviewing a candidate deck:

1. Can I tell what kind of talk this is within the first two slides?
2. Can the presenter likely finish on time?
3. Does each main slide have one clear message?
4. Are the important claims traceable?
5. Do numbers appear only where they matter?
6. Are needed figures actually present?
7. Are figures limited to what helps explanation?
8. Is there at least one meaningful discussion or implication slide?
9. Are backup slides clearly marked?
10. Would a real presenter rather speak from this deck than from the source note alone?

If the answer is `no` to any of `1-7`, the deck is probably below the minimum acceptable bar.

## 9. Current Practical Interpretation

For current actual-paper `Talk Pack` work, the most important benchmark signals are:
- no low-value repeated evidence panel on framing slides
- real paper visuals included where the argument depends on them
- quantitative sidebars only on the slides that use those quantities
- context slide present when the paper type would otherwise be unclear
- discussion slide present for journal-club use
- backup slide preserved when the deck is still a bounded or partial read
- preview PNGs are fresh enough for screen-level review, while staying outside the owner manifest contract

That is the current practical meaning of "good enough to count as a real presentation artifact" in PaperPipe.
