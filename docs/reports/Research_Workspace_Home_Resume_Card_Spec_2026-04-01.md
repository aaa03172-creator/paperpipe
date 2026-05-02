# Research Workspace Home Resume Card Spec (2026-04-01)

Status: working UI spec memo
Scope: home `Continue current work` card only
Basis:
- `docs/reports/Research_Workspace_Home_IA_Draft_2026-04-01.md`
- `docs/reports/Research_Workspace_Continue_Current_Work_Copy_Rules_2026-04-01.md`
- `docs/reports/Research_Workspace_Implementation_Sequencing_2026-04-01.md`
- current home surface in `frontend/src/app/pages/TriageDashboard.tsx`
- current shared primitives:
  - `frontend/src/app/components/StatusBadge.tsx`
  - `frontend/src/app/components/OperationalStateSummary.tsx`

This memo turns the saved home IA and copy rules into a small, repo-fit card spec.
It is not a new shell design.
It is a concrete insertion spec for the current home.

## 1. Product job

The card must answer one question immediately:

> What should I continue right now?

It should not try to answer:
- what every available route does
- which project system exists
- which artifact families are available

If it works, the user should be able to open the app and make one decision:
- continue the current thread now
- or ignore it and browse projects/queue below

## 2. Placement in the current home

## Recommended placement

On the current home in `TriageDashboard.tsx`, the card should become the dominant left-side hero block in the top content area.

### Current top area
- left:
  - `Start here`
- right:
  - `More tools`

### Recommended top area
- left:
  - `Continue current work`
- right:
  - compact secondary orientation block

The existing `Start here` content should not disappear, but it should be demoted below the resume card or compressed into a smaller help/onboarding block.

The existing `More tools` block should also be demoted or relabeled to a clearly secondary artifact/tools position.

## Why this placement is right
- it uses existing home real estate
- it does not require a new page shell
- it preserves the current dark-first surface language
- it fixes emphasis before adding new navigation

## 3. Visual hierarchy

The card should be the visually strongest block on the home screen, but it should still feel operational and research-focused, not marketing-like.

### Hierarchy order inside the card
1. block label
2. context line
3. paper title
4. next-action sentence
5. secondary hint
6. compact tokens
7. one primary CTA

### Weight rules
- paper title is the strongest text
- `Next:` sentence is the strongest supporting line
- context line is smaller than title
- tokens stay compact and sparse
- CTA sits low in the card and anchors the action

## 4. Desktop card anatomy

```text
Continue current work
Ketone Ester Neuroprotection
Lee et al. 2024

Next: Review flagged claims and evidence.
3 claim review flags recorded in the current paper summary.

[Needs review] [Open access]

[Resume review]
```

### Desktop layout guidance
- use a single surface card
- left-align all text content
- keep the CTA below the text stack, not floating in the header row
- avoid splitting the card into too many sub-panels
- if a right-side meta area is needed, keep it minimal:
  - last updated
  - optional access link

## 5. Mobile card anatomy

```text
Continue current work
Ketone Ester Neuroprotection
Lee et al. 2024
Next: Review flagged claims and evidence.
3 claim review flags recorded in the current paper summary.
[Resume review]
```

### Mobile layout guidance
- stack vertically
- keep tokens to one line max
- if space is tight, drop the second token before shortening the CTA
- do not create a two-column mobile card

## 6. Stable slot model

The card should keep a stable slot structure in all states.

### Slot A: block label
- fixed:
  - `Continue current work`

### Slot B: context line
- project title
- or:
  - `No project assigned`

### Slot C: paper title
- always the main title

### Slot D: primary next-action sentence
- one sentence only
- must start with `Next:`

### Slot E: secondary hint
- optional
- one line only
- examples:
  - blocker reason
  - review detail
  - unassigned explanation
  - draft recency hint

### Slot F: compact tokens
- maximum 2
- examples:
  - `Blocked`
  - `Needs review`
  - `Draft available`
  - access token

### Slot G: primary CTA
- exactly one

## 7. State-to-layout mapping

The layout stays the same.
Only slots D, E, F, and G change by state.

### Blocked state
- slot D:
  - `Next: Fix the blocker before continuing review.`
- slot E:
  - blocker reason
- slot F:
  - `Blocked`
  - optional access token
- slot G:
  - `Fix blocker`

### Review-needed state
- slot D:
  - `Next: Review flagged claims and evidence.`
- slot E:
  - review detail or issue-count sentence
- slot F:
  - `Needs review`
  - optional access token
- slot G:
  - `Resume review`

### Reading-resume state
- slot D:
  - `Next: Resume reading and note review.`
- slot E:
  - `Pick up the paper context before deeper evidence validation.`
- slot F:
  - optional access token
- slot G:
  - `Resume reading`

### Unassigned state
- slot B:
  - `No project assigned`
- slot D:
  - review-first or reading-first sentence depending on priority
- slot E:
  - unassigned context explanation
- slot G:
  - `Resume review` or `Resume reading`

### Draft-with-unresolved-review state
- slot D:
  - `Next: Finish evidence review before continuing the draft.`
- slot E:
  - draft recency hint
- slot F:
  - `Needs review`
  - `Draft available`
- slot G:
  - `Resume review`

### Draft-continuation state
- slot D:
  - `Next: Continue the latest draft from this paper thread.`
- slot E:
  - draft recency hint
- slot F:
  - `Draft available`
- slot G:
  - `Continue draft`

## 8. Recommended current-component translation

The card should reuse current language and primitives where possible instead of inventing a new mini design system.

### Good reuse candidates
- `StatusBadge`
  - for one compact access token
  - or a light state token if the copy is short enough
- existing home surface styling in `TriageDashboard.tsx`
  - rounded border
  - raised surface background
  - existing spacing scale

### Use carefully
- `OperationalStateSummary`
  - useful as a logic source
  - too verbose to drop into the resume card wholesale
  - better to translate its meaning into one short secondary hint

### Better not to use directly
- full `ContentReviewSummary`
  - the resume card should not become a mini inspection panel
- rail/table row density patterns
  - the card should feel like a current-thread anchor, not another list row

## 9. Recommended implementation shape in `TriageDashboard`

The cleanest first implementation is:

1. derive one `resumeThread` view model near the current home summary logic, but source it from `papers`, not `filteredPapers`
2. render one dedicated `Continue current work` section above the current `Start here` / `More tools` pair
3. then demote `Start here` and `More tools` into smaller supporting blocks

This is better than:
- rewriting the full page at once
- trying to merge resume, queue, and onboarding into one giant card

## 10. Minimal view-model contract

The first version does not need a full backend thread model.

It can start with a lightweight assembled view model such as:

```ts
type HomeResumeCardModel = {
  projectTitle?: string | null;
  paperId: string;
  paperTitle: string;
  primaryState: "blocked" | "review" | "reading" | "draft";
  nextActionLabel: string;
  nextActionHint?: string | null;
  ctaLabel: string;
  ctaHref: string;
  accessLabel?: string | null;
  accessTone?: string | null;
  lastUpdated?: string | null;
  draftHint?: string | null;
};
```

This should be assembled in the frontend first.
Do not wait for a global ranking API.

For the first patch, the model may be implemented as a narrower v1 that only supports:
- blocked resume
- review resume

until note-link data exists for a true `Resume reading` action.

## 11. What to avoid

Do not let the card become:
- a carousel of papers
- a ranked stack of 3 to 5 recommendations
- a project dashboard
- a mini queue table
- a mini artifact browser
- a badge wall

Do not add:
- multiple primary buttons
- both `Resume review` and `Open queue` inside the same card
- `Assign to project` as the dominant CTA

## 12. Relationship to the rest of home

The resume card is not the whole home.

It should make the rest of home easier to understand:
- if the user wants to continue now, they click the card CTA
- if they want a broader context, they scan `Active projects`
- if they want operational triage, they scan `Queue`
- if they want past output recovery, they scan `Recent artifacts`

That is why this card belongs first.

## 13. Recommendation summary

- implement the resume card as a dedicated top home block
- keep one stable slot model
- reuse current surface styling and compact badges
- translate ops/review logic into short copy instead of embedding full summaries
- keep the card singular, action-first, and thread-like
